# Gatwick-GO Project Structure

This document explains the reorganized project structure after integrating the imported model.

## Directory Layout

```
Gatwick-GO/
├── .git/                           # Git repository
├── .gitignore                      # Git ignore rules (updated for new structure)
├── README.md                       # Main project documentation
├── STRUCTURE.md                    # This file
├── start_app.sh                   # Linux/Mac startup script
├── start_app.bat                  # Windows startup script
│
├── backend/                        # Python Flask backend (main application)
│   ├── app.py                     # Flask web server (main entry point)
│   ├── config.py                  # Configuration and constants
│   ├── camera_burst.py            # Camera burst capture logic
│   ├── gemini_classifier.py       # Gemini AI integration
│   ├── flight_feed.py             # Flight data providers (SANDBOX, OPENSKY, FR24)
│   ├── flight_matcher.py          # Flight matching algorithm
│   ├── enrichment.py              # Data enrichment logic
│   ├── aircraft_detection_pipeline.py
│   ├── requirements.txt           # Python dependencies
│   │
│   ├── templates/                 # Flask HTML templates
│   │   └── index.html            # Main web interface
│   │
│   ├── static/                    # Static assets
│   │   ├── main.js               # Browser/webcam logic
│   │   ├── model/                # Exported Next.js model UI (built output)
│   │   │   ├── index.html
│   │   │   ├── camera.html
│   │   │   ├── _next/           # Next.js bundles
│   │   │   └── ...
│   │   └── generated/            # Generated images (if enabled)
│   │
│   ├── sandbox_feed/             # Test flight data snapshots
│   │   ├── t00.json
│   │   ├── t05.json
│   │   └── ...
│   │
│   ├── tools/                    # Utility scripts
│   │   └── generate_sandbox_feed.py
│   │
│   ├── testimages/              # Test images for classification
│   │
│   ├── START_WEB_APP.py         # Quick reference guide
│   ├── WEB_APP_SUMMARY.py       # Project summary
│   ├── CHEAT_SHEET.py           # Constants reference
│   ├── test_local_images.py     # Test classifier with local images
│   ├── test_system.py           # System verification script
│   └── __pycache__/             # Python cache (auto-generated)
│
└── frontend/                      # Next.js frontend (source code)
    └── gatwick-go/               # Next.js application
        ├── src/                  # Source code
        ├── public/               # Static assets
        ├── out/                  # Export output
        ├── .next/                # Build output
        ├── node_modules/         # Dependencies
        ├── package.json          # Node dependencies
        ├── next.config.ts        # Next.js configuration
        ├── tsconfig.json         # TypeScript configuration
        └── setup.sh              # Frontend setup script
```

## Key Changes Made

### 1. Backend Organization
- All Python files moved to `backend/` folder
- Flask app remains in `backend/app.py`
- Templates and static files stay in `backend/templates/` and `backend/static/`
- Configuration paths updated to use absolute paths via `os.path.dirname(__file__)`

### 2. Frontend Integration
- Next.js source code moved from `imported_model_zip/Gatwick-GO-main/gatwick-go/` → `frontend/gatwick-go/`
- No longer imports; now a fully integrated part of the project
- Exported/built static files served via Flask at `/model` route

### 3. Path Updates
- **config.py**: Updated paths for sandbox feed and generated output to use absolute paths
- **app.py**: Updated Flask initialization to use absolute paths for templates and static folders
- All relative paths now properly reference the backend directory

### 4. Root Level Files
- `start_app.sh`: Linux/Mac startup script with virtual environment setup
- `start_app.bat`: Windows startup script with virtual environment setup
- `.gitignore`: Comprehensive ignore patterns for Python and Node.js
- `README.md`: Updated documentation with new structure
- `STRUCTURE.md`: This file explaining the layout

## Running the Application

### Option 1: Using startup scripts
```bash
# Linux/Mac
./start_app.sh

# Windows
start_app.bat
```

### Option 2: Manual setup
```bash
cd backend
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 in your browser.

## Project References

All import paths and file references have been verified and updated:
- ✅ Flask template_folder and static_folder paths
- ✅ Config.py path references
- ✅ Sandbox feed directory paths
- ✅ Generated output directory paths
- ✅ No remaining references to `imported_model_zip`

## Development Workflow

### Python Development
```bash
cd backend
# All Python work happens here
python app.py
```

### Next.js Development (if needed)
```bash
cd frontend/gatwick-go
npm install
npm run dev
# Then build and export to backend/static/model
npm run build
npm run export
```

After rebuilding the frontend, the Flask app will automatically serve the new build from `backend/static/model/`.

## Environment Variables

Set these before running:
```bash
export GEMINI_API_KEY="your-api-key"          # Required
export OPENSKY_USERNAME="your-username"       # Optional
export OPENSKY_PASSWORD="your-password"       # Optional
```

## Notes

- The project is now properly compartmentalized with backend and frontend as distinct folders
- All references have been verified to work with the new structure
- The Next.js model is now part of the main project, not an import
- Database of test files and utilities are all properly organized
