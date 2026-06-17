"""
Local proctoring detector service (YOLO11 + Roboflow supervision).

Runs ISOLATED from the voice runner so torch/YOLO weights never load into the
Pipecat process — this box is RAM-constrained (~1.4 GiB free) and importing torch
into the interview process risks an OOM. The VisionAnalysisProcessor POSTs sampled
JPEG frames here and gets back deterministic proctoring signals from a local
YOLO11n pass parsed with supervision:

  * people_count   -> multiple_people / candidate_absent
  * phone_visible  (COCO 'cell phone')
  * other notable COCO objects visible in the frame

Run it with an interpreter that has ultralytics+supervision installed. Here that
is conda base, NOT the voice uv venv:

    /home/aoi/miniconda3/bin/python detector_service.py     # serves :7861

Everything is best-effort on the caller side: if this service is down the
interview and the Groq semantic analysis continue unaffected.
"""

import io
import os
from collections import Counter

import uvicorn
from fastapi import FastAPI, Request

MODEL_NAME = os.getenv("DETECTOR_MODEL", "yolo11n.pt")
CONF = float(os.getenv("DETECTOR_CONF", "0.35"))
PORT = int(os.getenv("DETECTOR_PORT", "7861"))

app = FastAPI(title="interview-proctor-detector")
_model = None
_names = None


def _load():
    global _model, _names
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(MODEL_NAME)
        _names = _model.names
    return _model


@app.on_event("startup")
async def _startup():
    # Warm the model so the first /detect isn't paying the load cost.
    _load()


@app.get("/health")
async def health():
    return {"ok": _model is not None, "model": MODEL_NAME}


@app.post("/detect")
async def detect(request: Request):
    """Accept raw JPEG bytes; return deterministic proctoring signals."""
    import supervision as sv
    from PIL import Image

    raw = await request.body()
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    model = _load()
    res = model(img, verbose=False, conf=CONF)[0]
    det = sv.Detections.from_ultralytics(res)

    counts = Counter(_names[int(c)] for c in det.class_id)
    persons = counts.get("person", 0)
    phones = counts.get("cell phone", 0)

    flags = []
    if persons > 1:
        flags.append("multiple_people")
    if persons == 0:
        flags.append("candidate_absent")
    if phones > 0:
        flags.append("phone_visible")

    return {
        "people_count": persons,
        "phone_visible": phones > 0,
        "integrity_flags": flags,
        "objects": dict(counts),
        "max_confidence": round(float(max(det.confidence)) if len(det) else 0.0, 3),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
