# 🎙️ AI-Recruiter: Voice Agent Sub-Project

A Pipecat-powered AI voice interviewer with a high-fidelity dashboard.

## 🚀 Key Features

- **Real-time Pipeline**: STT (Deepgram) → LLM (Groq) → TTS (Cartesia).
- **Interactive Dashboard**: Modern dark-mode UI with live transcripts, waveforms, and goal tracking.
- **Robust JSON Handling**: Aggregated token buffering ensures the bot never "speaks code."
- **State Persistence**: Memory-safe session management with support for re-joins.

## 🛠️ Setup & Execution

### 1. Install Dependencies
Navigate to the server directory and sync using `uv`:
```bash
cd pipecat-quickstart/server
uv sync
```

### 2. Configure Environment
Create a `.env` file in `pipecat-quickstart/server/` with:
- `GROQ_API_KEY`
- `DEEPGRAM_API_KEY`
- `CARTESIA_API_KEY`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

### 3. Run the Dashboard
The main entry point is `runner.py`, which starts both the FastAPI dashboard and the Bot:
```bash
uv run runner.py
```
Access the dashboard at **`http://127.0.0.1:7860`**.

## 🏗️ Project Structure

```
pipecat-quickstart/
├── server/
│   ├── runner.py        # Main entry point (FastAPI + Bot)
│   ├── bot_manager.py   # Pipeline orchestration
│   ├── index.html       # Single-file dashboard UI
│   ├── llm/
│   │   └── json_parser.py # Robust response extractor
│   └── core/
│       └── metrics.py    # Usage tracking
```

---
Part of the **AI-Recruiter** system. For root documentation, see [../GEMINI.md](../GEMINI.md).
