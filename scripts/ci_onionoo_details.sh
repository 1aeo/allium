# CI helpers for the setup end-to-end job.
#
# Sourced by setup.sh and by .github/workflows/ci.yml. Not used for production
# site builds: those do not set ALLIUM_CI_DETAILS_FALLBACK=1, so they still
# fetch Onionoo and do not fall back to the committed fixture.
#
# The seeded file is the existing onionoo_details cache (allium/data/cache).
# workers.py already treats a fresh cache as a 90s budget with no retries and
# returns it when the live request times out. This script does not add a
# second cache.

# Print the details fixture path, or return 1 when it is not available.
ci_onionoo_fixture_path() {
    if [ -n "${ALLIUM_CI_DETAILS_FIXTURE:-}" ] && [ -f "${ALLIUM_CI_DETAILS_FIXTURE}" ]; then
        printf '%s\n' "${ALLIUM_CI_DETAILS_FIXTURE}"
        return 0
    fi
    if [ -f tests/fixtures/ci/onionoo_details.json ]; then
        printf '%s\n' "tests/fixtures/ci/onionoo_details.json"
        return 0
    fi
    return 1
}

# Directory of the on-disk details cache for the checkout we are about to run.
_ci_details_cache_dir() {
    if [ -f allium/lib/workers.py ]; then
        printf '%s\n' "allium/data/cache"
        return 0
    fi
    if [ -f lib/workers.py ]; then
        printf '%s\n' "data/cache"
        return 0
    fi
    echo "❌ Could not find workers.py to locate the Onionoo details cache" >&2
    return 1
}

# Copy the fixture into the details cache before generation.
#
# The live request still runs. No timestamp file is written, so the request
# is not a conditional GET that could 304 back to this fixture. On timeout,
# workers.py returns this document and generation continues.
seed_ci_onionoo_details_cache() {
    if [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" != "1" ]; then
        return 0
    fi
    local src cache_dir
    if ! src=$(ci_onionoo_fixture_path); then
        echo "❌ ALLIUM_CI_DETAILS_FALLBACK=1 but the Onionoo details fixture was not found"
        return 1
    fi
    cache_dir=$(_ci_details_cache_dir) || return 1
    mkdir -p "$cache_dir"
    cp "$src" "${cache_dir}/onionoo_details.json"
    # A timestamp would send If-Modified-Since and could pin CI to this fixture.
    rm -f "${cache_dir}/onionoo_details_timestamp.txt"
    echo "🤖 CI: seeded Onionoo details cache from ${src}"
    echo "    The live details request still runs."
    echo "    If it exceeds the fresh-cache budget, generation uses this cache."
}

# True when path is a generated HTML page.
site_index_ready() {
    local index="$1"
    [ -f "$index" ] && grep -q '<html' "$index"
}

# Classify one live allium run. Always exits 0. Prints one word:
#   ok        page is ready, or this is not the setup job (allium's own exit 0)
#   fallback  setup job, allium exited 0, and index.html was not written
#   fail      allium exited non-zero; do not replace that with the fixture
ci_live_generation_outcome() {
    local exit_code="$1"
    local index="$2"
    if [ "$exit_code" -ne 0 ]; then
        printf 'fail\n'
        return 0
    fi
    if site_index_ready "$index"; then
        printf 'ok\n'
        return 0
    fi
    if [ "${ALLIUM_CI_DETAILS_FALLBACK:-}" = "1" ]; then
        printf 'fallback\n'
        return 0
    fi
    printf 'ok\n'
    return 0
}

# Serve the fixture over HTTP and generate into OUTPUT_DIR.
#
# allium rejects file:// URLs, so the fixture is served on 127.0.0.1.
# Usage: generate_from_ci_onionoo_fixture OUTPUT_DIR ALLIUM_PY
# Returns allium's exit status. Call this only after a live run exited 0
# without writing index.html (Onionoo unavailable). A non-zero allium exit
# is a setup or generation failure and must not be retried through here.
generate_from_ci_onionoo_fixture() {
    local out="$1"
    local allium_py="$2"
    local src dir port pid ready i code
    if ! src=$(ci_onionoo_fixture_path); then
        echo "❌ CI Onionoo details fixture is missing; cannot fall back"
        return 1
    fi
    dir=$(mktemp -d)
    cp "$src" "${dir}/onionoo_details.json"
    port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
    python3 -m http.server "$port" --bind 127.0.0.1 --directory "$dir" >"${dir}/http.log" 2>&1 &
    pid=$!
    ready=0
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        if curl -sf -o /dev/null "http://127.0.0.1:${port}/onionoo_details.json"; then
            ready=1
            break
        fi
        sleep 0.1
    done
    if [ "$ready" -ne 1 ]; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        rm -rf "$dir"
        echo "❌ CI fixture HTTP server did not start"
        return 1
    fi
    echo "🤖 CI: Onionoo details produced no site; generating from the committed details fixture"
    echo "    URL: http://127.0.0.1:${port}/onionoo_details.json"
    set +e
    python3 "$allium_py" --progress --apis details --out "$out" \
        --onionoo-details-url "http://127.0.0.1:${port}/onionoo_details.json"
    code=$?
    set -e
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -rf "$dir"
    return "$code"
}
