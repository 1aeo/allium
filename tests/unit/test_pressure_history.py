"""Pressure history: parse, seal, freeze, and do not backfill twice."""

import io
import tarfile
import lzma
from datetime import datetime, timezone
from email.message import Message

import pytest

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
    text += _descriptor("B" * 40, "2026-11-01", False)
    found = {}
    pressure.accumulate_descriptors([text], found)
    day = datetime(2026, 11, 1).date()
    publishers, overloaded, share = pressure.counts_from_fingerprints(found[day])
    assert publishers == 2
    assert overloaded == 1
    assert share == 50.0


def test_incomplete_consensus_day_is_not_a_flag_census():
    document = pressure.empty_document()
    # Six ordinary days around one collapsed Running count.
    parsed = {}
    for offset in range(7):
        day = datetime(2025, 6, 6 + offset).date()
        parsed[day] = {"Guard": 1000 if offset == 3 else 5000, "HSDir": 1000 if offset == 3 else 4000,
                       "Running": 1000 if offset == 3 else 8000}
    pressure.apply_relayflags(document, parsed)
    collapsed = document["days"]["2025-06-09"]
    assert collapsed["flags_ok"] is False
    assert document["days"]["2025-06-08"]["flags_ok"] is True


def test_sealed_overload_day_is_not_replaced():
    document = pressure.empty_document()
    day = datetime(2026, 1, 1).date()
    document["days"][day.isoformat()] = {
        "overload_publishers": 10, "overload_overloaded": 1, "overload_share": 10.0, "overload_sealed": True,
    }
    later = {day: {"F" * 40: True, "E" * 40: True}}
    pressure.apply_overload_maps(document, [later], pressure.HISTORY_START,
                                 datetime(2026, 1, 10, tzinfo=timezone.utc))
    assert document["days"][day.isoformat()]["overload_share"] == 10.0


def test_percentile_is_linear():
    assert pressure.percentile([1, 2, 3, 4], 0.5) == 2.5
    assert pressure.percentile([10], 0.9) == 10


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


def test_second_refresh_does_not_download_the_archive_again(tmp_path):
    archive = _tar_xz([
        _descriptor("A" * 40, "2021-11-02", True),
        _descriptor("B" * 40, "2021-11-02", False),
    ])
    flags = "date,flag,relays\n2021-11-02,Guard,5000\n2021-11-02,HSDir,4000\n2021-11-02,Running,8000\n"
    directory = "date,dirread,dirwrite,dirauthread,dirauthwrite\n2021-11-02,1,4.5,0,0\n"
    recent = '<a href="2021-11-15-00-00-00-server-descriptors">x</a>'
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
        if "server-descriptors-2021-11.tar.xz" in url:
            return _response(archive)
        if "2021-11-15-00-00-00-server-descriptors" in url:
            return _response(_descriptor("C" * 40, "2021-11-15", True))
        raise AssertionError(url)

    now = datetime(2021, 11, 20, tzinfo=timezone.utc)
    first = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _m: None)
    assert "2021-11" in first["processed_months"]
    assert first["days"]["2021-11-02"]["overload_share"] == 50.0
    assert first["days"]["2021-11-02"]["overload_sealed"] is True
    archive_calls = [url for url in calls if url.endswith(".tar.xz")]
    assert len(archive_calls) == 1

    calls.clear()
    second = pressure.refresh(cache_dir=str(tmp_path), now=now, opener=opener, log=lambda _m: None)
    assert not any(url.endswith(".tar.xz") for url in calls)
    assert second["days"]["2021-11-02"]["overload_share"] == 50.0
    assert second["processed_months"] == first["processed_months"]


def test_bands_freeze_once():
    document = pressure.empty_document()
    for offset in range(320):
        day = datetime(2025, 5, 1, tzinfo=timezone.utc).date() + __import__("datetime").timedelta(days=offset)
        if day > pressure.BASELINE_END:
            break
        document["days"][day.isoformat()] = {
            "guard": 5000 + (offset % 10),
            "hsdir": 4500,
            "running": 8000,
            "flags_ok": True,
            "flags_sealed": True,
            "directory": 5.0,
            "directory_sealed": True,
            "overload_share": 1.0,
            "overload_sealed": True,
        }
    pressure.freeze_bands(document)
    guard = document["bands"]["guard"]["p10"]
    document["days"]["2025-05-01"]["guard"] = 1
    pressure.freeze_bands(document)
    assert document["bands"]["guard"]["p10"] == guard
    assert document["bands"]["frozen"] is True
