"""
Simple flight matcher that scores sandbox/live flights against Gemini output.

Scoring inputs:
- airline match (most important)
- aircraft family match
- proximity to observer location (if provided)
- phase/altitude plausibility
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from flight_feed import haversine_km


def _normalize(name: Any) -> str:
    return str(name or "").strip()


def _distance_score(distance_km: Optional[float]) -> float:
    if distance_km is None:
        return 0.6  # neutral when no location provided
    if distance_km <= 3:
        return 1.0
    if distance_km <= 10:
        return 0.8
    if distance_km <= 25:
        return 0.55
    if distance_km <= 40:
        return 0.3
    return 0.1


def _phase_score(status: str, alt_ft: float) -> float:
    s = (status or "").lower()
    alt = alt_ft or 0
    if s == "landing":
        if alt < 3000:
            return 1.0
        if alt < 8000:
            return 0.8
        if alt < 12000:
            return 0.4
        return 0.2
    if s == "takeoff":
        if alt < 8000:
            return 1.0
        if alt < 15000:
            return 0.7
        return 0.3
    if s == "cruising":
        if alt > 30000:
            return 1.0
        if alt > 24000:
            return 0.8
        return 0.4
    return 0.5


def _airline_score(classified: str, flight_airline: str) -> float:
    if not classified or classified.upper() == "UNKNOWN":
        return 0.5
    if classified.lower() == flight_airline.lower():
        return 1.0
    return 0.1


def _family_score(classified_family: str, flight_family: str) -> float:
    if not classified_family or classified_family.upper() == "UNKNOWN":
        return 0.4
    if classified_family.lower() == flight_family.lower():
        return 1.0
    # same coarse family bucket (e.g., both start with A320)
    if classified_family.split("-")[0].lower() == flight_family.split("-")[0].lower():
        return 0.6
    return 0.2


def score_flight(
    classification: Dict[str, Any],
    flight: Dict[str, Any],
    observer: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Return score + reasoning for a single flight."""
    airline_pred = _normalize(classification.get("airline"))
    family_pred = _normalize(classification.get("aircraft_family"))
    flight_airline = _normalize(flight.get("airline"))
    flight_family = _normalize(flight.get("aircraft_family"))

    distance_km = None
    if observer and flight.get("lat") is not None and flight.get("lon") is not None:
        distance_km = haversine_km(observer[0], observer[1], float(flight["lat"]), float(flight["lon"]))

    a_score = _airline_score(airline_pred, flight_airline)
    f_score = _family_score(family_pred, flight_family)
    d_score = _distance_score(distance_km)
    p_score = _phase_score(flight.get("status", ""), float(flight.get("alt_ft", 0) or 0))

    total = 0.45 * a_score + 0.25 * f_score + 0.2 * d_score + 0.1 * p_score

    return {
        "flight": flight,
        "score": round(total, 3),
        "reasons": {
            "airline_match": a_score,
            "family_match": f_score,
            "proximity": d_score,
            "phase": p_score,
            "distance_km": round(distance_km, 2) if distance_km is not None else None,
        },
    }


def match_best_flight(
    classification: Dict[str, Any],
    flights: List[Dict[str, Any]],
    observer: Optional[Tuple[float, float]] = None,
    top_n: int = 3,
) -> Dict[str, Any]:
    """Score all flights and return the best candidates."""
    if not flights:
        return {"best": None, "candidates": [], "searched": 0}

    scored = [score_flight(classification, f, observer) for f in flights]
    scored.sort(key=lambda s: s["score"], reverse=True)

    return {
        "best": scored[0],
        "candidates": scored[:top_n],
        "searched": len(flights),
    }


__all__ = ["match_best_flight", "score_flight"]
