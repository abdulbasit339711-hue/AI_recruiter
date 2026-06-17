#!/usr/bin/env python
"""Offline YOLO annotation of a recorded interview video.

Draws bounding boxes + labels (person, cell phone, and other notable COCO
objects) over every frame of a recorded interview and writes
``{session_id}.annotated.mp4`` next to the source, re-muxing the original audio.

This is the *post-hoc* proctoring pass: the live interview runs WITHOUT the
YOLO detector (it is too CPU-heavy to run alongside the real-time voice pipeline
on a small box), so annotation happens here, offline, over the saved clip — every
frame, no realtime pressure.

Run with an interpreter that has ultralytics + supervision + cv2 installed
(NOT the voice uv venv). Here that is the conda base python:

    /home/aoi/miniconda3/bin/python scripts/annotate_video.py --session <sid>
"""

import argparse
import os
import subprocess
import sys
import tempfile


def _resolve_input(recordings_dir: str, session: str) -> str:
    """Prefer the muxed {session}.mp4; fall back to the video-only temp."""
    muxed = os.path.join(recordings_dir, f"{session}.mp4")
    if os.path.isfile(muxed):
        return muxed
    video_only = os.path.join(recordings_dir, f"{session}.video.mp4")
    if os.path.isfile(video_only):
        return video_only
    raise FileNotFoundError(f"No source video for session {session} in {recordings_dir}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--recordings-dir", default=os.getenv(
        "RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings"))
    ap.add_argument("--weights", default=os.getenv(
        "DETECTOR_MODEL",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolo11n.pt")))
    ap.add_argument("--conf", type=float, default=float(os.getenv("DETECTOR_CONF", "0.35")))
    args = ap.parse_args()

    import cv2
    import supervision as sv
    from ultralytics import YOLO

    src = _resolve_input(args.recordings_dir, args.session)
    out_final = os.path.join(args.recordings_dir, f"{args.session}.annotated.mp4")

    model = YOLO(args.weights)
    names = model.names

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"ERROR: cannot open {src}", file=sys.stderr)
        return 2
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Write video-only first, then mux the original audio back with ffmpeg.
    tmp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (w, h))

    box = sv.BoxAnnotator(thickness=2)
    labeler = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)
    tracker = sv.ByteTrack()

    frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        res = model(frame, verbose=False, conf=args.conf)[0]
        det = sv.Detections.from_ultralytics(res)
        det = tracker.update_with_detections(det)
        labels = [
            f"{names[int(c)]} {conf:.0%}"
            for c, conf in zip(det.class_id, det.confidence)
        ] if len(det) else []
        annotated = box.annotate(frame.copy(), detections=det)
        annotated = labeler.annotate(annotated, detections=det, labels=labels)
        writer.write(annotated)
        frames += 1

    cap.release()
    writer.release()
    print(f"Annotated {frames} frames -> {tmp_video}")

    # Mux original audio (if the source had any) into the annotated video.
    cmd = [
        "ffmpeg", "-y",
        "-i", tmp_video,
        "-i", src,
        "-map", "0:v:0", "-map", "1:a:0?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart",
        out_final,
    ]
    rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        os.remove(tmp_video)
    except OSError:
        pass
    if rc.returncode != 0:
        print(f"ERROR: ffmpeg mux failed: {rc.stderr.decode(errors='ignore')[-400:]}", file=sys.stderr)
        return 3

    print(f"OK: {out_final} ({os.path.getsize(out_final)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
