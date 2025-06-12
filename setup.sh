#!/bin/bash

# Allium Quick Setup Script
# Usage: curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash

set -e

echo "🌐 Allium - Tor Relay Analytics Setup"
echo "======================================"

# Check Python version
echo "🔍 Checking Python version..."
if ! python3 -c "import sys; assert sys.version_info >= (3, 8)" 2>/dev/null; then
    echo "❌ Error: Python 3.8+ required. Please install Python 3.8 or newer."
    exit 1
fi
echo "✅ Python version check passed"

# Check if we're in a git repo already or if allium.py exists in current directory
if [ -d ".git" ] && [ -f "allium/allium.py" ]; then
    echo "📁 Running in existing allium repository root directory"
    ALLIUM_ROOT="."
elif [ -d ".git" ] && [ -f "allium.py" ]; then
    echo "📁 Running in existing allium subdirectory"
    ALLIUM_ROOT=".."
else
    echo "📥 Cloning allium repository..."
    if [ -d "allium" ]; then
        echo "⚠️  Directory 'allium' already exists. Removing it..."
        rm -rf allium
    fi
    git clone https://github.com/1aeo/allium.git
    cd allium
    ALLIUM_ROOT="."
fi

echo "🔧 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🚀 Running first generation with progress tracking..."
cd allium
python3 allium.py --progress

echo ""
echo "🎉 Setup complete! Your Tor metrics site is ready."
echo ""
echo "📊 Generated files are in: ./www/"
echo "🌐 To serve locally, run:"
echo "   cd www && python3 -m http.server 8000"
echo "   Then visit: http://localhost:8000"
echo ""
echo "⚡ To regenerate with fresh data:"
echo "   First activate the virtual environment: source venv/bin/activate"
if [ "$ALLIUM_ROOT" = ".." ]; then
    echo "   Then run: python3 allium.py --progress"
else
    echo "   Then run: cd allium && python3 allium.py --progress"
fi
echo ""
echo "📚 Documentation: docs/README.md"
echo "🔧 Configuration options: python3 allium.py --help" 