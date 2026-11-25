#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "========================================="
echo "QuantBot Pro Setup for Termux (S25 Ultra)"
echo "========================================="

pkg update -y && pkg upgrade -y

echo "Installing system dependencies..."
pkg install -y python python-pip git clang make cmake libjpeg-turbo libpng freetype openblas

echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo "Installing numpy with optimized flags..."
MATHLIB=m pip install --no-binary=numpy numpy==1.26.4

echo "Installing pandas..."
pip install --no-binary=pandas pandas==2.2.1

echo "Installing remaining requirements..."
pip install -r requirements.txt

echo "Installing matplotlib via pkg..."
pkg install -y matplotlib

echo "Creating directories..."
mkdir -p logs data

echo "Setting up Termux API (for notifications)..."
pkg install -y termux-api

echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "To run the bot:"
echo "  python main.py --mode paper --symbol BTC/USDT"
echo ""
echo "To run the UI only:"
echo "  python -m ui.app_enhanced"
echo ""
echo "Access UI at: http://localhost:8080"
echo "========================================="
