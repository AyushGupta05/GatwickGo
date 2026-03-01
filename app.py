"""
Flask web server for Aircraft Detection System.

Serves a simple web interface with webcam access, burst photo classification,
and optional flight matching (sandbox replay or live provider).
"""

import base64
import os
from pathlib import Path

from flask import Flask, render_template, request, jsonify

from camera_burst import classify_burst_consensus

# Import config module (safer than importing many names that may change)
import config

from flight_feed import get_flight_provider, haversine_km
from flight_matcher import match_best_flight

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    """Serve the main page with webcam interface."""
    return render_template(
        "index.html",
        default_observer_lat=config.AIRPORT_COORDS[0],
        default_observer_lon=config.AIRPORT_COORDS[1],
        default_radius_km=config.DEFAULT_SEARCH_RADIUS_KM,
    )


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
        print("⚠️  WARNING: GEMINI_API_KEY environment variable not set!")
        print("PowerShell (persistent): setx GEMINI_API_KEY \"your-api-key\"")
        print("PowerShell (current session): $env:GEMINI_API_KEY=\"your-api-key\"")
        print()

    print("=" * 60)
    print("🚀 Aircraft Detection Web Server")
    print("=" * 60)
    print()
    print("🌐 Starting server...")
    print("📱 Open http://localhost:5000 in your browser")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    print("=" * 60)

    # Run Flask development server
    app.run(debug=True, port=5000, host="127.0.0.1")