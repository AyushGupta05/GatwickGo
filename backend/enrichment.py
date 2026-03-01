"""
Enrichment helpers for Gatwick GO.

Adds:
- origin (airport/city) metadata
- short grounded fact about the aircraft family/model with caching
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

import config

# -----------------------------------------------------------------------------
# Airport lookup (lightweight, local)
# -----------------------------------------------------------------------------

AIRPORTS: Dict[str, Dict[str, str]] = {
    "EGKK": {"iata": "LGW", "city": "London", "name": "London Gatwick"},
    "LEBL": {"iata": "BCN", "city": "Barcelona", "name": "Barcelona–El Prat"},
    "KJFK": {"iata": "JFK", "city": "New York", "name": "John F. Kennedy"},
    "LHBP": {"iata": "BUD", "city": "Budapest", "name": "Budapest Ferenc Liszt"},
    "EHAM": {"iata": "AMS", "city": "Amsterdam", "name": "Amsterdam Schiphol"},
    "OMDB": {"iata": "DXB", "city": "Dubai", "name": "Dubai International"},
    "LEPA": {"iata": "PMI", "city": "Palma", "name": "Palma de Mallorca"},
    "OTHH": {"iata": "DOH", "city": "Doha", "name": "Hamad International"},
    "EGCC": {"iata": "MAN", "city": "Manchester", "name": "Manchester"},
    "LFPO": {"iata": "ORY", "city": "Paris", "name": "Paris Orly"},
    "KLAX": {"iata": "LAX", "city": "Los Angeles", "name": "Los Angeles International"},
    "LEBB": {"iata": "BIO", "city": "Bilbao", "name": "Bilbao"},
    "EGPH": {"iata": "EDI", "city": "Edinburgh", "name": "Edinburgh"},
    "LPPT": {"iata": "LIS", "city": "Lisbon", "name": "Lisbon"},
    "KATL": {"iata": "ATL", "city": "Atlanta", "name": "Hartsfield–Jackson Atlanta"},
    "KBOS": {"iata": "BOS", "city": "Boston", "name": "Logan International"},
    "KEWR": {"iata": "EWR", "city": "Newark", "name": "Newark Liberty"},
    "CYYZ": {"iata": "YYZ", "city": "Toronto", "name": "Toronto Pearson"},
    "CYUL": {"iata": "YUL", "city": "Montreal", "name": "Montréal–Trudeau"},
    "KSEA": {"iata": "SEA", "city": "Seattle", "name": "Seattle–Tacoma"},
}

REVERSE_AIRPORTS_IATA = {v.get("iata"): k for k, v in AIRPORTS.items() if v.get("iata")}


def map_airport(icao: Optional[str], iata: Optional[str] = None, city: Optional[str] = None, name: Optional[str] = None) -> Optional[Dict[str, Optional[str]]]:
    meta: Dict[str, str] = {}
    code = None
    if icao:
        code = icao.upper()
        meta = AIRPORTS.get(code, {})
    elif iata:
        # reverse lookup by IATA
        for k, v in AIRPORTS.items():
            if v.get("iata") == iata.upper():
                code = k
                meta = v
                break
    if not code:
        return None
    return {
        "icao": code,
        "iata": iata or meta.get("iata"),
        "city": city or meta.get("city"),
        "name": name or meta.get("name"),
    }


def resolve_airport(code_or_name: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    if not code_or_name:
        return None
    token = code_or_name.strip()
    if len(token) == 4:
        return map_airport(token)
    if len(token) == 3:
        icao_guess = REVERSE_AIRPORTS_IATA.get(token.upper())
        return map_airport(icao_guess, token.upper())
    return None


# -----------------------------------------------------------------------------
# Fact cache + fallbacks
# -----------------------------------------------------------------------------

_FACT_CACHE: Dict[str, Dict[str, Any]] = {}
_FACT_TTL_SECONDS = 24 * 3600

# minimal local fact bank (fallback when Gemini grounding fails)
FACT_FALLBACK: Dict[str, list] = {
    "A320-family": [
        {"text": "The Airbus A320, first flown in 1987, was the first commercial jet with full fly-by-wire controls.", "source": "Airbus"},
        {"text": "A320-family aircraft typically seat 150–240 passengers and are the world’s best-selling single-aisle jets.", "source": "Airbus/ICAO"},
    ],
    "B737-family": [
        {"text": "The Boeing 737 is the most produced jet airliner in history, with over 10,000 delivered.", "source": "Boeing"},
    ],
    "A350": [
        {"text": "Airbus A350 uses over 50% carbon-fibre reinforced polymer in its airframe to cut weight and fuel burn.", "source": "Airbus"},
    ],
    "B777": [
        {"text": "The Boeing 777 was the first fly-by-wire Boeing airliner and set a 21-hour nonstop record on a 19,600 km flight in 2005.", "source": "Boeing"},
    ],
    "B787": [
        {"text": "The 787 Dreamliner’s electrical architecture replaces traditional bleed air systems, improving efficiency.", "source": "Boeing"},
    ],
    "A380": [
        {"text": "The Airbus A380 is the world’s largest passenger airliner, certified for up to 853 passengers in all-economy.", "source": "Airbus"},
    ],
    "E-Jet": [
        {"text": "Embraer E-Jets introduced double-bubble fuselage cross-sections to provide wide cabins in a regional jet footprint.", "source": "Embraer"},
    ],
    "ATR": [
        {"text": "ATR 72 turboprops use six-bladed propellers and are optimized for short runways and regional hops.", "source": "ATR"},
    ],
}

# simple seat/cabin hints per family
FAMILY_CAPACITY: Dict[str, str] = {
    "A320-family": "about 180–240 seats in single-class layouts",
    "B737-family": "around 160–200 seats in a single-class layout",
    "A350": "~300–350 seats as a long-haul widebody",
    "B787": "~240–330 seats with lower cabin altitude for comfort",
    "A380": "500+ seats on many carriers as a very-large jet",
    "B777": "roughly 314–396 seats on long-haul routes",
    "E-Jet": "around 76–110 seats for regional hops",
    "ATR": "about 68–78 seats for short-field operations",
}

# airline+family flavored fallbacks
FACT_FALLBACK_AIRLINE: Dict[str, list] = {
    "easyJet|A320-family": [
        {"text": "easyJet’s A320 fleet averages short European hops; their dense 186-seat layout keeps costs low.", "source": "easyJet fleet facts"},
    ],
    "British Airways|A350": [
        {"text": "BA’s A350-1000s feature the Club Suite with closing doors, debuting on the BA fleet in 2019.", "source": "British Airways"},
    ],
    "Qatar Airways|A350": [
        {"text": "Qatar Airways was the A350-900 launch customer in 2015 and later added the stretched -1000.", "source": "Qatar Airways"},
    ],
    "Emirates|A380": [
        {"text": "Emirates operates the world’s largest A380 fleet, over 100 jets, many with onboard showers in First.", "source": "Emirates"},
    ],
    "Ryanair|B737-family": [
        {"text": "Ryanair standardizes on high-density 737s to keep turnaround times under 30 minutes.", "source": "Ryanair"},
    ],
}


def _cache_get(key: str):
    item = _FACT_CACHE.get(key)
    if not item:
        return None
    if item["expires_at"] < time.time():
        _FACT_CACHE.pop(key, None)
        return None
    return item["value"]


def _cache_set(key: str, value: Dict[str, Any]):
    _FACT_CACHE[key] = {"value": value, "expires_at": time.time() + _FACT_TTL_SECONDS}


# -----------------------------------------------------------------------------
# Gemini grounded fact helper
# -----------------------------------------------------------------------------

def _parse_gemini_fact_response(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Try to extract text content then parse JSON inside it
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return None
    text = parts[0].get("text", "")
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    fact = parsed.get("fact")
    sources = parsed.get("sources") or []
    if fact and isinstance(sources, list) and sources:
        return {"text": fact, "sources": sources}
    return None


def _fetch_fact_from_gemini(prompt: str) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = getattr(config, "GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                ]
            }
        ],
        "tools": [{"googleSearchRetrieval": {}}],
    }
    try:
        resp = requests.post(url, json=body, timeout=getattr(config, "API_TIMEOUT", 30))
        resp.raise_for_status()
        return _parse_gemini_fact_response(resp.json())
    except Exception:
        return None


def get_fact_for_family(family: Optional[str]) -> Optional[Dict[str, Any]]:
    key = (family or "UNKNOWN").strip()
    cached = _cache_get(key)
    if cached:
        return cached

    prompt = (
        f"Provide one concise, verifiable fact (1-2 sentences) about the {key} aircraft family. "
        "Return JSON with keys: fact, sources (array of {title,url}). Keep it factual and cite public sources."
    )
    fact = _fetch_fact_from_gemini(prompt)
    if fact is None:
        fallback_list = FACT_FALLBACK.get(key) or FACT_FALLBACK.get(key.split("-")[0], [])
        if fallback_list:
            fact = {**fallback_list[0], "sources": [{"title": fallback_list[0]["source"], "url": None}]}

    if fact:
        _cache_set(key, fact)
    return fact


# -----------------------------------------------------------------------------
# Origin enrichment (OpenSky + sandbox)
# -----------------------------------------------------------------------------

def _fetch_opensky_origin(icao24: Optional[str], callsign: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    auth = None
    if config.OPENSKY_USERNAME and config.OPENSKY_PASSWORD:
        auth = (config.OPENSKY_USERNAME, config.OPENSKY_PASSWORD)

    now = int(time.time())
    begin = now - 6 * 3600
    session = requests.Session()
    base = "https://opensky-network.org/api/flights"

    def _query(path: str, params: Dict[str, Any]) -> Optional[str]:
        try:
            resp = session.get(path, params=params, auth=auth, timeout=8)
            resp.raise_for_status()
            flights = resp.json()
            if not isinstance(flights, list):
                return None
            flights = sorted(flights, key=lambda f: f.get("firstSeen", 0), reverse=True)
            for f in flights:
                dep = f.get("estDepartureAirport")
                if dep:
                    return dep
        except Exception:
            return None
        return None

    if icao24:
        dep = _query(f"{base}/aircraft", {"icao24": icao24, "begin": begin, "end": now})
        if dep:
            return map_airport(dep)

    if callsign:
        dep = _query(f"{base}/callsign", {"callsign": callsign.strip(), "begin": begin, "end": now})
        if dep:
            return map_airport(dep)

    return None


def enrich_origin(flight: Optional[Dict[str, Any]], provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not flight:
        return None

    # Structured fields first
    origin = map_airport(
        flight.get("origin_icao"),
        flight.get("origin_iata"),
        flight.get("origin_city"),
        flight.get("origin_name"),
    )
    if origin:
        return origin

    # If sandbox flight has a legacy string origin that is an IATA/ICAO code, try to map it.
    legacy = flight.get("origin")
    if isinstance(legacy, str) and len(legacy.strip()) in (3, 4):
        origin = map_airport(legacy.strip()) or map_airport(None, legacy.strip())
        if origin:
            return origin

    # OpenSky live lookup
    if provider and provider.lower() == "opensky":
        return _fetch_opensky_origin(flight.get("icao24"), flight.get("flight_number") or flight.get("callsign"))

    return None


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def enrich_match(classification: Dict[str, Any], match: Optional[Dict[str, Any]], feed: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    best_flight = match.get("best", {}).get("flight") if match else None
    provider = (feed or {}).get("provider")

    origin = enrich_origin(best_flight, provider=provider)
    fact = get_fact_for_aircraft(best_flight, classification) or get_fact_for_family(classification.get("aircraft_family"))

    return {"origin": origin, "fact": fact}


# -----------------------------------------------------------------------------
# Aircraft-specific fact
# -----------------------------------------------------------------------------

def _fact_cache_key(flight: Optional[Dict[str, Any]], classification: Dict[str, Any]) -> str:
    if flight:
        if flight.get("icao24"):
            return f"aircraft:{flight['icao24']}"
        if flight.get("flight_number"):
            return f"flight:{flight['flight_number']}"
    fam = classification.get("aircraft_family", "UNKNOWN")
    airline = classification.get("airline", "UNKNOWN")
    return f"family:{airline}|{fam}"


def get_fact_for_aircraft(flight: Optional[Dict[str, Any]], classification: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    key = _fact_cache_key(flight, classification)
    cached = _cache_get(key)
    if cached:
        return cached

    if not flight:
        return None

    airline = flight.get("airline") or classification.get("airline") or "UNKNOWN"
    family = classification.get("aircraft_family") or flight.get("aircraft_family") or "UNKNOWN"
    callsign = flight.get("callsign") or flight.get("flight_number")
    icao24 = flight.get("icao24")
    origin = flight.get("origin_city") or flight.get("origin_name") or flight.get("origin")
    dest = flight.get("destination")
    origin_meta = resolve_airport(flight.get("origin_icao") or flight.get("origin_iata") or origin)
    dest_meta = resolve_airport(dest)

    route = ""
    if origin or dest:
        route = f"Route: {origin or 'unknown'} -> {dest or 'unknown'}."

    prompt = (
        "Give one concise, verifiable fact (1–2 sentences) that feels specific to the aircraft operating this flight. "
        "Prefer details tied to the airline fleet, registration history, cabin/route usage, or delivery year. "
        "If no tail-specific detail is available, use an operator-specific fact about this aircraft family. "
        "Return JSON with keys: fact, sources (array of {title,url}). "
        f"Context: Airline: {airline}. Flight/callsign: {callsign or 'unknown'}. ICAO24 (hex): {icao24 or 'unknown'}. "
        f"Aircraft family: {family}. {route} Keep it factual, recent, and cite public sources."
    )

    fact = _fetch_fact_from_gemini(prompt)
    if fact and not _is_generic_fact(fact.get("text", "")):
        _cache_set(key, fact)
        return fact

    # operator + family fallback
    af_key = f"{airline}|{family}"
    fallback_list = FACT_FALLBACK_AIRLINE.get(af_key, [])
    if fallback_list:
        fact = {**fallback_list[0], "sources": [{"title": fallback_list[0]["source"], "url": None}]}
        _cache_set(key, fact)
        return fact

    # synthetic personalized fallback
    seat_hint = FAMILY_CAPACITY.get(family, "a suitable size for this route")
    origin_label = (origin_meta.get("name") or origin_meta.get("city")) if origin_meta else (origin or "this departure")
    dest_label = (dest_meta.get("name") or dest_meta.get("city")) if dest_meta else (dest or "its destination")
    flight_label = callsign or "this service"
    text = (
        f"{airline} flight {flight_label} is operating a {family} on the {origin_label} \u2192 {dest_label} run. "
        f"The {family} typically offers {seat_hint}, which fits {airline}'s demand on this leg."
    )
    fact = {"text": text, "sources": [{"title": "Generated from schedule context", "url": None}]}
    _cache_set(key, fact)
    return fact


def _is_generic_fact(text: str) -> bool:
    t = text.lower()
    generic_markers = [
        "most produced",
        "first flown",
        "world’s largest",
        "largest passenger airliner",
        "fly-by-wire controls",
    ]
    return any(marker in t for marker in generic_markers)
