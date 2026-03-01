#!/bin/bash
# Aircraft Detection System - Startup Script

echo "🚀 Starting Aircraft Detection System..."
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if required environment variables are set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY is not set."
    echo "   Set it with: export GEMINI_API_KEY='your-api-key'"
    echo ""
fi

# Navigate to backend directory
cd backend || { echo "❌ Cannot find backend directory"; exit 1; }

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate

# Install/update dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt

# Start the Flask app
echo ""
echo "✨ Starting Flask server..."
echo "   Open http://localhost:5000 in your browser"
echo ""

python app.py
