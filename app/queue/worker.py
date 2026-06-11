"""Background evaluation queue — in-process worker (MVP); swap for Celery/Redis later."""
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
            job_id = cand.job_id if cand else None
            if cand and cand.status == S.QUEUED:
                publish_candidate_event(candidate_id, S.QUEUED, job_id=job_id, event="queued")
            evaluate_candidate_pipeline(candidate_id, db)

            # No interview invite is minted here. Invites are sent only when HR
            # explicitly triggers POST /candidates/{id}/interview-invite after review —
            # never automatically as a side effect of an applicant's upload.

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
