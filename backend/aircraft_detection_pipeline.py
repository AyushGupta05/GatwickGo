

import json
import time
from pathlib import Path
from typing import Optional

from camera_burst import (
    capture_burst,
    select_sharpest,
    classify_burst,
    classify_burst_consensus,
)
from gemini_classifier import classify_aircraft, classify_aircraft_topk


def process_aircraft_burst(
    num_frames: int = 8,
    frame_delay: float = 0.05,
    topk: bool = False,
    k: int = 3,
    consensus: bool = True,
    top_m: int = 3,
    output_file: Optional[str] = None,
) -> dict:

    print(f"[INFO] Capturing {num_frames} frames with {frame_delay}s delay...")
    frames = capture_burst(num_frames=num_frames, delay=frame_delay)

    if not frames:
        print("[ERROR] No frames captured")
        return {
            "airline": "UNKNOWN",
            "aircraft_family": "UNKNOWN",
            "confidence": 0.0,
            "cues": [],
            "error": "no_frames_captured",
        }

    print(f"[INFO] Captured {len(frames)} frames")

    if consensus:
        print(f"[INFO] Using consensus across top {top_m} sharpest frames...")
        result = classify_burst_consensus(frames, topk=topk, k=k, top_m=top_m)
        print("[INFO] Consensus classification result:")
    else:
        idx, best_frame = select_sharpest(frames)
        print(f"[INFO] Selected sharpest frame: index {idx}")
        print("[INFO] Sending to Gemini for classification...")
        if topk:
            result = classify_aircraft_topk(best_frame, k=k)
            print(f"[INFO] Top-{k} classification result:")
        else:
            result = classify_aircraft(best_frame)
            print("[INFO] Classification result:")

    result["frames_captured"] = len(frames)

    print(json.dumps(result, indent=2))

    if output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))
        print(f"[INFO] Results saved to {output_file}")

    return result


def process_image_file(
    image_path: str,
    topk: bool = False,
    k: int = 3,
) -> dict:

    print(f"[INFO] Reading image from {image_path}...")
    image_bytes = Path(image_path).read_bytes()

    print("[INFO] Sending to Gemini for classification...")
    if topk:
        result = classify_aircraft_topk(image_bytes, k=k)
    else:
        result = classify_aircraft(image_bytes)

    print("[INFO] Classification result:")
    print(json.dumps(result, indent=2))

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        process_image_file(sys.argv[1], topk=(len(sys.argv) > 2 and sys.argv[2] == "topk"))
    else:
        print("[INFO] Starting aircraft detection pipeline...")
        print("[INFO] Make sure the camera is pointing at an aircraft!")
        time.sleep(2)
        process_aircraft_burst(num_frames=8, frame_delay=0.05, topk=False)
        print("[INFO] Pipeline complete.")
