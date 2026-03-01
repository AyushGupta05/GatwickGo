Aircraft Radar Demo
===================

What you get
- Gemini-based airline + family classifier (burst voting).
- Replayable sandbox feed around LGW with 15 moving flights (t0–t25).
- Live provider hooks (OpenSky ready, FR24 stub) behind a common API.
- Matcher that fuses classification + location to pick the most likely flight.

Run it
1) Install deps: `pip install -r requirements.txt`
2) Set keys:
   - `GEMINI_API_KEY` (required)
   - Optional live: `OPENSKY_CLIENT_ID`, `OPENSKY_CLIENT_SECRET` (or `FR24_API_KEY`)
3) Start: `python app.py` then open http://localhost:5000

API quick reference
- POST `/api/classify`
  - body: `{ images: [...base64...], mode: "SANDBOX" | "OPENSKY" | "FR24", location: {lat, lon, radius_km}, match: true }`
  - returns: classifier result + `match` (best flight) + `feed` metadata.

Switching feeds
- Default mode is SANDBOX (uses `sandbox_feed/` snapshots; updates every 5s).
- Pass `mode: "LIVE"` or set `FLIGHT_MODE` in `config.py` to hit OpenSky (needs creds).
- FR24 stub is wired but returns empty until a paid API call is added.

Customising the sandbox
- Snapshots live in `sandbox_feed/`; regenerate with `python tools/generate_sandbox_feed.py`.
- Edit `config.py` for interval, search radius, or home airport coords.
