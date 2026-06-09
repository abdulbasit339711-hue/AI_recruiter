-- ONE-TIME bootstrap, run as a superuser (the only step that needs sudo):
--   sudo -u postgres psql -d ai_recruiter -f alembic/bootstrap.sql
--
-- Purpose: let the application role `ai_user` own and manage the goal-tracking
-- schema so that all future migrations run as `ai_user` with no sudo.
--
-- It (1) lets ai_user create objects in the public schema, and (2) drops the
-- legacy postgres-owned goal-tracking objects so Alembic can recreate them
-- (owned by ai_user). The child tables hold only disposable test data.
-- After this, run:  alembic upgrade head

-- Ensure the role exists (no-op if it already does).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_user') THEN
        CREATE ROLE ai_user LOGIN PASSWORD 'secure_password';
    END IF;
END
$$;

-- Allow ai_user to create tables (including alembic_version) in public.
GRANT USAGE, CREATE ON SCHEMA public TO ai_user;

-- Drop legacy postgres-owned goal-tracking objects (recreated by Alembic 0001).
DROP VIEW IF EXISTS session_overview CASCADE;
DROP VIEW IF EXISTS goal_progress_summary CASCADE;
DROP TABLE IF EXISTS goal_progress_events CASCADE;
DROP TABLE IF EXISTS session_metrics CASCADE;
DROP TABLE IF EXISTS session_transcripts CASCADE;
DROP TABLE IF EXISTS session_goals CASCADE;
DROP TABLE IF EXISTS interview_sessions CASCADE;
DROP TABLE IF EXISTS goal_templates CASCADE;
DROP FUNCTION IF EXISTS update_session_goal_stats() CASCADE;
