#!/bin/bash

# Allium Quick Setup Script
# Usage: curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash

set -e

echo "🌐 Allium - Tor Relay Analytics Setup"
echo "======================================"
echo "🔥 Enhanced with AROI Reliability Scoring System"
echo ""

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
    IN_REPO=true
elif [ -f "allium.py" ]; then
    echo "📁 Running directly with allium.py in current directory"
    ALLIUM_ROOT="."
    IN_REPO=true
else
    echo "📥 Cloning allium repository..."
    if [ -d "allium" ]; then
        echo "⚠️  Directory 'allium' already exists. Removing it..."
        rm -rf allium
    fi
    git clone https://github.com/1aeo/allium.git
    cd allium
    ALLIUM_ROOT="."
    IN_REPO=false
fi

echo "🔧 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r config/requirements.txt

echo "🚀 Running first generation with progress tracking..."

# Run with retry logic to handle network issues
echo "🔄 Attempting to generate site (may retry on network issues)..."

# Check if we're in a CI environment (GitHub Actions, GitLab CI, etc.)
if [ -n "$CI" ] || [ -n "$GITHUB_ACTIONS" ] || [ -n "$GITLAB_CI" ]; then
    echo "🤖 CI environment detected - using details API only to reduce resource usage"
    API_MODE="--apis details"
else
    echo "🖥️  Regular environment - using all APIs for full functionality"
    API_MODE="--apis all"
fi

# Determine the correct path to allium.py based on the setup scenario
if [ -f "allium.py" ]; then
    ALLIUM_PY_PATH="allium.py"
else
    ALLIUM_PY_PATH="allium/allium.py"
fi

for attempt in 1 2 3; do
    echo "🔄 Generation attempt $attempt of 3..."
    echo "📁 Running from: $(pwd)"
    echo "🔧 Using allium.py path: $ALLIUM_PY_PATH"
    
    if python3 "$ALLIUM_PY_PATH" --progress $API_MODE; then
        echo "✅ Site generation completed successfully on attempt $attempt"
        break
    else
        exit_code=$?
        echo "⚠️  Attempt $attempt failed with exit code $exit_code"
        if [ $attempt -eq 3 ]; then
            echo "❌ All generation attempts failed"
            echo "🔧 This might be due to:"
            echo "   - Network connectivity issues with onionoo.torproject.org"
            echo "   - Temporary service unavailability"
            echo "   - System resource constraints"
            echo ""
            echo "💡 You can try running the generation manually later with:"
            if [ -f "allium.py" ]; then
                echo "   source venv/bin/activate && python3 allium.py --progress"
            else
                echo "   source venv/bin/activate && python3 allium/allium.py --progress"
            fi
            echo ""
            echo "🔧 For low-memory environments, try: python3 $ALLIUM_PY_PATH --progress --apis details"
            exit 1
        else
            echo "⏳ Waiting 10 seconds before retry..."
            sleep 10
        fi
    fi
done

echo ""
echo "🎉 Setup complete! Your Tor metrics site is ready."
echo ""
echo "📊 Generated files are in: ./www/"
echo "🌐 To serve locally, run:"
echo "   cd www && python3 -m http.server 8000"
echo "   Then visit: http://localhost:8000"
echo ""
echo "🏆 New Features Available:"
echo "   • Reliability Masters (6-month average uptime, 25+ relays)"
echo "   • Legacy Titans (5-year average uptime, 25+ relays)"
echo "   • Enhanced AROI leaderboards with 12 categories"
echo "   • Simplified reliability scoring (no weighting)"
echo "   • Improved geographic diversity scoring"
echo ""
echo "⚡ To regenerate with fresh data:"
echo "   First activate the virtual environment: source venv/bin/activate"
if [ -f "allium.py" ]; then
    echo "   Then run: python3 allium.py --progress"
else
    echo "   Then run: python3 allium/allium.py --progress"
fi
echo ""
echo "📚 Documentation: docs/README.md"
echo "🔧 Configuration options: python3 allium/allium.py --help" 