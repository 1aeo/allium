"""PNG charts: the Svg's drawing replayed with cairo at 2x and the PNG encoder."""

import re
import struct
import zlib
from datetime import datetime, timezone

import pytest

from allium.lib.charts import svg as svg_module
from allium.lib.charts.svg import GREEN, RED, TEXT, Svg

try:
    import numpy as np

    from allium.lib.charts import raster
except (ImportError, OSError):  # needs cairocffi, numpy and zlib-ng, and the cairo library
    pytest.skip("PNG charts need cairocffi, numpy, zlib-ng and the cairo library", allow_module_level=True)


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


def sample():
    svg = Svg(100)
    svg.line(10, 20, 90, 20, GREEN, 4)
    svg.rect(10, 40, 30, 20, RED, 0.5)
    svg.text(50, 85, "Sep 8 · 1–2", 12, TEXT, "middle", bold=True)
    return svg.finish(100)


def test_encode_round_trips_any_pixels():
    rows = np.random.RandomState(1).randint(0, 256, (7, 5 * 4)).astype(np.uint8)
    assert (decode(raster.encode(rows, 5, 7)).reshape(7, 20) == rows).all()


def test_full_color_png_is_twice_the_size_with_colors_in_rgba_order():
    pixels = decode(raster.png(sample(), colors="full"))
    assert pixels.shape == (200, 200, 4)
    assert tuple(pixels[4, 4]) == (0x1e, 0x1e, 0x1e, 255)  # background
    assert tuple(pixels[40, 100]) == (0x00, 0xff, 0x7f, 255)  # the middle of the 4 px (8 px at 2x) green line
    half = [(0xff + 0x1e) / 2, (0x6b + 0x1e) / 2, (0x6b + 0x1e) / 2]  # 50% red over the background
    assert np.abs(pixels[100, 50, :3] - half).max() <= 1
    assert (pixels[150:175, 40:160, 0] > 0x80).any()  # the text


def test_palette_png_keeps_the_chart_colors_exact_and_is_smaller():
    full, small = raster.png(sample(), colors="full"), raster.png(sample())
    pixels = decode(small)
    assert pixels.shape == (200, 200, 3) and len(small) < len(full)
    assert tuple(pixels[4, 4]) == (0x1e, 0x1e, 0x1e) and tuple(pixels[40, 100]) == (0x00, 0xff, 0x7f)
    assert np.abs(pixels.astype(int) - decode(full)[:, :, :3]).max() <= 48  # edge shades move a little at most
    assert decode(raster.png(sample(), 1.5)).shape == (150, 150, 3)


def test_palette_holds_every_named_chart_color():
    named = [v for v in vars(svg_module).values() if isinstance(v, str) and re.fullmatch("#[0-9a-f]{6}", v)]
    assert len(named) >= 13 and [c for c in named if c[1:] not in raster.PALETTE] == []


def test_every_color_a_chart_draws_is_in_the_palette():
    """A color added to the charts must be added to PALETTE too (scripts/chart_palette.py), or it shifts."""
    from .test_render import history, relay, writer
    drawn = []
    hit = int(datetime(2026, 9, 29, 22, tzinfo=timezone.utc).timestamp() * 1000)
    busy = relay("A", stability_is_overloaded=True,  # overload marker, spike callout, off-scale markers
                 overload_ratelimits={"timestamp": hit, "write-count": 3, "read-count": 0})
    spiky = history([100] * 10 + [400] + [100] * 10, [100] * 21)
    charts = writer([busy, relay("B")], {"A": spiky, "B": history([90 + i for i in range(21)])}, {"A": [999] * 180})
    charts._save = lambda directory, name, draw, *args: drawn.append(draw(*args)) or 0
    charts.relay(busy, None)
    charts.contact([0, 1], None)
    drawn = [svg for svg in drawn if svg]
    assert len(drawn) >= 3
    palette = set(raster.PALETTE)
    # Every color the drawing calls name...
    named = {op[5] for svg in drawn for op in svg.ops if op[0] in ("text", "line", "rect")}
    named |= {op[7] for svg in drawn for op in svg.ops if op[0] == "rect" and op[7]}
    named |= {c for svg in drawn for op in svg.ops if op[0] == "path" for c in (op[2], op[5]) if c != "none"}
    assert sorted(c[1:] for c in named if c[1:] not in palette) == []
    # ...and every blend that covers an area (translucent bands and legend swatches).
    for svg in drawn:
        _surface, rows, width, height = raster.render(svg, 2)
        colors, counts = np.unique(np.ascontiguousarray(rows).view("<u4") & 0xFFFFFF, return_counts=True)
        areas = colors[counts > 0.002 * width * height]
        flat = ["%02x%02x%02x" % (c & 255, (c >> 8) & 255, c >> 16) for c in map(int, areas)]
        assert [c for c in flat if c not in palette] == []
