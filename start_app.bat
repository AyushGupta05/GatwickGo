@echo off
REM Aircraft Detection System - Startup Script for Windows

echo.
echo 🚀 Starting Aircraft Detection System...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    exit /b 1
)

REM Check if GEMINI_API_KEY is set
if "%GEMINI_API_KEY%"=="" (
    echo ⚠️  GEMINI_API_KEY is not set.
    echo    Set it with: set GEMINI_API_KEY=your-api-key
    echo.
)

REM Navigate to backend directory
cd backend || (
    echo ❌ Cannot find backend directory
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo ✅ Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo 📚 Installing dependencies...
pip install -q -r requirements.txt

REM Start the Flask app
echo.
echo ✨ Starting Flask server...
echo    Open http://localhost:5000 in your browser
echo.

python app.py
