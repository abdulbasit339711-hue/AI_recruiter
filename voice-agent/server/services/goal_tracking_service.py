"""
Goal Tracking Service - High-level operations for goal management and analysis
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from groq import AsyncGroq
from loguru import logger

from database import db_manager
from interview_session import InterviewSession, InterviewGoal
from recruiter_shared import normalize_role_type


def _safe_json_loads(content: str) -> dict:
    """Parse an LLM JSON response defensively.

    Models occasionally return an empty string or wrap JSON in ```json fences.
    Returns {} if nothing parseable is found so callers degrade gracefully
    instead of raising 'Expecting value: line 1 column 1'.
    """
    if not content or not content.strip():
        return {}
    text = content.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                pass
    logger.warning(f"[GoalTracking] Could not parse LLM JSON response: {content[:120]!r}")
    return {}


class GoalTrackingService:
    """
    High-level service for goal tracking operations
    Uses dual Groq models: llama-3.3-70b-versatile for complex analysis, llama-3.1-8b-instant for real-time
    """

    def __init__(self, groq_api_key: str):
        self.groq_client = AsyncGroq(api_key=groq_api_key)
        self.primary_model = "llama-3.3-70b-versatile"  # Complex analysis
        self.fast_model = "llama-3.1-8b-instant"        # Real-time monitoring

        # Cache for session goals
        self._session_goals_cache: Dict[str, List[Dict[str, Any]]] = {}

    # ===================================
    # SESSION INITIALIZATION
    # ===================================

    async def initialize_session_goals(self, interview_session: InterviewSession) -> List[str]:
        """Initialize goal tracking for a session based on existing InterviewGoal objects"""
        session_id = interview_session.session_id
        # Use the normalized role slug so templates match the seeded/cached ones
        # (e.g. "Backend Engineer" -> "backend_engineer") instead of creating dupes.
        role_slug = normalize_role_type(interview_session.config.job_role)

        # Create database session entry
        session_data = {
            "session_id": session_id,
            "candidate_name": getattr(interview_session, 'candidate_name', None),
            "role_type": role_slug,
            "company_name": interview_session.config.company_name,
            "pipeline_mode": "dual",  # Assume dual mode for goal tracking
            "candidate_id": getattr(interview_session, "db_candidate_id", None),
            "job_id": getattr(interview_session, "db_job_id", None),
        }

        try:
            await db_manager.create_session(session_data)
        except Exception as e:
            logger.error(f"[GoalTracking] Failed to create session: {e}")
            # Continue with in-memory tracking if DB fails

        # Map existing InterviewGoal objects to database templates
        goal_ids = []
        for goal in interview_session.config.goals:
            try:
                # Create or match goal template (by normalized role slug)
                template_id = await self._ensure_goal_template(goal, role_slug)

                # Create session goal
                goal_data = {
                    "session_id": session_id,
                    "goal_template_id": template_id,
                    "completion_status": "not_started",
                    "progress_score": 0.0,
                    "confidence_level": 0.0
                }

                goal_id = await self._create_session_goal(goal_data)
                goal_ids.append(goal_id)

            except Exception as e:
                logger.error(f"[GoalTracking] Failed to initialize goal {goal.id}: {e}")
                continue

        # Cache goals for fast access
        await self._refresh_goals_cache(session_id)

        logger.info(f"[GoalTracking] Initialized {len(goal_ids)} goals for session: {session_id}")
        return goal_ids

    async def _ensure_goal_template(self, goal: InterviewGoal, role_type: str) -> str:
        """Ensure goal template exists in database, create if needed"""
        # Try to find existing template
        templates = await db_manager.get_goal_templates(role_type)
        existing = next((t for t in templates if t["title"] == goal.label), None)

        if existing:
            return existing["id"]

        # Create new template
        template_data = {
            "role_type": role_type,
            "category": "general",  # Default category
            "title": goal.label,
            "description": goal.description,
            "success_criteria": ["Goal completion assessed"],  # Default criteria
            "priority_weight": goal.weight,
            "estimated_time_minutes": 5,
            "question_templates": []
        }

        query = """
        INSERT INTO goal_templates
        (role_type, category, title, description, success_criteria, priority_weight, estimated_time_minutes, question_templates)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """

        template_id = await db_manager.execute_query(
            query,
            template_data["role_type"],
            template_data["category"],
            template_data["title"],
            template_data["description"],
            json.dumps(template_data["success_criteria"]),
            template_data["priority_weight"],
            template_data["estimated_time_minutes"],
            json.dumps(template_data["question_templates"])
        )

        return str(template_id)

    async def _create_session_goal(self, goal_data: Dict[str, Any]) -> str:
        """Create a session goal in database"""
        query = """
        INSERT INTO session_goals
        (session_id, goal_template_id, completion_status, progress_score, confidence_level)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """

        goal_id = await db_manager.execute_query(
            query,
            goal_data["session_id"],
            goal_data["goal_template_id"],
            goal_data["completion_status"],
            goal_data["progress_score"],
            goal_data["confidence_level"]
        )

        return str(goal_id)

    # ===================================
    # REAL-TIME GOAL ANALYSIS
    # ===================================

    async def analyze_candidate_response(self, session_id: str, response_text: str,
                                       context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze candidate response for goal progress using fast model
        Returns progress updates for affected goals
        """
        try:
            # Get current goals
            session_goals = await self.get_session_goals(session_id)
            if not session_goals:
                return {"goal_updates": [], "analysis_performed": False}

            # Build analysis prompt
            active_goals = [g for g in session_goals if g["completion_status"] in ["not_started", "in_progress"]]
            if not active_goals:
                return {"goal_updates": [], "analysis_performed": False, "reason": "all_goals_completed"}

            prompt = self._build_progress_analysis_prompt(response_text, active_goals, context)

            # Analyze with fast model for real-time response
            response = await self.groq_client.chat.completions.create(
                model=self.fast_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

            analysis = _safe_json_loads(response.choices[0].message.content)

            # Process goal updates
            for goal_update in analysis.get("goal_updates", []):
                await self._apply_goal_update(session_id, goal_update, response_text)

            # Track analysis metrics
            await self._track_analysis_metrics(session_id, "real_time_progress", self.fast_model)

            return analysis

        except Exception as e:
            logger.error(f"[GoalTracking] Analysis failed: {e}")
            return {"goal_updates": [], "error": str(e)}

    def _build_progress_analysis_prompt(self, response_text: str, active_goals: List[Dict],
                                      context: Dict[str, Any] = None) -> str:
        """Build prompt for real-time goal progress analysis"""
        goals_summary = []
        for goal in active_goals[:5]:  # Limit to 5 goals for prompt efficiency
            goals_summary.append(f"""
Goal: {goal['title']}
Description: {goal['description']}
Current Progress: {goal['progress_score']:.1%}
Success Criteria: {goal.get('success_criteria', [])}
""")

        context_info = ""
        if context:
            context_info = f"""
Conversation Context:
- Current Question: {context.get('current_question', 'N/A')}
- Interview Phase: {context.get('interview_phase', 'N/A')}
- Time Elapsed: {context.get('time_elapsed', 'N/A')}
"""

        return f"""You are analyzing a candidate's response for interview goal progress.

CANDIDATE RESPONSE: {response_text}

ACTIVE GOALS TO ASSESS:
{chr(10).join(goals_summary)}

{context_info}

Analyze this response and return JSON with:
{{
    "goal_updates": [
        {{
            "goal_title": "exact goal title",
            "evidence_type": "specific_example|technical_detail|problem_solving|quantifiable_impact|best_practices",
            "evidence_text": "exact quote showing evidence",
            "progress_delta": 0.0-0.3,
            "confidence": 0.0-1.0,
            "reasoning": "why this shows progress"
        }}
    ],
    "response_quality": "strong|moderate|weak",
    "topics_mentioned": ["topic1", "topic2"],
    "follow_up_needed": boolean,
    "suggested_probe": "natural follow-up question if needed"
}}

Only award progress for clear, substantial evidence. Be conservative with progress_delta (max 0.3 per response).
Focus on the most relevant goals that this response actually addresses."""

    async def _apply_goal_update(self, session_id: str, goal_update: Dict[str, Any],
                               response_text: str) -> bool:
        """Apply a goal update to the database"""
        try:
            # Find goal by title
            session_goals = await self.get_session_goals(session_id)
            target_goal = next((g for g in session_goals if g["title"] == goal_update["goal_title"]), None)

            if not target_goal:
                logger.warning(f"[GoalTracking] Goal not found: {goal_update['goal_title']}")
                return False

            # Calculate new progress. progress_score comes back from Postgres NUMERIC
            # as Decimal, so coerce to float before arithmetic (Decimal + float raises).
            current_progress = float(target_goal["progress_score"])
            progress_delta = max(-0.3, min(float(goal_update.get("progress_delta", 0.0)), 0.3))  # clamp [-0.3, 0.3]
            new_progress = max(0.0, min(1.0, current_progress + progress_delta))

            # Determine completion status
            completion_status = target_goal["completion_status"]
            if new_progress >= 0.8:
                completion_status = "completed"
            elif new_progress > 0.0:
                completion_status = "in_progress"

            # Build progress data
            progress_data = {
                "progress_score": new_progress,
                "confidence_level": goal_update.get("confidence", 0.5),
                "completion_status": completion_status,
                "evidence": {
                    "type": goal_update.get("evidence_type"),
                    "text": goal_update.get("evidence_text"),
                    "reasoning": goal_update.get("reasoning"),
                    "timestamp": datetime.now().isoformat()
                },
                "progress_delta": progress_delta,
                "evidence_type": goal_update.get("evidence_type"),
                "evidence_text": goal_update.get("evidence_text"),
                "analysis_model": self.fast_model,
                "confidence_score": goal_update.get("confidence", 0.5),
                "event_type": "evidence_found"
            }

            # Update database
            await db_manager.update_goal_progress(target_goal["id"], progress_data)

            # Invalidate cache
            if session_id in self._session_goals_cache:
                del self._session_goals_cache[session_id]

            logger.debug(f"[GoalTracking] Updated goal '{goal_update['goal_title']}': {current_progress:.2f} -> {new_progress:.2f}")
            return True

        except Exception as e:
            logger.error(f"[GoalTracking] Failed to apply goal update: {e}")
            return False

    # ===================================
    # COMPREHENSIVE ANALYSIS
    # ===================================

    async def comprehensive_goal_analysis(self, session_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive goal analysis using primary model
        Used for final assessment or mid-interview deep analysis
        """
        try:
            # Get session data
            session_overview = await db_manager.get_session_overview(session_id)
            if not session_overview:
                return {"error": "Session not found"}

            session_goals = await self.get_session_goals(session_id)

            # Get full transcript
            transcript = await self._get_session_transcript(session_id)

            # Build comprehensive analysis prompt
            prompt = self._build_comprehensive_analysis_prompt(session_goals, transcript, session_overview)

            # Analyze with primary model for depth
            response = await self.groq_client.chat.completions.create(
                model=self.primary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            analysis = _safe_json_loads(response.choices[0].message.content)

            # Track analysis metrics
            await self._track_analysis_metrics(session_id, "comprehensive_analysis", self.primary_model)

            return analysis

        except Exception as e:
            logger.error(f"[GoalTracking] Comprehensive analysis failed: {e}")
            return {"error": str(e)}

    def _build_comprehensive_analysis_prompt(self, session_goals: List[Dict],
                                           transcript: List[Dict], session_overview: Dict) -> str:
        """Build prompt for comprehensive goal analysis"""
        goals_detail = []
        for goal in session_goals:
            goals_detail.append(f"""
Goal: {goal['title']}
Category: {goal['category']}
Description: {goal['description']}
Success Criteria: {goal.get('success_criteria', [])}
Current Progress: {goal['progress_score']:.1%}
Status: {goal['completion_status']}
Evidence Found: {len(goal.get('evidence', []))} items
""")

        transcript_text = "\n".join([
            f"[{turn['speaker']}]: {turn['text']}"
            for turn in transcript[-50:]  # Last 50 turns for context
        ])

        return f"""You are an AI HR analyst conducting a comprehensive post-interview candidate evaluation.

SESSION OVERVIEW:
- Duration: {(session_overview.get('duration_seconds') or 0) // 60} minutes
- Role: {session_overview.get('role_type')}
- Total Goals: {len(session_goals)}
- Completed: {session_overview.get('completed_goals', 0)}

GOALS ANALYSIS:
{chr(10).join(goals_detail)}

CONVERSATION TRANSCRIPT:
{transcript_text}

Evaluate the candidate across ALL 14 dimensions below, then provide a final AI recommendation.

EVALUATION FRAMEWORK:
1. Communication Skills — clarity, active listening, professional interaction
2. Confidence & Presentation — confidence, demeanor, handling of challenging questions
3. Technical Competency — role-specific knowledge, practical application of skills
4. Problem-Solving & Critical Thinking — analytical ability, decision-making, creativity
5. Relevant Experience — prior responsibilities, achievements, demonstrated impact
6. Skills Match Assessment — alignment with job requirements, strengths and gaps
7. Cultural & Organizational Fit — values alignment, teamwork, ethics, adaptability
8. Leadership & Ownership — initiative, accountability, influence potential
9. Learning Agility — willingness to learn, adaptability to change and feedback
10. Emotional Intelligence — self-awareness, emotional control, conflict management
11. Motivation & Career Alignment — interest in the role, career goals, long-term commitment
12. Behavioral Assessment — professional attitude, work ethic, reliability
13. Resume & Interview Consistency — consistency between CV claims and interview responses
14. Overall Performance Evaluation — key strengths, development areas, suitability rating

Provide your analysis in JSON format:
{{
    "goal_assessments": [
        {{
            "goal_title": "string",
            "final_score": 0.0-1.0,
            "completion_status": "completed|partially_completed|not_addressed",
            "evidence_summary": {{
                "strong_evidence": ["evidence1", "evidence2"],
                "weak_evidence": ["evidence1"],
                "missing_elements": ["element1", "element2"]
            }},
            "key_quotes": ["quote1", "quote2"],
            "recommendations": ["improvement1", "improvement2"]
        }}
    ],
    "dimension_scores": {{
        "communication_skills": {{"score": 0-100, "notes": "..."}},
        "confidence_presentation": {{"score": 0-100, "notes": "..."}},
        "technical_competency": {{"score": 0-100, "notes": "..."}},
        "problem_solving": {{"score": 0-100, "notes": "..."}},
        "relevant_experience": {{"score": 0-100, "notes": "..."}},
        "skills_match": {{"score": 0-100, "notes": "..."}},
        "cultural_fit": {{"score": 0-100, "notes": "..."}},
        "leadership_ownership": {{"score": 0-100, "notes": "..."}},
        "learning_agility": {{"score": 0-100, "notes": "..."}},
        "emotional_intelligence": {{"score": 0-100, "notes": "..."}},
        "motivation_alignment": {{"score": 0-100, "notes": "..."}},
        "behavioral_assessment": {{"score": 0-100, "notes": "..."}},
        "resume_consistency": {{"score": 0-100, "notes": "..."}},
        "overall_performance": {{"score": 0-100, "notes": "..."}}
    }},
    "overall_assessment": {{
        "interview_effectiveness": 0.0-1.0,
        "goal_coverage_rate": 0.0-1.0,
        "candidate_performance": 0.0-1.0,
        "strengths": ["strength1", "strength2"],
        "areas_for_improvement": ["area1", "area2"],
        "overall_candidate_score": 0-100,
        "job_match_percentage": 0-100,
        "hiring_recommendation": "Hire|Consider|Reject"
    }},
    "final_ai_recommendation": {{
        "overall_candidate_score": 0-100,
        "job_match_percentage": 0-100,
        "decision": "Hire|Consider|Reject",
        "decision_rationale": "One concise paragraph explaining the recommendation",
        "key_strengths": ["strength1", "strength2", "strength3"],
        "development_areas": ["area1", "area2"]
    }},
    "next_steps": ["action1", "action2"]
}}

Scoring guide for hiring_recommendation / decision:
- Hire: strong candidate, clear fit, recommend for next stage (overall_candidate_score >= 70)
- Consider: mixed signals, conditional recommendation, needs further evaluation (40-69)
- Reject: significant gaps or misalignment (< 40)

Be thorough and evidence-based. Cite specific quotes from the transcript when scoring dimensions."""

    # ===================================
    # UTILITY METHODS
    # ===================================

    async def get_session_goals(self, session_id: str) -> List[Dict[str, Any]]:
        """Get current session goals with caching"""
        if session_id in self._session_goals_cache:
            return self._session_goals_cache[session_id]

        goals = await db_manager.get_session_goals(session_id)
        self._session_goals_cache[session_id] = goals
        return goals

    async def _refresh_goals_cache(self, session_id: str) -> None:
        """Refresh goals cache for session"""
        goals = await db_manager.get_session_goals(session_id)
        self._session_goals_cache[session_id] = goals

    async def get_goal_progress_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of goal progress for session"""
        session_goals = await self.get_session_goals(session_id)

        if not session_goals:
            return {"total_goals": 0, "progress": 0.0}

        total = len(session_goals)
        completed = len([g for g in session_goals if g["completion_status"] == "completed"])
        in_progress = len([g for g in session_goals if g["completion_status"] == "in_progress"])
        avg_progress = sum(g["progress_score"] for g in session_goals) / total if total > 0 else 0.0

        return {
            "total_goals": total,
            "completed_goals": completed,
            "in_progress_goals": in_progress,
            "not_started_goals": total - completed - in_progress,
            "average_progress": avg_progress,
            "completion_rate": completed / total if total > 0 else 0.0,
            "goals": [
                {
                    "title": g["title"],
                    "progress": g["progress_score"],
                    "status": g["completion_status"],
                    "category": g["category"]
                }
                for g in session_goals
            ]
        }

    async def _get_session_transcript(self, session_id: str) -> List[Dict[str, Any]]:
        """Get session transcript from database"""
        query = """
        SELECT speaker, text, timestamp, sequence_number
        FROM session_transcripts
        WHERE session_id = $1
        ORDER BY sequence_number ASC
        """
        return await db_manager.fetch_all(query, session_id)

    async def _track_analysis_metrics(self, session_id: str, analysis_type: str, model_name: str):
        """Track goal analysis metrics"""
        metrics_data = {
            "metric_type": "goal_analysis",
            "service_name": "groq",
            "model_name": model_name,
            "token_count": 100,  # Estimate, could be improved
            "cost_usd": 0.001,   # Rough estimate
            "analysis_type": analysis_type
        }

        try:
            await db_manager.add_session_metrics(session_id, metrics_data)
        except Exception as e:
            logger.warning(f"[GoalTracking] Failed to track metrics: {e}")

    async def manual_goal_update(self, session_id: str, goal_title: str,
                                update_data: Dict[str, Any]) -> bool:
        """Manually update goal progress (for dashboard overrides)"""
        try:
            session_goals = await self.get_session_goals(session_id)
            target_goal = next((g for g in session_goals if g["title"] == goal_title), None)

            if not target_goal:
                return False

            progress_data = {
                "progress_score": update_data.get("progress_score", target_goal["progress_score"]),
                "completion_status": update_data.get("completion_status", target_goal["completion_status"]),
                "confidence_level": update_data.get("confidence_level", target_goal["confidence_level"]),
                "event_type": "manual_override",
                "evidence_text": update_data.get("notes", "Manual update"),
                "analysis_model": "manual"
            }

            await db_manager.update_goal_progress(target_goal["id"], progress_data)

            # Invalidate cache
            if session_id in self._session_goals_cache:
                del self._session_goals_cache[session_id]

            logger.info(f"[GoalTracking] Manual update applied to '{goal_title}'")
            return True

        except Exception as e:
            logger.error(f"[GoalTracking] Manual update failed: {e}")
            return False