#!/usr/bin/env python3
"""
QUICK REFERENCE: Aircraft Detection System Cheat Sheet

Copy-paste examples for common tasks.
"""

# ============================================================================
# SETUP & CONFIGURATION
# ============================================================================

# Set API key (PowerShell)
$env:GEMINI_API_KEY = "AIzaSy..."

# Set API key (Command Prompt)
set GEMINI_API_KEY=AIzaSy...

# Set API key (Linux/Mac)
export GEMINI_API_KEY="AIzaSy..."

# Verify system is ready
python test_system.py

# ============================================================================
# CLASSIFY FROM CAMERA (Real-time)
# ============================================================================

# Basic burst capture and classify
python aircraft_detection_pipeline.py

# With custom frame count and delay
from camera_burst import capture_burst, classify_burst
frames = capture_burst(num_frames=12, delay=0.03)
result = classify_burst(frames)
print(result)

# ============================================================================
# CLASSIFY FROM FILE
# ============================================================================

# Single classification
python aircraft_detection_pipeline.py my_plane.jpg

# Top-K classification
python aircraft_detection_pipeline.py my_plane.jpg topk

# Programmatically
from gemini_classifier import classify_aircraft
image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft(image_bytes)

# ============================================================================
# TOP-K PREDICTIONS (Bonus Feature)
# ============================================================================

# Get top-5 airlines for an aircraft
from gemini_classifier import classify_aircraft_topk
image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft_topk(image_bytes, k=5)

# Example output:
# {
#   "topk": [
#     {"airline": "easyJet", "confidence": 0.87},
#     {"airline": "British Airways", "confidence": 0.08},
#     {"airline": "Vueling", "confidence": 0.03},
#     {"airline": "Wizz Air", "confidence": 0.01},
#     {"airline": "TUI Airways", "confidence": 0.01}
#   ],
#   "aircraft_family": "A320-family",
#   "family_confidence": 0.89,
#   "cues": ["orange fuselage", "twin engines"]
# }

# ============================================================================
# BATCH PROCESSING (Multiple Images)
# ============================================================================

from pathlib import Path
from gemini_classifier import classify_aircraft
import json

# Process all JPGs in a folder
results = []
for img_path in Path("aircraft_images").glob("*.jpg"):
    image_bytes = img_path.read_bytes()
    result = classify_aircraft(image_bytes)
    result["filename"] = img_path.name
    results.append(result)
    print(f"Classified {img_path.name}: {result['airline']}")

# Save batch results
with open("batch_results.json", "w") as f:
    json.dump(results, f, indent=2)

# ============================================================================
# EXTRACTING SPECIFIC INFORMATION
# ============================================================================

from gemini_classifier import classify_aircraft

image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft(image_bytes)

# Get just the airline
airline = result["airline"]  # "easyJet"

# Get just the aircraft family
family = result["aircraft_family"]  # "A320-family"

# Get confidence level
confidence = result["confidence"]  # 0.87

# Get visual cues
cues = result["cues"]  # ["orange fuselage", "twin engines", ...]

# Check if identified (not UNKNOWN)
is_identified = result["airline"] != "UNKNOWN" or result["aircraft_family"] != "UNKNOWN"

# ============================================================================
# FILTERING BY CONFIDENCE
# ============================================================================

from gemini_classifier import classify_aircraft

image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft(image_bytes)

# Accept only high-confidence results
if result["confidence"] >= 0.8:
    print(f"High confidence: {result['airline']}")
elif result["confidence"] >= 0.5:
    print(f"Medium confidence: {result['airline']}")
else:
    print(f"Low confidence, likely UNKNOWN")

# ============================================================================
# ERROR HANDLING
# ============================================================================

from gemini_classifier import classify_aircraft

try:
    image_bytes = open("plane.jpg", "rb").read()
    result = classify_aircraft(image_bytes)
    
    if result["airline"] == "UNKNOWN":
        print("Aircraft not identified - livery not clear")
    else:
        print(f"Identified: {result['airline']} ({result['confidence']*100:.0f}%)")
        print(f"Aircraft: {result['aircraft_family']}")
        print(f"Cues: {', '.join(result['cues'])}")
        
except ValueError as e:
    print(f"Configuration error: {e}")
    print("Did you set GEMINI_API_KEY?")
except Exception as e:
    print(f"Unexpected error: {e}")

# ============================================================================
# CUSTOMIZING BURST CAPTURE
# ============================================================================

from camera_burst import capture_burst, select_sharpest, classify_burst

# Fast jets (>400 mph) - capture quickly
frames = capture_burst(num_frames=15, delay=0.03)  # 450ms total

# Commercial aircraft (200-300 mph) - medium capture
frames = capture_burst(num_frames=10, delay=0.05)  # 500ms total

# Slow/prop aircraft (<150 mph) - slower capture
frames = capture_burst(num_frames=8, delay=0.10)   # 800ms total

# Get statistics about captured frames
print(f"Captured {len(frames)} frames")
idx, best = select_sharpest(frames)
print(f"Best frame: index {idx}")

# ============================================================================
# SAVING RESULTS
# ============================================================================

import json
from pathlib import Path
from gemini_classifier import classify_aircraft

image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft(image_bytes)

# Save as JSON
with open("result.json", "w") as f:
    json.dump(result, f, indent=2)

# Save as formatted text
output = f"""
Aircraft Classification Result
===============================

Airline: {result['airline']}
Aircraft Family: {result['aircraft_family']}
Confidence: {result['confidence']*100:.1f}%

Visual Cues:
{chr(10).join('  - ' + cue for cue in result['cues'])}
"""
Path("result.txt").write_text(output)

# ============================================================================
# TESTING WITH SAMPLE DATA
# ============================================================================

# Test without a real camera (mock test)
from gemini_classifier import classify_aircraft
from pathlib import Path

# Use any JPEG/PNG image
test_images = [
    "reference/easyjet.jpg",
    "reference/ba.jpg",
    "reference/emirates.jpg",
]

for img_path in test_images:
    try:
        image_bytes = Path(img_path).read_bytes()
        result = classify_aircraft(image_bytes)
        print(f"{img_path}: {result['airline']} ({result['confidence']:.2f})")
    except FileNotFoundError:
        print(f"{img_path}: File not found")

# ============================================================================
# TROUBLESHOOTING CLASSIFIER OUTPUT
# ============================================================================

from gemini_classifier import classify_aircraft
import json

image_bytes = open("plane.jpg", "rb").read()
result = classify_aircraft(image_bytes)

# Debug: Check why result is UNKNOWN
if result["airline"] == "UNKNOWN":
    print("Airline not recognized. Possible reasons:")
    print("  1. Livery not visible or damaged")
    print("  2. Aircraft from non-whitelisted carrier")
    print("  3. Poor image quality")
    print("  4. Image doesn't contain aircraft")
    print("\nDebug info:")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Cues extracted: {result['cues']}")

# Debug: Print full response
print("Full result:")
print(json.dumps(result, indent=2))

# ============================================================================
# CONFIGURATION TUNING
# ============================================================================

# Adjust capture parameters
from camera_burst import capture_burst
from config import BURST_FRAMES, FRAME_DELAY

# Use config values
frames = capture_burst(num_frames=BURST_FRAMES, delay=FRAME_DELAY)

# Or override inline
frames = capture_burst(num_frames=20, delay=0.02)  # 40 FPS capture

# Adjust classifier parameters
from gemini_classifier import classify_aircraft_topk

# Get top-10 instead of top-3
result = classify_aircraft_topk(image_bytes, k=10)

# ============================================================================
# INTEGRATING WITH WEB SERVICE
# ============================================================================

# Flask example (minimal)
from flask import Flask, request, jsonify
from gemini_classifier import classify_aircraft

app = Flask(__name__)

@app.route("/classify", methods=["POST"])
def classify_endpoint():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    
    image_file = request.files["image"]
    image_bytes = image_file.read()
    
    result = classify_aircraft(image_bytes)
    return jsonify(result)

# Usage: curl -F "image=@plane.jpg" http://localhost:5000/classify

# ============================================================================
# USEFUL REFERENCES
# ============================================================================

# Supported airlines
AIRLINES = {
    "easyJet", "British Airways", "Wizz Air", "TUI Airways",
    "Vueling", "Emirates", "Qatar Airways", "Turkish Airlines",
    "Norse Atlantic Airways", "Delta Air Lines"
}

# Supported aircraft families
FAMILIES = {
    "A320-family", "B737-family", "A220", "A330", "A340", "A350", "A380",
    "B747", "B757", "B767", "B777", "B787", "E-Jet", "ATR", "OTHER", "UNKNOWN"
}

# Typical aircraft by airline
FLEET_MAP = {
    "easyJet": ["A320-family"],
    "British Airways": ["A320-family", "A350", "A380", "B777", "B787"],
    "Emirates": ["A380", "B777"],
    "Delta Air Lines": ["A220", "A320-family", "B737", "B787"],
    # ... see config.py for full list
}

# ============================================================================
# PERFORMANCE NOTES
# ============================================================================

# Image size recommendations:
#  - Minimum: 256x256 px (will work but may be low quality)
#  - Optimal: 1024x768 to 1920x1080 px
#  - Maximum: 4096x4096 px (larger files slower, diminishing returns)

# Processing time:
#  - Camera capture: ~400-800ms (depends on frame count/delay)
#  - Gemini API: 2-5 seconds per image
#  - Total: 2.5-6 seconds per burst

# API rate limits:
#  - Free tier: varies (check Google AI Studio)
#  - Tier 1: ~60 requests/minute
#  - Tier 2: higher limits with paid account
