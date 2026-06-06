# OS-Specific Issues and Architectural Conflicts

This document summarizes the technical challenges encountered while developing the AI Recruiter bot on Windows, specifically focusing on the conflicts between FastAPI and the Pipecat/LiveKit real-time pipeline.

## 1. Windows vs. Linux: The "StartFrame" Race Condition

The `StartFrame not received yet` error is a classic timing and I/O race condition that is prevalent on Windows but often hidden on Linux.

- **Event Loop Differences:** Linux uses `SelectorEventLoop` (epoll), which handles task priority more predictably. Windows uses `ProactorEventLoop` (IOCP), which completes I/O operations (like network connections) and then notifies the application.
- **Why it happens on Windows:** The LiveKit transport often completes its connection and begins pushing data frames (like `BotConnectedFrame`) into the pipeline before the internal Python `StartFrame` task has had a chance to propagate through all processors.
- **Result:** Processors receive data before they are "started," causing them to log errors and stall.

## 2. FastAPI and LiveKit Integration Conflicts

Using FastAPI as a control plane for a real-time Pipecat bot introduces several architectural "friction points":

- **Initialization Desync:** FastAPI starts accepting HTTP requests (like `/chat`) almost instantly. However, the bot takes several seconds to join a room and initialize services (STT, LLM, TTS). If a message is injected via `/chat` before the bot is ready, the pipeline fails.
- **Event Loop Starvation:** Real-time audio generates thousands of micro-tasks per second. FastAPI also competes for event loop time. On Windows, the scheduler is less efficient at interleaving these, leading to high latency or "Internal Server Errors" under load.
- **External Injection vs. Closed Transport:** LiveKit normally operates in a "closed loop." The `/chat` endpoint is an external entry point that lacks visibility into the transport's current state (e.g., if it's reconnecting), leading to frame drops.

## 3. General Windows Development Gotchas

- **Multiprocessing (spawn vs. fork):** Windows must use `spawn`, which restarts the interpreter for every new process. Global variables or half-initialized objects are often `None` in worker processes.
- **Strict File Locking:** Windows locks open files. Any attempt to read/write/move a file used by a logger or another component will result in a `PermissionError`.
- **Case-Insensitivity:** Windows ignores filename casing (`Resume.pdf` == `resume.pdf`), while Linux is strict. This can lead to "File Not Found" errors when deploying to production.
- **IPv6 Resolution:** Windows often resolves `localhost` to `::1` (IPv6), while the server may only be listening on `127.0.0.1` (IPv4), causing "Connection Refused" errors.

## 4. Best Practices for This Project

1. **Use a Manager Class:** Encapsulate bot state in a `BotManager` to control the lifecycle.
2. **Implement Readiness Gates:** Use `asyncio.Event` to ensure FastAPI endpoints wait for the bot to be fully initialized before attempting to inject frames.
3. **Prefer Explicit IPs:** Use `127.0.0.1` instead of `localhost` to avoid IPv6 resolution issues on Windows.
4. **WSL2/Docker:** For production-parity development, use WSL2 or Docker to eliminate Windows-specific race conditions.
