"""Onionoo-shaped data and helpers the chart tests share."""

import struct
import zlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from allium.lib.charts.render import ChartWriter

try:
    import numpy as np

    from allium.lib.charts import raster
except (ImportError, OSError):  # needs cairocffi and numpy, and the cairo library
    np = raster = None
needs_png = pytest.mark.skipif(raster is None, reason="PNG charts need cairocffi, numpy and the cairo library")

DAY = 86400
T0 = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)  # every history's first point
PUBLISHED = "2026-09-30 12:00:00"
SPIKE = [100] * 10 + [400] + [100] * 10  # against a flat read of 100: write/read 4.00 on Sep 11, off the scale
OVERLOADED = dict(stability_is_overloaded=True, overload_ratelimits={  # last report Sep 29, 22:00 UTC
    "timestamp": int(datetime(2026, 9, 29, 22, tzinfo=timezone.utc).timestamp() * 1000),
    "write-count": 3, "read-count": 0})


def block(values, first="2026-09-01 12:00:00", interval=DAY, factor=1000.0):
    return {"first": first, "interval": interval, "factor": factor, "values": list(values)}


def history(write, read=None, key="1_month", **kwargs):
    """A relay's Onionoo bandwidth row for one period; ``read`` defaults to ``write``."""
    return {"write_history": {key: block(write, **kwargs)}, "read_history": {key: block(read or write, **kwargs)}}


def relay(fp, contact="url:example.com", flags=("Guard", "Running"), **extra):
    return dict({"fingerprint": fp, "nickname": "relay" + fp, "contact": contact, "flags": list(flags),
                 "advertised_bandwidth": 250000, "last_restarted": "2026-09-10 08:00:00",
                 "effective_family": [fp], "uptime_percentages": {"1_month": 99.5}}, **extra)


def writer(relays, bandwidth, uptime=None, image_format="svg", cache_dir=None, uptime_first="2026-09-01 12:00:00",
           **options):
    return ChartWriter(SimpleNamespace(
        json={"relays": relays},
        bandwidth_data={"relays_published": PUBLISHED, "relays": [dict(row, fingerprint=fp) for fp, row in bandwidth.items()]},
        uptime_data={"relays_published": PUBLISHED, "relays": [
            {"fingerprint": fp, "uptime": {"1_month": block(values, first=uptime_first, interval=14400, factor=1 / 999.0)}}
            for fp, values in (uptime or {}).items()]},
    ), image_format, cache_dir, **options)


def decode(png):
    """RGB(A) pixels of a PNG as raster writes it: 8-bit RGBA with "Up"-filtered rows, or 8-bit palette with
    unfiltered rows; chunk CRCs checked."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    while pos < len(png):
        length, kind = struct.unpack(">I4s", png[pos:pos + 8])
        data = png[pos + 8:pos + 8 + length]
        assert struct.unpack(">I", png[pos + 8 + length:pos + 12 + length])[0] == zlib.crc32(kind + data)
        chunks[kind] = chunks.get(kind, b"") + data
        pos += 12 + length
    width, height, depth, color = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert depth == 8 and color in (3, 6) and b"IEND" in chunks
    channels = 4 if color == 6 else 1
    rows = np.frombuffer(zlib.decompress(chunks[b"IDAT"]), np.uint8).reshape(height, width * channels + 1)
    if color == 3:
        assert (rows[:, 0] == 0).all()
        return np.frombuffer(chunks[b"PLTE"], np.uint8).reshape(-1, 3)[rows[:, 1:]]
    assert (rows[:, 0] == 2).all()
    return np.cumsum(rows[:, 1:], axis=0, dtype=np.uint8).reshape(height, width, 4)
