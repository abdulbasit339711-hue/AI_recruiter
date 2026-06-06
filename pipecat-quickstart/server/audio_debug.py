"""
Audio Pipeline Debugger
Helps diagnose audio flow issues in the Pipecat pipeline
"""

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameProcessor


class AudioDebugger(FrameProcessor):
    """
    Monitors audio frames flowing through the pipeline
    """

    def __init__(self, name: str = "AudioDebug"):
        super().__init__()
        self.name = name
        self.audio_frame_count = 0
        self.text_frame_count = 0
        self.tts_active = False

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Track audio frames
        if isinstance(frame, AudioRawFrame):
            self.audio_frame_count += 1
            if self.audio_frame_count % 100 == 0:  # Log every 100th audio frame
                logger.debug(f"[{self.name}] Audio frames received: {self.audio_frame_count}")

        # Track TTS events
        elif isinstance(frame, TTSStartedFrame):
            self.tts_active = True
            logger.info(f"[{self.name}] 🔊 TTS Started - Audio should be playing")

        elif isinstance(frame, TTSStoppedFrame):
            self.tts_active = False
            logger.info(f"[{self.name}] 🔇 TTS Stopped")

        # Track user speech
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info(f"[{self.name}] 🎤 User started speaking")

        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info(f"[{self.name}] 🤐 User stopped speaking")

        # Track text going to TTS
        elif isinstance(frame, TextFrame):
            self.text_frame_count += 1
            logger.info(f"[{self.name}] 📝 Text to TTS #{self.text_frame_count}: {frame.text[:50]}...")

        # Track STT transcriptions
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"[{self.name}] 👂 STT Transcription: {frame.text}")

        # Always pass the frame through
        await self.push_frame(frame, direction)


class AudioPipelineValidator:
    """
    Validates audio pipeline configuration
    """

    @staticmethod
    def validate_transport(transport):
        """Check if transport is configured for audio"""
        params = getattr(transport, 'params', None)
        if params:
            audio_in = getattr(params, 'audio_in_enabled', False)
            audio_out = getattr(params, 'audio_out_enabled', False)

            logger.info(f"[AudioValidator] Transport audio config:")
            logger.info(f"  - Audio IN (mic): {'✓ Enabled' if audio_in else '✗ Disabled'}")
            logger.info(f"  - Audio OUT (speaker): {'✓ Enabled' if audio_out else '✗ Disabled'}")

            return audio_in and audio_out
        else:
            logger.warning("[AudioValidator] No transport params found!")
            return False

    @staticmethod
    def validate_services(stt, tts, llm):
        """Check if audio services are properly configured"""
        results = {}

        # Check STT
        if stt:
            api_key = getattr(stt, '_api_key', None)
            results['stt'] = bool(api_key)
            logger.info(f"[AudioValidator] STT (Deepgram): {'✓ Configured' if results['stt'] else '✗ Missing API key'}")
        else:
            results['stt'] = False
            logger.error("[AudioValidator] STT service not initialized!")

        # Check TTS
        if tts:
            api_key = getattr(tts, '_api_key', None)
            voice = getattr(tts._settings, 'voice', None) if hasattr(tts, '_settings') else None
            results['tts'] = bool(api_key)
            logger.info(f"[AudioValidator] TTS (Cartesia): {'✓ Configured' if results['tts'] else '✗ Missing API key'}")
            if voice:
                logger.info(f"  - Voice ID: {voice}")
        else:
            results['tts'] = False
            logger.error("[AudioValidator] TTS service not initialized!")

        # Check LLM
        if llm:
            api_key = getattr(llm, '_api_key', None)
            results['llm'] = bool(api_key)
            logger.info(f"[AudioValidator] LLM (Groq): {'✓ Configured' if results['llm'] else '✗ Missing API key'}")
        else:
            results['llm'] = False
            logger.error("[AudioValidator] LLM service not initialized!")

        return all(results.values())


# Enhanced pipeline with audio debugging
def add_audio_debugging(pipeline_processors: list) -> list:
    """
    Add audio debugging to pipeline

    Usage:
        pipeline_processors = add_audio_debugging(pipeline_processors)
    """

    enhanced = []

    for i, processor in enumerate(pipeline_processors):
        # Add debugger before STT
        if "stt" in str(type(processor)).lower() and i == 1:  # STT is usually second
            enhanced.append(AudioDebugger("PreSTT"))

        enhanced.append(processor)

        # Add debugger after TTS
        if "tts" in str(type(processor)).lower():
            enhanced.append(AudioDebugger("PostTTS"))

    return enhanced


# Test audio configuration
def test_audio_setup():
    """
    Run this to test if audio is properly configured
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("Audio Configuration Test")
    print("=" * 60)

    # Check environment variables
    env_vars = {
        "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
        "CARTESIA_API_KEY": os.getenv("CARTESIA_API_KEY"),
        "CARTESIA_VOICE_ID": os.getenv("CARTESIA_VOICE_ID"),
        "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
        "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
        "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
    }

    for key, value in env_vars.items():
        if value:
            print(f"✓ {key}: Set ({len(value)} chars)")
        else:
            print(f"✗ {key}: Not set!")

    print("\n" + "=" * 60)

    # Check if all required vars are set
    required = ["DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
    missing = [k for k in required if not env_vars.get(k)]

    if missing:
        print(f"⚠️  Missing required environment variables: {', '.join(missing)}")
        print("Audio will not work properly without these!")
    else:
        print("✅ All required audio environment variables are set")

    print("=" * 60)


if __name__ == "__main__":
    test_audio_setup()