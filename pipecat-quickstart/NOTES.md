# AI Recruiter - Pipecat Project Notes

## 🚀 Current Project State: Phase 1 Complete

We have successfully built the core voice-interview pipeline using Pipecat. The system is capable of conducting a structured technical interview with real-time quality evaluation.

### ✅ What we built
- **InterviewSession Data Model**: Centralized state management for interview config, live status, and transcripts. Uses `dataclasses` for clean structure.
- **TranscriptAccumulator**: Passive observer that records candidate and agent turns.
- **QuestionFlowProcessor**: The core logic handler.
  - Sequence management (Opening -> Q1 -> Q2 -> ... -> Closing).
  - Quality heuristics: Word count thresholds (Short: 3, Medium: 15, Long: 40).
  - Filler word detection (threshold: 35%).
  - Theme keyword matching.
  - Follow-up logic: Up to 2 follow-ups per question if the answer is "weak".
- **bot.py Integration**: Multi-transport support (Daily, SmallWebRTC, LiveKit).

### 🧪 Validation Status
- **Success**: `test_interview_session.py` and `test_question_flow.py` pass with 100% coverage of core logic.
- **Mocking**: Used a custom mock environment to simulate Pipecat frames and transcription events, ensuring tests are fast and reliable.

### 🚩 Known Issues & Observations
- **Transcript Synchronization**: `TranscriptAccumulator` currently captures agent responses at the end of the response. Streaming capture could be improved for faster UI updates.
- **Heuristic Sensitivity**: The "Theme Signal" check is currently a simple keyword intersection. In Phase 3, we may want to use a small local model for more robust semantic checking.

### 🔜 Next Steps: Phase 2 - Resilience
- **Circuit Breaker**: Implement protection against LLM/STT latency or failure.
- **State Persistence**: Save `InterviewSession` to the SQLite database during the call to allow for reconnection.
- **Reconnection Logic**: Handle "paused" status when a candidate drops and rejoins.
