# Refactoring Plan: Pipecat Bot Service - COMPLETED

This document outlines the technical debt and planned improvements for `pipecat-quickstart/server/runner.py`.

## Technical Debt / Areas for Improvement

- [x] **Encapsulation of Bot State:** Moved global variables (`current_session`, `bot_worker`) into a `BotManager` class to improve testability and prevent race conditions.
- [x] **Safer Pipeline Injection:** Replaced fragile access to processors with explicit references and used `BotManager` to orchestrate initialization.
- [x] **Enhanced Debugging:**
  - Refactored `LLMResponseParser` to log full aggregated JSON.
  - Standardized logging across all pipeline stages with `loguru`.
  - Added a "Live Console" to the web dashboard for real-time visibility.

## Execution Priority
1. [x] Perform baseline test of current bot implementation.
2. [x] Encapsulate bot state and fix injection pattern.
3. [x] Improve debugging visibility (logging).
