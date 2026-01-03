#!/bin/bash
# Activate virtual environment and install requirements

echo "======================================================================"
echo "Activating Virtual Environment and Installing Requirements"
echo "======================================================================"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating it..."
    python scripts/setup_venv.py
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Install requirements
echo ""
echo "Installing requirements from requirements.txt..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install some requirements"
    exit 1
fi

echo ""
echo "======================================================================"
echo "SUCCESS: Virtual environment activated and requirements installed!"
echo "======================================================================"
echo ""
echo "Virtual environment is now active."
echo "To deactivate, run: deactivate"
echo ""

