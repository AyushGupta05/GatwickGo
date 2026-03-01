"""
Flask web server for Aircraft Detection System.

Serves a simple web interface with webcam access, burst photo classification,
and optional flight matching (sandbox replay or live provider).
"""

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pathlib
from typing import Any, Dict, Optional

from flask import Flask, redirect, render_template, request, jsonify, send_from_directory

from camera_burst import classify_burst_consensus

# Import config module (safer than importing many names that may change)
import config

from flight_feed import get_flight_provider, haversine_km
from flight_matcher import match_best_flight
from enrichment import enrich_match, get_fact_for_family
from supabase_client import supabase_as_user

# Optional: modern google.genai client for dev image generation
try:
    from google import genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"), static_folder=os.path.join(os.path.dirname(__file__), "static"))

# Path to the exported model UI (Next.js static build)
MODEL_STATIC_DIR = Path(app.static_folder) / "model"
GEMINI_CAPTURE_POINTS = 50
MIN_QUALIFYING_LIVE_MATCH_SCORE = 0.5
USER_PROGRESS_SQL_HINT = (
    "Apply backend/sql/20260301_user_progress_policies.sql to enable "
    "authenticated read/write access for public.user_stats and public.profiles."
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """Parse a Bearer token from Authorization header."""
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _jwt_subject(token: str) -> Optional[str]:
    """Return the user id (sub) from a Supabase JWT without verifying signature."""
    try:
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        return payload.get("sub") or payload.get("user_id") or payload.get("id")
    except Exception:
        return None


def _merge_unique_strings(existing: Any, new_value: Optional[str]) -> list[str]:
    """Return a stable, de-duplicated string list."""
    merged: list[str] = []
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, str) and item and item not in merged:
                merged.append(item)

    if new_value and new_value not in {"", "UNKNOWN"} and new_value not in merged:
        merged.append(new_value)

    return merged


def _first_row(response: Any) -> Optional[Dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data
    return None


def _best_flight_from_match(match: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    best = (match or {}).get("best") or {}
    flight = best.get("flight") or {}
    return flight if isinstance(flight, dict) else {}


def _error_text(error: Any) -> str:
    if isinstance(error, str):
        return error
    return str(error or "")


def _is_missing_table_error(error: Any, table_name: str) -> bool:
    text = _error_text(error)
    return "PGRST205" in text and table_name in text


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _promo_code_from_claim_id(claim_id: Any) -> Optional[str]:
    if not isinstance(claim_id, str) or not claim_id:
        return None
    compact = claim_id.replace("-", "").upper()
    return compact[:10] if compact else None


def _normalized_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().casefold()


def _best_match_score(match: Optional[Dict[str, Any]]) -> float:
    best = (match or {}).get("best") or {}
    if not isinstance(best, dict):
        return 0.0
    return max(0.0, min(1.0, _safe_float(best.get("score"), 0.0)))


def _is_qualifying_live_match(match: Optional[Dict[str, Any]], effective_mode: str) -> bool:
    return _best_match_score(match) > MIN_QUALIFYING_LIVE_MATCH_SCORE


def _resolve_family_metadata(
    supabase_client,
    family_code: Optional[str],
) -> tuple[Dict[str, Any], Optional[str]]:
    """
    Resolve family lookup metadata when possible without making inserts depend on it.
    """
    if not isinstance(family_code, str):
        return {"code": None, "display_name": None, "rarity": None}, None

    normalized = family_code.strip()
    if not normalized or normalized == "UNKNOWN":
        return {"code": None, "display_name": None, "rarity": None}, None

    try:
        family_resp = (
            supabase_client
            .table("aircraft_families")
            .select("code, display_name, rarity")
            .eq("code", normalized)
            .limit(1)
            .execute()
        )
        if getattr(family_resp, "error", None):
            return (
                {"code": normalized, "display_name": normalized, "rarity": None},
                f"Failed to read aircraft_families for `{normalized}`: {family_resp.error}",
            )
        row = _first_row(family_resp)
        if row:
            return {
                "code": row.get("code") or normalized,
                "display_name": row.get("display_name") or normalized,
                "rarity": row.get("rarity"),
            }, None
        return (
            {"code": normalized, "display_name": normalized, "rarity": None},
            f"Aircraft family `{normalized}` was not found in aircraft_families.code; storing raw family code.",
        )
    except Exception as exc:
        return (
            {"code": normalized, "display_name": normalized, "rarity": None},
            f"Failed to read aircraft_families for `{normalized}`: {exc}",
        )


def _build_collection_dedupe_key(
    user_id: str,
    best_flight: Dict[str, Any],
    detected_model: Optional[str],
    family_code: Optional[str],
) -> str:
    identity = (
        best_flight.get("icao24")
        or best_flight.get("flight_number")
        or best_flight.get("callsign")
        or "unknown-flight"
    )
    model_key = detected_model or "unknown-model"
    family_key = family_code or "unknown-family"
    return f"{user_id}|{identity}|{model_key}|{family_key}"


def _resolve_reward_row(
    supabase_client,
    reward_id: Optional[int] = None,
    reward_code: Optional[str] = None,
    reward_title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    active_rewards_resp = (
        supabase_client
        .table("rewards")
        .select("id, code, title, description, cost_points, is_active, created_at")
        .execute()
    )
    rewards_error = getattr(active_rewards_resp, "error", None)
    if rewards_error:
        raise RuntimeError(rewards_error)

    raw_rewards = getattr(active_rewards_resp, "data", None) or []
    rewards: list[Dict[str, Any]] = []
    if isinstance(raw_rewards, list):
        for row in raw_rewards:
            if not isinstance(row, dict):
                continue
            if row.get("is_active") is False:
                continue
            rewards.append(row)

    if reward_id and reward_id > 0:
        for row in rewards:
            if _safe_int(row.get("id"), 0) == reward_id:
                return row

    normalized_code = _normalized_text(reward_code)
    if normalized_code:
        for row in rewards:
            if _normalized_text(row.get("code")) == normalized_code:
                return row

    normalized_title = _normalized_text(reward_title)
    if normalized_title:
        for row in rewards:
            if _normalized_text(row.get("title")) == normalized_title:
                return row

    return None


def _read_user_stats_row(
    supabase_client,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    stats_resp = (
        supabase_client
        .table("user_stats")
        .select("user_id, points_total, collected_families, updated_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    stats_error = getattr(stats_resp, "error", None)
    if stats_error:
        raise RuntimeError(
            f"Failed to read public.user_stats: {stats_error}. {USER_PROGRESS_SQL_HINT}"
    )
    return _first_row(stats_resp)


def _award_capture_progress_via_tables(
    supabase_client,
    user_id: str,
    points_awarded: int,
    family_code: Optional[str],
) -> Dict[str, Any]:
    existing_row = _read_user_stats_row(supabase_client, user_id)
    current_points_total = int(existing_row.get("points_total") or 0) if existing_row else 0
    expected_points_total = current_points_total + points_awarded
    expected_families = _merge_unique_strings(
        existing_row.get("collected_families") if existing_row else [],
        family_code,
    )

    stats_payload = {
        "points_total": expected_points_total,
        "collected_families": expected_families,
        "updated_at": _utc_now_iso(),
    }
    if existing_row:
        update_resp = (
            supabase_client
            .table("user_stats")
            .update(stats_payload)
            .eq("user_id", user_id)
            .execute()
        )
        if getattr(update_resp, "error", None):
            raise RuntimeError(f"{update_resp.error}. {USER_PROGRESS_SQL_HINT}")
    else:
        insert_resp = (
            supabase_client
            .table("user_stats")
            .insert({
                "user_id": user_id,
                **stats_payload,
            })
            .execute()
        )
        if getattr(insert_resp, "error", None):
            raise RuntimeError(f"{insert_resp.error}. {USER_PROGRESS_SQL_HINT}")

    persisted_stats_row = _read_user_stats_row(supabase_client, user_id)
    if not persisted_stats_row:
        raise RuntimeError(
            "public.user_stats write did not persist or is hidden by row-level security. "
            + USER_PROGRESS_SQL_HINT
        )

    next_points_total = _safe_int(
        persisted_stats_row.get("points_total"),
        expected_points_total,
    )
    next_families = (
        persisted_stats_row.get("collected_families")
        if isinstance(persisted_stats_row.get("collected_families"), list)
        else expected_families
    )
    if next_points_total != expected_points_total:
        raise RuntimeError(
            "public.user_stats write completed without persisting the expected points_total. "
            + USER_PROGRESS_SQL_HINT
        )

    return {
        "points_total": next_points_total,
        "collected_families": next_families,
    }


def _award_capture_progress(
    supabase_client,
    user_id: str,
    points_awarded: int,
    family_code: Optional[str],
) -> Dict[str, Any]:
    rpc_resp = (
        supabase_client
        .rpc(
            "award_capture_progress",
            {
                "p_points": points_awarded,
                "p_family_code": family_code,
            },
        )
        .execute()
    )
    rpc_error = getattr(rpc_resp, "error", None)
    if rpc_error:
        rpc_error_text = _error_text(rpc_error)
        if "public.award_capture_progress" in rpc_error_text or "PGRST202" in rpc_error_text:
            return _award_capture_progress_via_tables(
                supabase_client=supabase_client,
                user_id=user_id,
                points_awarded=points_awarded,
                family_code=family_code,
            )
        raise RuntimeError(
            f"Failed to update public.user_stats via award_capture_progress: {rpc_error}. "
            + USER_PROGRESS_SQL_HINT
        )

    progress_row = _first_row(rpc_resp)
    if not progress_row:
        raise RuntimeError(
            "public.award_capture_progress returned no data. "
            + USER_PROGRESS_SQL_HINT
        )

    returned_user_id = progress_row.get("user_id")
    if isinstance(returned_user_id, str) and returned_user_id and returned_user_id != user_id:
        raise RuntimeError("public.award_capture_progress returned an unexpected user_id.")

    points_total = _safe_int(progress_row.get("points_total"), points_awarded)
    collected_families = progress_row.get("collected_families")
    if not isinstance(collected_families, list):
        collected_families = _merge_unique_strings([], family_code)

    return {
        "points_total": points_total,
        "collected_families": collected_families,
    }


def _persist_capture_for_user(
    supabase_client,
    user_id: str,
    result: Dict[str, Any],
    match: Optional[Dict[str, Any]],
    feed: Optional[Dict[str, Any]],
    enrichment: Optional[Dict[str, Any]],
    observer: tuple[float, float],
    radius_km: float,
    frames_processed: int,
    requested_mode: str,
    effective_mode: str,
    fallback_reason: Optional[str],
) -> Dict[str, Any]:
    """
    Award flat points for every classify call and persist Gemini capture data
    for the user, with live-match metadata when available.
    """
    best_flight = _best_flight_from_match(match)
    match_score = _best_match_score(match)
    qualifying_live_match = _is_qualifying_live_match(match, effective_mode)

    captured_airline = result.get("airline")
    if not isinstance(captured_airline, str) or not captured_airline or captured_airline == "UNKNOWN":
        captured_airline = str(best_flight.get("airline") or "UNKNOWN")

    captured_model = result.get("aircraft_model")
    if not isinstance(captured_model, str) or not captured_model or captured_model == "UNKNOWN":
        captured_model = result.get("aircraft_family")
    if not isinstance(captured_model, str) or not captured_model:
        captured_model = str(best_flight.get("aircraft_family") or "UNKNOWN")

    family_metadata, family_warning = _resolve_family_metadata(
        supabase_client=supabase_client,
        family_code=result.get("aircraft_family") or best_flight.get("aircraft_family"),
    )
    resolved_family_code = family_metadata.get("code")

    points_awarded = GEMINI_CAPTURE_POINTS
    next_points_total = 0
    next_families: list[str] = []
    storage_warnings: list[str] = []
    if family_warning:
        storage_warnings.append(family_warning)
    collection_saved = False
    already_in_collection = False
    collection_entry_id = None
    collection_item_key = None

    progress_info = _award_capture_progress(
        supabase_client=supabase_client,
        user_id=user_id,
        points_awarded=points_awarded,
        family_code=resolved_family_code,
    )
    next_points_total = _safe_int(progress_info.get("points_total"), 0)
    next_families = (
        progress_info.get("collected_families")
        if isinstance(progress_info.get("collected_families"), list)
        else []
    )

    collection_item_key = _build_collection_dedupe_key(
        user_id=user_id,
        best_flight=best_flight,
        detected_model=captured_model,
        family_code=resolved_family_code,
    )
    existing_collection_resp = (
        supabase_client
        .table("user_aircraft_collection")
        .select("id")
        .eq("user_id", user_id)
        .eq("dedupe_key", collection_item_key)
        .limit(1)
        .execute()
    )
    collection_error = getattr(existing_collection_resp, "error", None)
    if collection_error:
        if _is_missing_table_error(collection_error, "public.user_aircraft_collection"):
            storage_warnings.append(
                "Supabase table public.user_aircraft_collection is missing. Apply backend/sql/20260301_live_match_collection.sql to persist Gemini capture items."
            )
        else:
            raise RuntimeError(collection_error)
    else:
        existing_collection_row = _first_row(existing_collection_resp)
        if existing_collection_row:
            already_in_collection = True
            collection_entry_id = existing_collection_row.get("id")
        else:
            collection_payload: Dict[str, Any] = {
                "user_id": user_id,
                "dedupe_key": collection_item_key,
                "flight_number": best_flight.get("flight_number") or best_flight.get("callsign"),
                "airline": captured_airline,
                "detected_model": captured_model,
                "aircraft_family_code": resolved_family_code,
                "aircraft_family_display_name": family_metadata.get("display_name") or resolved_family_code,
                "family_rarity": family_metadata.get("rarity"),
                "match_score": match_score,
                "source_mode": effective_mode,
                "captured_at": _utc_now_iso(),
                "metadata": {
                    "confidence": result.get("confidence"),
                    "model_confidence": result.get("model_confidence"),
                    "family_confidence": result.get("family_confidence"),
                    "phase": result.get("phase"),
                    "phase_confidence": result.get("phase_confidence"),
                    "icao24": best_flight.get("icao24"),
                    "qualifying_live_match": qualifying_live_match,
                    "observer": {"lat": observer[0], "lon": observer[1], "radius_km": radius_km},
                    "frames_processed": frames_processed,
                    "requested_mode": requested_mode,
                    "effective_mode": effective_mode,
                    "fallback_reason": fallback_reason,
                },
            }
            collection_payload = {k: v for k, v in collection_payload.items() if v is not None}
            collection_insert_resp = (
                supabase_client
                .table("user_aircraft_collection")
                .insert(collection_payload)
                .execute()
            )
            insert_error = getattr(collection_insert_resp, "error", None)
            if insert_error:
                if _is_missing_table_error(insert_error, "public.user_aircraft_collection"):
                    storage_warnings.append(
                        "Supabase table public.user_aircraft_collection is missing. Apply backend/sql/20260301_live_match_collection.sql to persist Gemini capture items."
                    )
                else:
                    raise RuntimeError(insert_error)
            else:
                inserted_row = _first_row(collection_insert_resp)
                collection_entry_id = inserted_row.get("id") if inserted_row else None
                collection_saved = True

    return {
        "qualifying_live_match": qualifying_live_match,
        "match_score": match_score,
        "captured_airline": captured_airline,
        "captured_model": captured_model,
        "captured_family_code": resolved_family_code,
        "captured_family_display_name": family_metadata.get("display_name"),
        "points_awarded": points_awarded,
        "points_total": next_points_total,
        "collected_families": next_families,
        "collection_saved": collection_saved,
        "already_in_collection": already_in_collection,
        "collection_entry_id": collection_entry_id,
        "collection_item_key": collection_item_key,
        "storage_warnings": storage_warnings,
    }


@app.route("/")
def index():
    """Send the root URL to the Gemini capture page."""
    return redirect("/model")


@app.route("/model")
def model_capture_page():
    """Serve the Gemini-powered capture page after ticket validation."""
    return render_template(
        "index.html",
        default_observer_lat=config.AIRPORT_COORDS[0],
        default_observer_lon=config.AIRPORT_COORDS[1],
        default_radius_km=config.DEFAULT_SEARCH_RADIUS_KM,
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY"),
    )


@app.route("/home")
@app.route("/camera")
@app.route("/collection")
@app.route("/shop")
@app.route("/signin")
@app.route("/tickets")
@app.route("/auth/<path:subpath>")
@app.route("/_next/<path:subpath>")
def model_ui(subpath: str = ""):
    """
    Serve the exported model UI on clean top-level routes.
    Handles page routes like /home and static assets under /_next.
    """
    root = MODEL_STATIC_DIR.resolve()

    # Normalize and guard against traversal
    safe_sub = request.path.lstrip("/")
    if ".." in Path(safe_sub).parts:
        return jsonify({"error": "Invalid path"}), 400

    requested = root / safe_sub

    # If the exact path exists (files under _next, static assets, etc.)
    if requested.exists() and requested.is_file():
        return send_from_directory(str(root), requested.relative_to(root).as_posix())

    # Route-specific HTML fallback (e.g., /camera -> camera.html)
    html_candidate = root / f"{safe_sub}.html"
    if html_candidate.exists():
        return send_from_directory(str(root), html_candidate.relative_to(root).as_posix())

    # Directory index.html (safety)
    if requested.is_dir() and (requested / "index.html").exists():
        return send_from_directory(str(root), (requested / "index.html").relative_to(root).as_posix())

    # Fallback 404
    if (root / "404.html").exists():
        return send_from_directory(str(root), "404.html"), 404

    return jsonify({"error": "Not found"}), 404


@app.route("/api/classify", methods=["POST"])
def classify_endpoint():
    """
    Classify an aircraft image.

    Expects JSON with:
    {
        "images": [
            {"data": "data:image/jpeg;base64,..."},
            ...
        ],
        "mode": "SANDBOX" | "LIVE" | "OPENSKY",    # optional (default from config)
        "location": {"lat": 51.15, "lon": -0.18, "radius_km": 30},  # optional, defaults to LGW
        "match": true | false  # optional, default true
    }

    Returns:
    {
        "success": true,
        "result": {
            "airline": "easyJet",
            "aircraft_family": "A320-family",
            "confidence": 0.87,
            "uncertainty": 0.13,
            "cues": [...],
            "votes": [...]
        },
        "frames_processed": 3,
        "feed": {...},     # provider metadata
        "match": {...}     # best match + candidates
    }
    """
    try:
        token = _extract_bearer_token(request.headers.get("Authorization"))
        if not token:
            return jsonify({"success": False, "error": "Authorization bearer token required"}), 401

        try:
            supabase_client = supabase_as_user(token)
        except Exception as exc:
            return jsonify({"success": False, "error": f"Supabase configuration error: {exc}"}), 500

        user_id = _jwt_subject(token)
        if not user_id:
            return jsonify({"success": False, "error": "Invalid Supabase token"}), 401

        data = request.get_json()
        if not data or "images" not in data:
            return jsonify({"success": False, "error": "No images provided"}), 400

        mode = str(data.get("mode", config.FLIGHT_MODE)).upper()
        location = data.get("location") or {}
        observer = None
        radius_km = config.DEFAULT_SEARCH_RADIUS_KM
        fallback_reason = None

        # Read optional location overrides
        if isinstance(location, dict):
            lat = location.get("lat")
            lon = location.get("lon")
            if lat is not None and lon is not None:
                try:
                    observer = (float(lat), float(lon))
                except Exception:
                    observer = None
            if "radius_km" in location:
                try:
                    radius_km = float(location.get("radius_km", radius_km))
                except Exception:
                    radius_km = config.DEFAULT_SEARCH_RADIUS_KM

        if observer is None:
            observer = config.AIRPORT_COORDS

        do_match = bool(data.get("match", True))
        requested_mode = mode
        effective_mode = mode

        images = data["images"]
        if not isinstance(images, list) or len(images) == 0:
            return jsonify({"success": False, "error": "Empty image list"}), 400

        # Convert data URIs to bytes
        image_bytes_list = []
        for img_data in images:
            if isinstance(img_data, dict) and "data" in img_data:
                data_uri = img_data["data"]
            else:
                data_uri = img_data

            # Parse base64 data from data URI
            if "base64," in data_uri:
                b64_str = data_uri.split("base64,")[1]
            else:
                b64_str = data_uri

            try:
                img_bytes = base64.b64decode(b64_str)
                image_bytes_list.append(img_bytes)
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to decode image: {str(e)}"}), 400

        if not image_bytes_list:
            return jsonify({"success": False, "error": "No valid images"}), 400

        # Fuse burst frames with sharpness-weighted voting to handle blur/uncertainty
        result = classify_burst_consensus(
            image_bytes_list,
            topk=False,
            top_m=min(3, len(image_bytes_list)),
        )

        response_payload = {
            "success": True,
            "result": result,
            "frames_processed": len(image_bytes_list),
            "mode": requested_mode,
        }

        if do_match:
            try:
                # Live gating radius: if not in config, default to 30km
                live_gate_km = getattr(config, "LIVE_GATING_RADIUS_KM", 30)

                # Live gating: only allow OPENSKY when near LGW
                if requested_mode in ("OPENSKY", "LIVE"):
                    dist = haversine_km(
                        observer[0], observer[1],
                        config.AIRPORT_COORDS[0], config.AIRPORT_COORDS[1]
                    )
                    if dist > live_gate_km:
                        effective_mode = "SANDBOX"
                        fallback_reason = "outside_lgw_radius"
                    else:
                        effective_mode = "OPENSKY"

                # Build provider kwargs in a backward-compatible way
                provider_kwargs = dict(
                    snapshot_dir=Path(config.SANDBOX_SNAPSHOT_DIR),
                    interval_seconds=config.SANDBOX_SNAPSHOT_INTERVAL,
                    center=observer,
                    radius_km=radius_km,
                )

                # Your current config.py exposes OPENSKY_USERNAME / OPENSKY_PASSWORD
                opensky_user = getattr(config, "OPENSKY_USERNAME", None)
                opensky_pass = getattr(config, "OPENSKY_PASSWORD", None)

                # Some implementations expect client_id/client_secret instead.
                # We'll try both styles safely.
                provider = None
                try:
                    provider = get_flight_provider(
                        effective_mode,
                        opensky_username=opensky_user,
                        opensky_password=opensky_pass,
                        **provider_kwargs,
                    )
                except TypeError:
                    # Fallback naming
                    provider = get_flight_provider(
                        effective_mode,
                        opensky_client_id=opensky_user,
                        opensky_client_secret=opensky_pass,
                        **provider_kwargs,
                    )

                anchor_to = observer if effective_mode == "SANDBOX" else None
                flights, meta = provider.get_flights(center=observer, radius_km=radius_km, anchor_to=anchor_to)

                response_payload["match"] = match_best_flight(result, flights, observer=observer)
                response_payload["feed"] = {
                    "requested_mode": requested_mode,
                    "effective_mode": effective_mode,
                    "provider": getattr(meta, "provider", None),
                    "mode": getattr(meta, "mode", None),
                    "snapshot": getattr(meta, "snapshot", None),
                    "snapshot_time": getattr(meta, "snapshot_time", None),
                    "error": getattr(meta, "error", None),
                    "credentials_ok": getattr(meta, "credentials_ok", None),
                    "details": getattr(meta, "details", None),
                    "flight_count": len(flights),
                    "fallback_reason": fallback_reason,
                    "gate_radius_km": live_gate_km if requested_mode in ("OPENSKY", "LIVE") else None,
                }
                response_payload["observer"] = {
                    "lat": observer[0],
                    "lon": observer[1],
                    "radius_km": radius_km,
                }
                response_payload["feed"]["observer"] = response_payload["observer"]

            except Exception as exc:
                response_payload["match"] = None
                response_payload["feed"] = {"mode": mode, "error": str(exc)}

        # Enrichment layer (origin + fact)
        try:
            response_payload["enrichment"] = enrich_match(result, response_payload.get("match"), response_payload.get("feed"))
        except Exception as exc:
            response_payload["enrichment"] = {"origin": None, "fact": None, "error": str(exc)}

        try:
            persist_info = _persist_capture_for_user(
                supabase_client=supabase_client,
                user_id=user_id,
                result=result,
                match=response_payload.get("match"),
                feed=response_payload.get("feed"),
                enrichment=response_payload.get("enrichment"),
                observer=observer,
                radius_km=radius_km,
                frames_processed=len(image_bytes_list),
                requested_mode=requested_mode,
                effective_mode=effective_mode,
                fallback_reason=fallback_reason,
            )
            if persist_info.get("captured_airline"):
                response_payload["captured_airline"] = persist_info["captured_airline"]
            if persist_info.get("captured_model"):
                response_payload["captured_model"] = persist_info["captured_model"]
            if persist_info.get("captured_family_code"):
                response_payload["captured_family_code"] = persist_info["captured_family_code"]
            if persist_info.get("captured_family_display_name"):
                response_payload["captured_family_display_name"] = persist_info["captured_family_display_name"]
            response_payload["qualifying_live_match"] = bool(persist_info.get("qualifying_live_match"))
            response_payload["match_score"] = persist_info.get("match_score")
            if persist_info.get("points_awarded") is not None:
                response_payload["points_awarded"] = persist_info["points_awarded"]
            if persist_info.get("points_total") is not None:
                response_payload["points_total"] = persist_info["points_total"]
            response_payload["collection_saved"] = bool(persist_info.get("collection_saved"))
            response_payload["already_in_collection"] = bool(persist_info.get("already_in_collection"))
            if persist_info.get("collection_entry_id"):
                response_payload["collection_entry_id"] = persist_info["collection_entry_id"]
            if persist_info.get("collection_item_key"):
                response_payload["collection_item_key"] = persist_info["collection_item_key"]
            if persist_info.get("storage_warnings"):
                response_payload["storage_warnings"] = persist_info["storage_warnings"]
        except Exception as exc:
            storage_warnings = response_payload.get("storage_warnings")
            if not isinstance(storage_warnings, list):
                storage_warnings = []
            storage_warnings.append(
                f"Capture was classified successfully but database persistence was skipped: {exc}"
            )
            response_payload["storage_warnings"] = storage_warnings
            response_payload["points_awarded"] = GEMINI_CAPTURE_POINTS
            response_payload["captured_airline"] = (
                result.get("airline")
                if isinstance(result.get("airline"), str)
                else None
            )
            fallback_model = result.get("aircraft_model") or result.get("aircraft_family")
            if isinstance(fallback_model, str):
                response_payload["captured_model"] = fallback_model
            response_payload["collection_saved"] = False
            response_payload["already_in_collection"] = False

        return jsonify(response_payload)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    api_key_set = bool(os.getenv("GEMINI_API_KEY"))
    return jsonify({
        "status": "ok",
        "api_key_configured": api_key_set,
    })


@app.route("/api/fact", methods=["GET"])
def fact_endpoint():
    """Return a short fact for an aircraft family."""
    family = request.args.get("family")
    if not family:
        return jsonify({"success": False, "error": "family parameter required"}), 400
    fact = get_fact_for_family(family)
    if not fact:
        return jsonify({"success": False, "error": "No fact found"}), 404
    return jsonify({"success": True, "family": family, "fact": fact})


@app.route("/api/user/progress", methods=["GET"])
def user_progress_endpoint():
    """Return persisted progress for the signed-in user using the current schema."""
    token = _extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return jsonify({"success": False, "error": "Authorization bearer token required"}), 401

    try:
        supabase_client = supabase_as_user(token)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Supabase configuration error: {exc}"}), 500

    user_id = _jwt_subject(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid Supabase token"}), 401

    try:
        stats_resp = (
            supabase_client
            .table("user_stats")
            .select("user_id, points_total, collected_families, updated_at")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if getattr(stats_resp, "error", None):
            raise RuntimeError(stats_resp.error)
        stats_row = _first_row(stats_resp) or {
            "user_id": user_id,
            "points_total": 0,
            "collected_families": [],
            "updated_at": None,
        }
        collected_codes = stats_row.get("collected_families") if isinstance(stats_row.get("collected_families"), list) else []
        storage_warnings: list[str] = []

        families_resp = (
            supabase_client
            .table("aircraft_families")
            .select("code, display_name, rarity, created_at")
            .execute()
        )

        families = getattr(families_resp, "data", None) or []
        if getattr(families_resp, "error", None):
            storage_warnings.append(
                f"Could not read aircraft_families lookup table: {families_resp.error}"
            )
            families = []
        if not isinstance(families, list):
            families = []

        family_by_code: Dict[str, Dict[str, Any]] = {}
        for row in families:
            if isinstance(row, dict) and isinstance(row.get("code"), str):
                family_by_code[row["code"]] = row

        collected_family_details = []
        for code in collected_codes:
            if not isinstance(code, str):
                continue
            collected_family_details.append(
                family_by_code.get(
                    code,
                    {"code": code, "display_name": code, "rarity": None, "created_at": None},
                )
            )

        collection_entries: list[Dict[str, Any]] = []
        collection_resp = (
            supabase_client
            .table("user_aircraft_collection")
            .select("id, dedupe_key, flight_number, airline, detected_model, aircraft_family_code, aircraft_family_display_name, family_rarity, match_score, source_mode, captured_at, metadata")
            .eq("user_id", user_id)
            .limit(200)
            .execute()
        )
        collection_error = getattr(collection_resp, "error", None)
        if collection_error:
            if _is_missing_table_error(collection_error, "public.user_aircraft_collection"):
                storage_warnings.append(
                    "Supabase table public.user_aircraft_collection is missing. Apply backend/sql/20260301_live_match_collection.sql to load saved Gemini capture items."
                )
            else:
                raise RuntimeError(collection_error)
        else:
            raw_entries = getattr(collection_resp, "data", None) or []
            if isinstance(raw_entries, list):
                for row in raw_entries:
                    if not isinstance(row, dict):
                        continue
                    family_code = row.get("aircraft_family_code")
                    family_meta = family_by_code.get(family_code) if isinstance(family_code, str) else None
                    collection_entries.append({
                        **row,
                        "aircraft_family_display_name": row.get("aircraft_family_display_name")
                        or (family_meta or {}).get("display_name")
                        or family_code,
                        "family_rarity": row.get("family_rarity") or (family_meta or {}).get("rarity"),
                    })
                collection_entries.sort(key=lambda row: str(row.get("captured_at") or ""), reverse=True)

        return jsonify({
            "success": True,
            "stats": stats_row,
            "collected_family_details": collected_family_details,
            "collection_entries": collection_entries,
            "storage_warnings": storage_warnings,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": f"Failed to load user progress: {exc}"}), 500


@app.route("/api/shop", methods=["GET"])
def shop_state_endpoint():
    """Return DB-backed rewards shop state for the signed-in user."""
    token = _extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return jsonify({"success": False, "error": "Authorization bearer token required"}), 401

    try:
        supabase_client = supabase_as_user(token)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Supabase configuration error: {exc}"}), 500

    user_id = _jwt_subject(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid Supabase token"}), 401

    try:
        stats_resp = (
            supabase_client
            .table("user_stats")
            .select("user_id, points_total, collected_families, updated_at")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if getattr(stats_resp, "error", None):
            raise RuntimeError(stats_resp.error)

        stats_row = _first_row(stats_resp) or {
            "user_id": user_id,
            "points_total": 0,
            "collected_families": [],
            "updated_at": None,
        }

        rewards: list[Dict[str, Any]] = []
        reward_by_id: Dict[int, Dict[str, Any]] = {}
        storage_warnings: list[str] = []
        rewards_resp = (
            supabase_client
            .table("rewards")
            .select("id, code, title, description, cost_points, is_active, created_at")
            .execute()
        )
        rewards_error = getattr(rewards_resp, "error", None)
        if rewards_error:
            storage_warnings.append(f"Could not read rewards lookup table: {rewards_error}")
        else:
            raw_rewards = getattr(rewards_resp, "data", None) or []
            if isinstance(raw_rewards, list):
                for row in raw_rewards:
                    if not isinstance(row, dict):
                        continue
                    if row.get("is_active") is False:
                        continue
                    reward_id = _safe_int(row.get("id"), 0)
                    reward_row = {
                        "id": reward_id,
                        "code": row.get("code"),
                        "title": row.get("title") or row.get("code") or f"Reward {reward_id}",
                        "description": row.get("description") or "",
                        "cost_points": _safe_int(row.get("cost_points"), 0),
                        "is_active": bool(row.get("is_active", True)),
                        "created_at": row.get("created_at"),
                    }
                    rewards.append(reward_row)
                    reward_by_id[reward_id] = reward_row
            rewards.sort(key=lambda row: (row["cost_points"], row["id"]))

        claims: list[Dict[str, Any]] = []
        claims_resp = (
            supabase_client
            .table("reward_claims")
            .select("id, reward_id, claimed_at, status")
            .eq("user_id", user_id)
            .limit(200)
            .execute()
        )
        claims_error = getattr(claims_resp, "error", None)
        if claims_error:
            if _is_missing_table_error(claims_error, "public.reward_claims"):
                storage_warnings.append(
                    "Supabase table public.reward_claims is missing or unavailable for this user."
                )
            else:
                raise RuntimeError(claims_error)
        else:
            raw_claims = getattr(claims_resp, "data", None) or []
            if isinstance(raw_claims, list):
                for row in raw_claims:
                    if not isinstance(row, dict):
                        continue
                    reward_id = _safe_int(row.get("reward_id"), 0)
                    claims.append({
                        "id": row.get("id"),
                        "reward_id": reward_id,
                        "claimed_at": row.get("claimed_at"),
                        "status": row.get("status") or "claimed",
                        "promo_code": _promo_code_from_claim_id(row.get("id")),
                        "reward": reward_by_id.get(reward_id),
                    })
                claims.sort(key=lambda row: str(row.get("claimed_at") or ""), reverse=True)

        return jsonify({
            "success": True,
            "points_total": _safe_int(stats_row.get("points_total"), 0),
            "stats": stats_row,
            "rewards": rewards,
            "claims": claims,
            "storage_warnings": storage_warnings,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": f"Failed to load shop state: {exc}"}), 500


@app.route("/api/shop/redeem", methods=["POST"])
def shop_redeem_endpoint():
    """Redeem a reward, deducting DB-backed points and persisting the claim."""
    token = _extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return jsonify({"success": False, "error": "Authorization bearer token required"}), 401

    try:
        supabase_client = supabase_as_user(token)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Supabase configuration error: {exc}"}), 500

    user_id = _jwt_subject(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid Supabase token"}), 401

    data = request.get_json(silent=True) or {}
    reward_id = _safe_int(data.get("reward_id"), 0)
    reward_code = data.get("reward_code")
    reward_title = data.get("reward_title")
    if reward_id <= 0 and not isinstance(reward_code, str) and not isinstance(reward_title, str):
        return jsonify({"success": False, "error": "reward_id, reward_code, or reward_title is required"}), 400

    try:
        reward_row = _resolve_reward_row(
            supabase_client=supabase_client,
            reward_id=reward_id if reward_id > 0 else None,
            reward_code=reward_code if isinstance(reward_code, str) else None,
            reward_title=reward_title if isinstance(reward_title, str) else None,
        )
        if not reward_row or reward_row.get("is_active") is False:
            return jsonify({"success": False, "error": "Reward not found or inactive"}), 404

        resolved_reward_id = _safe_int(reward_row.get("id"), reward_id)

        redeem_resp = supabase_client.rpc("redeem_reward", {"p_reward_id": resolved_reward_id}).execute()
        redeem_error = getattr(redeem_resp, "error", None)
        if redeem_error:
            redeem_error_text = _error_text(redeem_error)
            if "INSUFFICIENT_POINTS" in redeem_error_text:
                return jsonify({"success": False, "error": "Not enough points to redeem this reward"}), 400
            if "public.redeem_reward" in redeem_error_text or "PGRST202" in redeem_error_text:
                return jsonify({
                    "success": False,
                    "error": "Supabase function public.redeem_reward is missing. Apply backend/sql/20260301_reward_redemption.sql.",
                }), 500
            raise RuntimeError(redeem_error)

        redeem_row = _first_row(redeem_resp)
        if not redeem_row:
            raise RuntimeError("Reward redemption returned no data")

        claim_id = redeem_row.get("claim_id") or redeem_row.get("id")
        promo_code = redeem_row.get("promo_code") or _promo_code_from_claim_id(claim_id)
        response_reward = {
            "id": resolved_reward_id,
            "code": reward_row.get("code"),
            "title": reward_row.get("title") or reward_row.get("code") or f"Reward {resolved_reward_id}",
            "description": reward_row.get("description") or "",
            "cost_points": _safe_int(reward_row.get("cost_points"), 0),
            "is_active": bool(reward_row.get("is_active", True)),
            "created_at": reward_row.get("created_at"),
        }

        return jsonify({
            "success": True,
            "points_total": _safe_int(redeem_row.get("points_total"), 0),
            "already_redeemed": bool(redeem_row.get("already_redeemed")),
            "claim": {
                "id": claim_id,
                "reward_id": _safe_int(redeem_row.get("reward_id"), resolved_reward_id),
                "claimed_at": redeem_row.get("claimed_at"),
                "status": redeem_row.get("status") or "claimed",
                "promo_code": promo_code,
                "reward": response_reward,
            },
        })
    except Exception as exc:
        return jsonify({"success": False, "error": f"Failed to redeem reward: {exc}"}), 500


# ---------------------------------------------------------------------------
# Dev-only: Gemini Nano Banana image generation for synthetic spotting frames
# ---------------------------------------------------------------------------


def _build_generation_prompt(airline: str, aircraft_family: str, scene: str, idx: int) -> str:
    angle = ["side-on", "3/4 front", "3/4 rear"][idx % 3]
    weather = {
        "final_approach": "low clouds, light haze",
        "climb_out": "morning mist, slight motion blur",
        "distant_dot": "heat shimmer, compressed pixels",
        "bad_weather": "rain streaks on phone lens, gray sky",
        "night": "airport lights, high ISO grain",
    }.get(scene, "mild haze")
    distance = ["close-up with wing detail", "mid-distance over runway", "far with full silhouette"][idx % 3]
    artifacts = "smartphone photo, slight compression, autofocus shimmer"
    return (
        f"Realistic smartphone spotting photo of a {airline} {aircraft_family} on {scene.replace('_', ' ')}; "
        f"{angle}, {distance}, {weather}, {artifacts}. Capture motion blur and atmospheric depth."
    )


def _generate_images_via_banana(airline: str, aircraft_family: str, scene: str, n: int):
    if genai is None:
        raise RuntimeError("google.genai SDK not installed")
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    model_name = "gemini-2.0-nano-banana"

    outputs = []
    for i in range(n):
        prompt = _build_generation_prompt(airline, aircraft_family, scene, i)
        resp = client.images.generate(model=model_name, prompt=prompt, n=1)
        images = getattr(resp, "images", None) or []
        if not images:
            continue
        img_bytes = images[0].image_bytes
        outputs.append({"prompt": prompt, "b64": base64.b64encode(img_bytes).decode("utf-8")})
    return outputs


@app.route("/api/dev/generate", methods=["POST"])
def dev_generate():
    if not getattr(config, "DEV_GENERATION_ENABLED", False):
        return jsonify({"success": False, "error": "Dev generation disabled"}), 403

    data = request.get_json() or {}
    airline = data.get("airline") or "unknown airline"
    family = data.get("aircraft_family") or data.get("family") or "UNKNOWN"
    scene = data.get("scene") or "final_approach"
    n = max(1, min(int(data.get("n", 1)), 6))
    save = bool(data.get("save", False))

    try:
        outputs = _generate_images_via_banana(airline, family, scene, n)
        if save and outputs:
            out_dir = pathlib.Path(getattr(config, "DEV_GENERATION_OUTPUT_DIR", "static/generated"))
            out_dir.mkdir(parents=True, exist_ok=True)
            saved = []
            for idx, item in enumerate(outputs):
                fname = f"{airline}_{family}_{scene}_{idx}.jpg".replace(" ", "_")
                (out_dir / fname).write_bytes(base64.b64decode(item["b64"]))
                saved.append(str(out_dir / fname))
            return jsonify({"success": True, "images": outputs, "saved": saved})
        return jsonify({"success": True, "images": outputs})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # Verify API key is set
    if not os.getenv("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY environment variable not set!")
        print('PowerShell (persistent): setx GEMINI_API_KEY "your-api-key"')
        print('PowerShell (current session): $env:GEMINI_API_KEY="your-api-key"')
        print()

    print("=" * 60)
    print("Aircraft Detection Web Server")
    print("=" * 60)
    print()
    print("Starting server...")
    print("Open http://localhost:5001 in your browser")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    print("=" * 60)

    # Run Flask development server
    app.run(debug=True, port=5001, host="127.0.0.1")
