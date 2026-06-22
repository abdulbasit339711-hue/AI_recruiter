"""
Live interview video analysis — HYBRID (local detector + cloud VLM).

Samples the candidate's camera (~1 fps), downscales, and runs two independent
loops on the latest frame:

  1. PROCTORING (local, deterministic) — every ``VISION_DETECT_INTERVAL_SECS`` it
     POSTs the frame to the local YOLO11 + supervision ``detector_service`` and
     gets back people_count / phone_visible / integrity flags. Runs in a separate
     process so torch never loads into this RAM-constrained interview process.
     Broadcast as ``vision_proctoring``.

  2. SEMANTIC (cloud VLM) — every ``VISION_ANALYZE_INTERVAL_SECS`` it asks a vision
     model for presence/engagement, a neutral summary, and advisory delivery
     notes. Backend is pluggable via ``VISION_BACKEND`` (groq|gemini). Broadcast
     as ``vision_analysis``.

Both streams are accumulated and written to a ``{session}.vision.json`` sidecar at
finalize. Everything is best-effort and OFF the critical path — any error (model
down, detector unreachable, bad frame) is logged and the interview + recording
continue unaffected.

⚠️ Compliance: these are ADVISORY observations for human review, deliberately NOT
auto-scored into the candidate's result (EEOC disparate impact, NYC Local Law 144,
EU AI Act). Keep a human in the loop.
"""

import asyncio
import base64
import io
import json
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

# Cadences (the frame itself is sampled at ~1 fps; these gate the expensive calls).
VISION_ANALYZE_INTERVAL_SECS: float = float(os.getenv("VISION_ANALYZE_INTERVAL_SECS", "30"))
VISION_DETECT_INTERVAL_SECS: float = float(os.getenv("VISION_DETECT_INTERVAL_SECS", "5"))
VISION_MAX_DIM: int = int(os.getenv("VISION_MAX_DIM", "768"))

# Semantic backend.
VISION_BACKEND: str = os.getenv("VISION_BACKEND", "groq").lower()
GROQ_VISION_MODEL: str = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GEMINI_VISION_MODEL: str = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

# Local proctoring detector service (see detector_service.py).
DETECTOR_URL: str = os.getenv("DETECTOR_URL", "http://127.0.0.1:7861")

_SYSTEM = (
    "You observe a single still frame from a candidate's live video interview. "
    "Report ONLY what is visible in THIS frame. Do NOT infer personality, "
    "competence, or hiring fitness, and do not guess attributes you cannot see. "
    "Respond with STRICT minified JSON and nothing else."
)

_PROMPT = (
    "Return JSON with exactly these keys:\n"
    '{"present": bool,           // a person is visibly on camera\n'
    ' "people_count": int,       // total number of people visible in the frame (0, 1, 2, ...)\n'
    ' "second_person": bool,     // true if ANY additional person is visible besides the candidate\n'
    ' "facing_screen": bool,     // oriented toward the camera/screen\n'
    ' "engagement": int,         // 0-5 visible attentiveness (0 none, 5 full)\n'
    ' "looking_away": bool,      // appears to look off-screen\n'
    ' "posture": str,            // body posture (e.g. upright/leaning/slouched/reclining)\n'
    ' "gestures": str,           // visible hand/arm gestures or "none" if hands not moving/visible\n'
    ' "facial_expression": str,  // neutral/smiling/frowning/concentrating/etc.\n'
    ' "eye_contact": str,        // direct/intermittent/avoidant\n'
    ' "is_avatar": bool,         // true if the person appears to be an AI-generated avatar, deepfake, or '
    'virtual presenter rather than a real human — look for: unnaturally smooth or texture-less skin, '
    'perfectly symmetric features, hair that looks rendered/painted, lighting inconsistent with the '
    'background, uncanny-valley expression, lip movements that do not match natural speech, or the '
    'face sitting inside a digital frame / virtual set instead of a real room\n'
    ' "background_real": bool,   // true if the background looks like a genuine physical space '
    '(room, office, outdoors) rather than a virtual/green-screen background, gradient, or studio asset\n'
    ' "liveness_notes": str,     // one factual sentence on any synthetic/avatar indicators, or "none" if the person appears genuine\n'
    ' "delivery_notes": str,     // brief factual note on how they are presenting (posture, gestures, expression)\n'
    ' "summary": str}            // one neutral factual sentence about the frame'
)


class VisionAnalysisProcessor(FrameProcessor):
    """Hybrid video analysis: local proctoring detector + cloud semantic VLM."""

    def __init__(self, broadcaster, api_key=None, backend=None):
        super().__init__()
        self._broadcaster = broadcaster
        self._session = None
        self._backend = (backend or VISION_BACKEND)
        self._groq_key = api_key or os.getenv("GROQ_API_KEY")
        self._gemini_key = os.getenv("GEMINI_API_KEY")
        self._groq_model = GROQ_VISION_MODEL
        self._gemini_model = GEMINI_VISION_MODEL

        self._groq_client = None
        self._http = None  # shared httpx client for detector + gemini

        self._latest_jpeg = None  # bytes
        self._last_kept_t = None
        self._start_t = None
        self._tasks = []
        self._stopped = False

        self.observations: list[dict] = []   # semantic VLM stream
        self.detections: list[dict] = []      # proctoring stream
        self.on_violation = None              # async callable(flags: list[str]) — set by BotManager

    def set_session(self, session):
        self._session = session

    # ------------------------------------------------------------------ frames
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, ImageRawFrame):
            try:
                self._capture(frame)
            except Exception as e:
                logger.warning(f"[VisionAnalysis] capture failed: {e}")
            if not self._tasks and not self._stopped:
                self._tasks = [
                    asyncio.create_task(self._vlm_loop()),
                    asyncio.create_task(self._detect_loop()),
                ]
        elif isinstance(frame, (EndFrame, CancelFrame)):
            await self.stop()

        await self.push_frame(frame, direction)

    def _capture(self, frame: ImageRawFrame) -> None:
        """Keep the latest frame as a downscaled JPEG (throttled to ~1 fps)."""
        now = time.monotonic()
        if self._start_t is None:
            self._start_t = now
        if self._last_kept_t is not None and (now - self._last_kept_t) < 1.0:
            return
        from PIL import Image

        w, h = frame.size
        mode = "RGBA" if (frame.format or "RGB").upper() == "RGBA" else "RGB"
        img = Image.frombytes(mode, (w, h), frame.image)
        if mode == "RGBA":
            img = img.convert("RGB")
        img.thumbnail((VISION_MAX_DIM, VISION_MAX_DIM))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        self._latest_jpeg = buf.getvalue()
        self._last_kept_t = now

    def _elapsed(self) -> float:
        return round(time.monotonic() - (self._start_t or time.monotonic()), 1)

    def _client(self):
        if self._http is None:
            import httpx
            self._http = httpx.AsyncClient(timeout=60)
        return self._http

    # ----------------------------------------------------------- proctoring loop
    async def _detect_loop(self) -> None:
        logger.info(f"[VisionAnalysis] proctoring detector loop every {VISION_DETECT_INTERVAL_SECS}s -> {DETECTOR_URL}")
        warned = False
        while not self._stopped:
            try:
                await asyncio.sleep(VISION_DETECT_INTERVAL_SECS)
                if self._stopped or not self._latest_jpeg:
                    continue
                r = await self._client().post(
                    f"{DETECTOR_URL}/detect", content=self._latest_jpeg,
                    headers={"content-type": "image/jpeg"},
                )
                r.raise_for_status()
                d = r.json()
                d["t"] = self._elapsed()
                self.detections.append(d)
                flags = d.get("integrity_flags") or []
                if flags:
                    logger.info(f"[VisionAnalysis] proctoring t={d['t']}s flags={flags} objects={d.get('objects')}")
                    if self.on_violation:
                        try:
                            await self.on_violation(flags)
                        except Exception as cb_err:
                            logger.warning(f"[VisionAnalysis] on_violation callback error: {cb_err}")
                await self._broadcaster.broadcast("vision_proctoring", {
                    "session_id": self._session.session_id if self._session else None,
                    **d,
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not warned:
                    logger.warning(f"[VisionAnalysis] detector unreachable ({DETECTOR_URL}): {e}; proctoring disabled this run")
                    warned = True

    # --------------------------------------------------------------- semantic loop
    async def _vlm_loop(self) -> None:
        if self._backend == "gemini" and not self._gemini_key:
            logger.warning("[VisionAnalysis] VISION_BACKEND=gemini but no GEMINI_API_KEY; falling back to groq")
            self._backend = "groq"
        if self._backend == "groq" and not self._groq_key:
            logger.warning("[VisionAnalysis] no GROQ_API_KEY; semantic analysis disabled")
            return
        logger.info(f"[VisionAnalysis] semantic loop every {VISION_ANALYZE_INTERVAL_SECS}s (backend={self._backend})")
        while not self._stopped:
            try:
                await asyncio.sleep(VISION_ANALYZE_INTERVAL_SECS)
                if self._stopped or not self._latest_jpeg:
                    continue
                b64 = base64.b64encode(self._latest_jpeg).decode()
                raw = await (self._gemini_json(b64) if self._backend == "gemini" else self._groq_json(b64))
                obs = self._parse(raw)
                if obs is None:
                    logger.warning(f"[VisionAnalysis] unparseable VLM output: {str(raw)[:160]}")
                    continue
                obs["t"] = self._elapsed()
                obs["backend"] = self._backend
                self.observations.append(obs)
                is_avatar = obs.get("is_avatar")
                logger.info(
                    f"[VisionAnalysis] semantic t={obs['t']}s present={obs.get('present')} "
                    f"people={obs.get('people_count')} engagement={obs.get('engagement')} "
                    f"avatar={is_avatar} bg_real={obs.get('background_real')}"
                )
                # Fire violations: absent candidate, second person, avatar/deepfake
                violation_flags = []
                if obs.get("present") is False:
                    violation_flags.append("candidate_absent")
                    logger.warning(f"[VisionAnalysis] candidate absent at t={obs['t']}s")
                if obs.get("second_person"):
                    violation_flags.append("multiple_people")
                if is_avatar:
                    violation_flags.append("avatar_detected")
                    logger.warning(
                        f"[VisionAnalysis] avatar/deepfake detected at t={obs['t']}s — "
                        f"liveness_notes: {obs.get('liveness_notes', 'n/a')}"
                    )
                if violation_flags and self.on_violation:
                    try:
                        await self.on_violation(violation_flags)
                    except Exception as cb_err:
                        logger.warning(f"[VisionAnalysis] on_violation (semantic) error: {cb_err}")
                await self._broadcaster.broadcast("vision_analysis", {
                    "session_id": self._session.session_id if self._session else None,
                    **obs,
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[VisionAnalysis] semantic tick failed: {e}")

    async def _groq_json(self, b64: str) -> str:
        if self._groq_client is None:
            from groq import AsyncGroq
            self._groq_client = AsyncGroq(api_key=self._groq_key)
        resp = await self._groq_client.chat.completions.create(
            model=self._groq_model, max_tokens=320, temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]},
            ],
        )
        return resp.choices[0].message.content or ""

    async def _gemini_json(self, b64: str) -> str:
        # Higher token cap: Gemini 2.5 spends "thinking" tokens that can otherwise
        # truncate the JSON body.
        body = {
            "system_instruction": {"parts": [{"text": _SYSTEM}]},
            "contents": [{"parts": [
                {"text": _PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 800},
        }
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self._gemini_model}:generateContent?key={self._gemini_key}")
        r = await self._client().post(url, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    def _parse(raw: str):
        raw = (raw or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.strip("`")
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:]
        try:
            return json.loads(raw)
        except Exception:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start:end + 1])
                except Exception:
                    return None
            return None

    # ------------------------------------------------------------------- output
    def aggregate(self) -> dict:
        agg = {"frames_analyzed": len(self.observations), "frames_detected": len(self.detections)}
        if self.observations:
            eng = [o["engagement"] for o in self.observations if isinstance(o.get("engagement"), (int, float))]
            agg["avg_engagement"] = round(sum(eng) / len(eng), 2) if eng else None
            agg["present_ratio"] = round(sum(1 for o in self.observations if o.get("present")) / len(self.observations), 2)
            agg["second_person_detected"] = any(o.get("second_person") for o in self.observations)
            agg["avatar_detected"] = any(o.get("is_avatar") for o in self.observations)
            bg_vals = [o["background_real"] for o in self.observations if isinstance(o.get("background_real"), bool)]
            agg["background_always_real"] = all(bg_vals) if bg_vals else True
            pc = [o["people_count"] for o in self.observations if isinstance(o.get("people_count"), int)]
            agg["max_people_count_semantic"] = max(pc) if pc else 0
        if self.detections:
            flags = [f for d in self.detections for f in (d.get("integrity_flags") or [])]
            agg["max_people_count"] = max((d.get("people_count") or 0) for d in self.detections)
            agg["phone_seen"] = any(d.get("phone_visible") for d in self.detections)
            agg["candidate_absent_ticks"] = sum(1 for d in self.detections if "candidate_absent" in (d.get("integrity_flags") or []))
            agg["integrity_flags"] = sorted(set(flags))
        return agg

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
        logger.info(f"[VisionAnalysis] stopped (semantic={len(self.observations)}, proctoring={len(self.detections)})")
