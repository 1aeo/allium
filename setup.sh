#!/bin/bash

# Allium Quick Setup Script
# 
# Production setup (default):
#   curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash
#   
# Developer setup (includes testing dependencies):
#   curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev

set -e

# Check if developer mode is requested
DEV_MODE=false
if [[ "$1" == "--dev" ]]; then
    DEV_MODE=true
fi

if [[ "$DEV_MODE" == "true" ]]; then
    echo "🌐 Allium - Tor Relay Analytics Setup (Developer Mode)"
    echo "===================================================="
    echo "🔥 Enhanced with AROI Reliability Scoring System"
    echo "🧪 Including testing and development dependencies"
else
    echo "🌐 Allium - Tor Relay Analytics Setup (Production Mode)"
    echo "====================================================="
    echo "🔥 Enhanced with AROI Reliability Scoring System"
    echo "📦 Minimal dependencies for production deployment"
fi
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
    git clone --depth 1 https://github.com/1aeo/allium.git
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

if [[ "$DEV_MODE" == "true" ]]; then
    echo "🧪 Installing development dependencies (includes testing tools)..."
    pip install -r config/requirements-dev.txt
else
    echo "📦 Installing production dependencies (minimal set)..."
    pip install -r config/requirements.txt
fi

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

# ALLIUM_CI_DETAILS_FALLBACK=1 is set only by the setup end-to-end job.
# It seeds the existing details cache and, if Onionoo returns no site,
# generates once from the committed fixture. Production builds leave it unset.
_load_ci_onionoo_helpers() {
    local helper="${ALLIUM_CI_ONIONOO_LIB:-}"
    if [ -z "$helper" ]; then
        local here
        here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
        if [ -f "${here}/scripts/ci_onionoo_details.sh" ]; then
            helper="${here}/scripts/ci_onionoo_details.sh"
        elif [ -f scripts/ci_onionoo_details.sh ]; then
            helper="scripts/ci_onionoo_details.sh"
        fi
    fi
    if [ -z "$helper" ] || [ ! -f "$helper" ]; then
        echo "❌ ALLIUM_CI_DETAILS_FALLBACK=1 but scripts/ci_onionoo_details.sh was not found"
        exit 1
    fi
    # shellcheck disable=SC1090
    source "$helper"
}

GEN_ATTEMPTS=3
if [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" = "1" ]; then
    _load_ci_onionoo_helpers
    seed_ci_onionoo_details_cache
    # One live attempt: a slow Onionoo hits the fresh-cache budget and uses
    # the seed. Repeating the live fetch would wait out that budget again.
    GEN_ATTEMPTS=1
fi

generation_ok=false
attempt=1
while [ "$attempt" -le "$GEN_ATTEMPTS" ]; do
    echo "🔄 Generation attempt $attempt of $GEN_ATTEMPTS..."
    echo "📁 Running from: $(pwd)"
    echo "🔧 Using allium.py path: $ALLIUM_PY_PATH"

    if python3 "$ALLIUM_PY_PATH" --progress $API_MODE; then
        exit_code=0
    else
        exit_code=$?
    fi
    if [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" = "1" ]; then
        outcome=$(ci_live_generation_outcome "$exit_code" "www/index.html")
        if [ "$outcome" = "ok" ]; then
            echo "✅ Site generation completed successfully on attempt $attempt"
            generation_ok=true
            break
        elif [ "$outcome" = "fallback" ]; then
            # allium exits 0 when Onionoo details is unavailable and there was
            # nothing to render. That is an API miss, not a generation crash.
            echo "⚠️  Generation exited 0 without www/index.html; Onionoo details was unavailable"
            break
        else
            echo "❌ Generation failed with exit code $exit_code"
            exit 1
        fi
    fi
    if [ "$exit_code" -eq 0 ]; then
        echo "✅ Site generation completed successfully on attempt $attempt"
        generation_ok=true
        break
    fi
    echo "⚠️  Attempt $attempt failed with exit code $exit_code"
    if [ "$attempt" -eq "$GEN_ATTEMPTS" ]; then
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
    fi
    echo "⏳ Waiting 10 seconds before retry..."
    sleep 10
    attempt=$((attempt + 1))
done

if [ "$generation_ok" != true ] && [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" = "1" ]; then
    if generate_from_ci_onionoo_fixture "www" "$ALLIUM_PY_PATH" && site_index_ready "www/index.html"; then
        echo "✅ Site generation completed from the CI Onionoo details fixture"
        generation_ok=true
    fi
fi

if [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" = "1" ] && [ "$generation_ok" != true ]; then
    echo "❌ Setup did not produce www/index.html"
    exit 1
fi

echo ""
echo "🎉 Setup complete! Your Tor metrics site is ready."
echo ""
# PNG charts (the default) need cairocffi and numpy from pip, plus the cairo library and the DejaVu Sans font:
# system packages pip cannot install. Say which one failed; until it is fixed, allium writes SVG charts.
png_missing=$(python3 -c '
try:
    import cairocffi, numpy  # noqa: F401
except ImportError as e:  # a Python package did not install
    print("package " + " ".join(str(e).split()))
except OSError as e:  # cairocffi did not find the cairo library
    print("library " + (str(e).splitlines() or ["OSError"])[0])
' 2>&1 || true)
if [[ -n "$png_missing" ]]; then
    echo "⚠️  PNG charts cannot load (${png_missing#* }); until they can, allium writes SVG charts."
    if [[ "$png_missing" == package* ]]; then
        echo "💡 Install the Python packages: source venv/bin/activate && pip install -r config/requirements.txt"
    else
        echo "💡 The cairo library and chart font, which pip cannot install, on Debian/Ubuntu: sudo apt install libcairo2 fonts-dejavu-core"
    fi
    echo "💡 Or keep SVG charts without the notice: source venv/bin/activate && python3 $ALLIUM_PY_PATH --chart-format svg"
    echo ""
fi
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
if [[ "$DEV_MODE" == "true" ]]; then
    echo "🧪 Developer Mode - Additional Tools Available:"
    echo "   • pytest: Run unit tests with 'pytest'"
    echo "   • pytest-cov: Generate coverage reports with 'pytest --cov'"
    echo "   • flake8: Check code style with 'flake8'"
    echo "   • bandit: Security analysis with 'bandit -r .'"
    echo "   • safety: Check dependencies with 'safety check'"
    echo "   • djlint: HTML/template linting with 'djlint allium/templates/'"
    echo "   • memory-profiler: Profile memory usage"
    echo ""
fi
echo "📚 Documentation: docs/README.md"
echo "🔧 Configuration options: python3 allium/allium.py --help" 