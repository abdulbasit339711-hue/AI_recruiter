# test_interview_session.py

from interview_session import (
    InterviewSession, RecruiterConfig, InterviewQuestion,
    InterviewGoal, FollowUpPrompt, AnswerDepth, GoalStatus,
    InterviewStatus
)

def make_test_session() -> InterviewSession:
    config = RecruiterConfig(
        job_role="Backend Engineer",
        company_name="Acme Corp",
        interview_type="technical",
        system_prompt="You are a professional interviewer at Acme Corp.",
        time_limit_seconds=1800,
        max_follow_ups_per_question=2,
        questions=[
            InterviewQuestion(
                id="q1",
                text="Tell me about a challenging technical problem you solved.",
                goal_id="problem_solving",
                expected_depth=AnswerDepth.LONG,
                expected_theme="structured thinking, clear outcome",
                follow_ups=[
                    FollowUpPrompt(
                        text="Can you be more specific about your approach?",
                        trigger_reason="answer too vague"
                    )
                ],
            ),
            InterviewQuestion(
                id="q2",
                text="How do you handle disagreements in a team?",
                goal_id="communication",
                expected_depth=AnswerDepth.MEDIUM,
                expected_theme="empathy, resolution, outcome",
            ),
        ],
        goals=[
            InterviewGoal(
                id="problem_solving",
                label="Problem Solving",
                description="Can reason through complex technical challenges",
                weight=0.6,
            ),
            InterviewGoal(
                id="communication",
                label="Communication",
                description="Communicates clearly and handles conflict well",
                weight=0.4,
            ),
        ],
    )
    return InterviewSession(
        candidate_id="cand_001",
        candidate_name="Sara Ahmed",
        config=config,
    )


def test_initial_state():
    s = make_test_session()
    assert s.status == InterviewStatus.PENDING
    assert s.current_question_index == 0
    assert s.current_question.id == "q1"
    assert len(s.question_states) == 2
    assert not s.is_complete
    print("✓ initial state correct")


def test_start():
    s = make_test_session()
    s.start()
    assert s.status == InterviewStatus.ACTIVE
    assert s.started_at is not None
    assert s.elapsed_seconds >= 0
    print("✓ start works")


def test_question_flow():
    s = make_test_session()
    s.start()

    s.mark_question_asked("q1")
    assert s.question_states["q1"].status == GoalStatus.IN_PROGRESS

    s.mark_question_answered("q1", GoalStatus.COVERED)
    assert s.question_states["q1"].status == GoalStatus.COVERED

    s.advance_question()
    assert s.current_question.id == "q2"
    print("✓ question flow works")


def test_completion():
    s = make_test_session()
    s.start()
    s.mark_question_answered("q1", GoalStatus.COVERED)
    s.mark_question_answered("q2", GoalStatus.WEAK)
    assert s.is_complete
    assert "problem_solving" in s.covered_goals
    print("✓ completion detection works")


def test_transcript():
    s = make_test_session()
    s.start()
    s.add_turn("agent", "Tell me about yourself.", question_id="q1")
    s.add_turn("candidate", "I'm a backend engineer with 5 years experience.")
    assert len(s.transcript) == 2
    assert s.transcript[0].speaker == "agent"
    print("✓ transcript append works")


def test_follow_up_tracking():
    s = make_test_session()
    s.start()
    s.mark_question_asked("q1")
    s.increment_follow_up("q1")
    s.increment_follow_up("q1")
    assert s.question_states["q1"].follow_up_count == 2
    print("✓ follow-up tracking works")


def test_exhausted_questions():
    s = make_test_session()
    s.advance_question()
    s.advance_question()
    assert s.current_question is None  # no crash, returns None
    print("✓ exhausted questions handled safely")


if __name__ == "__main__":
    test_initial_state()
    test_start()
    test_question_flow()
    test_completion()
    test_transcript()
    test_follow_up_tracking()
    test_exhausted_questions()
    print("\n✅ All tests passed — InterviewSession is solid")
