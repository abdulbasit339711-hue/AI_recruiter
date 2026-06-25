"""
Standalone STT test: generates synthetic speech audio and pipes it through
Silero VAD → Groq Whisper to verify the chain works without LiveKit.

Usage:
    cd voice-agent/server
    uv run python test_stt.py
"""

import asyncio
import os
import struct
import math
from dotenv import load_dotenv

load_dotenv(override=True)


def _sine_wave_pcm(freq=440, duration=2.0, sample_rate=16000, amplitude=0.5) -> bytes:
    """Generate a sine wave as 16-bit PCM — not speech, but produces audio."""
    n_samples = int(sample_rate * duration)
    samples = []
    for i in range(n_samples):
        v = amplitude * math.sin(2 * math.pi * freq * i / sample_rate)
        samples.append(int(v * 32767))
    return struct.pack(f"<{n_samples}h", *samples)


def _load_wav_pcm(path: str) -> tuple[bytes, int]:
    """Load a WAV file and return (pcm_bytes, sample_rate)."""
    import wave
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return frames, sr


async def test_groq_direct():
    """Call Groq Whisper API directly with raw PCM audio wrapped in a WAV container."""
    import io, wave
    from groq import AsyncGroq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY not set")
        return

    client = AsyncGroq(api_key=api_key)

    # Generate 2 seconds of 440 Hz tone as 16-bit PCM at 16 kHz
    pcm = _sine_wave_pcm(freq=440, duration=2.0, sample_rate=16000)

    # Wrap in a WAV container (Groq Whisper expects a file format)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    buf.seek(0)
    buf.name = "test.wav"

    print("Sending 2s of 440 Hz tone to Groq Whisper...")
    try:
        resp = await client.audio.transcriptions.create(
            file=("test.wav", buf, "audio/wav"),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
        print(f"Groq Whisper response (tone): '{resp}'")
        print("✓ Groq API is reachable and responding")
    except Exception as e:
        print(f"✗ Groq API error: {e}")
        return

    # Now test with silence
    pcm_silence = b"\x00" * (16000 * 2 * 2)  # 2s silence
    buf2 = io.BytesIO()
    with wave.open(buf2, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_silence)
    buf2.seek(0)
    buf2.name = "silence.wav"

    print("\nSending 2s of silence...")
    try:
        resp2 = await client.audio.transcriptions.create(
            file=("silence.wav", buf2, "audio/wav"),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
        print(f"Groq Whisper response (silence): '{resp2}'")
    except Exception as e:
        print(f"Groq error on silence: {e}")


async def test_vad_pipeline():
    """Run audio frames through VADProcessor + GroqSTTService using pipecat internals."""
    import struct as _struct
    from pipecat.frames.frames import AudioRawFrame, StartFrame, CancelFrame
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.services.groq.stt import GroqSTTService
    from pipecat.processors.frame_processor import FrameDirection

    api_key = os.environ.get("GROQ_API_KEY")
    sr = 16000
    chunk_ms = 20  # 20 ms chunks

    print("\n--- Testing VADProcessor + GroqSTTService pipeline ---")

    received_frames = []

    # Minimal downstream sink to collect output frames
    from pipecat.processors.frame_processor import FrameProcessor

    class CaptureSink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            received_frames.append(frame)
            await self.push_frame(frame, direction)

    vad = VADProcessor(vad_analyzer=SileroVADAnalyzer(sample_rate=sr))
    stt = GroqSTTService(api_key=api_key)
    sink = CaptureSink()

    vad.link(stt)
    stt.link(sink)

    start_frame = StartFrame()
    await vad.process_frame(start_frame, FrameDirection.DOWNSTREAM)

    # Generate 1.5s of 440 Hz tone — loud enough for Silero VAD to detect
    chunk_samples = sr * chunk_ms // 1000
    n_chunks = int(1500 / chunk_ms)
    print(f"Sending {n_chunks} audio chunks ({chunk_ms}ms each, 440Hz tone)...")
    for i in range(n_chunks):
        pcm = _sine_wave_pcm(
            freq=440,
            duration=chunk_ms / 1000,
            sample_rate=sr,
            amplitude=0.8,
        )
        frame = AudioRawFrame(audio=pcm, sample_rate=sr, num_channels=1)
        await vad.process_frame(frame, FrameDirection.DOWNSTREAM)
        await asyncio.sleep(chunk_ms / 1000)

    # Then 1s of silence to let VAD fire StoppedSpeaking
    print("Sending 1s silence to trigger VAD stop...")
    silence_chunk = b"\x00" * (chunk_samples * 2)
    for _ in range(1000 // chunk_ms):
        frame = AudioRawFrame(audio=silence_chunk, sample_rate=sr, num_channels=1)
        await vad.process_frame(frame, FrameDirection.DOWNSTREAM)
        await asyncio.sleep(chunk_ms / 1000)

    # Wait for STT to process
    print("Waiting for STT response...")
    await asyncio.sleep(4.0)

    from pipecat.frames.frames import TranscriptionFrame
    transcriptions = [f for f in received_frames if isinstance(f, TranscriptionFrame)]
    if transcriptions:
        for t in transcriptions:
            print(f"✓ TRANSCRIPTION: '{t.text}'")
    else:
        frame_types = list({type(f).__name__ for f in received_frames})
        print(f"✗ No TranscriptionFrame received. Frames seen: {frame_types}")


if __name__ == "__main__":
    asyncio.run(test_groq_direct())
    asyncio.run(test_vad_pipeline())
