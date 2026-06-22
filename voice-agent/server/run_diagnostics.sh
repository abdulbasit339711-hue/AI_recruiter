#!/bin/bash
# Diagnostic script to test the Pipecat voice agent

echo "======================================="
echo "Pipecat Voice Agent Diagnostic Script"
echo "======================================="

echo ""
echo "1. Checking Python environment..."
python --version

echo ""
echo "2. Checking required environment variables..."
if [ -f .env ]; then
    echo "✓ .env file found"
    # Check for required keys (without revealing values)
    for key in GROQ_API_KEY DEEPGRAM_API_KEY CARTESIA_API_KEY LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET; do
        if grep -q "^$key=" .env; then
            echo "✓ $key is set"
        else
            echo "✗ $key is missing"
        fi
    done
else
    echo "✗ .env file not found!"
fi

echo ""
echo "3. Checking module imports..."
python -c "
import sys
sys.path.insert(0, '.')
try:
    from events.broadcaster import broadcaster
    print('✓ events.broadcaster imported successfully')
except Exception as e:
    print(f'✗ events.broadcaster import failed: {e}')

try:
    from core.metrics import MetricsTracker
    print('✓ core.metrics imported successfully')
except Exception as e:
    print(f'✗ core.metrics import failed: {e}')

try:
    from llm.json_parser import LLMResponseParser
    print('✓ llm.json_parser imported successfully')
except Exception as e:
    print(f'✗ llm.json_parser import failed: {e}')

try:
    from transcript_accumulator import TranscriptAccumulator
    print('✓ transcript_accumulator imported successfully')
except Exception as e:
    print(f'✗ transcript_accumulator import failed: {e}')
"

echo ""
echo "4. Testing broadcaster functionality..."
python -c "
import asyncio
from events.broadcaster import broadcaster

async def test():
    # Subscribe
    queue = await broadcaster.subscribe()
    print('✓ Subscribed to broadcaster')

    # Broadcast a test event
    await broadcaster.broadcast('test', {'message': 'diagnostic test'})
    print('✓ Broadcast test event')

    # Try to receive
    try:
        message = await asyncio.wait_for(queue.get(), timeout=1.0)
        print('✓ Received event:', message[:50] + '...' if len(message) > 50 else message)
    except asyncio.TimeoutError:
        print('✗ Timeout waiting for event')

asyncio.run(test())
"

echo ""
echo "======================================="
echo "Diagnostic complete!"
echo ""
echo "To run the server with enhanced logging:"
echo "  export DEBUG_MODE=true"
echo "  uv run runner.py"
echo ""
echo "In another terminal, monitor SSE events:"
echo "  python test_sse_connection.py"
echo "======================================="