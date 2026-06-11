"""
Adaptive Questioning Processor - Generates follow-up questions based on goal progress
"""

import json
from typing import Dict, List, Optional, Any
from loguru import logger
from groq import AsyncGroq

from services.goal_tracking_service import GoalTrackingService


class AdaptiveQuestioningProcessor:
    """
    Generates adaptive follow-up questions based on goal progress
    Uses llama-3.3-70b-versatile for strategic questioning decisions
    """

    def __init__(self, goal_service: GoalTrackingService, groq_api_key: str):
        self.goal_service = goal_service
        self.groq_client = AsyncGroq(api_key=groq_api_key)
        self.primary_model = "llama-3.3-70b-versatile"  # Strategic questioning

    async def generate_follow_up_question(self, session_id: str, target_goal_title: str = None) -> Optional[str]:
        """
        Generate a natural follow-up question based on goal progress

        Args:
            session_id: The interview session ID
            target_goal_title: Specific goal to target (optional)

        Returns:
            Natural follow-up question or None if no follow-up needed
        """
        try:
            # Get session goals and progress
            session_goals = await self.goal_service.get_session_goals(session_id)
            if not session_goals:
                return None

            # Determine target goal
            target_goal = None
            if target_goal_title:
                target_goal = next((g for g in session_goals if g["title"] == target_goal_title), None)
            else:
                # Find most important underperforming goal
                target_goal = self._select_priority_goal(session_goals)

            if not target_goal:
                return None

            # Get conversation context
            conversation_context = await self._get_conversation_context(session_id)

            # Generate adaptive question
            question = await self._generate_question_for_goal(target_goal, conversation_context, session_goals)

            if question:
                logger.info(f"[AdaptiveQuestioning] Generated question for '{target_goal['title']}': {question[:50]}...")

            return question

        except Exception as e:
            logger.error(f"[AdaptiveQuestioning] Failed to generate question: {e}")
            return None

    def _select_priority_goal(self, session_goals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the highest priority goal that needs attention"""
        # Filter goals that need attention
        underperforming = [
            goal for goal in session_goals
            if (goal["progress_score"] < 0.6 and
                goal["completion_status"] in ["not_started", "in_progress"])
        ]

        if not underperforming:
            return None

        # Sort by priority weight (higher = more important)
        underperforming.sort(key=lambda g: g.get("priority_weight", 0.5), reverse=True)

        return underperforming[0]

    async def _get_conversation_context(self, session_id: str) -> Dict[str, Any]:
        """Get recent conversation context for question generation"""
        try:
            # Get recent transcript entries
            from database import db_manager
            query = """
            SELECT speaker, text, timestamp
            FROM session_transcripts
            WHERE session_id = $1
            ORDER BY sequence_number DESC
            LIMIT 10
            """
            recent_transcript = await db_manager.fetch_all(query, session_id)

            # Build context
            context = {
                "recent_exchanges": [],
                "candidate_topics": set(),
                "interview_flow": "ongoing"
            }

            # Analyze recent exchanges
            for i in range(0, len(recent_transcript) - 1, 2):
                if i + 1 < len(recent_transcript):
                    question = recent_transcript[i] if recent_transcript[i]["speaker"] == "agent" else None
                    response = recent_transcript[i + 1] if recent_transcript[i + 1]["speaker"] == "candidate" else recent_transcript[i]

                    if question and response:
                        context["recent_exchanges"].append({
                            "question": question["text"],
                            "response": response["text"]
                        })

            # Extract topics mentioned by candidate
            for entry in recent_transcript:
                if entry["speaker"] == "candidate":
                    # Simple keyword extraction (could be enhanced)
                    words = entry["text"].lower().split()
                    tech_keywords = ["python", "javascript", "react", "node", "database", "api", "microservices",
                                   "docker", "kubernetes", "aws", "testing", "agile", "git", "sql", "mongodb"]
                    for keyword in tech_keywords:
                        if keyword in words:
                            context["candidate_topics"].add(keyword)

            context["candidate_topics"] = list(context["candidate_topics"])
            return context

        except Exception as e:
            logger.error(f"[AdaptiveQuestioning] Failed to get context: {e}")
            return {"recent_exchanges": [], "candidate_topics": [], "interview_flow": "ongoing"}

    async def _generate_question_for_goal(self, target_goal: Dict[str, Any],
                                         context: Dict[str, Any],
                                         all_goals: List[Dict[str, Any]]) -> Optional[str]:
        """Generate a specific question for the target goal"""
        try:
            # Build question generation prompt
            prompt = self._build_question_prompt(target_goal, context, all_goals)

            # Generate with primary model for strategic depth
            response = await self.groq_client.chat.completions.create(
                model=self.primary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Slightly higher for creativity
                max_tokens=200
            )

            result = response.choices[0].message.content.strip()

            # Extract question if response contains JSON
            try:
                parsed = json.loads(result)
                return parsed.get("question", result)
            except json.JSONDecodeError:
                # Return raw response if not JSON
                return result if result and len(result) > 10 else None

        except Exception as e:
            logger.error(f"[AdaptiveQuestioning] Question generation failed: {e}")
            return None

    def _build_question_prompt(self, target_goal: Dict[str, Any],
                              context: Dict[str, Any],
                              all_goals: List[Dict[str, Any]]) -> str:
        """Build the prompt for question generation"""
        # Format recent exchanges
        recent_exchanges = ""
        for i, exchange in enumerate(context.get("recent_exchanges", [])[:3]):
            recent_exchanges += f"""
Exchange {i+1}:
Interviewer: {exchange['question']}
Candidate: {exchange['response']}
"""

        # Format goal context
        goal_context = f"""
Target Goal: {target_goal['title']}
Category: {target_goal['category']}
Description: {target_goal['description']}
Current Progress: {target_goal['progress_score']:.1%}
Success Criteria: {target_goal.get('success_criteria', [])}
"""

        # Format other goals for context
        other_goals = [g for g in all_goals if g['title'] != target_goal['title']]
        goals_status = []
        for goal in other_goals[:3]:  # Top 3 other goals
            goals_status.append(f"- {goal['title']}: {goal['progress_score']:.1%} ({goal['completion_status']})")

        other_goals_text = "\n".join(goals_status) if goals_status else "None"

        return f"""You are an expert interviewer generating a natural follow-up question to assess a specific goal.

GOAL TO ASSESS:
{goal_context}

RECENT CONVERSATION:
{recent_exchanges}

OTHER GOALS STATUS:
{other_goals_text}

CANDIDATE TOPICS MENTIONED: {', '.join(context.get('candidate_topics', []))}

Generate a natural, conversational follow-up question that:
1. Builds on the recent conversation flow
2. Specifically assesses the target goal
3. Feels natural and not robotic
4. Encourages specific examples or deeper explanation
5. Is appropriate for the goal's current progress level

Guidelines:
- If progress is low (< 30%), ask foundational questions
- If progress is moderate (30-60%), ask for specifics or examples
- If progress is high (60%+), ask for advanced insights or edge cases

Return ONLY the question text, no JSON or explanation:"""

    async def suggest_interview_direction(self, session_id: str) -> Dict[str, Any]:
        """Suggest overall interview direction based on goal progress"""
        try:
            progress_summary = await self.goal_service.get_goal_progress_summary(session_id)
            session_goals = await self.goal_service.get_session_goals(session_id)

            # Analyze progress patterns
            low_progress_goals = [g for g in progress_summary.get("goals", []) if g["progress"] < 0.4]
            completed_goals = [g for g in progress_summary.get("goals", []) if g["status"] == "completed"]

            completion_rate = progress_summary.get("completion_rate", 0)

            suggestion = {
                "direction": "continue",
                "focus": "general",
                "reasoning": "Interview progressing normally",
                "recommended_time": 5  # minutes
            }

            # Determine direction based on progress
            if completion_rate > 0.8:
                suggestion.update({
                    "direction": "wrap_up",
                    "focus": "final_questions",
                    "reasoning": f"Strong progress on {len(completed_goals)} goals. Ready to conclude.",
                    "recommended_time": 3
                })
            elif completion_rate < 0.3 and len(low_progress_goals) > 3:
                suggestion.update({
                    "direction": "redirect",
                    "focus": "priority_goals",
                    "reasoning": f"Low progress on {len(low_progress_goals)} goals. Need to focus.",
                    "recommended_time": 10,
                    "priority_goals": [g["title"] for g in low_progress_goals[:2]]
                })
            elif len(low_progress_goals) > 0:
                suggestion.update({
                    "direction": "deepen",
                    "focus": "specific_goals",
                    "reasoning": f"Need more depth on {len(low_progress_goals)} goals.",
                    "recommended_time": 7,
                    "target_goals": [g["title"] for g in low_progress_goals[:1]]
                })

            return suggestion

        except Exception as e:
            logger.error(f"[AdaptiveQuestioning] Failed to suggest direction: {e}")
            return {
                "direction": "continue",
                "focus": "general",
                "reasoning": "Error in analysis, continuing normally"
            }

    async def generate_goal_specific_questions(self, role_type: str, goal_category: str,
                                             count: int = 3) -> List[str]:
        """Generate a set of questions for a specific goal category"""
        try:
            prompt = f"""Generate {count} interview questions for assessing '{goal_category}' skills in a {role_type} role.

Requirements:
- Questions should be specific and actionable
- Mix of behavioral and technical questions
- Encourage specific examples
- Progressive difficulty levels

Return as JSON array of questions:
["question1", "question2", "question3"]"""

            response = await self.groq_client.chat.completions.create(
                model=self.primary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=400
            )

            questions = json.loads(response.choices[0].message.content)
            return questions if isinstance(questions, list) else []

        except Exception as e:
            logger.error(f"[AdaptiveQuestioning] Failed to generate questions: {e}")
            return []