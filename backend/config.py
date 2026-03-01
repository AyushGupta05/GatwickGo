"""
Configuration and constants for the aircraft detection pipeline.
Safe version — no hardcoded API keys.
"""

import os

# ============================================================================
# CAMERA BURST SETTINGS
# ============================================================================

BURST_FRAMES = 8
FRAME_DELAY = 0.05

# ============================================================================
# CLASSIFICATION SETTINGS
# ============================================================================

USE_TOPK = False
TOP_K = 3

# ============================================================================
# GEMINI API CONFIGURATION
# ============================================================================

# Recommended: gemini-2.5-flash for best vision performance
GEMINI_MODEL = "gemini-2.5-flash"

API_TIMEOUT = 30

# Reads from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Dev image generation (Gemini Nano Banana) toggle
DEV_GENERATION_ENABLED = os.getenv("DEV_GENERATION_ENABLED", "false").lower() == "true"
DEV_GENERATION_OUTPUT_DIR = os.getenv("DEV_GENERATION_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "static", "generated"))

# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

OUTPUT_FILE = None
VERBOSE = True

# ============================================================================
# AIRLINE WHITELIST
# ============================================================================

SUPPORTED_AIRLINES = {
    "easyJet",
    "British Airways",
    "Wizz Air",
    "TUI Airways",
    "Vueling",
    "Emirates",
    "Qatar Airways",
    "Turkish Airlines",
    "Norse Atlantic Airways",
    "Delta Air Lines",
}

# ============================================================================
# AIRCRAFT FAMILY TAXONOMY
# ============================================================================

AIRCRAFT_FAMILIES = {
    "A320-family",
    "B737-family",
    "A220",
    "A330",
    "A340",
    "A350",
    "A380",
    "B747",
    "B757",
    "B767",
    "B777",
    "B787",
    "E-Jet",
    "ATR",
    "OTHER",
    "UNKNOWN",
}

# ============================================================================
# FLIGHT FEED SETTINGS
# ============================================================================

# "SANDBOX" | "LIVE" | "OPENSKY"
FLIGHT_MODE = "SANDBOX"

SANDBOX_SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "sandbox_feed")
SANDBOX_SNAPSHOT_INTERVAL = 5

DEFAULT_SEARCH_RADIUS_KM = 30

AIRPORT_ICAO = "EGKK"
AIRPORT_NAME = "London Gatwick"
AIRPORT_COORDS = (51.1537, -0.1821)

# ============================================================================
# OPENSKY CONFIG (Environment Only)
# ============================================================================

OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME")
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD")

# ============================================================================
# SHARPNESS DETECTION SETTINGS
# ============================================================================

MIN_SHARPNESS_SCORE = 0.0

# ============================================================================
# CONFIDENCE THRESHOLDS
# ============================================================================

MIN_CONFIDENCE_AIRLINE = 0.5
MIN_CONFIDENCE_FAMILY = 0.3

# ============================================================================
# RETRY SETTINGS
# ============================================================================

MAX_RETRIES = 2
RETRY_DELAY = 1

# ============================================================================
# CAMERA SETTINGS
# ============================================================================

CAMERA_DEVICE = 0
TARGET_RESOLUTION = None
TARGET_FPS = None

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = "INFO"
