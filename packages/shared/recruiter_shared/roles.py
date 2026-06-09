"""Role-type slug normalization.

A Job's free-text title/department must map to a STABLE slug so it lines up with
seeded `goal_templates.role_type`. This fixes the historical mismatch where the
voice agent used "Backend Engineer" but the DB seeded "backend_engineer".
"""

import re

# Slugs that ship with curated goal_templates (see the voice agent's Alembic seed).
# Used to decide template-path vs LLM-fallback at a glance; not authoritative
# (the DB is) — kept here for shared, dependency-free reference.
KNOWN_ROLE_SLUGS = {"backend_engineer", "frontend_engineer"}

# Common title aliases → canonical slug. Extend as roles are added.
_ALIASES = {
    "backend": "backend_engineer",
    "backend_developer": "backend_engineer",
    "be_engineer": "backend_engineer",
    "frontend": "frontend_engineer",
    "frontend_developer": "frontend_engineer",
    "fe_engineer": "frontend_engineer",
}


def normalize_role_type(value: str | None) -> str:
    """Normalize a job title/role/department into a stable lowercase slug.

    Examples:
        "Backend Engineer"   -> "backend_engineer"
        "Senior Frontend Dev"-> "senior_frontend_dev"
        "  Data  Scientist " -> "data_scientist"
    """
    if not value:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return _ALIASES.get(slug, slug)
