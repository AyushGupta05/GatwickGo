Aircraft Radar Demo
===================

What you get
- Gemini-based airline + family classifier (burst voting).
- Replayable sandbox feed around LGW with 15 moving flights (t0–t25).
- Live provider hooks (OpenSky ready, FR24 stub) behind a common API.
- Matcher that fuses classification + location to pick the most likely flight.

Project Structure
```
Gatwick-GO/
├── backend/               # Python Flask backend
│   ├── app.py            # Main Flask application
│   ├── config.py         # Configuration (paths, settings)
│   ├── camera_burst.py   # Burst capture logic
│   ├── gemini_classifier.py  # Gemini API integration
│   ├── flight_feed.py    # Flight data providers
│   ├── flight_matcher.py # Flight matching algorithm
│   ├── enrichment.py     # Data enrichment
│   ├── aircraft_detection_pipeline.py
│   ├── templates/        # Flask HTML templates
│   ├── static/          # Static assets (CSS, JS, model UI)
│   ├── sandbox_feed/    # Test flight data snapshots
│   ├── tools/           # Utility scripts
│   ├── testimages/      # Test images
│   └── requirements.txt # Python dependencies
│
└── frontend/             # Next.js frontend (optional)
    └── gatwick-go/      # Next.js project
```

Installation & Setup
====================

1. Install backend dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```

2. Set environment variables:
   - `GEMINI_API_KEY` (required): Get from https://aistudio.google.com/app/apikeys
   - Optional: `OPENSKY_USERNAME`, `OPENSKY_PASSWORD` (for live flight data)

3. Run the application:
   ```
   cd backend
   python app.py
   ```
   Then open http://localhost:5000

Configuration
=============

Edit `backend/config.py` to customize:
- Airport location and search radius
- Burst capture settings
- Flight feed mode (SANDBOX, LIVE, OPENSKY)
- Confidence thresholds

API Quick Reference
===================

- POST `/api/classify`
  - body: `{ images: [...base64...], mode: "SANDBOX" | "OPENSKY" | "FR24", location: {lat, lon, radius_km}, match: true }`
  - returns: classifier result + `match` (best flight) + `feed` metadata.

Flight Feed Modes
================

- **SANDBOX** (default): Uses test snapshots from `backend/sandbox_feed/`; updates every 5 seconds
- **OPENSKY**: Connects to OpenSky Network (requires credentials)
- **FR24**: FlightRadar24 stub (ready for paid API integration)

Regenerate Sandbox Feed
=======================

```
cd backend
python tools/generate_sandbox_feed.py
```

Testing
=======

Test local images with the classifier:
```
cd backend
python test_local_images.py
python test_local_images.py --dir custom_folder
```

Verify system setup:
```
cd backend
python test_system.py
```
