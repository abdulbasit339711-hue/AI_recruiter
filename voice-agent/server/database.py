"""
Database connection and operations for AI Recruiter Goal Tracking
"""

import asyncpg
import asyncio
import os
import json
from typing import Optional, List, Dict, Any
from loguru import logger
from datetime import datetime
from dataclasses import dataclass


def _naive_local(dt: datetime) -> datetime:
    """Strip tzinfo so the value matches the naive ``TIMESTAMP`` columns.

    asyncpg binds a tz-aware datetime to a ``TIMESTAMP`` (without time zone)
    column by subtracting the naive Postgres epoch, which raises "can't subtract
    offset-naive and offset-aware datetimes". The agent transcript path already
    produces naive *local* datetimes (via ``datetime.fromtimestamp``), so convert
    aware values to local time and drop the tzinfo to stay consistent.
    """
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo is not None else dt


def _coerce_timestamp(value: Any) -> datetime:
    """Normalize a frame timestamp into a naive datetime for TIMESTAMP columns.

    Pipecat frame timestamps arrive either as a tz-aware ``datetime`` or as epoch
    seconds (often stringified, e.g. '1780829342.226'), but asyncpg requires a
    *naive* datetime for ``TIMESTAMP`` columns. Accepts datetime, epoch
    int/float/str, or ISO strings; falls back to now().
    """
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return _naive_local(value)
    # Epoch seconds as int/float/str
    try:
        return datetime.fromtimestamp(float(value))
    except (TypeError, ValueError):
        pass
    # ISO-8601 string
    try:
        return _naive_local(datetime.fromisoformat(str(value)))
    except (TypeError, ValueError):
        return datetime.now()


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""
    database: str = "ai_recruiter"
    min_size: int = 2
    max_size: int = 10


class DatabaseManager:
    """Manages PostgreSQL connections and operations for goal tracking"""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "ai_recruiter"),
            min_size=int(os.getenv("DB_MIN_CONNECTIONS", 2)),
            max_size=int(os.getenv("DB_MAX_CONNECTIONS", 10))
        )
        self.pool: Optional[asyncpg.Pool] = None
        self._init_lock = asyncio.Lock()

    async def _ensure_pool(self) -> None:
        """Lazily create the pool on first use.

        Handles the startup race (an HTTP request arriving before start() has run
        initialize()) and lets a failed/missed init self-heal. If connecting still
        fails, the underlying error (e.g. auth) propagates — which is far more
        useful than the generic 'Database not initialized'.
        """
        if self.pool is not None:
            return
        async with self._init_lock:
            if self.pool is None:
                await self.initialize()

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                command_timeout=30
            )
            logger.info(f"[Database] Connected to PostgreSQL at {self.config.host}:{self.config.port}")

            # Test connection
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    logger.info("[Database] Connection test successful")

            # Self-heal the resume schema (idempotent) so an existing deployment supports
            # interview resume even if alembic 0005 wasn't run: the progress columns, and
            # widening valid_session_status to allow 'interrupted' (the status a dropped
            # interview is marked so its link stays resumable). Non-fatal: a privilege
            # error here must not stop the server booting.
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        ALTER TABLE interview_sessions
                            ADD COLUMN IF NOT EXISTS current_question_index INTEGER NOT NULL DEFAULT 0,
                            ADD COLUMN IF NOT EXISTS question_states JSONB NOT NULL DEFAULT '{}'::jsonb;

                        ALTER TABLE interview_sessions DROP CONSTRAINT IF EXISTS valid_session_status;
                        ALTER TABLE interview_sessions ADD CONSTRAINT valid_session_status
                            CHECK (status IN ('active', 'completed', 'cancelled', 'interrupted'));
                        """
                    )
            except Exception as e:
                logger.warning(f"[Database] Could not ensure resume schema: {e}")

        except Exception as e:
            logger.error(f"[Database] Failed to initialize: {e}")
            raise

    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
            logger.info("[Database] Connection pool closed")

    async def execute_query(self, query: str, *args) -> Any:
        """Execute a query and return result"""
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Execute multiple queries in a transaction"""
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, args_list)

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row as dictionary"""
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries"""
        await self._ensure_pool()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    # ===================================
    # GOAL TRACKING SPECIFIC OPERATIONS
    # ===================================

    async def get_goal_templates(self, role_type: str) -> List[Dict[str, Any]]:
        """Get goal templates for a specific role"""
        query = """
        SELECT * FROM goal_templates
        WHERE role_type = $1
        ORDER BY priority_weight DESC, category, title
        """
        return await self.fetch_all(query, role_type)

    async def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Read a job (owned by the main API) from the shared database."""
        return await self.fetch_one(
            "SELECT id, title, department, job_description, llm_prompt, status, "
            "COALESCE(role_type, '') AS role_type "
            "FROM jobs WHERE id = $1",
            job_id,
        )

    async def update_goal_template(
        self, template_id: str, *, title: str, description: str,
        question_templates: list, priority_weight: float,
    ) -> None:
        """Edit a goal template in place (FK-safe — keeps the id, so existing
        session_goals references stay valid). Used by the per-job question editor."""
        await self.execute_query(
            """
            UPDATE goal_templates
            SET title = $2, description = $3, question_templates = $4::jsonb,
                priority_weight = $5, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            template_id, title, description,
            json.dumps(question_templates), float(priority_weight),
        )

    async def add_goal_template(self, t: Dict[str, Any]) -> Optional[str]:
        """Insert a goal template (used to cache LLM-generated role configs)."""
        query = """
        INSERT INTO goal_templates
        (role_type, category, title, description, success_criteria, priority_weight,
         estimated_time_minutes, question_templates)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8::jsonb)
        RETURNING id
        """
        return await self.execute_query(
            query,
            t["role_type"],
            t.get("category", "general"),
            t["title"],
            t.get("description", ""),
            json.dumps(t.get("success_criteria", [])),
            float(t.get("priority_weight", 0.5)),
            int(t.get("estimated_time_minutes", 5)),
            json.dumps(t.get("question_templates", [])),
        )

    async def get_candidate(self, candidate_id: int) -> Optional[Dict[str, Any]]:
        """Read a candidate (owned by the main API) from the shared database.

        Includes the Tier-3 résumé-screening evaluation (summary, scores, matched/
        missing skills) so the interviewer can be briefed on the scored profile, plus
        the résumé-tailored ``interview_questions``."""
        return await self.fetch_one(
            "SELECT id, name, email, job_id, current_role, years_experience, "
            "interview_questions, summary, tier3, total_score, "
            "skills_matched, skills_missing FROM candidates WHERE id = $1",
            candidate_id,
        )

    async def create_session(self, session_data: Dict[str, Any]) -> str:
        """Create a new interview session"""
        # Idempotent: dual-pipeline mode runs two goal processors that both
        # initialize the same session, so swallow the duplicate instead of erroring.
        query = """
        INSERT INTO interview_sessions
        (session_id, candidate_name, candidate_email, interviewer_name, role_type,
         company_name, pipeline_mode, candidate_id, job_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (session_id) DO UPDATE SET status = 'active', updated_at = NOW()
        RETURNING id
        """
        session_id = await self.execute_query(
            query,
            session_data["session_id"],
            session_data.get("candidate_name"),
            session_data.get("candidate_email"),
            session_data.get("interviewer_name"),
            session_data["role_type"],
            session_data.get("company_name"),
            session_data.get("pipeline_mode", "single"),
            session_data.get("candidate_id"),
            session_data.get("job_id"),
        )
        logger.info(f"[Database] Created session: {session_data['session_id']}")
        return session_id

    async def initialize_session_goals(self, session_id: str, role_type: str) -> List[str]:
        """Initialize goals for a session based on role templates"""
        # Get templates
        templates = await self.get_goal_templates(role_type)

        if not templates:
            logger.warning(f"[Database] No goal templates found for role: {role_type}")
            return []

        # Create session goals
        goal_ids = []
        query = """
        INSERT INTO session_goals
        (session_id, goal_template_id, completion_status, progress_score, confidence_level)
        VALUES ($1, $2, 'not_started', 0.0, 0.0)
        RETURNING id
        """

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for template in templates:
                    goal_id = await conn.fetchval(query, session_id, template["id"])
                    goal_ids.append(str(goal_id))

        # Update session statistics
        await self.update_session_stats(session_id)

        logger.info(f"[Database] Initialized {len(goal_ids)} goals for session: {session_id}")
        return goal_ids

    async def get_session_goals(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all goals for a session with template data"""
        query = """
        SELECT
            sg.id,
            sg.session_id,
            sg.completion_status,
            sg.progress_score,
            sg.confidence_level,
            sg.evidence,
            sg.time_spent_seconds,
            sg.started_at,
            sg.completed_at,
            gt.role_type,
            gt.category,
            gt.title,
            gt.description,
            gt.success_criteria,
            gt.priority_weight,
            gt.estimated_time_minutes,
            gt.question_templates
        FROM session_goals sg
        JOIN goal_templates gt ON sg.goal_template_id = gt.id
        WHERE sg.session_id = $1
        ORDER BY gt.priority_weight DESC, gt.category, gt.title
        """
        return await self.fetch_all(query, session_id)

    async def update_goal_progress(self, goal_id: str, progress_data: Dict[str, Any]) -> bool:
        """Update goal progress and create progress event"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Update session goal
                update_query = """
                UPDATE session_goals
                SET
                    progress_score = $2,
                    confidence_level = $3,
                    completion_status = $4::text,
                    evidence = COALESCE(evidence, '[]'::jsonb) || $5::jsonb,
                    time_spent_seconds = COALESCE(time_spent_seconds, 0) + $6,
                    completed_at = CASE WHEN $4::text = 'completed' THEN NOW() ELSE completed_at END,
                    started_at = CASE WHEN started_at IS NULL THEN NOW() ELSE started_at END
                WHERE id = $1::uuid
                """

                await conn.execute(
                    update_query,
                    goal_id,
                    progress_data.get("progress_score", 0.0),
                    progress_data.get("confidence_level", 0.0),
                    progress_data.get("completion_status", "in_progress"),
                    json.dumps([progress_data.get("evidence", {})]),
                    progress_data.get("time_delta_seconds", 0)
                )

                # Create progress event
                event_query = """
                INSERT INTO goal_progress_events
                (session_goal_id, event_type, progress_delta, evidence_type, evidence_text,
                 transcript_reference, analysis_model, confidence_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """

                await conn.execute(
                    event_query,
                    goal_id,
                    progress_data.get("event_type", "progress_update"),
                    progress_data.get("progress_delta", 0.0),
                    progress_data.get("evidence_type"),
                    progress_data.get("evidence_text"),
                    progress_data.get("transcript_reference"),
                    progress_data.get("analysis_model"),
                    progress_data.get("confidence_score", 0.0)
                )

                # Get session_id for stats update
                session_id = await conn.fetchval(
                    "SELECT session_id FROM session_goals WHERE id = $1",
                    goal_id
                )

        # Update session statistics
        await self.update_session_stats(session_id)

        logger.debug(f"[Database] Updated goal progress: {goal_id}")
        return True

    async def update_session_stats(self, session_id: str) -> None:
        """Update session-level goal statistics"""
        query = """
        UPDATE interview_sessions SET
            total_goals = (SELECT COUNT(*) FROM session_goals WHERE session_id = $1),
            completed_goals = (SELECT COUNT(*) FROM session_goals WHERE session_id = $1 AND completion_status = 'completed'),
            average_progress = (SELECT COALESCE(AVG(progress_score), 0) FROM session_goals WHERE session_id = $1),
            updated_at = NOW()
        WHERE session_id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id)

    async def finalize_session_record(self, session_id: str, overall_assessment: str,
                                      completed: bool = True) -> None:
        """Store a session's final assessment and stamp its terminal status.

        Called once when the interview ends (see GoalTrackingProcessor.finalize_session_goals).
        ``completed`` distinguishes a graceful end (all questions covered) from an
        interrupted one: a graceful interview is 'completed' (single-use — the link is
        spent), while an interrupted one is 'interrupted' so the candidate can resume.
        """
        status = "completed" if completed else "interrupted"
        query = """
        UPDATE interview_sessions SET
            status = $3,
            ended_at = COALESCE(ended_at, NOW()),
            duration_seconds = COALESCE(
                duration_seconds,
                EXTRACT(EPOCH FROM (NOW() - started_at))::int
            ),
            overall_assessment = $2,
            updated_at = NOW()
        WHERE session_id = $1
        """
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, overall_assessment, status)

    async def get_session_status(self, session_id: str) -> Optional[str]:
        """Return the current status of a session ('active'|'completed'|'interrupted'),
        or None if no such session exists. Used to enforce single-use links."""
        row = await self.fetch_one(
            "SELECT status FROM interview_sessions WHERE session_id = $1", session_id
        )
        return row["status"] if row else None

    async def mark_session_status(self, session_id: str, status: str) -> None:
        """Stamp a session's terminal status (and ended_at) without touching the
        assessment. Fallback used when there is no goal assessment to persist."""
        query = """
        UPDATE interview_sessions SET
            status = $2,
            ended_at = COALESCE(ended_at, NOW()),
            duration_seconds = COALESCE(
                duration_seconds,
                EXTRACT(EPOCH FROM (NOW() - started_at))::int
            ),
            updated_at = NOW()
        WHERE session_id = $1
        """
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, status)

    async def attach_transcript_evaluation(self, session_id: str, response_text: str, evaluation: Dict[str, Any]) -> None:
        """Attach a judge's per-answer evaluation to the matching candidate transcript row.

        Updates the most recent candidate turn whose text equals the evaluated response (same
        STT text the judge saw). UPDATE...LIMIT isn't allowed directly, so we target by id.
        """
        import json as _json
        query = """
        UPDATE session_transcripts SET evaluation = $2::jsonb
        WHERE id = (
            SELECT id FROM session_transcripts
            WHERE session_id = $1 AND speaker = 'candidate' AND text = $3
            ORDER BY sequence_number DESC LIMIT 1
        )
        """
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, _json.dumps(evaluation), response_text)

    async def update_session_audio(self, session_id: str, audio_path: str) -> None:
        """Store the path to this interview's recorded audio file on the session row."""
        query = """
        UPDATE interview_sessions SET audio_path = $2, updated_at = NOW()
        WHERE session_id = $1
        """
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, audio_path)

    async def get_session_overview(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive session overview including goals"""
        query = """
        SELECT * FROM session_overview WHERE session_id = $1
        """
        return await self.fetch_one(query, session_id)

    async def get_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        """Return the ordered conversation for a session as [{speaker, text}, ...].

        Used to resume an interrupted interview: when the same link is re-opened, the
        prior turns are replayed into the LLM context so the bot continues with full
        memory instead of restarting. ``speaker`` is 'agent' or 'candidate'."""
        # Tiebreak on created_at (insertion order) so any duplicate sequence_numbers
        # from older rows still replay in the true order they were written. NOTE: id
        # is a random UUID here, so it must NOT be used for ordering.
        rows = await self.fetch_all(
            "SELECT speaker, text FROM session_transcripts "
            "WHERE session_id = $1 ORDER BY sequence_number, created_at",
            session_id,
        )
        return [{"speaker": r["speaker"], "text": r["text"]} for r in rows]

    async def save_session_progress(
        self, session_id: str, current_question_index: int, question_states: Dict[str, Any]
    ) -> None:
        """Persist the question-flow position so an interrupted interview resumes in place.

        Called whenever the flow advances (question answered / skipped). Together with
        the persisted transcript this lets a re-opened link continue at the exact next
        question instead of restarting. Best-effort: a failure here must never break the
        live interview, so the caller wraps this in try/except."""
        query = """
        UPDATE interview_sessions
        SET current_question_index = $2,
            question_states = $3::jsonb,
            updated_at = NOW()
        WHERE session_id = $1
        """
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, int(current_question_index), json.dumps(question_states or {}))

    async def get_session_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the persisted question-flow position for a session, or None if absent.

        Shape: {"current_question_index": int, "question_states": {qid: {...}}}. Used on
        resume to restore where the candidate left off."""
        row = await self.fetch_one(
            "SELECT current_question_index, question_states "
            "FROM interview_sessions WHERE session_id = $1",
            session_id,
        )
        if not row:
            return None
        states = row.get("question_states")
        if isinstance(states, str):
            try:
                states = json.loads(states)
            except (TypeError, ValueError):
                states = {}
        return {
            "current_question_index": row.get("current_question_index") or 0,
            "question_states": states or {},
        }

    async def add_transcript_entry(self, session_id: str, transcript_data: Dict[str, Any]) -> str:
        """Add transcript entry to database"""
        # Compute the sequence number INSIDE the insert so it's atomic. Candidate
        # turns (goal_tracking_processor) and agent turns (transcript_metrics_processor)
        # are persisted from different processors; the old read-then-write
        # (SELECT MAX+1; INSERT) let two near-simultaneous turns grab the SAME number,
        # which then scrambled ORDER BY sequence_number on resume → the LLM replayed
        # the prior conversation out of order and "lost" the context.
        # $1 is used both as the INSERT value (column type character varying) and
        # in the subquery comparison; asyncpg otherwise deduces conflicting types
        # for it ("text versus character varying") and aborts the insert — which
        # then swallowed the candidate transcript broadcast. Cast both uses to
        # varchar so the parameter type is unambiguous.
        query = """
        INSERT INTO session_transcripts
        (session_id, speaker, text, timestamp, sequence_number, tokens_estimated)
        VALUES ($1::varchar, $2, $3, $4,
            (SELECT COALESCE(MAX(sequence_number), 0) + 1
             FROM session_transcripts WHERE session_id = $1::varchar),
            $5)
        RETURNING id
        """

        transcript_id = await self.execute_query(
            query,
            session_id,
            transcript_data["speaker"],
            transcript_data["text"],
            _coerce_timestamp(transcript_data.get("timestamp")),
            transcript_data.get("tokens_estimated", 0)
        )

        return str(transcript_id)

    async def add_session_metrics(self, session_id: str, metrics_data: Dict[str, Any]) -> str:
        """Add session metrics entry"""
        query = """
        INSERT INTO session_metrics
        (session_id, metric_type, service_name, model_name, token_count, cost_usd, goal_id, analysis_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """

        metrics_id = await self.execute_query(
            query,
            session_id,
            metrics_data["metric_type"],
            metrics_data.get("service_name"),
            metrics_data.get("model_name"),
            metrics_data.get("token_count", 0),
            metrics_data.get("cost_usd", 0.0),
            metrics_data.get("goal_id"),
            metrics_data.get("analysis_type")
        )

        return str(metrics_id)

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            if not self.pool:
                return False

            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1

        except Exception as e:
            logger.error(f"[Database] Health check failed: {e}")
            return False


# Global database instance
db_manager = DatabaseManager()


async def initialize_database():
    """Initialize database connection for the application"""
    await db_manager.initialize()


async def close_database():
    """Close database connections"""
    await db_manager.close()