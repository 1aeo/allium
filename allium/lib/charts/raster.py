"""PNG charts: an ``Svg``'s own drawing replayed with cairo (2x by default), then PNG-encoded.

About 10.5 ms a chart at 2x, against about 70 ms to rasterize the SVG text
with CairoSVG at the same size: there is no SVG to parse, and the encoders
below (numpy, deflate with zlib-ng) are several times faster than libpng.

By default every pixel is then snapped to PALETTE, 64 colors fixed in
advance, through a lookup table built once: an 8-bit palette PNG is about a
third of the full-color one (~50 KB against ~150 KB at 2x) and looks the
same, at about the same speed. ``colors="full"`` keeps every shade.
"""

import functools
import math
import re
import struct
import sys
import zlib

import cairocffi as cairo
import numpy as np

from .svg import BG

try:  # ~4x faster than zlib at the same size; zlib works too
    from zlib_ng import zlib_ng as deflate
except ImportError:  # pragma: no cover
    deflate = zlib

# Names the chart cache's folder (VERSION, with the background, which is painted
# outside the ops, the palette, the cairo version and the fonts found): change it
# when the replay or the encoding changes. The drawing itself keys each file.
_DRAWING = b"cairo-4"
# The chart's own named colors first (svg.py), so
# they stay exact, then the flat and edge shades that cover the most pixels in
# ~1,250 real charts. scripts/chart_palette.py chose them; run it again after
# adding a color to the charts (tests/unit/charts/test_raster.py checks this).
PALETTE = (
    "00ff7f 161a20 242424 323232 38bdf8 3c3c3c 4da6ff 555555 "
    "9a9a9a b48cff e6e6e6 ff6b6b ffb454 1e1e1e 302424 2d2821 "
    "1a3d2b 2f2f2f 2e2e2e 262626 303030 222222 313131 2b2b2b "
    "252525 232323 4c4c4c 363636 0ca458 06d76f 1b5c3a 553333 "
    "54442e ab7d40 80807f 636265 727173 d5d6d6 8d8d8d 866437 "
    "753c3d ae5051 b5b8b6 c4c6c5 16683f a6a8a7 137b47 3c594a "
    "108f50 6c8176 1cdfa3 0aca6a 8a6dbe 1b4c34 8e4547 41322a "
    "30c7ca 3e8ac4 0cb763 2c4c64 4d6a5b 346a8f 5d7669 7a9085"
).split()
_PLTE = bytes.fromhex("".join(PALETTE))  # R, G, B of each PALETTE color: the PNG's PLTE chunk
_PATH = re.compile(r"([MLlhz])([^MLlhz]*)")  # a command and its coordinates
# Cairo keeps ARGB32 pixels as native-endian words: B, G, R, A in memory on
# little-endian machines. Drawing with red and blue swapped leaves them in
# PNG's R, G, B, A order with no copy. The swap is exact because _FONT_OPTIONS
# keeps antialiasing per pixel: subpixel (per channel) antialiasing, which
# fontconfig turns on in stock Ubuntu, would put color fringes on text.
_SWAP = sys.byteorder == "little"
# Text drawn the same on every build host, and like a browser draws the SVG:
# no hinting, no advances rounded to whole pixels, greyscale antialiasing.
_FONT_OPTIONS = cairo.FontOptions()
_FONT_OPTIONS.set_antialias(cairo.ANTIALIAS_GRAY)
_FONT_OPTIONS.set_hint_style(cairo.HINT_STYLE_NONE)
_FONT_OPTIONS.set_hint_metrics(cairo.HINT_METRICS_OFF)


@functools.lru_cache(maxsize=None)
def _color(hex_color):
    r, g, b = (v / 255.0 for v in bytes.fromhex(hex_color[1:]))
    return (b, g, r) if _SWAP else (r, g, b)


@functools.lru_cache(maxsize=None)
def _face(bold):
    return cairo.ToyFontFace("DejaVu Sans", weight=cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)


def _fonts():
    """Advances of a probe string in the regular and bold faces cairo resolved. They differ for a fallback
    font, so charts drawn before DejaVu Sans was installed are not reused after."""
    ctx = cairo.Context(cairo.ImageSurface(cairo.FORMAT_A8, 1, 1))
    ctx.set_font_options(_FONT_OPTIONS)
    ctx.set_font_size(100)
    advances = []
    for bold in (False, True):
        ctx.set_font_face(_face(bold))
        advances.append("%.2f" % ctx.text_extents("Throughput · write/read – 0123456789")[4])
    return ",".join(advances).encode()


VERSION = b"/".join((_DRAWING, BG.encode(), " ".join(PALETTE).encode(), cairo.cairo_version_string().encode(), _fonts()))


@functools.lru_cache(maxsize=None)
def lookup():
    """Palette index for every 24-bit color (index = R | G << 8 | B << 16): the nearest PALETTE color on a
    6-bit-per-channel grid, and each PALETTE color for itself. 16 MB, built once (~0.4 s), before forking."""
    pal = np.frombuffer(_PLTE, np.uint8).reshape(-1, 3).astype(np.int32)
    grid = np.arange(1 << 18)
    centres = np.stack([grid & 63, (grid >> 6) & 63, grid >> 12], 1) * 4 + 2
    nearest = np.empty(1 << 18, np.uint8)
    for start in range(0, 1 << 18, 1 << 14):
        part = centres[start:start + (1 << 14), None, :] - pal[None]
        nearest[start:start + (1 << 14)] = (part * part).sum(-1).argmin(1)
    # Each grid cell covers 4 values of each channel: blue (high bits) outermost, red innermost.
    lut = nearest.reshape(64, 64, 64).repeat(4, 0).repeat(4, 1).repeat(4, 2).ravel()
    lut[pal[:, 0] | pal[:, 1] << 8 | pal[:, 2] << 16] = np.arange(len(PALETTE))
    return lut


def _stroke(ctx, color, width, dash):
    ctx.set_line_width(width)
    ctx.set_dash([float(v) for v in dash.split()] if dash else [])
    ctx.set_source_rgb(*_color(color))
    ctx.stroke()


def _trace(ctx, d):
    for cmd, args in _PATH.findall(d):
        if cmd == "z":
            ctx.close_path()
        elif cmd == "h":
            ctx.rel_line_to(float(args), 0)
        else:
            x, y = args.split()
            (ctx.move_to if cmd == "M" else ctx.line_to if cmd == "L" else ctx.rel_line_to)(float(x), float(y))


def _rect_path(ctx, x, y, w, h, rx):
    if not rx:
        ctx.rectangle(x, y, w, h)
        return
    ctx.new_sub_path()
    for cx, cy, start in ((x + w - rx, y + rx, -0.5), (x + w - rx, y + h - rx, 0),
                          (x + rx, y + h - rx, 0.5), (x + rx, y + rx, 1)):
        ctx.arc(cx, cy, rx, start * math.pi, (start + 0.5) * math.pi)
    ctx.close_path()


def _text(ctx, x, y, text, size, color, anchor, bold, rotate):
    ctx.save()
    ctx.set_font_face(_face(bold))
    ctx.set_font_size(size)
    if rotate:
        ctx.translate(x, y)
        ctx.rotate(-math.pi / 2)
        ctx.translate(-x, -y)
    if anchor != "start":
        advance = ctx.text_extents(text)[4]
        x -= advance if anchor == "end" else advance / 2
    ctx.move_to(x, y)
    ctx.set_source_rgb(*_color(color))
    ctx.show_text(text)
    ctx.restore()


def _rect(ctx, x, y, w, h, fill, opacity, stroke, rx):
    if not stroke:
        _rect_path(ctx, x, y, w, h, rx)
        ctx.set_source_rgba(*_color(fill), opacity or 1.0)
        ctx.fill()
        return
    if opacity:  # like SVG, the opacity applies to the fill and stroke together
        ctx.save()
        ctx.rectangle(x - 1, y - 1, w + 2, h + 2)  # keeps the group as small as the rect
        ctx.clip()
        ctx.push_group()
    _rect_path(ctx, x, y, w, h, rx)
    ctx.set_source_rgb(*_color(fill))
    ctx.fill_preserve()
    _stroke(ctx, stroke, 1.0, None)
    if opacity:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(opacity)
        ctx.restore()


def _draw(ctx, svg):
    ctx.set_source_rgb(*_color(BG))
    ctx.paint()
    clips = {}
    for kind, *args in svg.ops:
        if kind == "text":
            _text(ctx, *args)
        elif kind == "rect":
            _rect(ctx, *args)
        elif kind == "line":
            x1, y1, x2, y2, color, width, dash = args
            ctx.move_to(x1, y1)
            ctx.line_to(x2, y2)
            _stroke(ctx, color, width, dash)
        elif kind == "path":
            d, color, width, dash, fill, clip = args
            ctx.save()
            if clip:
                ctx.rectangle(*clips[clip])
                ctx.clip()
            _trace(ctx, d)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            if fill != "none":
                ctx.set_source_rgb(*_color(fill))
                ctx.fill_preserve()
            _stroke(ctx, color, width, dash)
            ctx.restore()
        elif kind == "clip":
            clips[args[0]] = args[1:]


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _png(width, height, color_type, idat, palette=b""):
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return b"".join((b"\x89PNG\r\n\x1a\n", _chunk(b"IHDR", header), _chunk(b"PLTE", palette) if palette else b"",
                     _chunk(b"IDAT", idat), _chunk(b"IEND", b"")))


def encode(rows, width, height):
    """8-bit RGBA PNG bytes for ``height`` rows of ``width`` RGBA pixels (a uint8 array, one row per line).

    Every row gets the "Up" filter (its difference from the row above): a
    chart is mostly flat color, so most of those bytes are zero.
    """
    filtered = np.empty((height, width * 4 + 1), np.uint8)
    filtered[:, 0] = 2
    filtered[0, 1:] = rows[0]
    np.subtract(rows[1:], rows[:-1], out=filtered[1:, 1:])
    return _png(width, height, 6, deflate.compress(filtered, 3))


def encode_palette(rows, width, height, block=64):
    """8-bit palette PNG bytes for the same rows, every pixel snapped to PALETTE (rows unfiltered: smaller here).

    Done ``block`` rows at a time so the index arrays stay in the CPU cache: with every core drawing charts,
    a whole chart at once (3 million 8-byte indices) was a third slower.
    """
    lut, filtered = lookup(), np.zeros((height, width + 1), np.uint8)
    words = np.ascontiguousarray(rows).view("<u4")  # R | G << 8 | B << 16 | A << 24
    key = np.empty((block, width), np.intp)
    for top in range(0, height, block):
        part = words[top:top + block]
        np.bitwise_and(part, 0xFFFFFF, out=key[:len(part)], casting="unsafe")
        lut.take(key[:len(part)], out=filtered[top:top + block, 1:], mode="wrap")  # keys < 2**24; "raise" buffers out
    return _png(width, height, 3, deflate.compress(filtered, 6), _PLTE)


def render(svg, scale):
    """The chart drawn at ``scale`` times its size: (surface, rows of RGBA bytes, width, height). The rows are
    the surface's own memory, so keep the surface until they are used."""
    width, height = int(round(svg.width * scale)), int(round(svg.height * scale))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_font_options(_FONT_OPTIONS)
    ctx.scale(scale, scale)
    _draw(ctx, svg)
    surface.flush()
    rows = np.frombuffer(surface.get_data(), np.uint8).reshape(height, surface.get_stride())[:, :width * 4]
    if not _SWAP:  # big-endian: A, R, G, B in memory
        rows = rows.reshape(height, width, 4)[:, :, [1, 2, 3, 0]].reshape(height, width * 4)
    return surface, rows, width, height


def png(svg, scale=2, colors="64"):
    """The chart at ``scale`` times its size as PNG bytes: snapped to PALETTE, or with ``colors="full"`` not."""
    surface, rows, width, height = render(svg, scale)
    data = (encode if colors == "full" else encode_palette)(rows, width, height)
    surface.finish()
    return data
