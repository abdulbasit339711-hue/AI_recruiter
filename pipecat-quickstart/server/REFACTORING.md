# Refactoring Plan: Pipecat Bot Service

This document outlines the technical debt and planned improvements for `pipecat-quickstart/server/runner.py`.

## Technical Debt / Areas for Improvement

- [ ] **Encapsulation of Bot State:** Current global variables (`current_session`, `bot_worker`) should be moved into a `BotManager` class to improve testability and prevent race conditions.
- [ ] **Safer Pipeline Injection:** Replace fragile access to `bot_worker._pipeline._processors[0]` with an explicit reference to the input transport.
- [ ] **Enhanced Debugging:**
  - Refactor `FrameLogger` to log the actual content of `TextFrame`/`TranscriptionFrame` objects rather than just their types.
  - Standardize logging across all pipeline stages.

## Execution Priority
1. [ ] Perform baseline test of current bot implementation.
2. [ ] Encapsulate bot state and fix injection pattern.
3. [ ] Improve debugging visibility (logging).
