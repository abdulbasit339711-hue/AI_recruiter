# Debugging Log: Pipecat Pipeline Initialization

This log documents troubleshooting attempts for the "StartFrame not received yet" error and LLM JSON issues.

## 6. Resolution: Mandatory `super()` and `BotConnectedFrame`
- **Solution:** Every custom processor MUST call `await super().process_frame(frame, direction)`. This allows Pipecat's base class to register the `StartFrame` and mark the processor as initialized.
- **Trigger Change:** Moved the interview "Opening" trigger from a manual timer to a `BotConnectedFrame` handler in `QuestionFlowProcessor`. This ensures the AI only starts speaking once the transport is 100% ready.

## 7. Fixing JSON Speech (Streaming Aggregation)
- **Problem:** Bot was reading raw JSON fragments aloud (e.g., `{"response":`).
- **Solution:** Implemented token buffering in `LLMResponseParser`. The parser now collects all `TextFrame` tokens from the LLM and only processes/broadcasts/speaks when it receives an `LLMFullResponseEndFrame`.
- **Regex Guard:** Added a Regex-based extraction to `LLMResponseParser` to find the JSON block `{...}` even if the LLM adds conversational prefix/suffix text.

## 8. Dashboard State Sync
- **Problem:** Dashboard missed messages if it connected late.
- **Solution:** Added a state recovery mechanism. The dashboard now polls `/session` and `/health` on load to reconstruct the transcript and service status from the server's memory.
