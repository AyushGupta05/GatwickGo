#!/usr/bin/env python3
"""
Aircraft Detection Web App - Quick Reference

This script shows the most important commands to get started.
"""

print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  ✈️  AIRCRAFT DETECTION WEB APP - QUICK REFERENCE          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

📋 SETUP (ONE-TIME)
═══════════════════════════════════════════════════════════════

1. Get API Key from Google AI Studio:
   → https://aistudio.google.com/app/apikeys

2. Set environment variable (PowerShell):
   $env:GEMINI_API_KEY = "your-api-key-here"

3. Install dependencies:
   pip install -r requirements.txt

4. Verify system (optional):
   python test_system.py


🚀 RUN THE WEB APP
═══════════════════════════════════════════════════════════════

   python app.py

   Then open: http://localhost:5000


✨ WEB INTERFACE FEATURES
═══════════════════════════════════════════════════════════════

   📹 Live webcam feed
   📸 One-click burst capture (8 frames)
   🤖 Instant Gemini classification
   🎯 Confidence scores & visual cues
   🔄 Clear & restart


📊 WHAT HAPPENS WHEN YOU CLICK "CAPTURE & CLASSIFY"
═══════════════════════════════════════════════════════════════

   1. Browser captures 8 frames from webcam
      (50ms apart to simulate moving aircraft)

   2. Sends to backend: POST /api/classify

   3. Backend processes with Gemini Vision API:
      - Analyzes image
      - Identifies airline (10 supported)
      - Identifies aircraft family (16 families)
      - Returns confidence & visual cues

   4. Results displayed in browser:
      ✓ Airline (e.g., easyJet)
      ✓ Aircraft Family (e.g., A320-family)
      ✓ Confidence (0-100%)
      ✓ Visual Cues (orange fuselage, etc.)


🛠️ TROUBLESHOOTING
═══════════════════════════════════════════════════════════════

   Problem: "Module not found"
   → pip install -r requirements.txt

   Problem: "Webcam not found"
   → Check browser permissions
   → Try different browser
   → Verify camera is connected

   Problem: "GEMINI_API_KEY not set"
   → $env:GEMINI_API_KEY = "your-key"

   Problem: "Classification shows UNKNOWN"
   → Better lighting needed
   → Aircraft should fill more of frame
   → Check if airline is in supported list (10 carriers)


📂 PROJECT FILES
═══════════════════════════════════════════════════════════════

   app.py                          Flask server
   templates/index.html            Web interface
   static/main.js                  Browser logic
   gemini_classifier.py            Classification engine
   config.py                       Configuration
   requirements.txt                Python dependencies


🌐 SUPPORTED AIRLINES (10)
═══════════════════════════════════════════════════════════════

   • easyJet
   • British Airways
   • Wizz Air
   • TUI Airways
   • Vueling
   • Emirates
   • Qatar Airways
   • Turkish Airlines
   • Norse Atlantic Airways
   • Delta Air Lines


✈️ AIRCRAFT FAMILIES (16)
═══════════════════════════════════════════════════════════════

   A320-family  •  B737-family  •  A220  •  A330
   A340         •  A350        •  A380  •  B747
   B757         •  B767        •  B777  •  B787
   E-Jet        •  ATR         •  OTHER •  UNKNOWN


💡 TIPS
═══════════════════════════════════════════════════════════════

   • Good lighting = better results
   • Aircraft should fill ~50% of frame
   • Side view (profile) works best
   • 10-50 meters distance optimal
   • Take multiple bursts for best chance


📊 EXAMPLE OUTPUT
═══════════════════════════════════════════════════════════════

   {
     "airline": "easyJet",
     "aircraft_family": "A320-family",
     "confidence": 0.87,
     "cues": [
       "orange fuselage with easyJet logotype",
       "twin engines",
       "winglets on wingtips"
     ]
   }


🔗 USEFUL LINKS
═══════════════════════════════════════════════════════════════

   Gemini API Docs:
   → https://ai.google.dev/

   Google AI Studio:
   → https://aistudio.google.com/

   Browser Capabilities:
   → https://caniuse.com/mediastream


⚡ PERFORMANCE
═══════════════════════════════════════════════════════════════

   Burst capture:      ~400ms (8 frames × 50ms)
   Gemini API:         2-5 seconds
   Result display:     <100ms
   ─────────────────
   Total:              ~3-6 seconds


🎯 NEXT STEPS
═══════════════════════════════════════════════════════════════

   1. Set GEMINI_API_KEY
   2. Run: python app.py
   3. Open: http://localhost:5000
   4. Point camera at aircraft
   5. Click "📸 Capture & Classify"
   6. See results!


📞 DOCUMENTATION
═══════════════════════════════════════════════════════════════

   Full guide:          README_WEB_APP.md
   API reference:       README_AIRCRAFT_DETECTION.md
   Code examples:       CHEAT_SHEET.py
   Implementation:      IMPLEMENTATION_COMPLETE.md


═══════════════════════════════════════════════════════════════

Ready to start? Run: python app.py

Happy aircraft detection! ✈️

═══════════════════════════════════════════════════════════════
""")
