# 🎙️ Pipecat Interview Bot: Sub-Project Onboarding

This subdirectory contains the **Pipecat** implementation for the AI-Recruiter system, focused on real-time voice interviews.

---

## 🏗️ Architecture & State Machine

The Pipecat bot is designed as a modular pipeline built on top of the Pipecat framework. It uses a **Single Source of Truth (SSOT)** pattern for session state.

### 1. Core Components (The "Engine")
- **`InterviewSession` (`interview_session.py`)**: The central state container.
  - **RecruiterConfig**: Immutable setup (job, company, questions, goals).
  - **Live State**: Mutable tracking of current question, status (Active/Paused/Comp), and connection events.
  - **Transcript**: Append-only log of every turn.
- **`QuestionFlowProcessor` (`question_flow_processor.py`)**: The "Brain" of the interview.
  - Handles the sequence of questions.
  - Evaluates answer quality (word count, filler ratio, theme signals).
  - Triggers follow-up questions if budget allows.
- **`TranscriptAccumulator` (`transcript_accumulator.py`)**: A silent observer.
  - Records candidate and agent turns without interfering with the pipeline flow.

### 2. The Pipeline Flow
```
[Transport Input] -> [STT] -> [TranscriptAccumulator] -> [UserAggregator] -> [QuestionFlowProcessor] -> [LLM] -> [TTS] -> [Transport Output]
```

---

## 🛠️ Implementation Details

### Answer Quality Gates
The `QuestionFlowProcessor` uses three primary heuristics to determine if an answer is "sufficient":
1. **Depth**: Minimum word counts based on `AnswerDepth` (Short/Medium/Long).
2. **Filler Ratio**: Rejects answers with >35% filler words (um, uh, like).
3. **Theme Signal**: Checks if keywords from the `expected_theme` are present in the response.

### Instruction Injection
Instead of letting the LLM decide what to ask next, the `QuestionFlowProcessor` injects specific **Developer Instructions** into the context. This ensures the bot follows the interview script exactly while maintaining a natural conversational tone.

---

## 🚦 Operational Workflows

### Running Locally
1. **Navigate to server**: `cd pipecat-quickstart/server`
2. **Install**: `uv sync`
3. **Run**: 
   - SmallWebRTC: `uv run bot.py`
   - LiveKit: `uv run bot.py --transport livekit` (requires `.env` setup)

### Testing
- **Unit Tests**: Run `pytest` in the `server/` directory.
  - `test_interview_session.py`: Validates state transitions.
  - `test_question_flow.py`: Validates interview logic and follow-up triggers.

---

## 📝 Coding Conventions
- **Explicit State**: Never modify `InterviewSession` outside of `QuestionFlowProcessor` write-helpers.
- **Frame Safety**: Custom processors must always `push_frame` to ensure the pipeline doesn't stall.
- **Logging**: Use `loguru` with clear prefixes like `[flow]` or `[transcript]`.

---

> [!TIP]
> This sub-project is part of the larger **AI-Recruiter** workspace. For general system architecture and database schemas, see the [root GEMINI.md](../GEMINI.md).
