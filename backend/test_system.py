#!/usr/bin/env python3
"""
Quick test script to verify the aircraft detection system is working.

Run this to ensure all modules are properly installed and configured.
"""

import os
import sys
from pathlib import Path


def check_dependencies():
    """Verify all required packages are installed."""
    print("=" * 60)
    print("CHECKING DEPENDENCIES")
    print("=" * 60)

    required = [
        ("google.generativeai", "google-generativeai"),
        ("cv2", "opencv-python"),
        ("PIL", "pillow"),
        ("numpy", "numpy"),
        ("requests", "requests"),
    ]

    all_ok = True
    for module_name, package_name in required:
        try:
            __import__(module_name)
            print(f"✅ {package_name:<25} installed")
        except ImportError:
            print(f"❌ {package_name:<25} NOT installed")
            print(f"   Install with: pip install {package_name}")
            all_ok = False

    return all_ok


def check_environment():
    """Check required environment variables."""
    print("\n" + "=" * 60)
    print("CHECKING ENVIRONMENT")
    print("=" * 60)

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        masked = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
        print(f"✅ GEMINI_API_KEY is set: {masked}")
    else:
        print("⚠️  GEMINI_API_KEY not set")
        print("   Set it with: $env:GEMINI_API_KEY = 'your-api-key'")
        print("   Or: export GEMINI_API_KEY='your-api-key'")

    return api_key is not None


def check_modules():
    """Verify all local modules can be imported."""
    print("\n" + "=" * 60)
    print("CHECKING LOCAL MODULES")
    print("=" * 60)

    modules = [
        ("gemini_classifier", "Core Gemini classification"),
        ("camera_burst", "Camera burst capture utilities"),
        ("aircraft_detection_pipeline", "End-to-end pipeline orchestrator"),
        ("config", "Configuration constants"),
    ]

    all_ok = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name:<35} ({description})")
        except ImportError as e:
            print(f"❌ {module_name:<35} ({description})")
            print(f"   Error: {e}")
            all_ok = False

    return all_ok


def check_files():
    """Check that all required files exist."""
    print("\n" + "=" * 60)
    print("CHECKING FILES")
    print("=" * 60)

    files = [
        ("gemini_classifier.py", "Core classifier module"),
        ("camera_burst.py", "Camera utilities"),
        ("aircraft_detection_pipeline.py", "Pipeline orchestrator"),
        ("config.py", "Configuration"),
        ("README_AIRCRAFT_DETECTION.md", "Documentation"),
    ]

    all_ok = True
    for filename, description in files:
        path = Path(filename)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"✅ {filename:<35} ({description}) [{size_kb:.1f} KB]")
        else:
            print(f"❌ {filename:<35} ({description}) [NOT FOUND]")
            all_ok = False

    return all_ok


def main():
    """Run all checks."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  AIRCRAFT DETECTION SYSTEM - HEALTH CHECK".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    deps_ok = check_dependencies()
    env_ok = check_environment()
    modules_ok = check_modules()
    files_ok = check_files()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    status = {
        "Dependencies": "✅" if deps_ok else "❌",
        "Environment": "✅" if env_ok else "⚠️",
        "Modules": "✅" if modules_ok else "❌",
        "Files": "✅" if files_ok else "❌",
    }

    for check, result in status.items():
        print(f"{check:<20} {result}")

    print()
    if all([deps_ok, modules_ok, files_ok]) and env_ok:
        print(
            "🎉 System is ready! Run: python aircraft_detection_pipeline.py"
        )
        return 0
    elif all([deps_ok, modules_ok, files_ok]):
        print(
            "⚠️  System ready but GEMINI_API_KEY not set. Set it before running."
        )
        return 1
    else:
        print("❌ System not ready. Please install missing dependencies/files.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
