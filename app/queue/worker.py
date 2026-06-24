"""Background evaluation queue — in-process worker (MVP); swap for Celery/Redis later."""
import datetime
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass

from ..core import status as S
from ..database import SessionLocal
from ..events import publish_candidate_event
from ..models import Candidate
from ..scoring.engine import evaluate_candidate_pipeline

_AVAILABILITY_THRESHOLD_DEFAULT = float(os.getenv("AVAILABILITY_THRESHOLD", "60"))

logger = logging.getLogger(__name__)

# Bounded so a flood of uploads can't grow the queue without limit (OOM). When
# full, enqueue raises queue.Full and the caller returns 503.
_QUEUE_MAX = int(os.getenv("EVAL_QUEUE_MAX", "500"))
evaluation_queue: "queue.Queue[int]" = queue.Queue(maxsize=_QUEUE_MAX)
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_processing_count = 0
_count_lock = threading.Lock()


@dataclass
class QueueStats:
    depth: int
    processing: int


def _set_processing(delta: int) -> None:
    global _processing_count
    with _count_lock:
        _processing_count += delta


def get_queue_stats() -> QueueStats:
    return QueueStats(depth=evaluation_queue.qsize(), processing=_processing_count)


def enqueue_candidate(candidate_id: int) -> None:
    """Enqueue a candidate for evaluation. Raises queue.Full if the queue is at
    capacity (caller should surface a 503 / retry)."""
    evaluation_queue.put_nowait(candidate_id)  # raises queue.Full when bounded queue is full
    logger.info(
        "Enqueued candidate %d (queue_depth=%d/%d)",
        candidate_id,
        evaluation_queue.qsize(),
        _QUEUE_MAX,
    )


def _worker_loop() -> None:
    while not _stop_event.is_set():
        try:
            candidate_id = evaluation_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        _set_processing(1)
        db = SessionLocal()
        started = time.perf_counter()
        try:
            cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if cand is None:
                # Deleted between enqueue and pickup — skip cleanly rather than
                # running the pipeline against a missing row (silent no-op before).
                logger.warning(
                    "Skipping candidate %d: no longer exists (deleted before processing).",
                    candidate_id,
                )
                continue  # still runs the finally block (task_done + processing count)
            if cand.status == S.QUEUED:
                publish_candidate_event(candidate_id, S.QUEUED, job_id=cand.job_id, event="queued")
            evaluate_candidate_pipeline(candidate_id, db)

            # Auto-send interview invite when the candidate clears the score threshold.
            # No HR action required — invite goes out automatically.
            try:
                from ..database import get_setting
                threshold = float(
                    get_setting(db, "availability_threshold", str(_AVAILABILITY_THRESHOLD_DEFAULT))
                    or _AVAILABILITY_THRESHOLD_DEFAULT
                )
                cand_after = db.query(Candidate).filter(Candidate.id == candidate_id).first()
                if (
                    cand_after
                    and cand_after.total_score >= threshold
                    and cand_after.email
                    and not cand_after.interview_invited_at
                ):
                    from ..availability_tokens import mint_availability_token
                    from ..services.email import send_availability_invite
                    job_obj = cand_after.job
                    if job_obj:
                        _, avail_url = mint_availability_token(cand_after.id)
                        send_availability_invite(
                            to=cand_after.email,
                            candidate_name=cand_after.name,
                            job_title=job_obj.title,
                            link=avail_url,
                        )
                        import datetime as _dt
                        cand_after.interview_invited_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
                        db.commit()
                        logger.info(
                            "Availability invite auto-sent to candidate %d (score=%.1f, email=%s)",
                            candidate_id, cand_after.total_score, cand_after.email,
                        )
                    else:
                        logger.warning(
                            "Candidate %d has no linked job; skipping auto-invite", candidate_id
                        )
            except Exception as e_invite:
                logger.error("Auto-interview-invite failed for candidate %d: %s", candidate_id, e_invite)

            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "Completed candidate %d in %.0fms (queue_depth=%d)",
                candidate_id,
                elapsed_ms,
                evaluation_queue.qsize(),
            )
        except Exception as e:
            logger.exception("Worker failed for candidate %d: %s", candidate_id, e)
            try:
                failed = db.query(Candidate).filter(Candidate.id == candidate_id).first()
                if failed and failed.status not in (S.ERROR, S.REJECTED):
                    failed.status = S.ERROR
                    failed.summary = f"Worker error: {e}"
                    db.commit()
                    publish_candidate_event(
                        candidate_id,
                        S.ERROR,
                        job_id=failed.job_id,
                    )
            except Exception:
                db.rollback()
        finally:
            db.close()
            _set_processing(-1)
            evaluation_queue.task_done()


def requeue_pending() -> int:
    """Re-enqueue candidates a prior crash left mid-flight.

    The in-process queue does NOT survive a restart, so rows stuck in Queued (enqueued
    but never picked up) or Processing (worker died mid-pipeline) would otherwise hang
    forever. The scoring pipeline is idempotent (it recomputes), so re-running is safe.
    Call once at startup, after start_worker().
    """
    db = SessionLocal()
    requeued = 0
    try:
        ids = [
            row[0]
            for row in db.query(Candidate.id)
            .filter(Candidate.status.in_([S.QUEUED, S.PROCESSING]))
            .all()
        ]
    finally:
        db.close()
    for cid in ids:
        try:
            enqueue_candidate(cid)
            requeued += 1
        except queue.Full:
            logger.warning(
                "requeue_pending: queue full after %d/%d; remaining will stay pending "
                "until re-uploaded or reprocessed.",
                requeued, len(ids),
            )
            break
    if requeued:
        logger.info("Requeued %d candidate(s) left pending by a prior restart.", requeued)
    return requeued


def start_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="evaluation-worker",
        daemon=True,
    )
    _worker_thread.start()
    logger.info("Evaluation worker started")


def stop_worker() -> None:
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5.0)
    logger.info("Evaluation worker stopped")
