# Debugging Log: Pipecat Pipeline Initialization

This log documents troubleshooting attempts for the "StartFrame not received yet" error.

## 1. FrameLogger Instrumentation
- **Attempt:** Inserted `FrameLogger` instances throughout the pipeline.
- **Why:** To visualize the frame flow and confirm if `StartFrame` was actually propagating.
- **Error/Outcome:** Confirmed that processors received data frames before the `StartFrame` propagated, causing `_check_started` to fail.

## 2. Global State Encapsulation (BotManager)
- **Attempt:** Moved global bot state (`bot_worker`, `current_session`) into a `BotManager` class.
- **Why:** To improve testability and attempt a cleaner, more controlled initialization flow.
- **Error/Outcome:** Did not solve the race condition; still encountered initialization stalls.

## 3. Explicit `StartFrame` Pushing
- **Attempt:** Explicitly called `await self.pipeline.queue_frame(StartFrame())` in `BotManager.start()` before running the worker.
- **Why:** To force pipeline initialization to complete before accepting inputs.
- **Error/Outcome:** Failed due to timing—automatic transport frames (e.g., `BotConnectedFrame`) still arrived before the manual `StartFrame` finished propagating.

## 4. Delaying Transport Connection
- **Attempt:** Separated `LiveKitTransport` setup from `transport.connect()` to defer connection until after `StartFrame` was pushed.
- **Why:** To prevent transport-initiated frames from racing against our manual `StartFrame`.
- **Error/Outcome:** `LiveKitTransport` does not have a `connect()` method (API mismatch), causing runtime crashes.

## 5. Persistent Observation
- **Ongoing Observation:** STT (`Deepgram`) connection errors are creating noise in logs due to lack of audio input, complicating the diagnosis of the underlying race condition.
