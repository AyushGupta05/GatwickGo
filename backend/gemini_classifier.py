import os
import re
import json
import base64
from typing import List, Dict, Any

import requests

from config import (
    GEMINI_MODEL,
    API_TIMEOUT,
    SUPPORTED_AIRLINES,
    MIN_CONFIDENCE_AIRLINE,
    MIN_CONFIDENCE_FAMILY,
)

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - might not be installed
    genai = None  # type: ignore


API_KEY = os.getenv("GEMINI_API_KEY")

_VALID_AIRLINES = SUPPORTED_AIRLINES

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

_ALLOWED_MODELS = {
    "A319",
    "A320",
    "A320neo",
    "A321",
    "A321neo",
    "A220-100",
    "A220-300",
    "A330-200",
    "A330-300",
    "A330-900",
    "A340-300",
    "A340-600",
    "A350-900",
    "A350-1000",
    "A380-800",
    "737-700",
    "737-800",
    "737 MAX 8",
    "737 MAX 9",
    "747-400",
    "757-200",
    "767-300",
    "767-400",
    "777-200",
    "777-300ER",
    "787-8",
    "787-9",
    "787-10",
    "E190",
    "E195",
    "ATR 72-600",
    "OTHER",
    "UNKNOWN",
}

_MODEL_ALIASES = {
    "A319": "A319",
    "AIRBUSA319": "A319",
    "A320": "A320",
    "AIRBUSA320": "A320",
    "A320NEO": "A320neo",
    "AIRBUSA320NEO": "A320neo",
    "A321": "A321",
    "AIRBUSA321": "A321",
    "A321NEO": "A321neo",
    "AIRBUSA321NEO": "A321neo",
    "A220": "A220-300",
    "A220100": "A220-100",
    "A220300": "A220-300",
    "AIRBUSA220100": "A220-100",
    "AIRBUSA220300": "A220-300",
    "A330": "A330-300",
    "A330200": "A330-200",
    "A330300": "A330-300",
    "A330900": "A330-900",
    "A330NEO": "A330-900",
    "AIRBUSA330200": "A330-200",
    "AIRBUSA330300": "A330-300",
    "AIRBUSA330900": "A330-900",
    "A340": "A340-300",
    "A340300": "A340-300",
    "A340600": "A340-600",
    "A350": "A350-900",
    "A350900": "A350-900",
    "A3501000": "A350-1000",
    "A380": "A380-800",
    "A380800": "A380-800",
    "AIRBUSA380": "A380-800",
    "AIRBUSA380800": "A380-800",
    "737": "737-800",
    "737700": "737-700",
    "737800": "737-800",
    "737MAX8": "737 MAX 8",
    "737MAX9": "737 MAX 9",
    "BOEING737700": "737-700",
    "BOEING737800": "737-800",
    "BOEING737MAX8": "737 MAX 8",
    "BOEING737MAX9": "737 MAX 9",
    "B737": "737-800",
    "B737700": "737-700",
    "B737800": "737-800",
    "B737MAX8": "737 MAX 8",
    "B737MAX9": "737 MAX 9",
    "747": "747-400",
    "747400": "747-400",
    "BOEING747400": "747-400",
    "B747": "747-400",
    "B747400": "747-400",
    "757": "757-200",
    "757200": "757-200",
    "BOEING757200": "757-200",
    "B757": "757-200",
    "B757200": "757-200",
    "767": "767-300",
    "767300": "767-300",
    "767400": "767-400",
    "BOEING767300": "767-300",
    "BOEING767400": "767-400",
    "B767": "767-300",
    "B767300": "767-300",
    "B767400": "767-400",
    "777": "777-300ER",
    "777200": "777-200",
    "777300ER": "777-300ER",
    "BOEING777200": "777-200",
    "BOEING777300ER": "777-300ER",
    "B777": "777-300ER",
    "B777200": "777-200",
    "B777300ER": "777-300ER",
    "787": "787-9",
    "7878": "787-8",
    "7879": "787-9",
    "78710": "787-10",
    "BOEING7878": "787-8",
    "BOEING7879": "787-9",
    "BOEING78710": "787-10",
    "BOEING787DREAMLINER": "787-9",
    "B787": "787-9",
    "B7878": "787-8",
    "B7879": "787-9",
    "B78710": "787-10",
    "E190": "E190",
    "EMBRAERE190": "E190",
    "E195": "E195",
    "EMBRAERE195": "E195",
    "ATR72": "ATR 72-600",
    "ATR72600": "ATR 72-600",
    "ATR726": "ATR 72-600",
}

_PROMPT_BASE = (
    """You are an image classifier that looks at a cropped picture of a commercial airplane and \
    extracts four things: airline/operator brand, exact aircraft model when visible, coarse aircraft family, \
    and flight phase (landing, takeoff, cruising, or unknown). Photos are often low-res or blurry; keep \
    confidence conservative. Allowed airlines: easyJet, British Airways, Wizz Air, TUI Airways, Vueling, \
    Emirates, Qatar Airways, Turkish Airlines, Norse Atlantic Airways, Delta Air Lines (otherwise use \
    "UNKNOWN"). Allowed families: A320-family, B737-family, A220, A330, A340, A350, A380, B747, B757, \
    B767, B777, B787, E-Jet, ATR, OTHER, UNKNOWN. Flight phase must be one of landing, takeoff, cruising, unknown.

    Respond with a single JSON object with keys: `airline`, `aircraft_model`, `aircraft_family`, \
    `confidence`, `model_confidence`, `family_confidence`, `cues`, `phase`, `phase_confidence`. \
    Confidences are 0-1. Cues = list of short visual notes.

    Rules:
    - Prefer UNKNOWN over guessing; keep confidence <0.5 when unsure or blurred.
    - Use `aircraft_model` for the most specific likely type you can see, such as A320neo, 737-800, \
      787-9, A350-1000, E190, ATR 72-600. Use UNKNOWN if you cannot tell the exact model.
    - Penalize when distant, occluded, or backlit.
    - Phase hints: nose-up + rotation + runway/ground speed => takeoff; flaps/spoilers, gear down, \
      low altitude over runway => landing; high altitude/clean configuration => cruising; otherwise unknown.
    - Clamp all confidences to [0,1]. Keep format strictly JSON."""
)

_PROMPT_TOPK = (
    """Given the same constraints, also provide the topk guesses for airline, plus model, family, and phase. \
    Output JSON keys: `topk` (array of {{airline, confidence}}), `aircraft_model`, `model_confidence`, \
    `aircraft_family`, `family_confidence`, `phase`, `phase_confidence`, `cues`. `topk` sorted high-to-low, \
    length <= {k}. Phase must be landing | takeoff | cruising | unknown. Confidences in [0,1]; be conservative."""
)


def _call_gemini(image_bytes: bytes, prompt: str) -> str:
    """Send the prompt+image to Gemini and return raw text output."""

    if not API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is not set")

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    if genai is not None:
        try:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(
                [
                    prompt,
                    {"mime_type": "image/jpeg", "data": b64},
                ]
            )
            return response.text
        except Exception:
            pass

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
    response = requests.post(url, headers=headers, json=body, timeout=API_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if "candidates" in data and len(data["candidates"]) > 0:
        candidate = data["candidates"][0]
        if "content" in candidate and "parts" in candidate["content"]:
            parts = candidate["content"]["parts"]
            if len(parts) > 0 and "text" in parts[0]:
                return parts[0]["text"]
    return json.dumps(data)


def _extract_json(text: str) -> Any:
    """Try to parse a JSON object from the given text."""

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _normalize_family(family: str) -> str:
    fam = family.strip()
    if fam in _ALLOWED_FAMILIES:
        return fam
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


def _normalize_model(model: str, family: str = "UNKNOWN") -> str:
    raw = model.strip()
    if not raw:
        return "UNKNOWN"
    if raw in _ALLOWED_MODELS:
        return raw

    key = re.sub(r"[^A-Z0-9]+", "", raw.upper())
    if key in _MODEL_ALIASES:
        return _MODEL_ALIASES[key]
    return "UNKNOWN"


def _clamp_confidence(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def classify_aircraft(image_bytes: bytes) -> dict:
    """Classify a cropped airplane image."""

    def attempt(prompt: str) -> dict:
        return _extract_json(_call_gemini(image_bytes, prompt))

    data = attempt(_PROMPT_BASE)
    if data is None:
        data = attempt(_PROMPT_BASE + "\nRespond ONLY with the JSON object and nothing else.")
    if data is None or not isinstance(data, dict):
        return {
            "airline": "UNKNOWN",
            "aircraft_model": "UNKNOWN",
            "aircraft_family": "UNKNOWN",
            "confidence": 0.0,
            "model_confidence": 0.0,
            "family_confidence": 0.0,
            "cues": [],
            "phase": "unknown",
            "phase_confidence": 0.0,
        }

    airline = data.get("airline", "UNKNOWN") or "UNKNOWN"
    if airline not in _VALID_AIRLINES:
        matched = next((candidate for candidate in _VALID_AIRLINES if candidate.lower() == airline.lower()), None)
        airline = matched or "UNKNOWN"

    family = _normalize_family(str(data.get("aircraft_family", "UNKNOWN") or "UNKNOWN"))
    model = _normalize_model(str(data.get("aircraft_model", "UNKNOWN") or "UNKNOWN"), family)
    conf = _clamp_confidence(data.get("confidence", 0.0))
    family_conf = _clamp_confidence(data.get("family_confidence", conf), conf)
    model_conf = _clamp_confidence(data.get("model_confidence", family_conf), family_conf)

    cues = data.get("cues", [])
    if not isinstance(cues, list):
        cues = []

    def fallback_from_topk() -> dict:
        top = classify_aircraft_topk(image_bytes, k=3)
        if not top or "topk" not in top or not top["topk"]:
            return {
                "airline": "UNKNOWN",
                "confidence": conf,
                "cues": cues,
                "aircraft_model": model,
                "model_confidence": model_conf,
                "aircraft_family": family,
                "family_confidence": family_conf,
                "phase": data.get("phase", "unknown"),
                "phase_confidence": data.get("phase_confidence", 0.0),
            }
        best = next((entry for entry in top["topk"] if entry.get("airline") != "UNKNOWN"), None)
        if not best:
            best = top["topk"][0]
        best_conf = _clamp_confidence(best.get("confidence", 0.0))
        return {
            "airline": best.get("airline", "UNKNOWN") or "UNKNOWN",
            "confidence": best_conf,
            "cues": top.get("cues", cues),
            "aircraft_model": top.get("aircraft_model", model),
            "model_confidence": top.get("model_confidence", model_conf),
            "aircraft_family": top.get("aircraft_family", family),
            "family_confidence": top.get("family_confidence", family_conf),
            "phase": top.get("phase", data.get("phase", "unknown")),
            "phase_confidence": top.get("phase_confidence", data.get("phase_confidence", 0.0)),
            "fallback_used": True,
        }

    if airline.upper() == "UNKNOWN" or conf < MIN_CONFIDENCE_AIRLINE:
        fallback = fallback_from_topk()
        airline = fallback["airline"]
        conf = _clamp_confidence(fallback["confidence"], conf)
        cues = fallback.get("cues", cues)
        family = _normalize_family(str(fallback.get("aircraft_family", family) or family))
        family_conf = _clamp_confidence(fallback.get("family_confidence", family_conf), family_conf)
        model = _normalize_model(str(fallback.get("aircraft_model", model) or model), family)
        model_conf = _clamp_confidence(fallback.get("model_confidence", model_conf), model_conf)

    phase = str(data.get("phase", "unknown") or "unknown").lower()
    if phase not in {"landing", "takeoff", "cruising", "unknown"}:
        phase = "unknown"
    phase_conf = _clamp_confidence(data.get("phase_confidence", 0.0))

    return {
        "airline": airline,
        "aircraft_model": model,
        "aircraft_family": family,
        "confidence": conf,
        "model_confidence": model_conf,
        "family_confidence": family_conf,
        "cues": cues,
        "phase": phase,
        "phase_confidence": phase_conf,
    }


def classify_aircraft_topk(image_bytes: bytes, k: int = 3) -> dict:
    """Return top-k airline guesses plus model and family."""

    prompt = _PROMPT_TOPK.format(k=k)

    data = _extract_json(_call_gemini(image_bytes, prompt))
    if data is None:
        data = _extract_json(_call_gemini(image_bytes, prompt + "\nReply with JSON only."))
    if data is None or not isinstance(data, dict):
        return {
            "topk": [],
            "aircraft_model": "UNKNOWN",
            "model_confidence": 0.0,
            "aircraft_family": "UNKNOWN",
            "family_confidence": 0.0,
            "phase": "unknown",
            "phase_confidence": 0.0,
            "cues": [],
        }

    topk = data.get("topk", [])
    if not isinstance(topk, list):
        topk = []

    sanitized: List[Dict[str, Any]] = []
    for entry in topk[:k]:
        if not isinstance(entry, dict):
            continue
        airline = entry.get("airline", "UNKNOWN") or "UNKNOWN"
        if airline not in _VALID_AIRLINES:
            matched = next((candidate for candidate in _VALID_AIRLINES if candidate.lower() == airline.lower()), None)
            airline = matched or "UNKNOWN"
        confidence = _clamp_confidence(entry.get("confidence", 0.0))
        sanitized.append({"airline": airline, "confidence": confidence})

    family = _normalize_family(str(data.get("aircraft_family", "UNKNOWN") or "UNKNOWN"))
    model = _normalize_model(str(data.get("aircraft_model", "UNKNOWN") or "UNKNOWN"), family)
    family_conf = _clamp_confidence(data.get("family_confidence", 0.0))
    model_conf = _clamp_confidence(data.get("model_confidence", family_conf), family_conf)

    cues = data.get("cues", [])
    if not isinstance(cues, list):
        cues = []

    phase = str(data.get("phase", "unknown") or "unknown").lower()
    if phase not in {"landing", "takeoff", "cruising", "unknown"}:
        phase = "unknown"
    phase_conf = _clamp_confidence(data.get("phase_confidence", 0.0))

    return {
        "topk": sanitized,
        "aircraft_model": model,
        "model_confidence": model_conf,
        "aircraft_family": family,
        "family_confidence": family_conf,
        "phase": phase,
        "phase_confidence": phase_conf,
        "cues": cues,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python gemini_classifier.py <image-file>")
        raise SystemExit(1)

    with open(sys.argv[1], "rb") as handle:
        image = handle.read()

    print("=== single classification ===")
    print(classify_aircraft(image))

    print("=== top-k classification ===")
    print(classify_aircraft_topk(image, k=5))
