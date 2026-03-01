#!/usr/bin/env python3
"""
Quick reference for the aircraft detection system.

This file used to contain shell snippets and copy-paste fragments as raw Python,
which broke backend compile checks. Keep executable Python here and store the
reference text inside a string constant instead.
"""

CHEAT_SHEET = """
Setup
=====

PowerShell:
  $env:GEMINI_API_KEY = "AIzaSy..."

Command Prompt:
  set GEMINI_API_KEY=AIzaSy...

Linux/macOS:
  export GEMINI_API_KEY="AIzaSy..."

Verify:
  python test_system.py

Classify from camera
====================

  python aircraft_detection_pipeline.py

Classify from file
==================

  python aircraft_detection_pipeline.py my_plane.jpg
  python aircraft_detection_pipeline.py my_plane.jpg topk

Programmatic use
================

  from gemini_classifier import classify_aircraft
  image_bytes = open("plane.jpg", "rb").read()
  result = classify_aircraft(image_bytes)

Useful notes
============

  - Typical total request time: 2.5 to 6 seconds
  - Optimal image size: 1024x768 to 1920x1080
  - See config.py for supported airlines and aircraft families
"""


def main() -> None:
    print(CHEAT_SHEET.strip())


if __name__ == "__main__":
    main()
