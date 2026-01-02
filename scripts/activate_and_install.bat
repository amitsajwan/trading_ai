@echo off
REM Activate virtual environment and install requirements

echo ======================================================================
echo Activating Virtual Environment and Installing Requirements
echo ======================================================================

REM Check if .venv exists
if not exist ".venv\" (
    echo Virtual environment not found. Creating it...
    python scripts/setup_venv.py
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing requirements from requirements.txt...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some requirements
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo SUCCESS: Virtual environment activated and requirements installed!
echo ======================================================================
echo.
echo Virtual environment is now active.
echo To deactivate, run: deactivate
echo.
pause

