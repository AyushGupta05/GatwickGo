import os
import re
import json
import base64
from typing import List, Dict, Any

import requests

# configuration lives in a separate module so we can easily change models/timeouts
from config import (
    GEMINI_MODEL,
    API_TIMEOUT,
    SUPPORTED_AIRLINES,
    MIN_CONFIDENCE_AIRLINE,
    MIN_CONFIDENCE_FAMILY,
)

# If google.generativeai is available, we'll try to use it. Otherwise we fall back
# to a direct HTTPS call.
try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - might not be installed
    genai = None  # type: ignore


API_KEY = os.getenv("GEMINI_API_KEY")

# only these carriers are relevant for our project; Gemini should be
# instructed to limit output to this list (UNKNOWN otherwise).  We also
# keep a simple mapping of the common aircraft families each operator
# flies for offline reference/testing.
_VALID_AIRLINES = SUPPORTED_AIRLINES

# mapping of some typical aircraft models/families for each airline
# this is for human reference, not currently used by the classifier.
_AIRLINE_MODELS = {
    "easyJet": ["A319", "A320", "A320neo", "A321"],
    "British Airways": ["A320-family", "A350", "A380", "B777", "B787", "B747"],
    "Wizz Air": ["A320-family"],
    "TUI Airways": ["B737", "B757", "B767", "B787", "A320-family"],
    "Vueling": ["A320-family"],
    "Emirates": ["A380", "B777"],
    "Qatar Airways": ["A350", "B787", "B777", "A320-family"],
    "Turkish Airlines": ["A320-family", "A330", "A350", "B737", "B777", "B787"],
    "Norse Atlantic Airways": ["B787"],
    "Delta Air Lines": ["A220", "A320-family", "A330", "B737", "B757", "B767", "B777", "B787"],
}

# taxonomy of aircraft families we expect
_ALLOWED_FAMILIES = {
    "A320-family",
    "B737-family",
    "A220",
    "A330",
    "A340",
    "A350",
    "A380",
    "B747",
    "B757",
    "B767",
    "B777",
    "B787",
    "E-Jet",
    "ATR",
    "OTHER",
    "UNKNOWN",
}

_PROMPT_BASE = (
    """You are an image classifier that looks at a cropped picture of a commercial airplane and \
    extracts three things: airline/operator brand, coarse aircraft family, and flight phase \
    (landing, takeoff, cruising, or unknown).  Photos are often low-res or blurry; keep confidence \
    conservative.  Allowed airlines: easyJet, British Airways, Wizz Air, TUI Airways, Vueling, \
    Emirates, Qatar Airways, Turkish Airlines, Norse Atlantic Airways, Delta Air Lines (otherwise \
    use "UNKNOWN").  Allowed families: A320-family, B737-family, A220, A330, A340, A350, A380, \
    B747, B757, B767, B777, B787, E-Jet, ATR, OTHER, UNKNOWN.  Flight phase must be one of \
    landing, takeoff, cruising, unknown.

    Respond with a single JSON object with keys: `airline`, `aircraft_family`, `confidence`, \
    `cues`, `phase`, `phase_confidence`.  confidences are 0-1.  Cues = list of short visual notes.

    Rules:
    - Prefer UNKNOWN over guessing; keep confidence <0.5 when unsure or blurred.
    - Penalize when distant/occluded/backlit.
    - Phase hints: nose-up + rotation + runway/ground speed => takeoff; flaps/spoilers, gear \
      down, low altitude over runway => landing; high altitude/clean configuration => cruising; \
      otherwise unknown.
    - Clamp all confidences to [0,1].  Keep format strictly JSON."""
)

_PROMPT_TOPK = (
    """Given the same constraints, also provide the topk guesses for airline, plus family and phase. \
    Output JSON keys: `topk` (array of {{airline, confidence}}), `aircraft_family`, \
    `family_confidence`, `phase`, `phase_confidence`, `cues`.  `topk` sorted high->low, length ≤ {k}. \
    Phase must be landing | takeoff | cruising | unknown.  Confidences in [0,1]; be conservative."""
)



def _call_gemini(image_bytes: bytes, prompt: str) -> str:
    """Send the prompt+image to Gemini and return raw text output."""

    if not API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # try official SDK first (google-generativeai)
    if genai is not None:
        try:
            genai.configure(api_key=API_KEY)
            # use whatever model is configured in config.py
            model = genai.GenerativeModel(GEMINI_MODEL)
            # send prompt + base64 image to Gemini
            response = model.generate_content(
                [
                    prompt,
                    {"mime_type": "image/jpeg", "data": b64},
                ]
            )
            return response.text
        except Exception:
            # fall through to HTTP-based approach
            pass

    # fallback: manual HTTP request to Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    body: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64,
                        }
                    },
                ]
            }
        ]
    }
    # use configurable timeout
    r = requests.post(url, headers=headers, json=body, timeout=API_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    # extract text from Gemini response
    if "candidates" in data and len(data["candidates"]) > 0:
        candidate = data["candidates"][0]
        if "content" in candidate and "parts" in candidate["content"]:
            parts = candidate["content"]["parts"]
            if len(parts) > 0 and "text" in parts[0]:
                return parts[0]["text"]
    return json.dumps(data)


def _extract_json(text: str) -> Any:
    """Try to parse a JSON object from the given text.

    Returns the parsed object or None if it cannot be extracted.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to pull first {...} block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _normalize_family(family: str) -> str:
    fam = family.strip()
    if fam in _ALLOWED_FAMILIES:
        return fam
    # simple case-insensitive mapping for a few common variants
    mapping = {
        "a320": "A320-family",
        "b737": "B737-family",
        "e jet": "E-Jet",
        "e-jet": "E-Jet",
        "atr": "ATR",
        "a380": "A380",
    }
    key = fam.lower()
    if key in mapping:
        return mapping[key]
    return "OTHER" if fam else "UNKNOWN"


def classify_aircraft(image_bytes: bytes) -> dict:
    """Classify a cropped airplane image.

    Returns:
        {
            "airline": str,
            "aircraft_family": str,
            "confidence": float,
            "cues": List[str],
            "phase": str,
            "phase_confidence": float,
        }
    """
    # perform one attempt, if parsing fails retry with a stronger directive
    def attempt(prompt: str) -> dict:
        text = _call_gemini(image_bytes, prompt)
        data = _extract_json(text)
        return data

    data = attempt(_PROMPT_BASE)
    if data is None:
        data = attempt(_PROMPT_BASE + "\nRespond ONLY with the JSON object and nothing else.")
    if data is None or not isinstance(data, dict):
        return {"airline": "UNKNOWN", "aircraft_family": "UNKNOWN", "confidence": 0.0, "cues": []}

    airline = data.get("airline", "UNKNOWN") or "UNKNOWN"
    # check against our allowed list (case-insensitive)
    if airline not in _VALID_AIRLINES:
        # try a case-insensitive match
        matched = next((a for a in _VALID_AIRLINES if a.lower() == airline.lower()), None)
        if matched:
            airline = matched
        else:
            airline = "UNKNOWN"
    family = _normalize_family(str(data.get("aircraft_family", "UNKNOWN") or "UNKNOWN"))
    try:
        conf = float(data.get("confidence", 0.0))
    except Exception:
        conf = 0.0
    # clamp
    conf = max(0.0, min(1.0, conf))
    cues = data.get("cues", [])
    if not isinstance(cues, list):
        cues = []

    def fallback_from_topk() -> dict:
        """When airline is UNKNOWN, pull best guess from a top-k call."""
        top = classify_aircraft_topk(image_bytes, k=3)
        if not top or "topk" not in top or not top["topk"]:
            return {"airline": "UNKNOWN", "confidence": conf, "cues": cues, "phase": data.get("phase", "unknown"), "phase_confidence": data.get("phase_confidence", 0.0)}
        best = next((entry for entry in top["topk"] if entry.get("airline") != "UNKNOWN"), None)
        if not best:
            best = top["topk"][0]
        try:
            best_conf = float(best.get("confidence", 0.0))
        except Exception:
            best_conf = 0.0
        return {
            "airline": best.get("airline", "UNKNOWN") or "UNKNOWN",
            "confidence": max(0.0, min(1.0, best_conf)),
            "cues": top.get("cues", cues),
            "aircraft_family": top.get("aircraft_family", family),
            "family_confidence": top.get("family_confidence", 0.0),
            "phase": top.get("phase", data.get("phase", "unknown")),
            "phase_confidence": top.get("phase_confidence", data.get("phase_confidence", 0.0)),
            "fallback_used": True,
        }

    # If model said UNKNOWN or confidence is below threshold, choose best-guess instead.
    if airline.upper() == "UNKNOWN" or conf < MIN_CONFIDENCE_AIRLINE:
        fb = fallback_from_topk()
        airline = fb["airline"]
        conf = fb["confidence"]
        cues = fb.get("cues", cues)
        family = fb.get("aircraft_family", family)

    # phase parsing
    phase_raw = data.get("phase", "unknown") or "unknown"
    phase = str(phase_raw).lower()
    if phase not in {"landing", "takeoff", "cruising", "unknown"}:
        phase = "unknown"
    try:
        phase_conf = float(data.get("phase_confidence", 0.0))
    except Exception:
        phase_conf = 0.0
    phase_conf = max(0.0, min(1.0, phase_conf))

    return {
        "airline": airline,
        "aircraft_family": family,
        "confidence": conf,
        "cues": cues,
        "phase": phase,
        "phase_confidence": phase_conf,
    }


def classify_aircraft_topk(image_bytes: bytes, k: int = 3) -> dict:
    """Return top-k airline guesses plus family.

    Output structure:
        {
            "topk": [{"airline": str, "confidence": float}, ...],
            "aircraft_family": str,
            "family_confidence": float,
            "phase": str,
            "phase_confidence": float,
            "cues": List[str],
        }
    """
    prompt = _PROMPT_TOPK.format(k=k)

    data = _extract_json(_call_gemini(image_bytes, prompt))
    if data is None:
        data = _extract_json(_call_gemini(image_bytes, prompt + "\nReply with JSON only."))
    if data is None or not isinstance(data, dict):
        return {"topk": [], "aircraft_family": "UNKNOWN", "family_confidence": 0.0, "cues": []}

    topk = data.get("topk", [])
    if not isinstance(topk, list):
        topk = []
    # clamp confidences and sanitize airline names (filter to our list)
    sanitized: List[Dict[str, Any]] = []
    for entry in topk[:k]:
        if not isinstance(entry, dict):
            continue
        al = entry.get("airline", "UNKNOWN") or "UNKNOWN"
        if al not in _VALID_AIRLINES:
            matched = next((a for a in _VALID_AIRLINES if a.lower() == al.lower()), None)
            if matched:
                al = matched
            else:
                al = "UNKNOWN"
        try:
            cf = float(entry.get("confidence", 0.0))
        except Exception:
            cf = 0.0
        cf = max(0.0, min(1.0, cf))
        sanitized.append({"airline": al, "confidence": cf})
    family = _normalize_family(str(data.get("aircraft_family", "UNKNOWN") or "UNKNOWN"))
    try:
        fam_conf = float(data.get("family_confidence", 0.0))
    except Exception:
        fam_conf = 0.0
    fam_conf = max(0.0, min(1.0, fam_conf))
    cues = data.get("cues", [])
    if not isinstance(cues, list):
        cues = []
    phase = str(data.get("phase", "unknown") or "unknown").lower()
    if phase not in {"landing", "takeoff", "cruising", "unknown"}:
        phase = "unknown"
    try:
        p_conf = float(data.get("phase_confidence", 0.0))
    except Exception:
        p_conf = 0.0
    p_conf = max(0.0, min(1.0, p_conf))

    return {
        "topk": sanitized,
        "aircraft_family": family,
        "family_confidence": fam_conf,
        "phase": phase,
        "phase_confidence": p_conf,
        "cues": cues,
    }


# Example usage snippet
if __name__ == "__main__":
    # this block demonstrates how the functions can be used; remove or modify for production.
    import sys

    if len(sys.argv) < 2:
        print("Usage: python gemini_classifier.py <image-file>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "rb") as f:
        img = f.read()

    print("=== single classification ===")
    print(classify_aircraft(img))

    print("=== top-k classification ===")
    print(classify_aircraft_topk(img, k=5))
