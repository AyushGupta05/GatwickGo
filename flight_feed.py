from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Default reference point (London Gatwick)
DEFAULT_CENTER = (51.1537, -0.1821)
DEFAULT_RADIUS_KM = 30.0


class FlightMode(str, Enum):
    SANDBOX = "SANDBOX"
    OPENSKY = "OPENSKY"
    FR24 = "FR24"
    LIVE = "LIVE"  # alias for OPENSKY unless overriden


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in kilometers between two points."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _bbox_from_center(center: Tuple[float, float], radius_km: float) -> Tuple[float, float, float, float]:
    """Return (lat_min, lat_max, lon_min, lon_max) for a given center/radius."""
    lat, lon = center
    dlat = radius_km / 111.0
    cos_lat = max(0.01, math.cos(math.radians(lat)))
    dlon = radius_km / (111.0 * cos_lat)
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


@dataclass
class ProviderMeta:
    provider: str
    mode: str
    snapshot: Optional[str] = None
    snapshot_time: Optional[str] = None
    error: Optional[str] = None
    credentials_ok: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None


class SandboxReplayProvider:
    """Replay snapshots from sandbox_feed every N seconds for deterministic demos."""

    def __init__(
        self,
        snapshot_dir: Path,
        interval_seconds: int = 5,
        loop: bool = True,
        center: Tuple[float, float] = DEFAULT_CENTER,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.interval_seconds = interval_seconds
        self.loop = loop
        self.center = center
        self.start_time = time.time()
        self.snapshot_paths = self._discover_snapshots()
        if not self.snapshot_paths:
            raise FileNotFoundError(f"No snapshots found in {snapshot_dir}")

    def _discover_snapshots(self) -> List[Path]:
        paths = list(self.snapshot_dir.glob("t*.json"))

        def sort_key(p: Path) -> int:
            try:
                stem = p.stem
                return int(stem.lstrip("t"))
            except Exception:
                return 0

        return sorted(paths, key=sort_key)

    def _current_index(self) -> int:
        elapsed = time.time() - self.start_time
        idx = int(elapsed // self.interval_seconds)
        if self.loop:
            idx = idx % len(self.snapshot_paths)
        else:
            idx = min(idx, len(self.snapshot_paths) - 1)
        return idx

    def _load_snapshot(self, idx: int) -> Tuple[List[Dict[str, Any]], ProviderMeta]:
        path = self.snapshot_paths[idx]
        flights = _load_json(path)
        snapshot_time = None
        if flights and isinstance(flights, list):
            snapshot_time = flights[0].get("timestamp")
        meta = ProviderMeta(
            provider="sandbox",
            mode=FlightMode.SANDBOX.value,
            snapshot=path.name,
            snapshot_time=snapshot_time,
        )
        return flights, meta

    def get_flights(
        self,
        center: Optional[Tuple[float, float]] = None,
        radius_km: float = DEFAULT_RADIUS_KM,
        anchor_to: Optional[Tuple[float, float]] = None,
    ) -> Tuple[List[Dict[str, Any]], ProviderMeta]:
        flights, meta = self._load_snapshot(self._current_index())

        # If anchor_to provided, shift the entire snapshot so it is centered near the user's location.
        if anchor_to:
            dlat = anchor_to[0] - self.center[0]
            dlon = anchor_to[1] - self.center[1]
            shifted = []
            for f in flights:
                nf = dict(f)
                nf["lat"] = float(nf.get("lat", 0)) + dlat
                nf["lon"] = float(nf.get("lon", 0)) + dlon
                shifted.append(nf)
            flights = shifted
            if meta.details is None:
                meta.details = {}
            meta.details["anchored"] = True

        center_point = center or anchor_to or self.center
        filtered = flights
        if center_point and radius_km:
            filtered = [
                f for f in flights
                if haversine_km(center_point[0], center_point[1], f.get("lat", 0), f.get("lon", 0)) <= radius_km
            ]
            # If over-filtered to zero, fall back to the unfiltered list so matching still works.
            if not filtered:
                filtered = flights
        return filtered, meta


def _airline_from_callsign(callsign: str) -> str:
    """Best-effort mapping from ICAO/IATA prefix."""
    if not callsign:
        return "UNKNOWN"
    prefix = callsign.strip().upper()[:3]
    mapping = {
        "BAW": "British Airways",
        "EZY": "easyJet",
        "EJU": "easyJet",
        "VLG": "Vueling",
        "QTR": "Qatar Airways",
        "UAE": "Emirates",
        "NRS": "Norse Atlantic Airways",
        "DAL": "Delta Air Lines",
        "TOM": "TUI Airways",
        "TUI": "TUI Airways",
        "WZZ": "Wizz Air",
    }
    return mapping.get(prefix, "UNKNOWN")


class OpenSkyLiveProvider:
    """OpenSky wrapper using OAuth2 Client Credentials (Bearer token)."""

    def __init__(
        self,
        center: Tuple[float, float] = DEFAULT_CENTER,
        radius_km: float = DEFAULT_RADIUS_KM,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        self.center = center
        self.radius_km = radius_km

        self.client_id = client_id or os.getenv("OPENSKY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("OPENSKY_CLIENT_SECRET")

        self._token: Optional[str] = None
        self._token_expiry: float = 0.0  # epoch seconds

    def _get_token(self) -> str:
        if self._token and time.time() < (self._token_expiry - 30):
            return self._token

        if not (self.client_id and self.client_secret):
            raise RuntimeError("OpenSky OAuth creds missing. Set OPENSKY_CLIENT_ID/OPENSKY_CLIENT_SECRET.")

        token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

        resp = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=8,
        )
        resp.raise_for_status()
        js = resp.json()

        self._token = js["access_token"]
        expires_in = int(js.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in
        return self._token

    def get_flights(
        self,
        center: Optional[Tuple[float, float]] = None,
        radius_km: Optional[float] = None,
        **_: Any,
    ) -> Tuple[List[Dict[str, Any]], ProviderMeta]:
        if not (self.client_id and self.client_secret):
            return [], ProviderMeta(
                provider="opensky",
                mode=FlightMode.OPENSKY.value,
                error="OpenSky OAuth credentials not configured",
                credentials_ok=False,
            )

        center_point = center or self.center
        radius = radius_km or self.radius_km
        lamin, lamax, lomin, lomax = _bbox_from_center(center_point, radius)

        try:
            token = self._get_token()

            resp = requests.get(
                "https://opensky-network.org/api/states/all",
                params={
                    "lamin": lamin,
                    "lomin": lomin,
                    "lamax": lamax,
                    "lomax": lomax,
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            states = data.get("states", []) or []
            flights: List[Dict[str, Any]] = []
            for s in states:
                # OpenSky states vector layout: https://opensky-network.org/apidoc/rest.html
                callsign = (s[1] or "").strip()
                icao24 = (s[0] or "").strip()
                lat = s[6]
                lon = s[5]
                geo_alt = s[13]  # meters
                baro_alt = s[7]  # meters
                heading = s[10] or 0
                speed_ms = s[9] or 0

                if lat is None or lon is None:
                    continue

                alt_m = geo_alt if geo_alt is not None else (baro_alt or 0)
                alt_ft = int(alt_m * 3.28084) if alt_m is not None else 0
                speed_kt = int(speed_ms * 1.94384)

                flights.append(
                    {
                        "flight_number": callsign or icao24 or "UNKNOWN",
                        "callsign": callsign or None,
                        "icao24": icao24 or None,
                        "airline": _airline_from_callsign(callsign),
                        "aircraft_family": "UNKNOWN",
                        "lat": float(lat),
                        "lon": float(lon),
                        "alt_ft": alt_ft,
                        "heading": int(heading),
                        "speed_kt": speed_kt,
                        "status": "unknown",
                        "origin": "unknown",
                        "origin_icao": None,
                        "origin_iata": None,
                        "origin_city": None,
                        "origin_name": None,
                        "destination": "unknown",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(data.get("time", time.time()))),
                    }
                )

            return flights, ProviderMeta(
                provider="opensky",
                mode=FlightMode.OPENSKY.value,
                credentials_ok=True,
                details={"count": len(flights), "radius_km": radius, "center": center_point},
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return [], ProviderMeta(
                provider="opensky",
                mode=FlightMode.OPENSKY.value,
                error=str(exc),
                credentials_ok=True,
            )


class FR24PlaceholderProvider:
    """Stub for Flightradar24/FR24 Explorer API. Implement when key is available."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("FR24_API_KEY")

    def get_flights(
        self,
        center: Optional[Tuple[float, float]] = None,
        radius_km: float = DEFAULT_RADIUS_KM,
        **_: Any,
    ) -> Tuple[List[Dict[str, Any]], ProviderMeta]:
        if not self.api_key:
            return [], ProviderMeta(
                provider="fr24",
                mode=FlightMode.FR24.value,
                error="FR24 API key not configured",
                credentials_ok=False,
            )
        # Placeholder until paid API access is wired up.
        return [], ProviderMeta(
            provider="fr24",
            mode=FlightMode.FR24.value,
            credentials_ok=True,
            details={"center": center, "radius_km": radius_km, "todo": "implement FR24 REST call"},
        )


def get_flight_provider(
    mode: str,
    snapshot_dir: Optional[Path] = None,
    interval_seconds: int = 5,
    opensky_client_id: Optional[str] = None,
    opensky_client_secret: Optional[str] = None,
    fr24_api_key: Optional[str] = None,
    center: Tuple[float, float] = DEFAULT_CENTER,
    radius_km: float = DEFAULT_RADIUS_KM,
):
    """Factory to pick the right provider based on mode string."""
    normalized = (mode or "").upper()
    if normalized == FlightMode.SANDBOX.value:
        return SandboxReplayProvider(
            snapshot_dir=snapshot_dir or Path("sandbox_feed"),
            interval_seconds=interval_seconds,
            center=center,
        )
    if normalized in (FlightMode.LIVE.value, FlightMode.OPENSKY.value):
        return OpenSkyLiveProvider(
            center=center,
            radius_km=radius_km,
            client_id=opensky_client_id,
            client_secret=opensky_client_secret,
        )
    if normalized == FlightMode.FR24.value:
        return FR24PlaceholderProvider(api_key=fr24_api_key)
    # default fallback
    return SandboxReplayProvider(
        snapshot_dir=snapshot_dir or Path("sandbox_feed"),
        interval_seconds=interval_seconds,
        center=center,
    )


__all__ = [
    "FlightMode",
    "SandboxReplayProvider",
    "OpenSkyLiveProvider",
    "FR24PlaceholderProvider",
    "get_flight_provider",
    "haversine_km",
    "DEFAULT_CENTER",
    "DEFAULT_RADIUS_KM",
]
