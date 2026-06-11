# AI Recruiter Implementation Roadmap

## Executive Summary

**Priority Order**: Goal Tracking → Post-Call Analysis
**Timeline**: 3 weeks for Goal Tracking, then 4 weeks for Post-Call Analysis
**Database**: Start with Goal Tracking schema (3 core tables) then extend for analysis

## Phase 1: Goal Tracking Implementation (Priority #1)

### **Why Goal Tracking First?**

1. **Foundation for Everything**: Creates structured data that Post-Call Analysis needs
2. **Immediate ROI**: Real-time interview improvement vs delayed insights
3. **Simpler Database**: 3 core tables vs 5+ complex analysis tables
4. **User Adoption**: Live guidance more valuable than retrospective reports
5. **Testing Easier**: Real-time feedback easier to validate than complex analysis

### **Week 1: Database Foundation & Core Services**

#### Database Setup (Days 1-2)
```bash
# Create database schema
psql -d ai_recruiter -f database_schema.sql
```

**Core Tables Created:**
- `goal_templates` - Reusable interview objectives
- `session_goals` - Goal instances per interview
- `goal_progress_events` - Real-time progress tracking
- `interview_sessions` - Session management
- `session_transcripts` - Conversation history
- `session_metrics` - Cost and performance tracking

#### Goal Service Implementation (Days 3-5)
```python
# File: services/goal_tracking_service.py
class GoalTrackingService:
    def __init__(self, db_pool, groq_api_key):
        self.db = db_pool
        self.primary_model = "llama-3.3-70b-versatile"  # Complex analysis
        self.fast_model = "llama-3.1-8b-instant"        # Real-time monitoring
        self.groq_client = AsyncGroq(api_key=groq_api_key)

    async def initialize_session_goals(self, session_id, role_type):
        """Load goal templates and create session instances"""
        templates = await self.get_goal_templates(role_type)
        session_goals = []

        for template in templates:
            goal = await self.create_session_goal(session_id, template)
            session_goals.append(goal)

        return session_goals

    async def analyze_candidate_response(self, text, session_context):
        """Real-time analysis using fast model"""
        prompt = self._build_progress_analysis_prompt(text, session_context)

        response = await self.groq_client.chat.completions.create(
            model=self.fast_model,  # llama-3.1-8b-instant for speed
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800
        )

        return json.loads(response.choices[0].message.content)
```

### **Week 2: Real-Time Integration**

#### Pipeline Integration (Days 6-8)
```python
# File: goal_tracking_processor.py
class GoalTrackingProcessor(FrameProcessor):
    """Integrates with existing dual LLM pipeline"""

    async def process_frame(self, frame: Frame, direction):
        if isinstance(frame, TranscriptionFrame):
            if frame.user_id != "manual-input":  # Candidate speech
                # Real-time goal progress analysis
                asyncio.create_task(
                    self._analyze_for_goal_progress(frame.text)
                )

        await super().process_frame(frame, direction)

    async def _analyze_for_goal_progress(self, text):
        """Background analysis of candidate response"""
        progress_update = await self.goal_service.analyze_candidate_response(
            text, self.session_context
        )

        # Update database
        await self.goal_service.update_progress(progress_update)

        # Broadcast to dashboard
        await self.broadcaster.broadcast("goal_progress", progress_update)
```

#### Dashboard Integration (Days 9-10)
```python
# Add to runner.py
@app.get("/goals/{session_id}")
async def get_goal_status(session_id: str):
    return await goal_service.get_session_progress(session_id)

@app.post("/goals/{session_id}/manual-update")
async def manual_goal_update(session_id: str, update: dict):
    return await goal_service.manual_update(session_id, update)
```

### **Week 3: Adaptive Questioning & Testing**

#### Adaptive Question Engine (Days 11-13)
```python
class AdaptiveQuestioningEngine:
    async def suggest_next_question(self, session_goals):
        """Use primary model for strategic questioning"""
        underperforming_goals = [
            g for g in session_goals
            if g.progress_score < 0.6 and g.completion_status != 'skipped'
        ]

        if not underperforming_goals:
            return None  # All goals adequately covered

        priority_goal = max(underperforming_goals, key=lambda g: g.priority_weight)

        prompt = f"""
        Generate a natural follow-up question for this interview goal:

        Goal: {priority_goal.title}
        Current Progress: {priority_goal.progress_score:.1%}
        Missing Criteria: {priority_goal.get_missing_criteria()}

        Context: {self.get_conversation_context()}

        Return a question that naturally advances the conversation while assessing this goal.
        """

        response = await self.groq_client.chat.completions.create(
            model=self.primary_model,  # llama-3.3-70b-versatile for strategy
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )

        return response.choices[0].message.content
```

#### Testing & Validation (Days 14-15)
- Integration testing with existing pipeline
- Dashboard real-time updates testing
- Goal progress accuracy validation
- Performance optimization

## Phase 2: Post-Call Analysis Implementation (4 weeks)

### **Week 4-5: Analysis Engine**
- Multi-model analysis pipeline
- Comprehensive session evaluation
- Report generation system

### **Week 6-7: Advanced Features**
- Bias detection
- Predictive analytics
- Candidate comparison

### **Week 8: Integration & Optimization**
- Dashboard integration
- Performance tuning
- Documentation completion

## Technical Implementation Details

### **Database Connection Setup**

```python
# File: database.py
import asyncpg
import os
from typing import Optional

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool"""
        self.pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", 5432),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "ai_recruiter"),
            min_size=2,
            max_size=10
        )

    async def close(self):
        if self.pool:
            await self.pool.close()

# Global database instance
db_manager = DatabaseManager()
```

### **Integration with Existing Code**

```python
# Modify bot_manager_dual.py
from services.goal_tracking_service import GoalTrackingService
from processors.goal_tracking_processor import GoalTrackingProcessor

class BotManager:
    def __init__(self, ...):
        # ... existing code ...

        # Add goal tracking
        self.goal_service = GoalTrackingService(
            db_manager.pool,
            os.getenv("GROQ_API_KEY")
        )

    async def create_pipeline(self):
        # ... existing processors ...

        # Add goal tracking processor
        goal_processor = GoalTrackingProcessor(
            self.session,
            self.broadcaster,
            self.goal_service
        )

        processors = [
            stt,
            transcript_processor,
            goal_processor,      # Add goal tracking
            user_aggregator,
            llm,
            metrics_processor,
            tts
        ]

        return Pipeline(processors=processors)
```

### **Environment Variables**

```bash
# Add to .env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=ai_recruiter

# Goal tracking settings
GOAL_TRACKING_ENABLED=true
ADAPTIVE_QUESTIONING=true
REAL_TIME_ANALYSIS=true
```

## Success Metrics for Phase 1

### **Technical KPIs**
- [ ] Goal detection accuracy >85%
- [ ] Real-time analysis latency <3 seconds
- [ ] Database write performance <500ms
- [ ] Dashboard update responsiveness <2 seconds

### **Business KPIs**
- [ ] Interview goal coverage >75%
- [ ] Interviewer satisfaction >4.0/5
- [ ] Adaptive question relevance >80%
- [ ] Time-to-hire improvement measurable

## Risk Mitigation

### **Technical Risks**
1. **Database Performance**: Use connection pooling and optimized queries
2. **LLM API Limits**: Implement retry logic and fallback strategies
3. **Real-time Processing**: Async processing with proper error handling

### **Business Risks**
1. **User Adoption**: Start with simple MVP, gather feedback
2. **Accuracy Concerns**: A/B test with manual validation
3. **Cost Control**: Monitor token usage, implement cost alerts

## Decision Points

### **Go/No-Go Criteria for Phase 2**
- [ ] Phase 1 goal tracking shows >80% accuracy
- [ ] Real-time performance meets targets
- [ ] User feedback positive (>4.0/5)
- [ ] Database performance stable under load
- [ ] Cost per session <$2.00

## Resource Requirements

### **Development Time**
- **Phase 1**: 3 weeks (1 developer)
- **Phase 2**: 4 weeks (1 developer)
- **Total**: 7 weeks end-to-end

### **Infrastructure**
- PostgreSQL database (existing or new)
- Groq API access (existing)
- No additional services required

### **Testing**
- Unit tests for goal tracking logic
- Integration tests with existing pipeline
- Load testing for real-time performance
- User acceptance testing with sample interviews

## Conclusion

**Start with Goal Tracking immediately** - it provides immediate value, creates the foundation for Post-Call Analysis, and has lower implementation complexity. The database schema is ready, the integration points are clear, and the success metrics are achievable.

Post-Call Analysis will be much more effective once Goal Tracking provides structured, real-time data about interview progression and candidate assessment.