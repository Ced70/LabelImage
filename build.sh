#!/bin/bash
# Build LabelImage with PyInstaller
# Usage: ./build.sh

set -e

echo "=== LabelImage Build ==="

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Build
echo "Building with PyInstaller..."
pyinstaller labelimage.spec --clean

echo ""
echo "=== Build complete ==="
echo "Output: dist/LabelImage/"

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS app bundle: dist/LabelImage.app/"
fi
