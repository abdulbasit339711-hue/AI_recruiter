# Goal Tracking Implementation Plan

## Overview
This document outlines the implementation plan for intelligent goal tracking during AI recruiter interviews using Groq LLM models. The system will dynamically track interview objectives, assess goal completion, and adapt questioning strategies in real-time.

## Current System Analysis

### Existing Infrastructure
- ✅ **Dual LLM Pipeline**: Judge + Responder architecture
- ✅ **Real-time Processing**: Live transcript and evaluation
- ✅ **Session Management**: Complete interview state tracking
- ✅ **Event Broadcasting**: Dashboard integration for live updates
- ✅ **Token Metrics**: Resource usage monitoring

### Available Data Sources
- **Live Transcripts**: Real-time conversation flow
- **Judge Evaluations**: Candidate response assessments
- **Session Context**: Interview progress and timing
- **Question History**: Topics covered and depth achieved
- **Candidate Responses**: Technical discussions and examples

## Goal Tracking Architecture

### 1. Goal Tracking Pipeline

```
Interview Start → Goal Definition → Live Monitoring → Progress Assessment → Adaptive Questioning
               ↓                ↓               ↓                    ↓
         Goal Templates    Real-time Parsing  Coverage Analysis  Dynamic Prompts
```

### 2. Groq Model Strategy

**Primary Model**: `llama-3.3-70b-versatile`
- **Role**: Complex goal analysis and strategic decisions
- **Tasks**: Goal completion assessment, interview adaptation, comprehensive analysis
- **Context**: Large context window for full session understanding

**Secondary Model**: `llama-3.1-8b-instant`
- **Role**: Real-time goal monitoring and quick assessments
- **Tasks**: Live progress tracking, quick goal updates, instant feedback
- **Speed**: Fast responses for real-time processing

### 3. Goal Categories

#### A. Technical Competency Goals
- **System Design**: Architecture discussion, scalability considerations
- **Coding Skills**: Algorithm knowledge, problem-solving approach
- **Technology Stack**: Framework expertise, tool proficiency
- **Best Practices**: Code quality, security awareness, testing

#### B. Communication & Collaboration Goals
- **Technical Communication**: Explaining complex concepts clearly
- **Problem-Solving Process**: Thought process articulation
- **Team Collaboration**: Experience working with others
- **Learning Ability**: Adaptability and growth mindset

#### C. Experience Validation Goals
- **Project Depth**: Detailed project discussions
- **Role Responsibilities**: Actual contributions vs. claimed experience
- **Challenge Handling**: Problem resolution examples
- **Impact Demonstration**: Measurable outcomes and results

#### D. Cultural Fit Goals
- **Values Alignment**: Company culture compatibility
- **Work Style**: Collaboration preferences, communication style
- **Career Motivation**: Long-term goals and aspirations
- **Company Interest**: Research depth and genuine interest

## Implementation Plan

### Phase 1: Goal Definition Framework (Week 1)

#### Task 1.1: Goal Template System
```python
class InterviewGoal:
    def __init__(self, goal_id, category, title, description, success_criteria):
        self.id = goal_id
        self.category = category
        self.title = title
        self.description = description
        self.success_criteria = success_criteria
        self.completion_status = "not_started"  # not_started, in_progress, completed, failed
        self.evidence = []
        self.progress_score = 0.0  # 0.0 to 1.0

class GoalTracker:
    def __init__(self, role_type):
        self.goals = self.load_role_goals(role_type)
        self.session_id = None
        self.current_phase = "opening"
```

#### Task 1.2: Role-Specific Goal Templates
```python
BACKEND_ENGINEER_GOALS = [
    InterviewGoal(
        goal_id="tech_depth",
        category="technical",
        title="Assess Technical Depth",
        description="Evaluate depth of backend development knowledge",
        success_criteria=[
            "Discusses at least 2 backend frameworks",
            "Explains database design principles",
            "Demonstrates API development experience"
        ]
    ),
    InterviewGoal(
        goal_id="system_design",
        category="technical",
        title="System Design Thinking",
        description="Assess ability to design scalable systems",
        success_criteria=[
            "Discusses scalability considerations",
            "Mentions load balancing or caching",
            "Shows understanding of microservices"
        ]
    )
]
```

#### Task 1.3: Groq Integration Setup
```python
class GoalTrackingService:
    def __init__(self, groq_api_key):
        self.primary_client = AsyncGroq(api_key=groq_api_key)
        self.fast_client = AsyncGroq(api_key=groq_api_key)
        self.primary_model = "llama-3.3-70b-versatile"
        self.fast_model = "llama-3.1-8b-instant"
```

### Phase 2: Real-Time Monitoring (Week 2)

#### Task 2.1: Live Goal Progress Tracker
```python
class LiveGoalMonitor:
    async def process_transcript_update(self, speaker, text, session_context):
        if speaker == "candidate":
            # Use fast model for real-time processing
            progress_update = await self.analyze_candidate_response(text)
            await self.update_goal_progress(progress_update)

        elif speaker == "agent":
            # Track what topics interviewer is covering
            topic_analysis = await self.analyze_interviewer_focus(text)
            await self.update_coverage_tracking(topic_analysis)

    async def analyze_candidate_response(self, text):
        prompt = f"""
        Analyze this candidate response for goal progress:

        Response: {text}

        Current Goals:
        {self.format_active_goals()}

        Return JSON with:
        - goal_updates: [{{goal_id, evidence_found, progress_delta}}]
        - new_topics: [topics mentioned]
        - depth_indicators: [technical depth signals]
        """

        response = await self.fast_client.chat.completions.create(
            model=self.fast_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        return json.loads(response.choices[0].message.content)
```

#### Task 2.2: Progress Scoring Algorithm
```python
class ProgressCalculator:
    def calculate_goal_progress(self, goal, new_evidence):
        # Weighted scoring based on evidence quality
        evidence_weights = {
            "specific_example": 0.3,
            "technical_detail": 0.25,
            "problem_solving": 0.2,
            "quantifiable_impact": 0.15,
            "best_practices": 0.1
        }

        progress_delta = 0
        for evidence_type, weight in evidence_weights.items():
            if evidence_type in new_evidence:
                progress_delta += weight

        return min(1.0, goal.progress_score + progress_delta)
```

#### Task 2.3: Adaptive Questioning Engine
```python
class AdaptiveQuestioner:
    async def suggest_next_question(self, goal_status, session_context):
        underperforming_goals = [
            goal for goal in goal_status
            if goal.progress_score < 0.5 and goal.completion_status != "failed"
        ]

        if not underperforming_goals:
            return await self.generate_wrap_up_question()

        priority_goal = max(underperforming_goals, key=lambda g: g.priority_weight)

        prompt = f"""
        Generate a follow-up question to assess this goal:

        Goal: {priority_goal.title}
        Description: {priority_goal.description}
        Current Progress: {priority_goal.progress_score:.1%}
        Missing Criteria: {priority_goal.get_missing_criteria()}

        Session Context:
        - Duration: {session_context.duration}
        - Topics Covered: {session_context.topics_covered}
        - Candidate Engagement: {session_context.engagement_level}

        Return a natural follow-up question that will help assess this goal.
        """

        response = await self.primary_client.chat.completions.create(
            model=self.primary_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content
```

### Phase 3: Intelligent Analysis (Week 3)

#### Task 3.1: Goal Completion Assessment
```python
class GoalAnalyzer:
    async def comprehensive_goal_analysis(self, session_data):
        # Use primary model for deep analysis
        analysis_prompt = f"""
        Perform comprehensive goal completion analysis:

        Interview Session:
        - Transcript: {session_data.full_transcript}
        - Duration: {session_data.duration}
        - Goals: {session_data.goals}

        For each goal, analyze:
        1. Completion Status (completed/partial/not_addressed)
        2. Evidence Quality (strong/moderate/weak)
        3. Specific Examples Found
        4. Missing Elements
        5. Confidence Score (0-100)

        Return structured JSON analysis.
        """

        response = await self.primary_client.chat.completions.create(
            model=self.primary_model,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.1,
            max_tokens=2000
        )
        return json.loads(response.choices[0].message.content)
```

#### Task 3.2: Coverage Gap Detection
```python
async def detect_coverage_gaps(self, goals, transcript):
    gap_analysis_prompt = f"""
    Analyze interview coverage gaps:

    Planned Goals: {[goal.title for goal in goals]}
    Full Transcript: {transcript}

    Identify:
    1. Completely missed topics
    2. Superficially covered areas needing depth
    3. Opportunities for follow-up questions
    4. Time allocation efficiency
    5. Interview flow improvements

    Provide actionable recommendations.
    """

    response = await self.primary_client.chat.completions.create(
        model=self.primary_model,
        messages=[{"role": "user", "content": gap_analysis_prompt}],
        temperature=0.2,
        max_tokens=1500
    )
    return response.choices[0].message.content
```

### Phase 4: Dashboard Integration (Week 4)

#### Task 4.1: Real-Time Goal Visualization
```python
class GoalDashboard:
    async def broadcast_goal_update(self, goal_update):
        await self.broadcaster.broadcast("goal_progress", {
            "session_id": self.session_id,
            "goal_id": goal_update.goal_id,
            "progress_score": goal_update.progress_score,
            "completion_status": goal_update.completion_status,
            "latest_evidence": goal_update.latest_evidence,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_coverage_summary(self):
        summary = {
            "total_goals": len(self.goals),
            "completed": len([g for g in self.goals if g.completion_status == "completed"]),
            "in_progress": len([g for g in self.goals if g.completion_status == "in_progress"]),
            "not_started": len([g for g in self.goals if g.completion_status == "not_started"]),
            "overall_progress": sum(g.progress_score for g in self.goals) / len(self.goals),
            "time_remaining": self.estimate_remaining_time()
        }

        await self.broadcaster.broadcast("goal_coverage_summary", summary)
```

#### Task 4.2: Interactive Goal Management
```python
@app.get("/goals/{session_id}")
async def get_goal_status(session_id: str):
    tracker = goal_trackers.get(session_id)
    if not tracker:
        return {"error": "Session not found"}

    return {
        "goals": [goal.to_dict() for goal in tracker.goals],
        "session_progress": tracker.get_session_progress(),
        "recommendations": await tracker.get_recommendations()
    }

@app.post("/goals/{session_id}/adjust")
async def adjust_goals(session_id: str, adjustments: GoalAdjustments):
    tracker = goal_trackers.get(session_id)
    await tracker.adjust_goals(adjustments)
    return {"status": "goals_updated"}
```

## Technical Implementation Details

### 1. Integration with Existing Pipeline

#### Modify Judge Processor for Goal Tracking
```python
class GoalTrackingJudgeProcessor(JudgeProcessor):
    def __init__(self, session, broadcaster, api_key, goal_tracker):
        super().__init__(session, broadcaster, api_key)
        self.goal_tracker = goal_tracker

    async def _evaluate_response(self, text: str):
        # Original evaluation
        await super()._evaluate_response(text)

        # Goal tracking analysis
        goal_progress = await self.goal_tracker.analyze_response_for_goals(text)
        await self.goal_tracker.update_progress(goal_progress)

        # Broadcast goal updates
        await self.broadcaster.broadcast("goal_update", goal_progress)
```

#### Enhance Context Processor for Goal-Driven Questions
```python
class GoalAwareDualLLMContextProcessor(DualLLMContextProcessor):
    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Add goal-driven context to LLM
        if self.should_inject_goal_context(frame):
            goal_context = await self.goal_tracker.get_next_question_context()
            # Inject goal-driven questioning context
            await self.inject_goal_context(frame, goal_context)
```

### 2. Database Schema

```sql
-- Goal Templates
CREATE TABLE goal_templates (
    id UUID PRIMARY KEY,
    role_type VARCHAR(100),
    category VARCHAR(50),
    title VARCHAR(200),
    description TEXT,
    success_criteria JSONB,
    priority_weight DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Session Goal Tracking
CREATE TABLE session_goals (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES interview_sessions(id),
    goal_template_id UUID REFERENCES goal_templates(id),
    completion_status VARCHAR(50),
    progress_score DECIMAL(3,2),
    evidence JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Goal Progress Events
CREATE TABLE goal_progress_events (
    id UUID PRIMARY KEY,
    session_goal_id UUID REFERENCES session_goals(id),
    event_type VARCHAR(50),
    progress_delta DECIMAL(3,2),
    evidence TEXT,
    confidence_score DECIMAL(3,2),
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_session_goals_session ON session_goals(session_id);
CREATE INDEX idx_goal_events_session_goal ON goal_progress_events(session_goal_id);
CREATE INDEX idx_goal_events_timestamp ON goal_progress_events(timestamp);
```

### 3. API Endpoints

```python
@app.get("/goals/templates/{role_type}")
async def get_goal_templates(role_type: str):
    return await goal_service.get_templates_for_role(role_type)

@app.post("/sessions/{session_id}/goals/initialize")
async def initialize_session_goals(session_id: str, role_config: RoleConfig):
    return await goal_service.initialize_goals(session_id, role_config)

@app.get("/sessions/{session_id}/goals/progress")
async def get_goal_progress(session_id: str):
    return await goal_service.get_live_progress(session_id)

@app.post("/sessions/{session_id}/goals/{goal_id}/manual-update")
async def manual_goal_update(session_id: str, goal_id: str, update: ManualGoalUpdate):
    return await goal_service.manual_update(session_id, goal_id, update)
```

### 4. Prompt Templates

#### Real-Time Progress Analysis Prompt
```python
PROGRESS_ANALYSIS_PROMPT = """
You are analyzing a candidate's response for interview goal progress.

CANDIDATE RESPONSE: {response_text}

ACTIVE GOALS:
{active_goals}

PREVIOUS CONTEXT:
{conversation_context}

Analyze this response and return JSON with:
{{
    "goal_updates": [
        {{
            "goal_id": "string",
            "evidence_type": "specific_example|technical_detail|problem_solving|impact",
            "evidence_text": "exact quote from response",
            "progress_delta": 0.0-1.0,
            "confidence": 0.0-1.0
        }}
    ],
    "topics_mentioned": ["topic1", "topic2"],
    "depth_level": "surface|moderate|deep",
    "follow_up_needed": boolean
}}

Be precise and only award progress for clear, substantive evidence.
"""
```

#### Comprehensive Goal Analysis Prompt
```python
COMPREHENSIVE_ANALYSIS_PROMPT = """
You are conducting a final analysis of interview goal achievement.

FULL INTERVIEW:
Transcript: {full_transcript}
Duration: {duration_minutes} minutes
Role: {target_role}

GOALS TO ASSESS:
{goal_list}

For each goal, provide detailed analysis:

{{
    "goal_analysis": [
        {{
            "goal_id": "string",
            "completion_status": "completed|partially_completed|not_addressed",
            "final_score": 0.0-1.0,
            "evidence_summary": {{
                "strong_indicators": ["evidence1", "evidence2"],
                "weak_indicators": ["evidence1"],
                "missing_elements": ["element1", "element2"]
            }},
            "key_quotes": ["quote1", "quote2"],
            "assessment_confidence": 0.0-1.0,
            "improvement_areas": ["area1", "area2"]
        }}
    ],
    "overall_assessment": {{
        "interview_effectiveness": 0.0-1.0,
        "goal_coverage": 0.0-1.0,
        "candidate_performance": 0.0-1.0,
        "missed_opportunities": ["opportunity1"],
        "interview_recommendations": ["recommendation1"]
    }}
}}

Provide thorough, evidence-based analysis.
"""
```

## Performance Optimization

### 1. Model Usage Strategy
```python
class OptimizedGoalTracker:
    async def route_analysis_request(self, request_type, complexity, urgency):
        if urgency == "real_time" and complexity == "low":
            # Use fast model for immediate feedback
            return await self.analyze_with_fast_model(request)
        elif complexity == "high" or request_type == "comprehensive":
            # Use primary model for deep analysis
            return await self.analyze_with_primary_model(request)
        else:
            # Default to fast model for most operations
            return await self.analyze_with_fast_model(request)
```

### 2. Caching Strategy
```python
class GoalTrackingCache:
    def __init__(self):
        self.goal_templates = {}
        self.session_progress = {}
        self.analysis_results = {}

    async def get_or_compute_analysis(self, cache_key, compute_func):
        if cache_key in self.analysis_results:
            return self.analysis_results[cache_key]

        result = await compute_func()
        self.analysis_results[cache_key] = result
        return result
```

### 3. Batch Processing
```python
async def process_goal_updates_batch(self, updates_batch):
    # Process multiple goal updates together
    if len(updates_batch) == 1:
        return await self.process_single_update(updates_batch[0])

    # Batch multiple updates for efficiency
    batch_prompt = self.create_batch_analysis_prompt(updates_batch)
    response = await self.fast_client.chat.completions.create(
        model=self.fast_model,
        messages=[{"role": "user", "content": batch_prompt}],
        temperature=0.1,
        max_tokens=1500
    )
    return self.parse_batch_response(response.choices[0].message.content)
```

## Quality Assurance

### 1. Goal Tracking Accuracy
```python
class GoalTrackingValidator:
    async def validate_progress_update(self, goal, evidence, proposed_delta):
        # Consistency checks
        if proposed_delta > 0.5 and not self.has_strong_evidence(evidence):
            return False

        # Progress logic validation
        if goal.progress_score + proposed_delta > 1.0:
            return False

        # Evidence quality check
        return await self.validate_evidence_quality(evidence)
```

### 2. Model Response Validation
```python
async def validate_llm_response(self, response_json):
    required_fields = ["goal_updates", "topics_mentioned", "depth_level"]

    try:
        data = json.loads(response_json)
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")
        return True
    except json.JSONDecodeError:
        return False
```

## Monitoring & Analytics

### 1. Goal Tracking Metrics
```python
class GoalTrackingMetrics:
    async def collect_session_metrics(self, session_id):
        return {
            "goal_completion_rate": self.calculate_completion_rate(),
            "average_goal_progress": self.calculate_average_progress(),
            "time_to_goal_completion": self.calculate_time_metrics(),
            "interviewer_effectiveness": self.calculate_interviewer_score(),
            "candidate_engagement": self.calculate_engagement_score()
        }
```

### 2. Performance Monitoring
```python
async def monitor_goal_tracking_performance():
    metrics = {
        "analysis_latency": await measure_analysis_speed(),
        "goal_accuracy": await measure_progress_accuracy(),
        "model_usage": await track_model_costs(),
        "dashboard_responsiveness": await measure_ui_performance()
    }
    await send_metrics_to_monitoring(metrics)
```

## Success Metrics

### 1. Technical KPIs
- **Goal Detection Accuracy**: >90% correct identification of goal-related content
- **Real-time Processing**: <3 second latency for progress updates
- **Analysis Completion Rate**: >95% successful goal assessments
- **Model Cost Efficiency**: <$0.50 per interview session

### 2. Interview Quality Metrics
- **Goal Coverage**: Average 80%+ goal completion per interview
- **Interview Efficiency**: Reduced time to assess key competencies
- **Question Relevance**: 85%+ of questions aligned with incomplete goals
- **Adaptive Questioning**: Demonstrated improvement in follow-up quality

### 3. User Experience Metrics
- **Dashboard Responsiveness**: <2 second goal status updates
- **Interviewer Satisfaction**: 4.5+ rating on goal tracking utility
- **Decision Confidence**: Increased hiring decision confidence scores
- **Time Savings**: 30% reduction in post-interview assessment time

## Future Enhancements

### 1. Advanced Features
- **Dynamic Goal Adjustment**: AI-suggested goal modifications mid-interview
- **Personality Assessment Integration**: Goal tracking for soft skills
- **Multi-Round Interview Coordination**: Goal progression across interview stages
- **Industry-Specific Templates**: Specialized goals for different tech domains

### 2. Machine Learning Integration
- **Goal Importance Weighting**: ML-based priority adjustment
- **Predictive Goal Completion**: Forecast interview outcomes early
- **Question Effectiveness Scoring**: Learn optimal question patterns
- **Candidate Success Correlation**: Link goal achievement to job performance

## Conclusion

This goal tracking implementation leverages the dual Groq model strategy to provide intelligent, real-time interview guidance. The `llama-3.3-70b-versatile` model handles complex analysis and strategic decisions, while `llama-3.1-8b-instant` ensures responsive real-time monitoring.

The system transforms static interview processes into adaptive, goal-driven conversations that maximize assessment efficiency while maintaining candidate experience quality.

**Implementation Priority:**
1. Phase 1: Foundation framework and basic tracking
2. Phase 2: Real-time monitoring and progress updates
3. Phase 3: Advanced analysis and recommendation engine
4. Phase 4: Dashboard integration and user experience optimization

This approach ensures systematic development while delivering immediate value through improved interview focus and goal achievement tracking.