"""Daily network-pressure history: one sealed row per UTC day, then a short tail.

Guard and HSDir counts and directory bytes served come from Tor Metrics.
The overload share comes from CollecTor server descriptors (the
``overload-general`` line). The first run backfills the history. Later runs
only refresh days that are not sealed, and do not download archive months
again.

Directory bytes served are the bytes a directory mirror sent while answering
directory requests (consensuses, descriptors, microdescriptors). Tor Metrics
publishes that outbound total as ``dirwrite``.
"""

import json
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from .charts.series import WINDOW
from .workers import CACHE_DIR

METRICS = "https://metrics.torproject.org"
COLLECTOR = "https://collector.torproject.org"
ARCHIVE = COLLECTOR + "/archive/relay-descriptors/server-descriptors/server-descriptors-%s.tar.xz"
RECENT = COLLECTOR + "/recent/relay-descriptors/server-descriptors/"
USER_AGENT = "Allium/1.0"
# Relays publish about every 18 hours. A UTC day stays open for this long after
# it ends so a descriptor published late still counts, matching the descriptor
# worker's coverage window.
SEAL_AFTER = timedelta(hours=36)
# 5Y charts reach back this far. Months before the cache are not inferred.
HISTORY_START = datetime(2021, 11, 1, tzinfo=timezone.utc).date()
# Quiet year the usual-range band is frozen from. Not recomputed later.
BASELINE_START = datetime(2025, 5, 1, tzinfo=timezone.utc).date()
BASELINE_END = datetime(2026, 5, 31, tzinfo=timezone.utc).date()
# Above the frozen p90, and below this, the overload status is "elevated".
HIGH_SHARE = 10.0
# A Running count under half the surrounding days is an incomplete consensus.
INCOMPLETE_RUNNING = 0.5
RECENT_NAME = re.compile(
    r"href=\"([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-server-descriptors)\""
)
DOCUMENT_NAME = "pressure_history.json"
FILES_NAME = "pressure_descriptor_files.json"


def document_path(cache_dir=None):
    return os.path.join(cache_dir or CACHE_DIR, DOCUMENT_NAME)


def files_path(cache_dir=None):
    return os.path.join(cache_dir or CACHE_DIR, FILES_NAME)


def empty_document():
    return {
        "version": 1,
        "days": {},
        "processed_months": [],
        "bands": {},
        "flags_fetched_through": None,
        "directory_fetched_through": None,
        # Unsealed overload days still need the fingerprint sets so a later
        # descriptor file can be merged without double-counting.
        "overload_open": {},
    }


def load_document(cache_dir=None):
    path = document_path(cache_dir)
    if not os.path.exists(path):
        return empty_document()
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("days", {})
    data.setdefault("processed_months", [])
    data.setdefault("bands", {})
    data.setdefault("overload_open", {})
    return data


def save_document(document, cache_dir=None):
    path = document_path(cache_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(document, handle, separators=(",", ":"), sort_keys=True)
    os.replace(temporary, path)


def load_descriptor_files(cache_dir=None):
    path = files_path(cache_dir)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def save_descriptor_files(files, cache_dir=None):
    path = files_path(cache_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(files, handle, separators=(",", ":"), sort_keys=True)
    os.replace(temporary, path)


def percentile(values, fraction):
    """Linear percentile, rank ``(n - 1) * fraction``."""
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _day(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def _day_row(document, day):
    key = day.isoformat()
    row = document["days"].get(key)
    if row is None:
        row = document["days"][key] = {}
    return row


def _call(action, attempts=4):
    """Retry a network read. A stalled socket should not throw away a finished archive."""
    error = None
    for attempt in range(attempts):
        try:
            return action()
        except OSError as failed:
            error = failed
            time.sleep(min(20, 2 ** attempt))
    raise error


def _http_bytes(url, timeout, opener=None):
    def once():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        open_url = opener or urllib.request.urlopen
        with open_url(request, timeout=timeout) as response:
            return response.read()

    return _call(once)


def _http_text(url, timeout, opener=None):
    return _http_bytes(url, timeout, opener).decode("utf-8", "replace")


def parse_relayflags(text):
    """``{date: {flag: count}}`` from a Tor Metrics ``relayflags.csv`` body."""
    found = {}
    for line in text.splitlines():
        if not line.startswith("20"):
            continue
        day_text, flag, count = line.strip().split(",")
        found.setdefault(_day(day_text), {})[flag] = int(count)
    return found


def parse_dirbytes(text):
    """``{date: dirwrite Gbit/s}``. A missing date is absent. A zero is kept."""
    found = {}
    for line in text.splitlines():
        if not line.startswith("20"):
            continue
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        found[_day(parts[0])] = float(parts[2])
    return found


def _consume_descriptor(state, line):
    """Feed one line. ``state`` is ``[fp, published, overload, started]``."""
    if line.startswith("@type server-descriptor") or (line.startswith("router ") and state[3]):
        finished = _finish_descriptor(state)
        state[:] = [None, None, False, line.startswith("router ") or line.startswith("@type")]
        if line.startswith("router "):
            state[3] = True
        return finished
    if line.startswith("router "):
        state[3] = True
    elif line.startswith("fingerprint "):
        state[0] = line.split(" ", 1)[1].replace(" ", "").strip().upper()
    elif line.startswith("published ") and len(line) >= 20:
        state[1] = line[10:20]
    elif line.startswith("overload-general "):
        state[2] = True
    return None


def _finish_descriptor(state):
    fingerprint, published, overload, started = state
    if not started or not fingerprint or len(fingerprint) != 40 or not published:
        return None
    try:
        day = _day(published)
    except ValueError:
        return None
    return day, fingerprint, bool(overload)


def accumulate_descriptors(chunks, into):
    """Merge descriptor text or binary chunks into ``into[day][fingerprint] = overloaded``.

    A relay counts once per day. It is overloaded that day when any descriptor
    it published that day contains ``overload-general``.
    """
    state = [None, None, False, False]

    def feed(line):
        found = _consume_descriptor(state, line)
        if found:
            day, fingerprint, overload = found
            bucket = into.setdefault(day, {})
            bucket[fingerprint] = bucket.get(fingerprint, False) or overload

    for chunk in chunks:
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", "replace")
        else:
            text = chunk
        for line in text.splitlines():
            feed(line.rstrip("\r"))
    found = _finish_descriptor(state)
    if found:
        day, fingerprint, overload = found
        bucket = into.setdefault(day, {})
        bucket[fingerprint] = bucket.get(fingerprint, False) or overload


def counts_from_fingerprints(day_map):
    publishers = len(day_map)
    overloaded = sum(1 for flagged in day_map.values() if flagged)
    share = (100.0 * overloaded / publishers) if publishers else None
    return publishers, overloaded, share


def apply_relayflags(document, parsed):
    """Merge flag counts. Every day but the newest in this fetch is sealed."""
    if not parsed:
        return
    newest = max(parsed)
    for day, flags in parsed.items():
        row = _day_row(document, day)
        row["guard"] = flags.get("Guard")
        row["hsdir"] = flags.get("HSDir")
        row["running"] = flags.get("Running")
        row["flags_sealed"] = day != newest
    document["flags_fetched_through"] = newest.isoformat()
    _mark_incomplete_flags(document)


def apply_dirbytes(document, parsed):
    if not parsed:
        return
    newest = max(parsed)
    for day, value in parsed.items():
        row = _day_row(document, day)
        row["directory"] = value
        row["directory_sealed"] = day != newest
    document["directory_fetched_through"] = newest.isoformat()


def _mark_incomplete_flags(document):
    """A Running count under half the surrounding days is not a real census."""
    dated = sorted(
        ( _day(key), row) for key, row in document["days"].items()
        if isinstance(row.get("running"), int)
    )
    for index, (day, row) in enumerate(dated):
        window = []
        for other in range(max(0, index - 3), min(len(dated), index + 4)):
            if other != index:
                window.append(dated[other][1]["running"])
        if len(window) < 4:
            row["flags_ok"] = True
            continue
        typical = sorted(window)[len(window) // 2]
        row["flags_ok"] = not (typical and row["running"] < INCOMPLETE_RUNNING * typical)


def seal_before(now):
    """The first UTC day that is still open."""
    moment = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (moment - SEAL_AFTER).date()


def apply_overload_maps(document, day_maps, opened_before, now):
    """Merge fingerprint maps into unsealed days and seal days that have closed.

    ``day_maps`` is a list of ``{day: {fingerprint: overloaded}}``. Sealed days
    are left as stored.
    """
    combined = defaultdict(dict)
    for day_text, pairs in (document.get("overload_open") or {}).items():
        day = _day(day_text)
        for fingerprint, overloaded in pairs.items():
            combined[day][fingerprint] = bool(overloaded)
    for day_map in day_maps:
        for day, fingerprints in day_map.items():
            row = document["days"].get(day.isoformat())
            if row and row.get("overload_sealed"):
                continue
            for fingerprint, overloaded in fingerprints.items():
                previous = combined[day].get(fingerprint, False)
                combined[day][fingerprint] = previous or bool(overloaded)
    horizon = seal_before(now)
    open_sets = {}
    for day, fingerprints in combined.items():
        if day < opened_before:
            continue
        publishers, overloaded, share = counts_from_fingerprints(fingerprints)
        row = _day_row(document, day)
        row["overload_publishers"] = publishers
        row["overload_overloaded"] = overloaded
        row["overload_share"] = None if share is None else round(share, 4)
        if day < horizon:
            row["overload_sealed"] = True
        else:
            row["overload_sealed"] = False
            open_sets[day.isoformat()] = {fp: bool(flag) for fp, flag in fingerprints.items()}
    document["overload_open"] = open_sets


def freeze_bands(document):
    """Fill any missing usual-range band from the quiet year. Never replace one."""
    bands = document.setdefault("bands", {})
    window = [
        (day, row) for day, row in (
            (_day(key), row) for key, row in document["days"].items()
        )
        if BASELINE_START <= day <= BASELINE_END
    ]
    if "guard" not in bands:
        values = [row.get("guard") for _day, row in window if row.get("flags_ok") and row.get("guard") is not None]
        if len(values) >= 300:
            bands["guard"] = {"p10": round(percentile(values, 0.10)), "p90": round(percentile(values, 0.90)),
                              "n": len(values)}
    if "hsdir" not in bands:
        values = [row.get("hsdir") for _day, row in window if row.get("flags_ok") and row.get("hsdir") is not None]
        if len(values) >= 300:
            bands["hsdir"] = {"p10": round(percentile(values, 0.10)), "p90": round(percentile(values, 0.90)),
                              "n": len(values)}
    if "directory" not in bands:
        values = [row.get("directory") for _day, row in window if isinstance(row.get("directory"), (int, float))]
        if len(values) >= 300:
            bands["directory"] = {"p10": round(percentile(values, 0.10), 1), "p90": round(percentile(values, 0.90), 1),
                                  "n": len(values)}
    if "overload" not in bands:
        values = [row.get("overload_share") for _day, row in window
                  if isinstance(row.get("overload_share"), (int, float)) and row.get("overload_sealed")]
        if len(values) >= 300:
            bands["overload"] = {"p10": round(percentile(values, 0.10), 1), "p90": round(percentile(values, 0.90), 1),
                                 "n": len(values)}
    if len(bands) == 4:
        bands["window"] = [BASELINE_START.isoformat(), BASELINE_END.isoformat()]
        bands["frozen"] = True


def months_to_backfill(document, today):
    """Complete archive months from HISTORY_START through the month before ``today``."""
    done = set(document.get("processed_months") or [])
    year, month = HISTORY_START.year, HISTORY_START.month
    end_year, end_month = today.year, today.month
    pending = []
    while (year, month) < (end_year, end_month):
        name = "%04d-%02d" % (year, month)
        if name not in done:
            pending.append(name)
        month += 1
        if month == 13:
            month = 1
            year += 1
    return pending


def current_month_pending(document, today):
    """The in-progress month is archived once, then left to the recent files."""
    name = "%04d-%02d" % (today.year, today.month)
    return name if name not in set(document.get("processed_months") or []) else None


def _download(url, dest, timeout, opener=None):
    def once():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        open_url = opener or urllib.request.urlopen
        with open_url(request, timeout=timeout) as response, open(dest, "wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)

    _call(once)


def accumulate_archive(path, into):
    """Stream a CollecTor ``.tar.xz`` of server descriptors into ``into``."""
    import lzma
    with lzma.open(path) as compressed:
        with tarfile.open(fileobj=compressed, mode="r|") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                accumulate_descriptors(_line_chunks(extracted), into)


def _line_chunks(fileobj):
    """Yield text lines from a binary file object without holding the member."""
    buffer = b""
    while True:
        block = fileobj.read(1024 * 1024)
        if not block:
            if buffer:
                yield buffer
            return
        buffer += block
        lines = buffer.split(b"\n")
        buffer = lines.pop()
        for line in lines:
            yield line


def _recent_names(listing_html, now):
    cutoff = (now if now.tzinfo else now.replace(tzinfo=timezone.utc)) - SEAL_AFTER
    names = []
    for name in sorted(RECENT_NAME.findall(listing_html)):
        stamp = datetime.strptime(name[:19], "%Y-%m-%d-%H-%M-%S").replace(tzinfo=timezone.utc)
        if stamp >= cutoff:
            names.append(name)
    return names


def _csv_url(kind, start):
    if kind == "flags":
        return "%s/relayflags.csv?start=%s" % (METRICS, start.isoformat())
    return "%s/dirbytes.csv?start=%s" % (METRICS, start.isoformat())


def _tail_start(document, field, today):
    """Where a CSV tail starts: the last sealed day, or the history floor."""
    sealed = [
        _day(key) for key, row in document["days"].items()
        if row.get(field)
    ]
    if not sealed:
        return HISTORY_START
    return max(sealed)


def refresh(cache_dir=None, now=None, opener=None, log=None, fetch_archives=True):
    """Backfill whatever months and CSV history are missing, then refresh the tail.

    Returns the document. A second call with the same sealed history does not
    download archive months again.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.date()
    log = log or (lambda message: None)
    document = load_document(cache_dir)
    file_cache = load_descriptor_files(cache_dir)

    flag_start = _tail_start(document, "flags_sealed", today)
    directory_start = _tail_start(document, "directory_sealed", today)
    # The newest day stays unsealed, so the tail includes it and can replace it.
    if document.get("flags_fetched_through"):
        flag_start = _day(document["flags_fetched_through"])
    if document.get("directory_fetched_through"):
        directory_start = _day(document["directory_fetched_through"])
    log("pressure flags from %s" % flag_start.isoformat())
    apply_relayflags(document, parse_relayflags(_http_text(_csv_url("flags", flag_start), 120, opener)))
    log("pressure directory bytes from %s" % directory_start.isoformat())
    apply_dirbytes(document, parse_dirbytes(_http_text(_csv_url("directory", directory_start), 120, opener)))

    if fetch_archives:
        for month in months_to_backfill(document, today):
            _archive_month(document, month, cache_dir, opener, log, now, timeout=600)
        current = current_month_pending(document, today)
        if current:
            _archive_month(document, current, cache_dir, opener, log, now, timeout=600)

    listing = _http_text(RECENT, 120, opener)
    for name in _recent_names(listing, now):
        if name in file_cache:
            continue
        log("pressure descriptor file %s" % name)
        try:
            body = _http_text(RECENT + name, 180, opener)
        except OSError as failed:
            # The next run fetches this file again. Sealed days stay as stored.
            log("pressure descriptor file %s skipped: %s" % (name, failed))
            continue
        parsed = defaultdict(dict)
        accumulate_descriptors([body], parsed)
        file_cache[name] = {
            day.isoformat(): {fingerprint: bool(flag) for fingerprint, flag in fingerprints.items()}
            for day, fingerprints in parsed.items()
        }
    horizon = seal_before(now)
    kept = {}
    recent_maps = []
    for name, days in file_cache.items():
        useful = False
        day_map = {}
        for day_text, pairs in days.items():
            if _day(day_text) >= horizon:
                useful = True
                day_map[_day(day_text)] = pairs
        if useful:
            kept[name] = days
            recent_maps.append(day_map)
    apply_overload_maps(document, recent_maps, HISTORY_START, now)
    save_descriptor_files(kept, cache_dir)
    freeze_bands(document)
    save_document(document, cache_dir)
    log("pressure history %d days, %d archive months" % (
        len(document["days"]), len(document["processed_months"])))
    return document


def _archive_month(document, month, cache_dir, opener, log, now, timeout):
    dest = None
    try:
        log("pressure archive %s downloading" % month)
        handle = tempfile.NamedTemporaryFile(prefix="server-descriptors-%s-" % month, suffix=".tar.xz", delete=False)
        dest = handle.name
        handle.close()
        _download(ARCHIVE % month, dest, timeout, opener)
        log("pressure archive %s parsing" % month)
        parsed = defaultdict(dict)
        accumulate_archive(dest, parsed)
        apply_overload_maps(document, [parsed], HISTORY_START, now)
        document.setdefault("processed_months", []).append(month)
        document["processed_months"] = sorted(set(document["processed_months"]))
        save_document(document, cache_dir)
        log("pressure archive %s done (%d days)" % (month, len(parsed)))
    finally:
        if dest and os.path.exists(dest):
            os.remove(dest)


def series_window(document, field, end, period, flags=False):
    """``(datetimes, values)`` for one chart period ending at ``end``.

    Missing days and, for flag series, incomplete consensus days are None.
    """
    stamps, values = [], []
    # WINDOW is longer than the label (31 days for "last 30 days"); the chart
    # period id is what date_ticks expects, and the extra day matches Onionoo.
    last = end.date() if isinstance(end, datetime) else end
    cursor = last - WINDOW[period] + timedelta(days=1)
    while cursor <= last:
        row = document["days"].get(cursor.isoformat()) or {}
        value = row.get(field)
        if flags and row.get("flags_ok") is False:
            value = None
        if not isinstance(value, (int, float)):
            value = None
        stamps.append(datetime(cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc))
        values.append(value)
        cursor += timedelta(days=1)
    return stamps, values


def latest_value(document, field, flags=False):
    """``(day, value)`` of the newest plotted point, or ``(None, None)``."""
    found = None
    for key in sorted(document["days"]):
        row = document["days"][key]
        if flags and row.get("flags_ok") is False:
            continue
        value = row.get(field)
        if isinstance(value, (int, float)):
            found = (_day(key), value)
    return found or (None, None)


def status_since(document, p90):
    """``(status, day, share)`` of the newest overload run, and when it began."""
    points = []
    for key in sorted(document["days"]):
        share = document["days"][key].get("overload_share")
        if isinstance(share, (int, float)):
            points.append((_day(key), share))
    if not points or p90 is None:
        return None, None, None
    latest_day, latest_share = points[-1]

    def status(share):
        if share <= p90:
            return "usual"
        if share <= HIGH_SHARE:
            return "elevated"
        return "high"

    current = status(latest_share)
    began = latest_day
    for day, share in reversed(points):
        if status(share) != current:
            break
        began = day
    return current, began, latest_share


def guard_below_since(document, low):
    """``(day, days)`` the Guard count has stayed under ``low``, or ``(None, 0)``."""
    if low is None:
        return None, 0
    points = []
    for key in sorted(document["days"]):
        row = document["days"][key]
        if row.get("flags_ok") is False:
            continue
        value = row.get("guard")
        if isinstance(value, int):
            points.append((_day(key), value))
    if not points or points[-1][1] >= low:
        return None, 0
    began = points[-1][0]
    for day, value in reversed(points):
        if value >= low:
            break
        began = day
    return began, (points[-1][0] - began).days


def hsdir_noise(document):
    """``(off, counted)`` quiet-year days more than 10% off a trailing 28-day median."""
    points = []
    for key in sorted(document["days"]):
        row = document["days"][key]
        if row.get("flags_ok") is False:
            continue
        value = row.get("hsdir")
        if isinstance(value, int):
            points.append((_day(key), value))
    off = counted = 0
    by_day = {day: value for day, value in points}
    ordered = [day for day, _value in points]
    index = {day: position for position, day in enumerate(ordered)}
    for day, value in points:
        if not (BASELINE_START <= day <= BASELINE_END):
            continue
        position = index[day]
        window = [by_day[ordered[older]] for older in range(max(0, position - 28), position)]
        if len(window) < 14:
            continue
        typical = median(window)
        counted += 1
        if typical and abs(value - typical) / typical > 0.10:
            off += 1
    return off, counted
