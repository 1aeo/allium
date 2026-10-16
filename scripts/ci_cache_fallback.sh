#!/bin/bash
# CI-only cache seed for the setup job. Production curl|bash does not source this.
#
# tests/fixtures/ci/<api_name>.json is copied to the existing cache file
# <api_name>.json. No timestamp file is written, so the live request is not a
# conditional GET. workers.py then uses the fresh-cache budget (at most 90s,
# no retries) and returns the seeded document when that request times out.
# Bandwidth, AROI, exit DNS, and CollecTor skip the network when that cache
# is fresh; details and uptime still try once.

# Cache keys for every API Coordinator enables with --apis all.
# tests/fixtures/ci/<name>.json must match this list.
CI_CACHE_FIXTURES="
onionoo_details
onionoo_uptime
onionoo_bandwidth
aroi_validation
exit_dns_health
collector_consensus
collector_descriptors
"

# True only when every name in CI_CACHE_FIXTURES is present. A details-only
# directory must not be treated as a full substitute set.
_ci_fixtures_complete() {
    local dir="$1" name
    for name in $CI_CACHE_FIXTURES; do
        [ -f "${dir}/${name}.json" ] || return 1
    done
}

ci_fixture_dir() {
    if [ -n "${ALLIUM_CI_FIXTURE_DIR:-}" ]; then
        if _ci_fixtures_complete "${ALLIUM_CI_FIXTURE_DIR}"; then
            printf '%s\n' "${ALLIUM_CI_FIXTURE_DIR}"
            return 0
        fi
        return 1
    fi
    local here
    here=$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    if _ci_fixtures_complete "${here}/../tests/fixtures/ci"; then
        (CDPATH= cd -- "${here}/../tests/fixtures/ci" && pwd)
        return 0
    fi
    if _ci_fixtures_complete tests/fixtures/ci; then
        (CDPATH= cd -- tests/fixtures/ci && pwd)
        return 0
    fi
    return 1
}

_ci_cache_dir() {
    if [ -f allium/lib/workers.py ]; then
        printf '%s\n' "allium/data/cache"
        return 0
    fi
    if [ -f lib/workers.py ]; then
        printf '%s\n' "data/cache"
        return 0
    fi
    echo "❌ Could not find workers.py to locate the API cache" >&2
    return 1
}

# Download tests/fixtures/ci from a commit. The setup job clones the default
# branch, which does not have these files until the change is merged.
download_ci_fixtures() {
    local dest="$1" repo="$2" sha="$3" name url
    mkdir -p "$dest"
    for name in $CI_CACHE_FIXTURES; do
        url="https://raw.githubusercontent.com/${repo}/${sha}/tests/fixtures/ci/${name}.json"
        curl -fsSL --connect-timeout 30 --max-time 60 "$url" -o "${dest}/${name}.json"
        test -s "${dest}/${name}.json"
    done
}

# Copy every fixture into the cache. Rewrites fetched_at so CollecTor's
# 3-hour cache check accepts the file. A no-op unless the setup job opted in.
seed_ci_api_caches() {
    if [ "${ALLIUM_CI_CACHE_FALLBACK:-}" != "1" ]; then
        return 0
    fi
    local src cache_dir fixture name
    if ! src=$(ci_fixture_dir); then
        echo "❌ ALLIUM_CI_CACHE_FALLBACK=1 but the CI API fixtures were not found"
        return 1
    fi
    cache_dir=$(_ci_cache_dir) || return 1
    mkdir -p "$cache_dir"
    for fixture in "$src"/*.json; do
        name=$(basename "$fixture" .json)
        cp "$fixture" "${cache_dir}/${name}.json"
        rm -f "${cache_dir}/${name}_timestamp.txt"
    done
    python3 - "$cache_dir" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

cache_dir = sys.argv[1]
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for name in os.listdir(cache_dir):
    if not name.endswith(".json"):
        continue
    path = os.path.join(cache_dir, name)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "fetched_at" in data:
        data["fetched_at"] = now
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, separators=(",", ":"))
            handle.write("\n")
PY
    echo "🤖 CI: seeded API caches from ${src}"
    echo "    Live requests still run. A fresh-cache timeout uses these files."
}

site_index_ready() {
    local index="$1"
    [ -f "$index" ] && grep -q '<html' "$index"
}

# Print ok, fallback, or fail. Always exits 0.
# fallback: the setup job, allium exited 0, and index.html was not written.
# fail: allium exited non-zero. Do not replace that with fixtures.
ci_live_generation_outcome() {
    local exit_code="$1" index="$2"
    if [ "$exit_code" -ne 0 ]; then
        printf 'fail\n'
        return 0
    fi
    if site_index_ready "$index"; then
        printf 'ok\n'
        return 0
    fi
    if [ "${ALLIUM_CI_CACHE_FALLBACK:-}" = "1" ]; then
        printf 'fallback\n'
        return 0
    fi
    printf 'ok\n'
}

# One live attempt, then fixtures if allium exits 0 without a page.
# Uses API_MODE (setup.sh's --apis flag). Collector has no URL flag; its
# seeded cache is the substitute when the live CollecTor fetch times out.
ci_generate_once() {
    local out="$1" allium_py="$2" code outcome mode
    mode="${API_MODE:---apis details}"
    set +e
    python3 "$allium_py" --progress $mode --out "$out"
    code=$?
    set -e
    outcome=$(ci_live_generation_outcome "$code" "${out}/index.html")
    case "$outcome" in
        ok)
            echo "✅ Site generation completed"
            ;;
        fallback)
            echo "⚠️  Generation exited 0 without ${out}/index.html; using CI fixtures"
            generate_from_ci_fixtures "$out" "$allium_py" "$mode" || return $?
            echo "✅ Site generation completed from the CI API fixtures"
            ;;
        *)
            echo "❌ Generation failed with exit code ${code}"
            return "$code"
            ;;
    esac
}

generate_from_ci_fixtures() {
    local out="$1" allium_py="$2" mode="$3"
    local src dir port pid code ready
    if ! src=$(ci_fixture_dir); then
        echo "❌ CI API fixtures are missing; cannot fall back"
        return 1
    fi
    dir=$(mktemp -d)
    cp "$src"/*.json "$dir/"
    port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
    python3 -m http.server "$port" --bind 127.0.0.1 --directory "$dir" >/dev/null 2>&1 &
    pid=$!
    ready=0
    for _try in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
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
    echo "🤖 CI: generating from committed API fixtures at http://127.0.0.1:${port}/"
    set +e
    python3 "$allium_py" --progress $mode --out "$out" \
        --onionoo-details-url "http://127.0.0.1:${port}/onionoo_details.json" \
        --onionoo-uptime-url "http://127.0.0.1:${port}/onionoo_uptime.json" \
        --onionoo-bandwidth-url "http://127.0.0.1:${port}/onionoo_bandwidth.json" \
        --aroi-url "http://127.0.0.1:${port}/aroi_validation.json" \
        --exit-dns-health-url "http://127.0.0.1:${port}/exit_dns_health.json"
    code=$?
    set -e
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -rf "$dir"
    if [ "$code" -ne 0 ] || ! site_index_ready "${out}/index.html"; then
        return 1
    fi
}
