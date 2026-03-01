"""
Flask web server for Aircraft Detection System.

Serves a simple web interface with webcam access, burst photo classification,
and optional flight matching (sandbox replay or live provider).
"""

import base64
import json
import os
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


def _compute_reward_points(result: Dict[str, Any], match: Optional[Dict[str, Any]]) -> int:
    """
    Simple heuristic: base points + small boost for confidence and successful match.
    Actual totals are maintained by database triggers; this is just the ledger delta.
    """
    base_points = 10
    try:
        conf = float(result.get("confidence", 0) or 0)
    except Exception:
        conf = 0
    base_points += int(round(conf * 5))
    if match and match.get("best"):
        base_points += 5
    return base_points


def _persist_sighting_to_supabase(
    supabase_client,
    user_id: Optional[str],
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
    Persist the classification pipeline outputs into Supabase tables.
    """
    sighting_row: Dict[str, Any] = {
        "observer_lat": observer[0],
        "observer_lon": observer[1],
        "radius_km": radius_km,
        "frames_processed": frames_processed,
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "fallback_reason": fallback_reason,
        "result": result,
        "match": match,
        "feed": feed,
        "enrichment": enrichment,
    }
    if user_id:
        sighting_row["user_id"] = user_id

    sighting_row = {k: v for k, v in sighting_row.items() if v is not None}

    sighting_resp = supabase_client.table("sightings").insert(sighting_row).execute()
    if getattr(sighting_resp, "error", None):
        raise RuntimeError(sighting_resp.error)
    sighting_data = getattr(sighting_resp, "data", None) or []
    sighting_id = sighting_data[0].get("id") if sighting_data else None

    classification_row: Dict[str, Any] = {
        "sighting_id": sighting_id,
        "airline": result.get("airline"),
        "aircraft_family": result.get("aircraft_family"),
        "confidence": result.get("confidence"),
        "uncertainty": result.get("uncertainty"),
        "votes": result.get("votes"),
        "cues": result.get("cues"),
    }
    classification_row = {k: v for k, v in classification_row.items() if v is not None}
    supabase_client.table("sighting_classifications").insert(classification_row).execute()

    if match and match.get("best"):
        match_row: Dict[str, Any] = {
            "sighting_id": sighting_id,
            "best": match.get("best"),
            "candidates": match.get("candidates"),
            "searched": match.get("searched"),
            "mode": (feed or {}).get("effective_mode") or effective_mode,
        }
        match_row = {k: v for k, v in match_row.items() if v is not None}
        supabase_client.table("sighting_matches").insert(match_row).execute()

    points_awarded = _compute_reward_points(result, match)
    reward_row: Dict[str, Any] = {
        "sighting_id": sighting_id,
        "points": points_awarded,
        "reason": "sighting_classified",
    }
    if user_id:
        reward_row["user_id"] = user_id
    reward_row = {k: v for k, v in reward_row.items() if v is not None}
    supabase_client.table("reward_ledger").insert(reward_row).execute()

    return {"sighting_id": sighting_id, "points_awarded": points_awarded}


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

        # Persist to Supabase (best-effort; classification response is still returned)
        try:
            persist_info = _persist_sighting_to_supabase(
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
            if persist_info.get("sighting_id"):
                response_payload["sighting_id"] = persist_info["sighting_id"]
            if persist_info.get("points_awarded") is not None:
                response_payload["points_awarded"] = persist_info["points_awarded"]
        except Exception as exc:
            response_payload["storage_error"] = str(exc)

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
