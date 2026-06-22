"""
Local interview video recorder.

The candidate publishes their camera to the LiveKit room; with
``video_in_enabled`` set on the transport, those frames are delivered into the
pipeline as ``ImageRawFrame``s (RGB24). This processor taps them and encodes a
real-time-paced MP4 next to the merged audio WAV, so HR can replay the interview
with picture, not just sound.

Design notes:
  * Encoding is incremental (one packet per kept frame) so memory stays flat
    over a 30-minute call instead of buffering every raw frame.
  * Frames are throttled to at most ``VIDEO_RECORD_FPS`` per second; extra frames
    are dropped, and kept frames get sequential constant-frame-rate PTS. Because
    phone cameras run well above the throttle rate, the number of frames kept per
    second ≈ the throttle rate, so CFR playback ≈ true real-time speed (and PyAV
    muxing is far happier with CFR than a fine variable-rate time base).
  * This writes a VIDEO-ONLY MP4. ``BotManager`` muxes it with the audio WAV at
    finalize into the final ``{session}.mp4``.

It is fully best-effort: any encode/IO error is logged and the audio recording
(and the interview itself) continues unaffected. If PyAV is unavailable or every
frame fails, ``video_path`` stays ``None`` and finalize simply keeps the WAV.
"""

import os
import time

from loguru import logger
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    ImageRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# At most this many frames/sec are kept; the rest are dropped before encoding.
# This is also the playback frame rate (constant-frame-rate output).
VIDEO_RECORD_FPS: float = float(os.getenv("VIDEO_RECORD_FPS", "10"))


class VideoRecorderProcessor(FrameProcessor):
    """Encode incoming candidate video frames to a local (video-only) MP4."""

    def __init__(self, output_path_provider):
        super().__init__()
        # Resolved lazily on the first frame: the session_id (and thus the file
        # name) is only known once the candidate has connected.
        self._output_path_provider = output_path_provider
        self._container = None
        self._stream = None
        self._path = None
        self._start_t = None
        self._last_kept_t = None
        self._min_interval = 1.0 / VIDEO_RECORD_FPS if VIDEO_RECORD_FPS > 0 else 0.0
        self._frames_written = 0
        self._closed = False

    @property
    def video_path(self):
        """Path to the written video-only MP4, or None if nothing was captured."""
        return self._path if self._frames_written > 0 else None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, ImageRawFrame):
            try:
                self._handle_image(frame)
            except Exception as e:  # never let a bad frame break the pipeline
                logger.warning(f"[VideoRecorder] frame encode failed: {e}")
        elif isinstance(frame, (EndFrame, CancelFrame)):
            self.close()

        await self.push_frame(frame, direction)

    def _handle_image(self, frame: ImageRawFrame) -> None:
        if self._closed:
            return
        now = time.monotonic()
        if self._start_t is None:
            self._start_t = now
        # Throttle to the target fps.
        if self._last_kept_t is not None and (now - self._last_kept_t) < self._min_interval:
            return

        if self._container is None:
            self._open(frame)
            if self._container is None:
                return

        import av
        import numpy as np

        w, h = frame.size
        fmt = (frame.format or "RGB").upper()
        if fmt in ("RGBA",):
            arr = np.frombuffer(frame.image, dtype=np.uint8).reshape(h, w, 4)
            vframe = av.VideoFrame.from_ndarray(arr, format="rgba")
        else:  # "RGB" / "RGB24" (what the LiveKit transport emits) and fallback
            arr = np.frombuffer(frame.image, dtype=np.uint8).reshape(h, w, 3)
            vframe = av.VideoFrame.from_ndarray(arr, format="rgb24")

        # H.264 wants yuv420p; convert explicitly (PyAV does not auto-convert).
        vframe = vframe.reformat(format="yuv420p")
        # Sequential CFR PTS in the stream's own time base (1/fps); the encoder
        # rejects a fine variable-rate base here ([Errno 22] on mux).
        vframe.pts = self._frames_written

        for packet in self._stream.encode(vframe):
            self._container.mux(packet)

        self._last_kept_t = now
        self._frames_written += 1

    def _open(self, frame: ImageRawFrame) -> None:
        try:
            import av  # noqa: F401
        except Exception as e:
            logger.error(f"[VideoRecorder] PyAV unavailable, video disabled: {e}")
            self._closed = True
            return
        import av

        try:
            self._path = self._output_path_provider()
            if not self._path:
                return  # session not attached yet; try again on the next frame
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            w, h = frame.size
            self._container = av.open(self._path, mode="w")
            rate = int(VIDEO_RECORD_FPS) or 10
            self._stream = self._container.add_stream("h264", rate=rate)
            self._stream.width = w
            self._stream.height = h
            self._stream.pix_fmt = "yuv420p"
            # Real-time-friendly: fast preset, modest quality (review, not archival).
            self._stream.options = {"crf": "28", "preset": "veryfast", "tune": "zerolatency"}
            logger.info(
                f"[VideoRecorder] Recording candidate video → {self._path} "
                f"({w}x{h} @≤{VIDEO_RECORD_FPS}fps)"
            )
        except Exception as e:
            logger.error(f"[VideoRecorder] failed to open container: {e}")
            self._container = None

    def close(self) -> None:
        """Flush the encoder and close the file. Idempotent."""
        if self._closed and self._container is None:
            return
        self._closed = True
        if self._container is None:
            return
        try:
            for packet in self._stream.encode():  # flush remaining frames
                self._container.mux(packet)
        except Exception as e:
            logger.warning(f"[VideoRecorder] flush failed: {e}")
        try:
            self._container.close()
        except Exception as e:
            logger.warning(f"[VideoRecorder] close failed: {e}")
        logger.info(
            f"[VideoRecorder] Closed video file: {self._path} ({self._frames_written} frames)"
        )
        self._container = None
        self._stream = None
