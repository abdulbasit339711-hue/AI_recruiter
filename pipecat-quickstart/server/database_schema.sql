-- AI Recruiter Database Schema
-- Goal Tracking Implementation (Phase 1)
-- Models: llama-3.3-70b-versatile + llama-3.1-8b-instant
--
-- REFERENCE SNAPSHOT ONLY. The authoritative schema is managed by Alembic
-- (see alembic/versions/ and alembic/README.md). For a real database, run
-- `alembic upgrade head` instead of applying this file directly.

-- ===================================
-- GOAL TRACKING TABLES
-- ===================================

-- Goal Templates (Reusable interview objectives)
CREATE TABLE goal_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_type VARCHAR(100) NOT NULL,           -- 'backend_engineer', 'frontend_engineer', etc.
    category VARCHAR(50) NOT NULL,             -- 'technical', 'communication', 'experience', 'cultural_fit'
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    success_criteria JSONB NOT NULL,           -- Array of completion criteria
    priority_weight DECIMAL(3,2) DEFAULT 1.0, -- 0.0 to 1.0, higher = more important
    estimated_time_minutes INTEGER DEFAULT 5,  -- Expected time to assess
    question_templates JSONB,                  -- Suggested questions for this goal
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Session Goals (Goal instances for specific interviews)
CREATE TABLE session_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,         -- References interview_sessions(session_id)
    goal_template_id UUID REFERENCES goal_templates(id),
    completion_status VARCHAR(50) DEFAULT 'not_started', -- 'not_started', 'in_progress', 'completed', 'skipped'
    progress_score DECIMAL(3,2) DEFAULT 0.0,  -- 0.0 to 1.0 progress
    confidence_level DECIMAL(3,2) DEFAULT 0.0, -- AI confidence in assessment
    evidence JSONB DEFAULT '[]'::jsonb,       -- Array of evidence found
    time_spent_seconds INTEGER DEFAULT 0,     -- Time spent on this goal
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_progress CHECK (progress_score >= 0.0 AND progress_score <= 1.0),
    CONSTRAINT valid_confidence CHECK (confidence_level >= 0.0 AND confidence_level <= 1.0),
    CONSTRAINT valid_completion_status CHECK (completion_status IN ('not_started', 'in_progress', 'completed', 'skipped'))
);

-- Goal Progress Events (Real-time tracking of progress changes)
CREATE TABLE goal_progress_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_goal_id UUID REFERENCES session_goals(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,          -- 'evidence_found', 'progress_update', 'completion', 'manual_override'
    progress_delta DECIMAL(3,2) NOT NULL,     -- Change in progress (-1.0 to +1.0)
    evidence_type VARCHAR(100),               -- 'specific_example', 'technical_detail', 'problem_solving', etc.
    evidence_text TEXT,                       -- Actual quote/content from candidate
    transcript_reference VARCHAR(500),        -- Reference to transcript location
    analysis_model VARCHAR(100),              -- 'llama-3.3-70b-versatile' or 'llama-3.1-8b-instant'
    confidence_score DECIMAL(3,2),           -- AI confidence in this event
    created_by VARCHAR(50) DEFAULT 'system',  -- 'system' or 'manual' for human overrides
    timestamp TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_progress_delta CHECK (progress_delta >= -1.0 AND progress_delta <= 1.0),
    CONSTRAINT valid_confidence_score CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    CONSTRAINT valid_event_type CHECK (event_type IN ('evidence_found', 'progress_update', 'completion', 'manual_override'))
);

-- ===================================
-- SESSION MANAGEMENT TABLES
-- ===================================

-- Interview Sessions (Main session tracking)
CREATE TABLE interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) UNIQUE NOT NULL,  -- External session identifier
    candidate_name VARCHAR(200),
    candidate_email VARCHAR(200),
    interviewer_name VARCHAR(200),
    role_type VARCHAR(100) NOT NULL,
    company_name VARCHAR(200),
    status VARCHAR(50) DEFAULT 'active',      -- 'active', 'completed', 'cancelled'
    pipeline_mode VARCHAR(20) DEFAULT 'single', -- 'single', 'dual'
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Goal tracking summary
    total_goals INTEGER DEFAULT 0,
    completed_goals INTEGER DEFAULT 0,
    average_progress DECIMAL(3,2) DEFAULT 0.0,
    overall_assessment TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_session_status CHECK (status IN ('active', 'completed', 'cancelled')),
    CONSTRAINT valid_pipeline_mode CHECK (pipeline_mode IN ('single', 'dual'))
);

-- Session Transcripts (Conversation history)
CREATE TABLE session_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
    speaker VARCHAR(50) NOT NULL,             -- 'candidate', 'agent', 'system'
    text TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    sequence_number INTEGER NOT NULL,         -- Order within session
    tokens_estimated INTEGER DEFAULT 0,      -- For cost tracking

    -- Full-text search
    text_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Session Metrics (Performance and cost tracking)
CREATE TABLE session_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
    metric_type VARCHAR(100) NOT NULL,       -- 'stt_tokens', 'llm_tokens', 'tts_tokens', 'goal_analysis_cost'
    service_name VARCHAR(100),               -- 'deepgram', 'groq', 'cartesia'
    model_name VARCHAR(200),                 -- 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant'
    token_count INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT NOW(),

    -- Metadata for goal tracking
    goal_id UUID REFERENCES session_goals(id),
    analysis_type VARCHAR(100)               -- 'real_time_progress', 'comprehensive_analysis', 'adaptive_questioning'
);

-- ===================================
-- INDEXES FOR PERFORMANCE
-- ===================================

-- Session Goals Indexes
CREATE INDEX idx_session_goals_session_id ON session_goals(session_id);
CREATE INDEX idx_session_goals_template ON session_goals(goal_template_id);
CREATE INDEX idx_session_goals_status ON session_goals(completion_status);
CREATE INDEX idx_session_goals_progress ON session_goals(progress_score);

-- Goal Progress Events Indexes
CREATE INDEX idx_goal_events_session_goal ON goal_progress_events(session_goal_id);
CREATE INDEX idx_goal_events_timestamp ON goal_progress_events(timestamp);
CREATE INDEX idx_goal_events_type ON goal_progress_events(event_type);
CREATE INDEX idx_goal_events_model ON goal_progress_events(analysis_model);

-- Goal Templates Indexes
CREATE INDEX idx_goal_templates_role ON goal_templates(role_type);
CREATE INDEX idx_goal_templates_category ON goal_templates(category);
CREATE INDEX idx_goal_templates_priority ON goal_templates(priority_weight DESC);

-- Session Indexes
CREATE INDEX idx_sessions_status ON interview_sessions(status);
CREATE INDEX idx_sessions_started ON interview_sessions(started_at);
CREATE INDEX idx_sessions_role ON interview_sessions(role_type);

-- Transcript Indexes
CREATE INDEX idx_transcripts_session ON session_transcripts(session_id);
CREATE INDEX idx_transcripts_speaker ON session_transcripts(speaker);
CREATE INDEX idx_transcripts_timestamp ON session_transcripts(timestamp);
CREATE INDEX idx_transcripts_sequence ON session_transcripts(session_id, sequence_number);
CREATE INDEX idx_transcripts_search ON session_transcripts USING gin(text_vector);

-- Metrics Indexes
CREATE INDEX idx_metrics_session ON session_metrics(session_id);
CREATE INDEX idx_metrics_type ON session_metrics(metric_type);
CREATE INDEX idx_metrics_timestamp ON session_metrics(timestamp);
CREATE INDEX idx_metrics_goal ON session_metrics(goal_id);

-- ===================================
-- SEED DATA - DEFAULT GOAL TEMPLATES
-- ===================================

-- Backend Engineer Goals
INSERT INTO goal_templates (role_type, category, title, description, success_criteria, priority_weight, estimated_time_minutes, question_templates) VALUES
(
    'backend_engineer',
    'technical',
    'System Design Understanding',
    'Assess ability to design scalable backend systems',
    '["Discusses scalability considerations", "Mentions load balancing or caching", "Shows understanding of microservices or monoliths", "Addresses database design choices"]'::jsonb,
    0.9,
    10,
    '["How would you design a system to handle 1M concurrent users?", "Walk me through your approach to database optimization", "How do you handle service communication in a distributed system?"]'::jsonb
),
(
    'backend_engineer',
    'technical',
    'API Development Expertise',
    'Evaluate REST API and backend service development skills',
    '["Describes API design principles", "Discusses authentication/authorization", "Shows knowledge of HTTP methods and status codes", "Mentions API versioning or documentation"]'::jsonb,
    0.8,
    8,
    '["How do you design RESTful APIs?", "What is your approach to API authentication?", "How do you handle API versioning?"]'::jsonb
),
(
    'backend_engineer',
    'technical',
    'Database Proficiency',
    'Assess database design and query optimization skills',
    '["Discusses database normalization", "Shows SQL query optimization knowledge", "Mentions indexing strategies", "Addresses data modeling decisions"]'::jsonb,
    0.8,
    8,
    '["How would you optimize a slow SQL query?", "Explain your database design process", "When would you use NoSQL vs SQL?"]'::jsonb
),
(
    'backend_engineer',
    'communication',
    'Technical Communication',
    'Evaluate ability to explain complex technical concepts clearly',
    '["Explains concepts in simple terms", "Uses analogies effectively", "Structures explanations logically", "Engages in technical discussion"]'::jsonb,
    0.7,
    5,
    '["Explain microservices to a non-technical stakeholder", "How would you document this system for your team?"]'::jsonb
),
(
    'backend_engineer',
    'experience',
    'Project Impact Validation',
    'Verify claimed experience with specific project examples',
    '["Provides specific project examples", "Describes personal contributions clearly", "Mentions measurable outcomes", "Discusses challenges and solutions"]'::jsonb,
    0.9,
    12,
    '["Tell me about your most challenging backend project", "What was your specific role and contribution?", "How did you measure success?"]'::jsonb
);

-- Frontend Engineer Goals
INSERT INTO goal_templates (role_type, category, title, description, success_criteria, priority_weight, estimated_time_minutes, question_templates) VALUES
(
    'frontend_engineer',
    'technical',
    'Modern Framework Proficiency',
    'Assess expertise in modern frontend frameworks',
    '["Discusses React/Vue/Angular concepts", "Shows state management understanding", "Mentions component lifecycle", "Addresses performance optimization"]'::jsonb,
    0.9,
    10,
    '["How do you manage state in large React applications?", "Explain component lifecycle and optimization", "How do you handle performance in SPAs?"]'::jsonb
),
(
    'frontend_engineer',
    'technical',
    'CSS and Responsive Design',
    'Evaluate CSS skills and responsive design understanding',
    '["Shows CSS Grid/Flexbox knowledge", "Discusses responsive design principles", "Mentions CSS preprocessors", "Addresses browser compatibility"]'::jsonb,
    0.7,
    8,
    '["How do you approach responsive design?", "Explain CSS Grid vs Flexbox usage", "How do you handle browser compatibility?"]'::jsonb
),
(
    'frontend_engineer',
    'experience',
    'User Experience Focus',
    'Assess understanding of UX principles and user-centered design',
    '["Discusses user experience considerations", "Shows accessibility awareness", "Mentions user testing or feedback", "Addresses performance from user perspective"]'::jsonb,
    0.6,
    8,
    '["How do you ensure good user experience in your applications?", "What is your approach to accessibility?", "How do you gather and implement user feedback?"]'::jsonb
);

-- ===================================
-- USEFUL VIEWS
-- ===================================

-- Goal Progress Summary View
CREATE VIEW goal_progress_summary AS
SELECT
    sg.session_id,
    sg.id as goal_id,
    gt.title as goal_title,
    gt.category,
    sg.completion_status,
    sg.progress_score,
    sg.confidence_level,
    COALESCE(sg.time_spent_seconds, 0) as time_spent_seconds,
    gt.priority_weight,
    COUNT(gpe.id) as progress_events_count,
    MAX(gpe.timestamp) as last_update
FROM session_goals sg
JOIN goal_templates gt ON sg.goal_template_id = gt.id
LEFT JOIN goal_progress_events gpe ON sg.id = gpe.session_goal_id
GROUP BY sg.id, sg.session_id, gt.title, gt.category, sg.completion_status,
         sg.progress_score, sg.confidence_level, sg.time_spent_seconds, gt.priority_weight;

-- Session Overview View
CREATE VIEW session_overview AS
SELECT
    s.id,
    s.session_id,
    s.candidate_name,
    s.role_type,
    s.status,
    s.started_at,
    s.ended_at,
    s.duration_seconds,
    s.total_goals,
    s.completed_goals,
    s.average_progress,
    ROUND((s.completed_goals::decimal / NULLIF(s.total_goals, 0)) * 100, 1) as completion_percentage,
    COUNT(st.id) as transcript_entries,
    SUM(CASE WHEN sm.metric_type = 'llm_tokens' THEN sm.token_count ELSE 0 END) as total_llm_tokens,
    SUM(sm.cost_usd) as total_cost_usd
FROM interview_sessions s
LEFT JOIN session_transcripts st ON s.session_id = st.session_id
LEFT JOIN session_metrics sm ON s.session_id = sm.session_id
GROUP BY s.id, s.session_id, s.candidate_name, s.role_type, s.status,
         s.started_at, s.ended_at, s.duration_seconds, s.total_goals,
         s.completed_goals, s.average_progress;

-- ===================================
-- FUNCTIONS FOR GOAL TRACKING
-- ===================================

-- Function to update session goal statistics
CREATE OR REPLACE FUNCTION update_session_goal_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update session statistics when goal status changes
    UPDATE interview_sessions SET
        total_goals = (SELECT COUNT(*) FROM session_goals WHERE session_id = NEW.session_id),
        completed_goals = (SELECT COUNT(*) FROM session_goals WHERE session_id = NEW.session_id AND completion_status = 'completed'),
        average_progress = (SELECT COALESCE(AVG(progress_score), 0) FROM session_goals WHERE session_id = NEW.session_id),
        updated_at = NOW()
    WHERE session_id = NEW.session_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update session stats
CREATE TRIGGER trigger_update_session_stats
    AFTER INSERT OR UPDATE ON session_goals
    FOR EACH ROW
    EXECUTE FUNCTION update_session_goal_stats();

-- session_goals is declared before interview_sessions, so its FK to the external
-- session identifier is added here once both tables exist.
ALTER TABLE session_goals
    ADD CONSTRAINT session_goals_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id) ON DELETE CASCADE;

-- ===================================
-- PRIVILEGES FOR APPLICATION USER
-- ===================================
-- The voice bot connects as `ai_user` (see DB_USER in .env), but objects above
-- are created by the superuser running this script. Grant DML access so the bot
-- can read/write goal-tracking data without "permission denied" errors.

-- Create the application role if it doesn't exist yet (idempotent).
-- NOTE: change this password to match DB_PASSWORD in your .env before production.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_user') THEN
        CREATE ROLE ai_user LOGIN PASSWORD 'secure_password';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO ai_user;

-- Tables and views (interview_sessions, goal_templates, session_goals,
-- goal_progress_events, session_metrics, session_transcripts, session_overview)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_user;

-- IDs use gen_random_uuid() (no sequences today), but grant defensively.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ai_user;

-- Ensure objects created later by the schema owner are also accessible.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO ai_user;