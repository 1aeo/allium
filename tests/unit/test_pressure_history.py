"""Pressure history: parse, seal, freeze, and do not backfill a finished month twice."""

import io
import lzma
import tarfile
import urllib.error
from datetime import datetime, timedelta, timezone

from allium.lib import pressure_history as pressure


def _descriptor(fingerprint, published, overload=False):
    spaced = " ".join(fingerprint[i:i + 4] for i in range(0, 40, 4))
    lines = [
        "@type server-descriptor 1.0",
        "router test 1.2.3.4 9001 0 0",
        "published %s 00:00:00" % published,
        "fingerprint %s" % spaced,
    ]
    if overload:
        lines.append("overload-general 1 %s 00:00:00" % published)
    return "\n".join(lines) + "\n"


def test_descriptor_share_counts_a_relay_once():
    text = _descriptor("A" * 40, "2026-11-01", True) + _descriptor("A" * 40, "2026-11-01", False)
    text += _descriptor("B" * 40, "2026-11-01", False) + _descriptor("G" * 40, "2026-11-01", True)
    found = {}
    pressure.accumulate_descriptors([text], found)
    day = datetime(2026, 11, 1).date()
    publishers, overloaded, share = pressure.counts_from_fingerprints(found[day])
    assert publishers == 2
    assert overloaded == 1
    assert share == 50.0


def test_incomplete_consensus_day_is_not_a_flag_census():
    document = pressure.empty_document()
    parsed = {}
    for offset in range(7):
        day = datetime(2025, 6, 6 + offset).date()
        parsed[day] = {"Guard": 1000 if offset == 3 else 5000, "HSDir": 1000 if offset == 3 else 4000,
                       "Running": 1000 if offset == 3 else 8000}
    pressure.apply_relayflags(document, parsed)
    assert document["days"]["2025-06-09"]["flags_ok"] is False
    assert document["days"]["2025-06-08"]["flags_ok"] is True


def test_flag_census_ignores_days_outside_the_calendar_window():
    document = pressure.empty_document()
    pressure.apply_relayflags(document, {
        datetime(2025, 6, 1).date(): {"Guard": 5000, "HSDir": 4000, "Running": 8000},
        datetime(2025, 7, 1).date(): {"Guard": 100, "HSDir": 100, "Running": 100},
    })
    assert document["days"]["2025-07-01"]["flags_ok"] is True


def test_sealed_overload_day_is_not_replaced():
    document = pressure.empty_document()
    day = datetime(2026, 1, 1).date()
    document["days"][day.isoformat()] = {
        "overload_publishers": 10, "overload_overloaded": 1, "overload_share": 10.0, "overload_sealed": True,
    }
    later = {day: {"F" * 40: True, "E" * 40: True}}
    pressure.apply_overload_maps(document, [later], datetime(2026, 1, 10, tzinfo=timezone.utc))
    assert document["days"][day.isoformat()]["overload_share"] == 10.0


def test_percentile_is_linear():
    assert pressure.percentile([1, 2, 3, 4], 0.5) == 2.5
    assert pressure.percentile([10], 0.9) == 10


def test_csv_skips_bad_lines_and_finds_dirwrite():
    flags = pressure.parse_relayflags("date,flag,relays\n2026-01-01,Guard,nope\n2026-01-01,Guard,5\n")
    assert flags[datetime(2026, 1, 1).date()]["Guard"] == 5
    directory = pressure.parse_dirbytes("date,dirwrite,dirread\n2026-01-01,7.5,1\nbad\n")
    assert directory[datetime(2026, 1, 1).date()] == 7.5


def _response(body):
    class _Response:
        def __init__(self):
            self._rest = body if isinstance(body, bytes) else body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            if not self._rest:
                return b""
            if size is None or size < 0 or size >= len(self._rest):
                taken, self._rest = self._rest, b""
                return taken
            taken, self._rest = self._rest[:size], self._rest[size:]
            return taken

    return _Response()


def _tar_xz(descriptors):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        payload = "\n".join(descriptors).encode("utf-8")
        info = tarfile.TarInfo("desc")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    raw.seek(0)
    return lzma.compress(raw.read())


def _refresh(tmp_path, now, archive, recent="<html></html>", descriptor=None):
    flags = "date,flag,relays\n2021-11-02,Guard,5000\n2021-11-02,HSDir,4000\n2021-11-02,Running,8000\n"
    directory = "date,dirread,dirwrite,dirauthread,dirauthwrite\n2021-11-02,1,4.5,0,0\n"
    calls = []

    def opener(request, timeout=None):
        url = request.full_url
        calls.append(url)
        if "relayflags.csv" in url:
            return _response(flags)
        if "dirbytes.csv" in url:
            return _response(directory)
        if url.endswith("server-descriptors/"):
            return _response(recent)
        if url.endswith(".tar.xz"):
            return _response(archive)
        if descriptor and "server-descriptors" in url:
            return _response(descriptor)
        raise AssertionError(url)

    document = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    return document, calls


def test_open_month_is_not_marked_finished(tmp_path):
    archive = _tar_xz([
        _descriptor("A" * 40, "2021-11-02", True),
        _descriptor("B" * 40, "2021-11-02", False),
    ])
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    first, calls = _refresh(tmp_path, now, archive)
    assert "2021-11" not in first["processed_months"]
    assert first["current_month_through"] == "2021-11-02"
    assert first["days"]["2021-11-02"]["overload_share"] == 50.0
    assert first["days"]["2021-11-02"]["overload_sealed"] is True
    assert len([url for url in calls if url.endswith(".tar.xz")]) == 1

    _second, again = _refresh(tmp_path, now, archive)
    assert not any(url.endswith(".tar.xz") for url in again)
    assert _second["days"]["2021-11-02"]["overload_share"] == 50.0


def test_finished_month_is_downloaded_once(tmp_path):
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", True)])
    now = datetime(2021, 12, 15, tzinfo=timezone.utc)
    first, calls = _refresh(tmp_path, now, archive)
    tar_calls = [url for url in calls if url.endswith(".tar.xz")]
    assert any(url.endswith("server-descriptors-2021-11.tar.xz") for url in tar_calls)
    assert "2021-11" in first["processed_months"]
    assert "2021-12" not in first["processed_months"]

    _second, again = _refresh(tmp_path, now, archive)
    assert not any(url.endswith(".tar.xz") for url in again)


def test_month_marked_done_too_early_is_fetched_again(tmp_path):
    document = pressure.empty_document()
    document["processed_months"] = ["2021-11"]
    pressure.save_document(document, str(tmp_path))
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    refreshed, calls = _refresh(tmp_path, now, archive)
    assert "2021-11" not in refreshed["processed_months"]
    assert any(url.endswith("server-descriptors-2021-11.tar.xz") for url in calls)
    assert refreshed["days"]["2021-11-02"]["overload_publishers"] == 1


def test_old_cache_redownloads_only_its_newest_month(tmp_path):
    document = pressure.empty_document()
    document["processed_months"] = ["2021-10", "2021-11"]
    pressure.save_document(document, str(tmp_path))
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    now = datetime(2021, 12, 15, tzinfo=timezone.utc)
    refreshed, calls = _refresh(tmp_path, now, archive)
    tar = [url for url in calls if url.endswith(".tar.xz")]
    assert any(url.endswith("server-descriptors-2021-11.tar.xz") for url in tar)
    assert not any("2021-10" in url for url in tar)
    assert "2021-11" in refreshed["processed_months"]
    assert refreshed["archive_revision"] == 2
    _again, later = _refresh(tmp_path, now, archive)
    assert not any(url.endswith("2021-11.tar.xz") or url.endswith("2021-10.tar.xz") for url in later)


def test_open_month_is_fetched_again_when_a_sealed_day_is_missing(tmp_path):
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    _refresh(tmp_path, now, archive)
    later = now + timedelta(days=2)
    _document, calls = _refresh(tmp_path, later, archive)
    assert any(url.endswith(".tar.xz") for url in calls)


def test_open_month_stays_cached_when_sealed_days_are_present(tmp_path):
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    document, _calls = _refresh(tmp_path, now, archive)
    last = pressure.seal_before(now + timedelta(days=2)) - timedelta(days=1)
    day = datetime(2021, 11, 3).date()
    while day <= last:
        document["days"][day.isoformat()] = {"overload_sealed": True, "overload_share": 1.0}
        day += timedelta(days=1)
    pressure.save_document(document, str(tmp_path))
    _again, calls = _refresh(tmp_path, now + timedelta(days=2), archive)
    assert not any(url.endswith(".tar.xz") for url in calls)


def test_recent_day_past_the_archive_stays_open(tmp_path):
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    recent = '<a href="2021-11-19-00-00-00-server-descriptors">x</a>'
    body = _descriptor("C" * 40, "2021-11-10", True)
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    document, _calls = _refresh(tmp_path, now, archive, recent=recent, descriptor=body)
    row = document["days"]["2021-11-10"]
    assert row["overload_sealed"] is False
    assert row["overload_share"] == 100.0
    assert document["days"]["2021-11-02"]["overload_sealed"] is True


def test_recent_relay_is_counted_before_the_day_seals(tmp_path):
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    recent = '<a href="2021-11-19-00-00-00-server-descriptors">x</a>'
    body = _descriptor("B" * 40, "2021-11-02", True)
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    document, _calls = _refresh(tmp_path, now, archive, recent=recent, descriptor=body)
    row = document["days"]["2021-11-02"]
    assert row["overload_sealed"] is True
    assert row["overload_publishers"] == 2
    assert row["overload_share"] == 50.0


def test_status_run_stops_at_a_missing_day():
    document = pressure.empty_document()
    document["bands"]["guard"] = {"p10": 1000, "p90": 2000}
    for day, guard in ((1, 100), (19, 100)):
        current = datetime(2021, 11, day).date()
        document["days"][current.isoformat()] = {"guard": guard, "flags_ok": True, "overload_share": 20.0}
    began, days = pressure.guard_below_since(document, 1000)
    assert began == datetime(2021, 11, 19).date()
    assert days == 0
    status, since, _share = pressure.status_since(document, 1.9)
    assert status == "high"
    assert since == datetime(2021, 11, 19).date()


def test_failed_recent_file_does_not_seal_the_day(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    recent = '<a href="2021-11-19-00-00-00-server-descriptors">x</a>'
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)

    def opener(request, timeout=None):
        url = request.full_url
        if "2021-11-19-00-00-00-server-descriptors" in url:
            raise OSError("missing")
        if "relayflags.csv" in url:
            return _response("date,flag,relays\n2021-11-02,Guard,5000\n2021-11-02,Running,8000\n")
        if "dirbytes.csv" in url:
            return _response("date,dirread,dirwrite\n2021-11-02,1,4.5\n")
        if url.endswith("server-descriptors/"):
            return _response(recent)
        if url.endswith(".tar.xz"):
            return _response(archive)
        raise AssertionError(url)

    document = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    assert document["days"]["2021-11-02"]["overload_sealed"] is False
    assert document["overload_open"]["2021-11-02"]["A" * 40] is False
    pending = pressure.load_descriptor_files(str(tmp_path))
    assert pending["2021-11-19-00-00-00-server-descriptors"] == {"pending": True}

    calls = []

    def opener_later(request, timeout=None):
        url = request.full_url
        calls.append(url)
        if url.endswith("server-descriptors/"):
            return _response("")
        if "2021-11-19-00-00-00-server-descriptors" in url:
            return _response(_descriptor("B" * 40, "2021-11-02", True))
        return opener(request, timeout)

    # The file has left the 36-hour listing and is still inside the 72-hour window.
    sealed = pressure.refresh(cache_dir=str(tmp_path), now=now + timedelta(days=1), opener=opener_later,
                              log=lambda _message: None)
    assert any("2021-11-19-00-00-00-server-descriptors" in url for url in calls)
    row = sealed["days"]["2021-11-02"]
    assert row["overload_sealed"] is True
    assert row["overload_publishers"] == 2
    assert row["overload_share"] == 50.0


def test_gone_recent_file_does_not_block_sealing(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    archive = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    recent = '<a href="2021-11-19-00-00-00-server-descriptors">x</a>'
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    name = "2021-11-19-00-00-00-server-descriptors"

    def opener(request, timeout=None):
        url = request.full_url
        if name in url and not url.endswith("/"):
            raise OSError("down")
        if "relayflags.csv" in url:
            return _response("date,flag,relays\n")
        if "dirbytes.csv" in url:
            return _response("date,dirwrite\n")
        if url.endswith("server-descriptors/"):
            return _response(recent)
        if url.endswith(".tar.xz"):
            return _response(archive)
        raise AssertionError(url)

    first = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    assert first["days"]["2021-11-02"]["overload_sealed"] is False

    def gone(request, timeout=None):
        url = request.full_url
        if name in url and not url.endswith("/"):
            raise urllib.error.HTTPError(url, 404, "not found", hdrs=None, fp=io.BytesIO(b""))
        if url.endswith("server-descriptors/"):
            return _response("")
        return opener(request, timeout)

    later = pressure.refresh(cache_dir=str(tmp_path), now=now + timedelta(days=1), opener=gone,
                             log=lambda _message: None)
    assert pressure.load_descriptor_files(str(tmp_path))[name]["gone"] is True
    assert later["days"]["2021-11-02"]["overload_sealed"] is True
    assert later["days"]["2021-11-02"]["overload_publishers"] == 1


def test_expired_pending_file_clears_when_the_archive_covers_its_day(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    name = "2021-11-19-00-00-00-server-descriptors"
    early = _tar_xz([_descriptor("A" * 40, "2021-11-02", False)])
    covered = _tar_xz([
        _descriptor("A" * 40, "2021-11-19", False),
        _descriptor("B" * 40, "2021-11-19", True),
    ])
    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    hold = {"archive": early}

    def opener(request, timeout=None):
        url = request.full_url
        if name in url and not url.endswith("/"):
            raise OSError("down")
        if "relayflags.csv" in url:
            return _response("date,flag,relays\n")
        if "dirbytes.csv" in url:
            return _response("date,dirwrite\n")
        if url.endswith("server-descriptors/"):
            return _response('<a href="%s">x</a>' % name)
        if url.endswith(".tar.xz"):
            return _response(hold["archive"])
        raise AssertionError(url)

    first = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    assert first["days"]["2021-11-02"]["overload_sealed"] is False
    assert pressure.load_descriptor_files(str(tmp_path))[name] == {"pending": True}

    calls = []
    hold["archive"] = covered

    def later_opener(request, timeout=None):
        calls.append(request.full_url)
        if request.full_url.endswith("server-descriptors/"):
            return _response("")
        return opener(request, timeout)

    later = pressure.refresh(cache_dir=str(tmp_path), now=now + timedelta(days=4), opener=later_opener,
                             log=lambda _message: None)
    assert not any(name in url and not url.endswith("/") for url in calls)
    assert name not in pressure.load_descriptor_files(str(tmp_path))
    row = later["days"]["2021-11-19"]
    assert row["overload_sealed"] is True
    assert row["overload_publishers"] == 2
    assert row["overload_share"] == 50.0


def test_open_month_archive_does_not_cover_an_earlier_pending_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    now = datetime(2021, 12, 10, tzinfo=timezone.utc)
    name = "2021-11-19-00-00-00-server-descriptors"
    document = pressure.empty_document()
    document["archive_revision"] = 2
    document["current_month_through"] = "2021-12-04"
    document["current_month_fetched_at"] = now.isoformat()
    document["days"]["2021-11-19"] = {
        "overload_publishers": 1, "overload_overloaded": 0, "overload_share": 0.0, "overload_sealed": False,
    }
    document["overload_open"] = {"2021-11-19": {"A" * 40: False}}
    pressure.save_document(document, str(tmp_path))
    pressure.save_descriptor_files({name: {"pending": True}}, str(tmp_path))

    def opener(request, timeout=None):
        url = request.full_url
        if "relayflags.csv" in url or "dirbytes.csv" in url or url.endswith("server-descriptors/"):
            return _response("date,flag,relays\n")
        if url.endswith(".tar.xz"):
            raise OSError("archive unavailable")
        raise AssertionError(url)

    refreshed = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    assert name in pressure.load_descriptor_files(str(tmp_path))
    assert refreshed["days"]["2021-11-19"]["overload_sealed"] is False


def test_finished_month_seals_days_that_were_still_open(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    now = datetime(2021, 12, 5, tzinfo=timezone.utc)
    document = pressure.empty_document()
    document["archive_revision"] = 2
    document["processed_months"] = ["2021-11"]
    document["current_month_through"] = "2021-12-02"
    document["current_month_fetched_at"] = now.isoformat()
    document["days"]["2021-11-30"] = {
        "overload_publishers": 1, "overload_overloaded": 1, "overload_share": 100.0, "overload_sealed": False,
    }
    document["overload_open"] = {"2021-11-30": {"A" * 40: True}}
    pressure.save_document(document, str(tmp_path))

    def opener(request, timeout=None):
        url = request.full_url
        if "relayflags.csv" in url or "dirbytes.csv" in url or url.endswith("server-descriptors/"):
            return _response("date,flag,relays\n")
        raise AssertionError(url)

    refreshed = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _message: None)
    assert refreshed["days"]["2021-11-30"]["overload_sealed"] is True
    assert "2021-11-30" not in refreshed["overload_open"]


def _quiet_opener(request, timeout=None):
    url = request.full_url
    if "relayflags.csv" in url or "dirbytes.csv" in url or url.endswith("server-descriptors/"):
        return _response("date,flag,relays\n")
    if url.endswith(".tar.xz"):
        raise OSError("archive unavailable")
    raise AssertionError(url)


def test_bands_wait_until_every_baseline_month_is_archived(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    document = pressure.empty_document()
    document["archive_revision"] = 2
    day = datetime(2025, 5, 1, tzinfo=timezone.utc).date()
    for offset in range(320):
        current = day + timedelta(days=offset)
        if current > pressure.BASELINE_END:
            break
        document["days"][current.isoformat()] = {
            "guard": 5000, "hsdir": 4500, "running": 8000, "flags_ok": True,
            "directory": 5.0, "overload_share": 1.0, "overload_sealed": True,
        }
    document["processed_months"] = [name for name in pressure.baseline_months() if name != "2026-03"]
    pressure.save_document(document, str(tmp_path))
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)
    first = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=_quiet_opener, log=lambda _message: None)
    assert "frozen" not in first["bands"]

    first["processed_months"] = pressure.baseline_months()
    first["archive_revision"] = 2
    pressure.save_document(first, str(tmp_path))
    second = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=_quiet_opener, log=lambda _message: None)
    assert second["bands"]["frozen"] is True


def test_failed_fetch_keeps_the_saved_document(tmp_path, monkeypatch):
    monkeypatch.setattr(pressure.time, "sleep", lambda _seconds: None)
    document = pressure.empty_document()
    document["days"]["2021-11-02"] = {"overload_share": 3.0, "overload_sealed": True}
    pressure.save_document(document, str(tmp_path))

    def opener(_request, timeout=None):
        raise OSError("down")

    got = pressure.refresh(cache_dir=str(tmp_path), now=datetime(2021, 11, 20, tzinfo=timezone.utc),
                           opener=opener, log=lambda _message: None)
    assert got["days"]["2021-11-02"]["overload_share"] == 3.0


def test_bands_freeze_once():
    document = pressure.empty_document()
    day = datetime(2025, 5, 1, tzinfo=timezone.utc).date()
    for offset in range(320):
        current = day + timedelta(days=offset)
        if current > pressure.BASELINE_END:
            break
        document["days"][current.isoformat()] = {
            "guard": 5000 + (offset % 10), "hsdir": 4500, "running": 8000, "flags_ok": True, "flags_sealed": True,
            "directory": 5.0, "directory_sealed": True, "overload_share": 1.0, "overload_sealed": True,
        }
    pressure.freeze_bands(document)
    guard = document["bands"]["guard"]["p10"]
    document["days"]["2025-05-01"]["guard"] = 1
    pressure.freeze_bands(document)
    assert document["bands"]["guard"]["p10"] == guard
    assert document["bands"]["frozen"] is True
