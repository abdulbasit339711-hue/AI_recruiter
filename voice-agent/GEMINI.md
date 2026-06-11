# 🎙️ Pipecat Interview Bot: Sub-Project Onboarding

This subdirectory contains the **Pipecat** implementation for the AI-Recruiter system, focused on real-time voice interviews.

---

## 🏗️ Architecture & State Machine

The Pipecat bot is designed as a modular pipeline built on top of the Pipecat framework. It uses a **Single Source of Truth (SSOT)** pattern for session state.

### 1. Core Components (The "Engine")
- **`BotManager` (`bot_manager.py`)**: The central orchestrator. Encapsulates the pipeline and worker.
- **`InterviewSession` (`interview_session.py`)**: The central state container.
  - **RecruiterConfig**: Immutable setup (job, company, questions, goals).
  - **Live State**: Mutable tracking of current question and connection events.
  - **Transcript**: Append-only log of every turn.
- **`LLMResponseParser` (`llm/json_parser.py`)**: The extractor.
  - Buffers streaming tokens to ensure full sentences.
  - Uses Regex to find JSON blocks and route conversational text to TTS vs evaluation data to the dashboard.

### 2. The Pipeline Flow
```
[Transport Input] -> [STT] -> [UserAggregator] -> [QuestionFlowProcessor] -> [LLM] -> [Parser] -> [TTS] -> [Transport Output] -> [AssistantAggregator]
```

---

## 🛠️ Implementation Details

### Aggregation & JSON Parsing
The AI produces JSON containing both evaluation data and conversational text. To prevent the bot from reading code, the **Parser** buffers all incoming `TextFrame` fragments and only emits the natural `response` field once the full thought is finished.

### State Recovery
The dashboard (`index.html`) is resilient to network drops. Upon loading, it fetches the current `InterviewSession` from the server, allowing the transcript and progress to be reconstructed even if the browser is refreshed mid-interview.

---

## 🚦 Operational Workflows

### Running the Full Stack
1. **Navigate to server**: `cd voice-agent/server`
2. **Install**: `uv sync`
3. **Run**: `uv run runner.py`
4. **Access Dashboard**: `http://127.0.0.1:7860`

---

## 📝 Coding Conventions
- **Lifecycle Safety**: Always call `await super().process_frame()` in custom processors.
- **Event-Driven**: Trigger interactions on `BotConnectedFrame` or transcription events.
- **Natural Voice**: Never push raw LLM tokens directly to TTS; always pass through the Parser buffer.

---

> [!TIP]
> This sub-project is part of the larger **AI-Recruiter** workspace. For general system architecture and database schemas, see the [root GEMINI.md](../GEMINI.md).
