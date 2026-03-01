import io
import time
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image

from config import (
    MIN_CONFIDENCE_AIRLINE,
    MIN_CONFIDENCE_FAMILY,
    MIN_SHARPNESS_SCORE,
)
from gemini_classifier import classify_aircraft, classify_aircraft_topk


def _frame_to_bytes(frame) -> bytes:
    """Convert an OpenCV BGR frame to JPEG bytes."""
    # convert color space for PIL
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG")
    return buf.getvalue()


def capture_burst(num_frames: int = 5, delay: float = 0.1) -> List[bytes]:
    """Capture a short burst of frames from the default camera.

    Args:
        num_frames: how many images to grab in the burst.
        delay: seconds to wait between frames (helps with motion blur).

    Returns:
        list of JPEG-encoded bytes for each frame.
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("unable to open camera")

    frames: List[bytes] = []
    try:
        for _ in range(num_frames):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(_frame_to_bytes(frame))
            time.sleep(delay)
    finally:
        cap.release()
    return frames


def _sharpness(image_bytes: bytes) -> float:
    """Estimate sharpness using variance of Laplacian."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def _normalize_quality(scores: List[float]) -> List[float]:
    """Normalize sharpness scores to 0-1 range (avoid all-zero collapse)."""
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [1.0 for _ in scores]
    return [max(s, 0.0) / max_score for s in scores]


def _best_airline_from_pred(pred: Dict) -> Tuple[str, float]:
    """Extract best airline/confidence regardless of single or topk format."""
    if "airline" in pred:
        try:
            return pred.get("airline", "UNKNOWN") or "UNKNOWN", float(pred.get("confidence", 0.0))
        except Exception:
            return pred.get("airline", "UNKNOWN") or "UNKNOWN", 0.0
    topk = pred.get("topk", [])
    if isinstance(topk, list) and topk:
        first = topk[0]
        if isinstance(first, dict):
            try:
                return first.get("airline", "UNKNOWN") or "UNKNOWN", float(first.get("confidence", 0.0))
            except Exception:
                return first.get("airline", "UNKNOWN") or "UNKNOWN", 0.0
    return "UNKNOWN", 0.0


def _best_family_from_pred(pred: Dict) -> Tuple[str, float]:
    """Extract aircraft family/confidence regardless of schema."""
    fam = pred.get("aircraft_family", "UNKNOWN") or "UNKNOWN"
    try:
        conf = float(pred.get("family_confidence", pred.get("confidence", 0.0)))
    except Exception:
        conf = 0.0
    return fam, conf


def _best_phase_from_pred(pred: Dict) -> Tuple[str, float]:
    """Extract phase/confidence if present."""
    phase = str(pred.get("phase", "unknown") or "unknown").lower()
    if phase not in {"landing", "takeoff", "cruising", "unknown"}:
        phase = "unknown"
    try:
        conf = float(pred.get("phase_confidence", 0.0))
    except Exception:
        conf = 0.0
    return phase, conf


def _aggregate_predictions(preds: List[Dict], qualities: List[float], frame_indices: List[int]) -> Dict:
    """Merge multiple frame predictions into a single decision with uncertainty."""
    if not preds:
        return {
            "airline": "UNKNOWN",
            "aircraft_family": "UNKNOWN",
            "phase": "unknown",
            "phase_confidence": 0.0,
            "confidence": 0.0,
            "uncertainty": 1.0,
            "frames_used": 0,
            "cues": [],
            "votes": [],
            "family_votes": [],
            "phase_votes": [],
        }

    q_norm = _normalize_quality(qualities)

    airline_votes: Dict[str, float] = {}
    family_votes: Dict[str, float] = {}
    phase_votes: Dict[str, float] = {}
    total_airline_weight = 0.0
    total_family_weight = 0.0
    total_phase_weight = 0.0
    total_raw_weight = 0.0
    raw_candidates: List[Tuple[str, float, List[str]]] = []

    # track cues for the strongest vote on the winning airline
    winning_cues: List[str] = []
    winning_airline_weight = -1.0

    for pred, q_weight, frame_idx in zip(preds, q_norm, frame_indices):
        airline, a_conf = _best_airline_from_pred(pred)
        family, f_conf = _best_family_from_pred(pred)
        phase, p_conf = _best_phase_from_pred(pred)

        # collect raw candidates (even if low confidence) for fallback
        if airline != "UNKNOWN":
            raw_score = max(0.0, min(1.0, a_conf)) * q_weight
            raw_candidates.append(
                (
                    airline,
                    raw_score,
                    pred.get("cues", []) if isinstance(pred.get("cues", []), list) else [],
                )
            )
            total_raw_weight += raw_score

        # enforce minimum confidence thresholds by down-weighting uncertain frames
        if a_conf < MIN_CONFIDENCE_AIRLINE:
            airline = "UNKNOWN"
        if f_conf < MIN_CONFIDENCE_FAMILY:
            family = "UNKNOWN"

        a_weight = max(0.0, min(1.0, a_conf)) * q_weight
        f_weight = max(0.0, min(1.0, f_conf)) * q_weight
        p_weight = max(0.0, min(1.0, p_conf)) * q_weight

        airline_votes[airline] = airline_votes.get(airline, 0.0) + a_weight
        family_votes[family] = family_votes.get(family, 0.0) + f_weight
        phase_votes[phase] = phase_votes.get(phase, 0.0) + p_weight

        total_airline_weight += a_weight
        total_family_weight += f_weight
        total_phase_weight += p_weight

        if a_weight > winning_airline_weight and airline != "UNKNOWN":
            winning_airline_weight = a_weight
            winning_cues = pred.get("cues", []) if isinstance(pred.get("cues", []), list) else []

    best_airline, best_airline_score = ("UNKNOWN", 0.0)
    if airline_votes:
        best_airline, best_airline_score = max(airline_votes.items(), key=lambda kv: kv[1])

    best_family, best_family_score = ("UNKNOWN", 0.0)
    if family_votes:
        best_family, best_family_score = max(family_votes.items(), key=lambda kv: kv[1])

    airline_conf = best_airline_score / total_airline_weight if total_airline_weight > 0 else 0.0
    family_conf = best_family_score / total_family_weight if total_family_weight > 0 else 0.0
    best_phase, best_phase_score = ("unknown", 0.0)
    if phase_votes:
        best_phase, best_phase_score = max(phase_votes.items(), key=lambda kv: kv[1])
    phase_conf = best_phase_score / total_phase_weight if total_phase_weight > 0 else 0.0
    uncertainty = 1.0 - airline_conf

    fallback_used = False
    if best_airline == "UNKNOWN" and raw_candidates:
        # choose the raw candidate with the highest weighted confidence
        raw_candidates.sort(key=lambda tup: tup[1], reverse=True)
        fb_airline, fb_score, fb_cues = raw_candidates[0]
        if fb_score > 0:
            best_airline = fb_airline
            airline_conf = fb_score / total_raw_weight if total_raw_weight > 0 else fb_score
            uncertainty = 1.0 - airline_conf
            winning_cues = fb_cues
            fallback_used = True

    # produce sorted vote breakdowns for transparency
    vote_list = [{"airline": a, "weight": round(w, 3)} for a, w in sorted(airline_votes.items(), key=lambda kv: kv[1], reverse=True)]
    family_vote_list = [{"family": f, "weight": round(w, 3)} for f, w in sorted(family_votes.items(), key=lambda kv: kv[1], reverse=True)]
    phase_vote_list = [{"phase": p, "weight": round(w, 3)} for p, w in sorted(phase_votes.items(), key=lambda kv: kv[1], reverse=True)]

    return {
        "airline": best_airline,
        "aircraft_family": best_family,
        "confidence": round(airline_conf, 3),
        "family_confidence": round(family_conf, 3),
        "phase": best_phase,
        "phase_confidence": round(phase_conf, 3),
        "uncertainty": round(uncertainty, 3),
        "frames_used": len(preds),
        "source_frames": frame_indices,
        "cues": winning_cues,
        "votes": vote_list,
        "family_votes": family_vote_list,
        "phase_votes": phase_vote_list,
        "fallback_used": fallback_used,
    }


def select_sharpest(frames: List[bytes]) -> Tuple[int, bytes]:
    """Return index and bytes of the sharpest frame."""
    best_idx = 0
    best_score = -1.0
    for idx, fb in enumerate(frames):
        score = _sharpness(fb)
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx, frames[best_idx]


def classify_burst(frames: List[bytes], topk: bool = False, k: int = 3) -> dict:
    """Classify either the sharpest frame or all frames and merge results.

    If topk is False we run the regular classifier on the sharpest frame.
    If topk is True we run classify_aircraft_topk on the best frame.

    Returns a dictionary similar to the underlying classifier.
    """
    if not frames:
        return {}
    idx, best = select_sharpest(frames)
    if topk:
        return classify_aircraft_topk(best, k=k)
    else:
        return classify_aircraft(best)


def classify_burst_consensus(
    frames: List[bytes],
    topk: bool = False,
    k: int = 3,
    top_m: int = 3,
) -> dict:
    """
    Classify multiple frames from a burst and fuse the results with uncertainty handling.

    Steps:
    1. Score each frame by sharpness.
    2. Keep the top_m sharpest frames (or all if fewer).
    3. Run Gemini on each selected frame (topk optional).
    4. Aggregate votes weighted by sharpness and model confidence.

    Returns a dict containing airline, aircraft_family, confidence, uncertainty,
    and vote breakdowns.
    """
    if not frames:
        return {
            "airline": "UNKNOWN",
            "aircraft_family": "UNKNOWN",
            "confidence": 0.0,
            "uncertainty": 1.0,
            "frames_used": 0,
            "cues": [],
            "votes": [],
            "family_votes": [],
            "source_frames": [],
            "sharpness_scores": {},
        }

    scored: List[Tuple[int, bytes, float]] = []
    for idx, fb in enumerate(frames):
        s = _sharpness(fb)
        scored.append((idx, fb, s))

    # filter out very blurry frames if threshold is set
    usable = [item for item in scored if item[2] >= MIN_SHARPNESS_SCORE] or scored
    usable.sort(key=lambda tup: tup[2], reverse=True)
    selected = usable[:top_m]

    preds: List[Dict] = []
    qualities: List[float] = []
    frame_indices: List[int] = []

    for idx, frame_bytes, sharp in selected:
        pred = classify_aircraft_topk(frame_bytes, k=k) if topk else classify_aircraft(frame_bytes)
        preds.append(pred)
        qualities.append(sharp)
        frame_indices.append(idx)

    result = _aggregate_predictions(preds, qualities, frame_indices)
    result["sharpness_scores"] = {idx: round(score, 2) for idx, _, score in selected}
    return result


if __name__ == "__main__":
    # quick demo: capture and classify
    bursts = capture_burst(8, delay=0.05)
    if not bursts:
        print("no frames captured")
    else:
        print("captured", len(bursts), "frames")
        idx, best = select_sharpest(bursts)
        print(f"sharpest frame index {idx}")
        print("classification:", classify_aircraft(best))
        print("top-k:", classify_aircraft_topk(best, k=5))
