"""PNG charts: the Svg's drawing replayed with cairo at 2x and the PNG encoder."""

import struct
import zlib

import pytest

from allium.lib.charts.svg import GREEN, RED, TEXT, Svg

try:
    import numpy as np

    from allium.lib.charts import raster
except (ImportError, OSError):  # needs cairocffi, numpy and zlib-ng, and the cairo library
    pytest.skip("PNG charts need cairocffi, numpy, zlib-ng and the cairo library", allow_module_level=True)


def decode(png):
    """RGBA pixels of a PNG as raster writes it: 8-bit RGBA, every row "Up"-filtered, chunks checked."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    while pos < len(png):
        length, kind = struct.unpack(">I4s", png[pos:pos + 8])
        data = png[pos + 8:pos + 8 + length]
        assert struct.unpack(">I", png[pos + 8 + length:pos + 12 + length])[0] == zlib.crc32(kind + data)
        chunks[kind] = chunks.get(kind, b"") + data
        pos += 12 + length
    width, height, depth, color = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert (depth, color) == (8, 6) and b"IEND" in chunks
    rows = np.frombuffer(zlib.decompress(chunks[b"IDAT"]), np.uint8).reshape(height, width * 4 + 1)
    assert (rows[:, 0] == 2).all()
    return np.cumsum(rows[:, 1:], axis=0, dtype=np.uint8).reshape(height, width, 4)


def test_encode_round_trips_any_pixels():
    rows = np.random.RandomState(1).randint(0, 256, (7, 5 * 4)).astype(np.uint8)
    assert (decode(raster.encode(rows, 5, 7)).reshape(7, 20) == rows).all()


def test_png_is_twice_the_size_with_colors_in_rgba_order():
    svg = Svg(100)
    svg.line(10, 20, 90, 20, GREEN, 4)
    svg.rect(10, 40, 30, 20, RED, 0.5)
    svg.text(50, 85, "Sep 8 · 1–2", 12, TEXT, "middle", bold=True)
    pixels = decode(raster.png(svg.finish(100)))
    assert pixels.shape == (200, 200, 4)
    assert tuple(pixels[4, 4]) == (0x1e, 0x1e, 0x1e, 255)  # background
    assert tuple(pixels[40, 100]) == (0x00, 0xff, 0x7f, 255)  # the middle of the 4 px (8 px at 2x) green line
    half = [(0xff + 0x1e) / 2, (0x6b + 0x1e) / 2, (0x6b + 0x1e) / 2]  # 50% red over the background
    assert np.abs(pixels[100, 50, :3] - half).max() <= 1
    assert (pixels[150:175, 40:160, 0] > 0x80).any()  # the text
