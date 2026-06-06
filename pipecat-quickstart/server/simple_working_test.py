#!/usr/bin/env python3
"""
Simple test to verify the working configuration loads
"""

def test_imports():
    """Test if our working modules can be imported"""

    print("Testing working processors...")
    try:
        exec("""
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor

class TestProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

print('✓ Processor pattern works')
""")
    except Exception as e:
        print(f"✗ Processor error: {e}")
        return False

    print("Testing basic pipeline...")
    try:
        exec("""
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams

class MockTransport:
    def input(self): return self
    def output(self): return self
    def push_frame(self, frame): pass

# Test pipeline creation
pipeline = Pipeline([MockTransport()])
print('✓ Pipeline creation works')
""")
    except Exception as e:
        print(f"✗ Pipeline error: {e}")
        return False

    return True

if __name__ == "__main__":
    print("=" * 50)
    print("TESTING WORKING CONFIGURATION")
    print("=" * 50)

    success = test_imports()

    if success:
        print("\n✅ All tests passed!")
        print("The working configuration should function properly.")
    else:
        print("\n❌ Some tests failed.")

    print("=" * 50)