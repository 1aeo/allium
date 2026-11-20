"""Daily network-pressure history: one sealed row per UTC day, then a short tail.

Guard and HSDir counts and directory bytes served come from Tor Metrics.
The overload share comes from CollecTor server descriptors (``overload-general``).
The first run backfills complete archive months. Later runs only refresh days
that are not sealed, and download a month again only while that month is still
open.

Directory bytes served are the bytes a directory mirror sent while answering
directory requests. Tor Metrics publishes that outbound total as ``dirwrite``.
"""

import json
import lzma
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from .charts.series import WINDOW

METRICS = "https://metrics.torproject.org"
COLLECTOR = "https://collector.torproject.org"
ARCHIVE = COLLECTOR + "/archive/relay-descriptors/server-descriptors/server-descriptors-%s.tar.xz"
RECENT = COLLECTOR + "/recent/relay-descriptors/server-descriptors/"
USER_AGENT = "Allium/1.0"
# Relays publish about every 18 hours. A day stays open this long after it ends.
SEAL_AFTER = timedelta(hours=36)
# CollecTor keeps an hourly descriptor file in /recent/ for about three days.
RECENT_AVAILABLE = timedelta(hours=72)
HISTORY_START = datetime(2021, 11, 1, tzinfo=timezone.utc).date()
BASELINE_START = datetime(2025, 5, 1, tzinfo=timezone.utc).date()
BASELINE_END = datetime(2026, 5, 31, tzinfo=timezone.utc).date()
HIGH_SHARE = 10.0
INCOMPLETE_RUNNING = 0.5
MIN_BAND = 300
RECENT_NAME = re.compile(
    r"href=\"([0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-server-descriptors)\""
)
_HEX = set("0123456789ABCDEF")
_PATHS = {"days": "pressure_history.json", "files": "pressure_descriptor_files.json"}


def _root(cache_dir=None):
    """Resolve the cache directory when a call asks for one."""
    if cache_dir:
        return cache_dir
    from .workers import CACHE_DIR
    return CACHE_DIR


def _path(kind, cache_dir=None):
    return os.path.join(_root(cache_dir), _PATHS[kind])


def empty_document():
    return {
        "version": 1, "days": {}, "processed_months": [], "bands": {},
        "flags_fetched_through": None, "directory_fetched_through": None,
        "current_month_fetched_at": None, "current_month_through": None,
        # Fingerprint sets for days still inside the publish window.
        "overload_open": {},
    }


def _load(kind, cache_dir, default):
    fallback = default() if callable(default) else default
    try:
        with open(_path(kind, cache_dir), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return fallback
    return data if isinstance(data, dict) else fallback


def _save(kind, data, cache_dir):
    path = _path(kind, cache_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pressure-", dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, separators=(",", ":"), sort_keys=True)
        os.replace(temporary, path)
    except Exception:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise


def load_document(cache_dir=None):
    document = _load("days", cache_dir, empty_document)
    for key, value in empty_document().items():
        document.setdefault(key, value() if callable(value) else value)
    for key in ("days", "bands", "overload_open"):
        if not isinstance(document.get(key), dict):
            document[key] = {}
    if not isinstance(document.get("processed_months"), list):
        document["processed_months"] = []
    return document


def save_document(document, cache_dir=None):
    _save("days", document, cache_dir)


def load_descriptor_files(cache_dir=None):
    return _load("files", cache_dir, {})


def save_descriptor_files(files, cache_dir=None):
    _save("files", files, cache_dir)


def percentile(values, fraction):
    """Linear percentile, rank ``(n - 1) * fraction``."""
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _day(text):
    return datetime.strptime(str(text)[:10], "%Y-%m-%d").date()


def _as_day(value):
    """A ``date``, or None when ``value`` is not one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return _day(value)
    except (TypeError, ValueError):
        return None


def _month(day):
    return "%04d-%02d" % (day.year, day.month)


def _stamp(day):
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _utc(now):
    now = now or datetime.now(timezone.utc)
    return now if now.tzinfo else now.replace(tzinfo=timezone.utc)


def _day_row(document, day):
    return document["days"].setdefault(day.isoformat(), {})


def _dated_rows(document):
    days = document.get("days") if isinstance(document.get("days"), dict) else {}
    for key in sorted(day_key for day_key in days if isinstance(day_key, str)):
        day = _as_day(key)
        if day is not None and isinstance(days[key], dict):
            yield day, days[key]


def _call(action, attempts=4):
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
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response:
            return response.read()

    return _call(once)


def _http_text(url, timeout, opener=None):
    return _http_bytes(url, timeout, opener).decode("utf-8", "replace")


def _recent_body(url, opener):
    """``(text, gone)``. ``gone`` is true when CollecTor no longer has the file."""
    try:
        return _http_text(url, 180, opener), False
    except urllib.error.HTTPError as failed:
        return None, failed.code == 404
    except OSError:
        return None, False


def _download(url, dest, timeout, opener=None):
    def once():
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with (opener or urllib.request.urlopen)(request, timeout=timeout) as response, open(dest, "wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)

    _call(once)


def _csv_rows(text):
    """``(header, fields)`` for data rows. ``header`` is None when the file has none."""
    header = None
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if not parts or not parts[0]:
            continue
        if header is None and parts[0] == "date":
            header = parts
            continue
        if parts[0].startswith("20"):
            yield header, parts


def _csv_day(parts):
    try:
        return _day(parts[0])
    except (TypeError, ValueError):
        return None


def parse_relayflags(text):
    """``{date: {flag: count}}`` from a Tor Metrics ``relayflags.csv`` body."""
    found = {}
    for _header, parts in _csv_rows(text):
        day = _csv_day(parts)
        if day is None or len(parts) < 3:
            continue
        try:
            found.setdefault(day, {})[parts[1]] = int(parts[2])
        except ValueError:
            continue
    return found


def parse_dirbytes(text):
    """``{date: dirwrite Gbit/s}``. A date with no row is absent, not zero."""
    found = {}
    for header, parts in _csv_rows(text):
        index = header.index("dirwrite") if header and "dirwrite" in header else 2
        day = _csv_day(parts)
        if day is None or len(parts) <= index:
            continue
        try:
            found[day] = float(parts[index])
        except ValueError:
            continue
    return found


def _finish_descriptor(state):
    fingerprint, published, overload, started = state
    if not started or not published or not fingerprint or len(fingerprint) != 40:
        return None
    if any(character not in _HEX for character in fingerprint):
        return None
    try:
        return _day(published), fingerprint, bool(overload)
    except ValueError:
        return None


def _consume_descriptor(state, line):
    """``state`` is ``[fingerprint, published, overload, started]``."""
    new_document = line.startswith("@type server-descriptor") or (line.startswith("router ") and state[3])
    if new_document:
        finished = _finish_descriptor(state)
        state[:] = [None, None, False, True]
        return finished
    if line.startswith("router "):
        state[3] = True
    elif line.startswith("fingerprint "):
        state[0] = "".join(line.split()[1:]).upper()
    elif line.startswith("published "):
        state[1] = line[10:20]
    elif line.startswith("overload-general "):
        state[2] = True
    return None


def _store_fingerprint(into, found):
    if not found:
        return
    day, fingerprint, overload = found
    bucket = into.setdefault(day, {})
    bucket[fingerprint] = bucket.get(fingerprint, False) or overload


def accumulate_descriptors(chunks, into):
    """Merge descriptor text into ``into[day][fingerprint] = overloaded``.

    A relay counts once per day, and is overloaded when any descriptor it
    published that day contains ``overload-general``.
    """
    state = [None, None, False, False]

    def feed(line):
        _store_fingerprint(into, _consume_descriptor(state, line.rstrip("\r")))

    for chunk in chunks:
        text = chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk
        for line in text.splitlines():
            feed(line)
    _store_fingerprint(into, _finish_descriptor(state))


def counts_from_fingerprints(day_map):
    publishers = len(day_map)
    overloaded = sum(1 for flagged in day_map.values() if flagged)
    share = (100.0 * overloaded / publishers) if publishers else None
    return publishers, overloaded, share


def _mark_incomplete_flags(document):
    """A Running count under half of the days within three calendar days is not a census."""
    dated = [(day, row) for day, row in _dated_rows(document) if isinstance(row.get("running"), int)]
    by_day = dict(dated)
    for day, row in dated:
        window = [by_day[day + timedelta(days=offset)]["running"]
                  for offset in range(-3, 4) if offset and (day + timedelta(days=offset)) in by_day]
        typical = sorted(window)[len(window) // 2] if len(window) >= 4 else 0
        row["flags_ok"] = not (typical and row["running"] < INCOMPLETE_RUNNING * typical)


def _apply_sealed_tail(document, parsed, stamp_key, assign):
    """Write ``parsed`` and seal every day except the newest one in the fetch."""
    if not parsed:
        return
    newest = max(parsed)
    for day, value in parsed.items():
        assign(_day_row(document, day), value, day == newest)
    document[stamp_key] = newest.isoformat()


def apply_relayflags(document, parsed):
    def assign(row, flags, open_day):
        row.update(guard=flags.get("Guard"), hsdir=flags.get("HSDir"), running=flags.get("Running"),
                   flags_sealed=not open_day)

    _apply_sealed_tail(document, parsed, "flags_fetched_through", assign)
    _mark_incomplete_flags(document)


def apply_dirbytes(document, parsed):
    def assign(row, value, open_day):
        row.update(directory=value, directory_sealed=not open_day)

    _apply_sealed_tail(document, parsed, "directory_fetched_through", assign)


def seal_before(now):
    """The first UTC day that is still open."""
    return (_utc(now) - SEAL_AFTER).date()


def _sealed(document, day):
    row = document["days"].get(day.isoformat())
    return bool(row and row.get("overload_sealed"))


def _merge_fingerprints(combined, day, fingerprints):
    if not isinstance(fingerprints, dict):
        return
    bucket = combined[day]
    for fingerprint, overloaded in fingerprints.items():
        bucket[fingerprint] = bucket.get(fingerprint, False) or bool(overloaded)


def apply_overload_maps(document, day_maps, now, seal_on=None):
    """Merge fingerprint maps into unsealed days. Sealed days stay as stored.

    ``seal_on(day)`` is false for days the monthly archive has not covered yet,
    so a partial recent-file count is not frozen.
    """
    combined = defaultdict(dict)
    sources = [document.get("overload_open") or {}]
    sources.extend(day_maps)
    for source in sources:
        if not isinstance(source, dict):
            continue
        for raw_day, fingerprints in source.items():
            day = _as_day(raw_day)
            if day is None or day < HISTORY_START or _sealed(document, day):
                continue
            _merge_fingerprints(combined, day, fingerprints)
    horizon = seal_before(now)
    seal_on = seal_on or (lambda _day: True)
    open_sets = {}
    for day, fingerprints in combined.items():
        publishers, overloaded, share = counts_from_fingerprints(fingerprints)
        row = _day_row(document, day)
        row["overload_publishers"] = publishers
        row["overload_overloaded"] = overloaded
        row["overload_share"] = None if share is None else round(share, 4)
        row["overload_sealed"] = day < horizon and seal_on(day)
        if not row["overload_sealed"]:
            open_sets[day.isoformat()] = {fingerprint: bool(flag) for fingerprint, flag in fingerprints.items()}
    document["overload_open"] = open_sets


def _rounded(value, digits):
    return round(value, digits) if digits else round(value)


def _band_values(window, accept):
    return [value for _day_value, row in window if (value := accept(row)) is not None and isinstance(value, (int, float))]


def freeze_bands(document):
    """Fill any missing usual-range band from the quiet year. Never replace one."""
    bands = document.setdefault("bands", {})
    window = [(day, row) for day, row in _dated_rows(document) if BASELINE_START <= day <= BASELINE_END]

    def accept_flag(field):
        return lambda row: row.get(field) if row.get("flags_ok") else None

    specs = (
        ("guard", accept_flag("guard"), 0),
        ("hsdir", accept_flag("hsdir"), 0),
        ("directory", lambda row: row.get("directory"), 1),
        ("overload", lambda row: row.get("overload_share") if row.get("overload_sealed") else None, 1),
    )
    for key, accept, digits in specs:
        if key in bands:
            continue
        values = _band_values(window, accept)
        if len(values) < MIN_BAND:
            continue
        low, high = percentile(values, 0.10), percentile(values, 0.90)
        bands[key] = {"p10": _rounded(low, digits), "p90": _rounded(high, digits), "n": len(values)}
    if all(key in bands for key, _accept, _digits in specs):
        bands["window"] = [BASELINE_START.isoformat(), BASELINE_END.isoformat()]
        bands["frozen"] = True


def baseline_months():
    """UTC months from May 2025 through May 2026, the frozen usual-range window."""
    year, month = BASELINE_START.year, BASELINE_START.month
    last = (BASELINE_END.year, BASELINE_END.month)
    names = []
    while (year, month) <= last:
        names.append("%04d-%02d" % (year, month))
        month, year = (1, year + 1) if month == 12 else (month + 1, year)
    return names


def baseline_archives_ready(document):
    """True when every baseline month was saved from a finished archive."""
    done = set(document.get("processed_months") or [])
    return all(name in done for name in baseline_months())


def months_to_backfill(document, today):
    """Complete months from HISTORY_START through the month before ``today``."""
    done = set(document.get("processed_months") or [])
    year, month = HISTORY_START.year, HISTORY_START.month
    pending = []
    while (year, month) < (today.year, today.month):
        name = "%04d-%02d" % (year, month)
        if name not in done:
            pending.append(name)
        month, year = (1, year + 1) if month == 12 else (month + 1, year)
    return pending


def _missing_sealed_day(document, now):
    """True when a day that should already be sealed is still absent after the last archive day."""
    through = _as_day(document.get("current_month_through"))
    if through is None:
        return True
    day = through + timedelta(days=1)
    last = seal_before(now) - timedelta(days=1)
    while day <= last:
        row = (document.get("days") or {}).get(day.isoformat()) or {}
        if not row.get("overload_sealed"):
            return True
        day += timedelta(days=1)
    return False


def needs_current_month(document, now):
    """The open month is fetched again only when a sealed day may be missing, and at most every 36 hours."""
    today = _utc(now).date()
    if _month(today) in set(document.get("processed_months") or []):
        return False
    if not document.get("current_month_fetched_at"):
        return True
    if not _missing_sealed_day(document, now):
        return False
    try:
        fetched_at = datetime.fromisoformat(document["current_month_fetched_at"])
    except (TypeError, ValueError):
        return True
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return _utc(now) - fetched_at >= SEAL_AFTER


def accumulate_archive(path, into):
    """Stream a CollecTor ``.tar.xz`` of server descriptors into ``into``."""
    with lzma.open(path) as compressed, tarfile.open(fileobj=compressed, mode="r|") as archive:
        for member in archive:
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is not None:
                accumulate_descriptors(_chunks(extracted), into)


def _chunks(fileobj):
    pending = b""
    while True:
        block = fileobj.read(1024 * 1024)
        if not block:
            if pending:
                yield pending
            return
        pending += block
        lines = pending.split(b"\n")
        pending = lines.pop()
        for line in lines:
            yield line


def _recent_names(listing_html, now):
    cutoff = _utc(now) - SEAL_AFTER
    names = []
    for name in RECENT_NAME.findall(listing_html):
        try:
            stamp = datetime.strptime(name[:19], "%Y-%m-%d-%H-%M-%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if stamp >= cutoff:
            names.append(name)
    return sorted(names)


def _seal_limit(limit, month=None):
    """Seal days up to ``limit``. ``month`` restricts that to one archive month."""
    def allow(day):
        if limit is None or day > limit:
            return False
        return month is None or _month(day) == month
    return allow


def _remember_month(document, month, parsed, now, complete):
    """A finished month seals now. The open month waits until recent files are merged."""
    if parsed:
        # Recent files downloaded later in this run can still add relays to the open month.
        seal = _seal_limit(max(parsed), month) if complete else (lambda _day: False)
        apply_overload_maps(document, [parsed], now, seal)
    if complete and parsed:
        document["processed_months"] = sorted(set(document.get("processed_months") or []) | {month})
        return
    if not complete:
        document["current_month_fetched_at"] = _utc(now).isoformat()
        if parsed:
            document["current_month_through"] = max(parsed).isoformat()


def _archive_month(document, month, cache_dir, opener, log, now, complete):
    dest = None
    try:
        log("pressure archive %s downloading" % month)
        handle = tempfile.NamedTemporaryFile(prefix="server-descriptors-%s-" % month, suffix=".tar.xz", delete=False)
        dest = handle.name
        handle.close()
        _download(ARCHIVE % month, dest, 600, opener)
        log("pressure archive %s parsing" % month)
        parsed = defaultdict(dict)
        accumulate_archive(dest, parsed)
        _remember_month(document, month, parsed, now, complete)
        save_document(document, cache_dir)
        log("pressure archive %s done (%d days)" % (month, len(parsed)))
        return True
    finally:
        if dest and os.path.exists(dest):
            os.remove(dest)


def _safe(log, label, action):
    try:
        return action()
    except OSError as failed:
        log("pressure %s unavailable: %s" % (label, failed))
        return None


def _release_open_month(document, today):
    """The month still in progress is not finished, even if an older run marked it."""
    name = _month(today)
    document["processed_months"] = [month for month in document.get("processed_months") or [] if month != name]


def _repair_processed_months(document, today):
    """Older runs marked the in-progress month done. Drop that newest entry once."""
    if document.get("archive_revision") != 2:
        done = list(document.get("processed_months") or [])
        if done:
            latest = max(done)
            document["processed_months"] = [month for month in done if month != latest]
        document["archive_revision"] = 2
    _release_open_month(document, today)


def _saved_day(document, key):
    try:
        return _day(document[key]) if document.get(key) else HISTORY_START
    except (TypeError, ValueError):
        return HISTORY_START


def _is_pending(days):
    """A descriptor file we still have to download, or one CollecTor has removed."""
    return isinstance(days, dict) and days.get("pending") is True and set(days) <= {"pending", "gone"}


def _file_time(name):
    try:
        return datetime.strptime(name[:19], "%Y-%m-%d-%H-%M-%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _recent_available(name, now):
    """True while CollecTor may still be serving this hourly file."""
    stamp = _file_time(name)
    return stamp is not None and _utc(now) - stamp < RECENT_AVAILABLE


def _archive_has_file(document, name):
    """True when a saved archive already covers the day this file was published."""
    stamp = _file_time(name)
    if stamp is None:
        return True
    day = stamp.date()
    if _month(day) in set(document.get("processed_months") or []):
        return True
    through = _as_day(document.get("current_month_through"))
    # The open-month snapshot does not contain days from any earlier month.
    return through is not None and _month(through) == _month(day) and through >= day


def _cache_lock(cache_dir):
    """One writer at a time. Two builds otherwise share a temp file and can drop the cache."""
    directory = _root(cache_dir)
    os.makedirs(directory, exist_ok=True)
    handle = open(os.path.join(directory, "pressure_history.lock"), "a+")
    try:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except ImportError:
        pass
    return handle


def refresh(cache_dir=None, now=None, opener=None, log=None, fetch_archives=True):
    """Backfill missing months, then refresh the tail. Returns the document.

    A second call does not download a complete archive month again. The month
    that is still in progress is downloaded again only when a day that should
    already be sealed is still missing.
    """
    lock = _cache_lock(cache_dir)
    try:
        return _refresh(cache_dir, now, opener, log, fetch_archives)
    finally:
        lock.close()


def _refresh(cache_dir, now, opener, log, fetch_archives):
    now = _utc(now)
    today = now.date()
    log = log or (lambda _message: None)
    document = load_document(cache_dir)
    file_cache = load_descriptor_files(cache_dir)
    if not isinstance(file_cache, dict):
        file_cache = {}

    log("pressure flags from %s" % _saved_day(document, "flags_fetched_through").isoformat())
    flags = _safe(log, "flags", lambda: _http_text(
        "%s/relayflags.csv?start=%s" % (METRICS, _saved_day(document, "flags_fetched_through").isoformat()), 120, opener))
    if flags:
        apply_relayflags(document, parse_relayflags(flags))
    log("pressure directory bytes from %s" % _saved_day(document, "directory_fetched_through").isoformat())
    directory = _safe(log, "directory bytes", lambda: _http_text(
        "%s/dirbytes.csv?start=%s" % (METRICS, _saved_day(document, "directory_fetched_through").isoformat()), 120, opener))
    if directory:
        apply_dirbytes(document, parse_dirbytes(directory))

    if fetch_archives:
        _repair_processed_months(document, today)
        for month in months_to_backfill(document, today):
            saved = _safe(log, "archive %s" % month, lambda month=month: _archive_month(
                document, month, cache_dir, opener, log, now, True))
            if saved is None and month not in set(document.get("processed_months") or []):
                break
        if needs_current_month(document, now):
            _safe(log, "archive %s" % _month(today), lambda: _archive_month(
                document, _month(today), cache_dir, opener, log, now, False))

    listing_body = _safe(log, "recent descriptors", lambda: _http_text(RECENT, 120, opener))
    # A file still inside the 72-hour window can hold the relay that changes a share.
    # Leave open days unsealed until that download succeeds. An older pending file
    # waits for the monthly archive instead, and does not block every other day.
    recent_incomplete = listing_body is None
    listing = listing_body or ""
    names = _recent_names(listing, now)
    for name, days in file_cache.items():
        if _is_pending(days) and name not in names:
            names.append(name)
    for name in names:
        if name in file_cache and not _is_pending(file_cache[name]):
            continue
        stored = file_cache.get(name)
        if _is_pending(stored) and (stored.get("gone") or not _recent_available(name, now)):
            continue
        log("pressure descriptor file %s" % name)
        body, gone = _recent_body(RECENT + name, opener)
        if gone:
            # The file has left CollecTor. Keep the marker until an archive covers its day.
            file_cache[name] = {"gone": True, "pending": True}
            continue
        if not body:
            file_cache[name] = {"pending": True}
            if _recent_available(name, now):
                recent_incomplete = True
            continue
        parsed = defaultdict(dict)
        accumulate_descriptors([body], parsed)
        file_cache[name] = {day.isoformat(): dict(fingerprints) for day, fingerprints in parsed.items()}

    kept, recent_maps = {}, []
    for name, days in file_cache.items():
        if _is_pending(days):
            if _archive_has_file(document, name):
                continue
            kept[name] = days
            if _recent_available(name, now) and not days.get("gone"):
                recent_incomplete = True
            continue
        if not isinstance(days, dict):
            continue
        day_map = {}
        for day_text, pairs in days.items():
            day = _as_day(day_text)
            # Keep a day the archive has not sealed yet. Dropping it here would
            # throw away the only copy of a published date still inside the tail.
            if day is not None and isinstance(pairs, dict) and not _sealed(document, day):
                day_map[day] = pairs
        if day_map:
            kept[name] = days
            recent_maps.append(day_map)
    through = _as_day(document.get("current_month_through"))
    seal = (lambda _day: False) if recent_incomplete else _seal_limit(through, None if through is None else _month(through))
    apply_overload_maps(document, recent_maps, now, seal)
    save_descriptor_files(kept, cache_dir)
    if baseline_archives_ready(document):
        freeze_bands(document)
    save_document(document, cache_dir)
    log("pressure history %d days, %d archive months" % (len(document["days"]), len(document.get("processed_months") or [])))
    return document


def series_window(document, field, end, period, flags=False):
    """``(datetimes, values)`` for one chart period ending at ``end``.

    Missing days and, for flag series, incomplete consensus days are None.
    """
    last = end.date() if isinstance(end, datetime) else end
    cursor = last - WINDOW[period] + timedelta(days=1)
    stamps, values = [], []
    while cursor <= last:
        row = document["days"].get(cursor.isoformat()) or {}
        value = row.get(field)
        if (flags and row.get("flags_ok") is False) or not isinstance(value, (int, float)):
            value = None
        stamps.append(_stamp(cursor))
        values.append(value)
        cursor += timedelta(days=1)
    return stamps, values


def _numeric_points(document, field, flags=False):
    for day, row in _dated_rows(document):
        if flags and row.get("flags_ok") is False:
            continue
        value = row.get(field)
        if isinstance(value, (int, float)):
            yield day, value


def latest_value(document, field, flags=False):
    """``(day, value)`` of the newest plotted point, or ``(None, None)``."""
    found = None
    for day, value in _numeric_points(document, field, flags):
        found = (day, value)
    return found or (None, None)


def _run_start(points, keep):
    """Day the newest run of ``keep(value)`` began, plus the newest point.

    A missing calendar day ends the run, so a gap is not described as continuous.
    """
    if not points or not keep(points[-1][1]):
        return None, points[-1] if points else (None, None)
    began = previous = points[-1][0]
    for day, value in reversed(points):
        if previous - day > timedelta(days=1) or not keep(value):
            break
        began, previous = day, day
    return began, points[-1]


def status_since(document, p90):
    """``(status, day, share)`` of the newest overload run, and when it began."""
    points = list(_numeric_points(document, "overload_share"))
    if not points or p90 is None:
        return None, None, None

    def status(share):
        if share <= p90:
            return "usual"
        return "elevated" if share <= HIGH_SHARE else "high"

    current = status(points[-1][1])
    began, (_day_value, share) = _run_start(points, lambda value: status(value) == current)
    return current, began, share


def guard_below_since(document, low):
    """``(day, days)`` the Guard count has stayed under ``low``, or ``(None, 0)``."""
    if low is None:
        return None, 0
    points = [(day, value) for day, value in _numeric_points(document, "guard", flags=True) if isinstance(value, int)]
    began, latest = _run_start(points, lambda value: value < low)
    if began is None or latest[0] is None:
        return None, 0
    return began, (latest[0] - began).days


def hsdir_noise(document):
    """``(off, counted)`` quiet-year days more than 10% off a trailing 28-day median."""
    points = list(_numeric_points(document, "hsdir", flags=True))
    off = counted = 0
    for position, (day, value) in enumerate(points):
        if not (BASELINE_START <= day <= BASELINE_END):
            continue
        window = [points[older][1] for older in range(max(0, position - 28), position)]
        if len(window) < 14:
            continue
        typical = median(window)
        counted += 1
        if typical and abs(value - typical) / typical > 0.10:
            off += 1
    return off, counted
