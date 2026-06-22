# Database migrations (Alembic)

Alembic is the authoritative source for the voice-agent goal-tracking schema.
Migrations use raw SQL via `op.execute(...)` (the app talks to PostgreSQL with
asyncpg directly, so there are no SQLAlchemy models to autogenerate from).

The connection is built from the `DB_*` variables in `.env` (see `env.py`); set
`DATABASE_URL` to override.

## Key convention: session_id is the linking key

Child tables (`session_goals`, `session_transcripts`, `session_metrics`) link to
an interview by the **external** identifier `interview_sessions.session_id`
(a `VARCHAR(100)`), **not** the internal `id` UUID. The application uses the
external `session_id` string everywhere. Any new table referencing a session
must use `session_id VARCHAR(100) REFERENCES interview_sessions(session_id)` —
never `UUID REFERENCES interview_sessions(id)`. Mixing the two caused the
`operator does not exist: character varying = uuid` failures.

## First-time setup

Run the idempotent bootstrap script. It creates the `ai_user` role and the
database if missing, applies the privileged grants/cleanup from `bootstrap.sql`,
and runs the migrations — all in one safe-to-re-run command:

```bash
uv run python scripts/bootstrap_db.py
```

It connects with the privileged `DB_SUPERUSER` / `DB_SUPERUSER_PASSWORD` from
`.env` (default role `postgres`) **only** for this step; the app and all later
migrations connect as the unprivileged `DB_USER`. Pass `--no-migrate` to do the
role/database/grant setup without applying migrations.

If you skip bootstrap and run `alembic upgrade head` on a fresh database, it
fails fast with `permission denied for schema public` and points you back here.

### Manual fallback (peer auth / no superuser password)

If your install uses peer auth, do the privileged step by hand, then migrate:

```bash
sudo -u postgres psql -d ai_recruiter -f alembic/bootstrap.sql
uv run alembic upgrade head
```

## Everyday commands

```bash
uv run alembic current              # show applied revision
uv run alembic history              # list revisions
uv run alembic upgrade head         # apply pending migrations
uv run alembic downgrade -1         # roll back one revision
uv run alembic revision -m "desc"   # create a new (empty) migration
uv run alembic upgrade head --sql   # print SQL without applying (offline)
```

## Authoring a new migration

Add SQL in `upgrade()` and the inverse in `downgrade()`:

```python
def upgrade() -> None:
    op.execute("ALTER TABLE session_goals ADD COLUMN notes TEXT")

def downgrade() -> None:
    op.execute("ALTER TABLE session_goals DROP COLUMN notes")
```

`database_schema.sql` in the server root is now only a human-readable reference
snapshot; do not apply it directly — use Alembic.
