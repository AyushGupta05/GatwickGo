"""
Generate a repeatable sandbox replay feed for Gatwick (LGW).

Creates JSON snapshots t0.json, t5.json, ... under sandbox_feed/.
Each snapshot contains 15 flights with light movement so the demo
looks alive while remaining deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "sandbox_feed"
SNAPSHOT_INTERVAL = 5  # seconds between snapshots
SNAPSHOT_STEPS = [0, 5, 10, 15, 20, 25]
BASE_TIME = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)

# Minimal airport lookup used to enrich sandbox flights with origin metadata.
AIRPORTS = {
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
}


def _origin_fields(origin_icao: str) -> Dict[str, str]:
    meta = AIRPORTS.get(origin_icao, {})
    return {
        "origin": meta.get("city", origin_icao),  # legacy string for compatibility
        "origin_icao": origin_icao,
        "origin_iata": meta.get("iata"),
        "origin_city": meta.get("city"),
        "origin_name": meta.get("name"),
    }


def _flight(
    flight_number: str,
    airline: str,
    aircraft_family: str,
    lat: float,
    lon: float,
    alt_ft: int,
    heading: int,
    speed_kt: int,
    status: str,
    origin_icao: str,
    destination: str,
    delta: Dict[str, float],
    icao24: str | None = None,
) -> Dict:
    base = {
        "flight_number": flight_number,
        "callsign": flight_number,
        "icao24": icao24,
        "airline": airline,
        "aircraft_family": aircraft_family,
        "lat": lat,
        "lon": lon,
        "alt_ft": alt_ft,
        "heading": heading,
        "speed_kt": speed_kt,
        "status": status,
        "destination": destination,
        "delta": delta,
    }
    base.update(_origin_fields(origin_icao))
    return base


FLIGHTS: List[Dict] = [
    # Landing: easyJet vs Vueling red herring + BA/Delta
    _flight("EZY1234", "easyJet", "A320-family", 51.200, -0.250, 5000, 82, 180, "landing", "LEBL", "LGW",
            {"lat": -0.0035, "lon": 0.0040, "alt_ft": -800, "speed_kt": -10}),
    _flight("BAW845", "British Airways", "A350", 51.180, -0.300, 6000, 95, 190, "landing", "KJFK", "LGW",
            {"lat": -0.0035, "lon": 0.0050, "alt_ft": -900, "speed_kt": -12}),
    _flight("WZZ901", "Wizz Air", "A320-family", 51.230, -0.210, 7000, 100, 170, "landing", "LHBP", "LGW",
            {"lat": -0.0045, "lon": 0.0030, "alt_ft": -900, "speed_kt": -8}),
    _flight("VLG512", "Vueling", "A320-family", 51.210, -0.280, 6400, 85, 175, "landing", "LEBL", "LGW",
            {"lat": -0.0038, "lon": 0.0045, "alt_ft": -850, "speed_kt": -9}),
    _flight("DAL35", "Delta Air Lines", "B767", 51.240, -0.350, 7200, 100, 200, "landing", "KJFK", "LGW",
            {"lat": -0.0040, "lon": 0.0050, "alt_ft": -1000, "speed_kt": -11}),

    # Takeoff departures
    _flight("EZY8911", "easyJet", "A320-family", 51.150, -0.170, 0, 260, 20, "takeoff", "EGKK", "Amsterdam",
            {"lat": 0.0015, "lon": -0.0060, "alt_ft": 1200, "speed_kt": 40}),
    _flight("BAW263", "British Airways", "B777", 51.152, -0.170, 0, 260, 30, "takeoff", "EGKK", "Dubai",
            {"lat": 0.0010, "lon": -0.0060, "alt_ft": 1500, "speed_kt": 35}),
    _flight("TUI072", "TUI Airways", "B737-family", 51.158, -0.160, 0, 80, 25, "takeoff", "EGKK", "Palma de Mallorca",
            {"lat": -0.0010, "lon": 0.0060, "alt_ft": 1300, "speed_kt": 38}),
    _flight("QTR808", "Qatar Airways", "B787", 51.150, -0.150, 0, 95, 30, "takeoff", "EGKK", "Doha",
            {"lat": -0.0010, "lon": 0.0070, "alt_ft": 1600, "speed_kt": 40}),
    _flight("NRS701", "Norse Atlantic Airways", "B787", 51.140, -0.180, 0, 255, 28, "takeoff", "EGKK", "JFK",
            {"lat": 0.0020, "lon": -0.0060, "alt_ft": 1400, "speed_kt": 37}),

    # Cruising/overhead
    _flight("BAW915", "British Airways", "A320-family", 51.400, -0.050, 28000, 210, 440, "cruising", "EGCC", "ORY",
            {"lat": -0.0015, "lon": -0.0020, "alt_ft": -200, "speed_kt": -5}),
    _flight("QTR16", "Qatar Airways", "A350", 51.450, -0.100, 36000, 290, 470, "cruising", "OTHH", "JFK",
            {"lat": -0.0010, "lon": -0.0025, "alt_ft": 0, "speed_kt": 0}),
    _flight("UAE9", "Emirates", "A380", 51.350, -0.250, 38000, 300, 480, "cruising", "OMDB", "LAX",
            {"lat": -0.0008, "lon": -0.0020, "alt_ft": 0, "speed_kt": 0}),
    _flight("VLG902", "Vueling", "A320-family", 51.320, -0.120, 32000, 200, 450, "cruising", "LEBB", "AMS",
            {"lat": -0.0012, "lon": -0.0025, "alt_ft": -150, "speed_kt": -4}),
    _flight("EZY77", "easyJet", "A320-family", 51.300, -0.300, 30000, 240, 430, "cruising", "EGPH", "LIS",
            {"lat": -0.0010, "lon": -0.0020, "alt_ft": -100, "speed_kt": -3}),
]


def generate_snapshots() -> None:
    SNAPSHOT_DIR.mkdir(exist_ok=True)

    for step in SNAPSHOT_STEPS:
        ts = BASE_TIME + timedelta(seconds=step)
        factor = step / SNAPSHOT_INTERVAL

        snapshot = []
        for f in FLIGHTS:
            lat = f["lat"] + f["delta"]["lat"] * factor
            lon = f["lon"] + f["delta"]["lon"] * factor
            alt = max(0, int(f["alt_ft"] + f["delta"]["alt_ft"] * factor))
            speed = max(0, int(f["speed_kt"] + f["delta"]["speed_kt"] * factor))

            snapshot.append(
                {
                    "flight_number": f["flight_number"],
                    "airline": f["airline"],
                    "aircraft_family": f["aircraft_family"],
                    "callsign": f.get("callsign"),
                    "icao24": f.get("icao24"),
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "alt_ft": alt,
                    "heading": f["heading"],
                    "speed_kt": speed,
                    "status": f["status"],
                    "origin": f["origin"],
                    "origin_icao": f["origin_icao"],
                    "origin_iata": f["origin_iata"],
                    "origin_city": f["origin_city"],
                    "origin_name": f["origin_name"],
                    "destination": f["destination"],
                    "timestamp": ts.isoformat().replace("+00:00", "Z"),
                }
            )

        out_path = SNAPSHOT_DIR / f"t{step}.json"
        out_path.write_text(json.dumps(snapshot, indent=2))
        print(f"wrote {out_path}")


if __name__ == "__main__":
    generate_snapshots()
