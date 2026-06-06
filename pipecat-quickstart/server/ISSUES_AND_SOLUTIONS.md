# Issues and Solutions - AI Recruiter Bot

This document tracks critical issues encountered during development and their solutions.

## Issue #1: Bot Not Responding to Manual Chat Input

**Problem**: Messages sent via `/chat` endpoint were received but bot did not generate responses.

**Symptoms**:
- Chat messages showed "received" status
- No LLM response generated in logs
- Pipeline appeared to receive frames but no processing occurred

**Root Cause**: Incorrect frame injection method
- Using `pipeline.push_frame()` instead of proper transport routing
- Frame not flowing through complete pipeline chain

**Solution**:
```python
# WRONG (bot_manager_dual.py:134)
await self.pipeline.push_frame(frame)

# CORRECT
await self.transport.input().push_frame(frame)
```

**File**: `bot_manager_dual.py:134`

---

## Issue #2: TranscriptionFrame Timestamp Validation Error

**Problem**: Validation error when creating TranscriptionFrame with integer timestamp.

**Error Message**:
```
1 validation error for UserTranscriptionMessageData
timestamp
  Input should be a valid string [type=string_type, input_value=0, input_type=int]
```

**Root Cause**: Pipecat expects timestamp as string, not integer.

**Solution**:
```python
# WRONG
timestamp=0

# CORRECT (bot_manager_dual.py:132)
timestamp=str(time.time())
```

**File**: `bot_manager_dual.py:132`

---

## Issue #3: Duplicate Bot Responses in Transcript

**Problem**: Each word of bot response appeared as separate transcript entry instead of complete response.

**Symptoms**:
- Multiple transcript broadcasts for single response
- Dashboard showing fragmented text
- Poor user experience with repeated text

**Root Cause**: Streaming transcript broadcasts in metrics processor duplicating the final transcript broadcast.

**Solution**: Remove duplicate streaming broadcasts
```python
# REMOVED (working_processors.py:141-156)
# Streaming broadcast that was causing duplicates
# asyncio.create_task(self._broadcaster.broadcast("transcript", {
#     "speaker": "agent",
#     "text": text,
#     "streaming": True
# }))
```

**File**: `working_processors.py:141-156`

---

## Issue #4: Missing/Incorrect Token Metrics

**Problem**: Token usage showing as 0 for all services, particularly STT metrics.

**Symptoms**:
- STT estimated tokens: 0
- LLM tokens not displaying properly
- Cost calculations incorrect

**Root Cause**: Incorrect token estimation formula in STT metrics.

**Solution**: Fix token calculation
```python
# WRONG
self._stt_metrics["estimated_tokens"] += len(text) // 4

# CORRECT (working_processors.py:42,67)
self._stt_metrics["estimated_tokens"] += len(text.split())  # Count words
```

**File**: `working_processors.py:42,67`

---

## Issue #5: LLMMessagesFrame Import Error

**Problem**: Import error for non-existent frame type.

**Error Message**:
```
cannot import name 'LLMMessagesFrame' from 'pipecat.frames.frames'
```

**Root Cause**: Frame type doesn't exist in Pipecat API.

**Solution**: Use correct frame type
```python
# WRONG
from pipecat.frames.frames import LLMMessagesFrame

# CORRECT (runner.py:265)
from pipecat.frames.frames import LLMMessagesUpdateFrame
await bot_manager.pipeline.push_frame(LLMMessagesUpdateFrame(messages=[], run_llm=True))
```

**File**: `runner.py:265-266`

---

## Issue #6: Pipeline Timeout After 5 Minutes

**Problem**: Pipeline stops processing after 5-minute timeout, making testing difficult.

**Symptoms**:
- Bot responses work initially
- After 5 minutes, injected messages don't generate responses
- No error messages, silent failure

**Root Cause**: Default pipeline timeout in Pipecat.

**Temporary Solution**: Restart server for testing
**Long-term Solution**: Configure pipeline timeout settings or implement session refresh

---

## Key Lessons Learned

### Frame Injection Best Practices
1. Always use `transport.input().push_frame()` for manual frame injection
2. Ensure timestamp fields are strings, not integers
3. Use proper frame types that exist in Pipecat API

### Metrics Implementation
1. Use word count for token estimation, not character division
2. Avoid duplicate broadcasts that create UI issues
3. Implement both streaming and final metrics appropriately

### Debugging Tips
1. Check server logs for validation errors
2. Verify frame routing through complete pipeline
3. Test with manual chat injection for quick debugging
4. Monitor token metrics in real-time via dashboard

### Pipeline Architecture
```
Transport Input → STT → TranscriptProcessor → UserAggregator → LLM → MetricsProcessor → TTS → Transport Output
```

Frame injection must enter at `Transport Input` to flow through complete pipeline.

---

## Verification Commands

Test the fixes:
```bash
# Start server
uv run runner.py

# Test chat (in another terminal)
curl -X POST http://127.0.0.1:7860/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, test message"}'

# Check session data
curl -s http://127.0.0.1:7860/session | python -m json.tool
```

## Status: ✅ RESOLVED
- Bot responses working correctly
- Single transcript entries (no duplicates)
- Accurate token metrics for all services
- Proper cost estimation
- Complete conversation flow functional