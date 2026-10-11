"""PNG charts: an ``Svg``'s own drawing replayed with cairo at 2x, then PNG-encoded.

About 11 ms a chart, against about 70 ms to rasterize the SVG text with
CairoSVG at the same size: there is no SVG to parse, and the encoder below
(PNG "Up" filter with numpy, deflate with zlib-ng) is several times faster
than libpng at about the same file size.
"""

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

SCALE = 2
# Part of the chart cache key (VERSION, with the cairo version and the fonts
# found): change it when the drawing or the encoding changes.
_DRAWING = b"cairo-2x-2"
_PATH = re.compile(r"[MLlhz]|-?[\d.]+")
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
_FACES = {}
_COLORS = {}


def _color(hex_color):
    rgb = _COLORS.get(hex_color)
    if rgb is None:
        r, g, b = (int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        rgb = _COLORS[hex_color] = (b, g, r) if _SWAP else (r, g, b)
    return rgb


def _face(bold):
    face = _FACES.get(bold)
    if face is None:
        face = _FACES[bold] = cairo.ToyFontFace(
            "DejaVu Sans", weight=cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    return face


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


VERSION = b"/".join((_DRAWING, cairo.cairo_version_string().encode(), _fonts()))


def _stroke(ctx, color, width, dash):
    ctx.set_line_width(width)
    ctx.set_dash([float(v) for v in dash.split()] if dash else [])
    ctx.set_source_rgb(*_color(color))
    ctx.stroke()


def _trace(ctx, d):
    cmd = None
    tokens = _PATH.findall(d)
    i = 0
    while i < len(tokens):
        if tokens[i] in "MLlhz":
            cmd = tokens[i]
            i += 1
            if cmd == "z":
                ctx.close_path()
                continue
        if cmd == "h":
            ctx.rel_line_to(float(tokens[i]), 0)
            i += 1
            continue
        x, y = float(tokens[i]), float(tokens[i + 1])
        i += 2
        (ctx.move_to if cmd == "M" else ctx.line_to if cmd == "L" else ctx.rel_line_to)(x, y)


def _rect(ctx, x, y, w, h, rx):
    if not rx:
        ctx.rectangle(x, y, w, h)
        return
    ctx.new_sub_path()
    for cx, cy, start in ((x + w - rx, y + rx, -0.5), (x + w - rx, y + h - rx, 0),
                          (x + rx, y + h - rx, 0.5), (x + rx, y + rx, 1)):
        ctx.arc(cx, cy, rx, start * 3.141592653589793, (start + 0.5) * 3.141592653589793)
    ctx.close_path()


def _draw(ctx, svg):
    ctx.set_source_rgb(*_color(BG))
    ctx.paint()
    clips = {}
    for op in svg.ops:
        kind = op[0]
        if kind == "text":
            _, x, y, text, size, color, anchor, bold, rotate = op
            ctx.save()
            ctx.set_font_face(_face(bold))
            ctx.set_font_size(size)
            if rotate:
                ctx.translate(x, y)
                ctx.rotate(-1.5707963267948966)
                ctx.translate(-x, -y)
            if anchor != "start":
                advance = ctx.text_extents(text)[4]
                x -= advance if anchor == "end" else advance / 2
            ctx.move_to(x, y)
            ctx.set_source_rgb(*_color(color))
            ctx.show_text(text)
            ctx.restore()
        elif kind == "line":
            _, x1, y1, x2, y2, color, width, dash = op
            ctx.move_to(x1, y1)
            ctx.line_to(x2, y2)
            _stroke(ctx, color, width, dash)
        elif kind == "rect":
            _, x, y, w, h, fill, opacity, stroke, rx = op
            if not stroke:
                _rect(ctx, x, y, w, h, rx)
                ctx.set_source_rgba(*(_color(fill) + (opacity or 1.0,)))
                ctx.fill()
                continue
            if opacity:  # like SVG, the opacity applies to the fill and stroke together
                ctx.save()
                ctx.rectangle(x - 1, y - 1, w + 2, h + 2)  # keeps the group as small as the rect
                ctx.clip()
                ctx.push_group()
            _rect(ctx, x, y, w, h, rx)
            ctx.set_source_rgb(*_color(fill))
            ctx.fill_preserve()
            _stroke(ctx, stroke, 1.0, None)
            if opacity:
                ctx.pop_group_to_source()
                ctx.paint_with_alpha(opacity)
                ctx.restore()
        elif kind == "path":
            _, d, color, width, dash, fill, clip = op
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
            clips[op[1]] = op[2:]


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode(rows, width, height):
    """PNG bytes for ``height`` rows of ``width`` RGBA pixels (a uint8 array, one row per line).

    Every row gets the "Up" filter (its difference from the row above): a
    chart is mostly flat color, so most of those bytes are zero.
    """
    filtered = np.empty((height, width * 4 + 1), np.uint8)
    filtered[:, 0] = 2
    filtered[0, 1:] = rows[0]
    np.subtract(rows[1:], rows[:-1], out=filtered[1:, 1:])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return b"".join((b"\x89PNG\r\n\x1a\n", _chunk(b"IHDR", header),
                     _chunk(b"IDAT", deflate.compress(filtered, 3)), _chunk(b"IEND", b"")))


def png(svg):
    """The chart at ``SCALE`` times its size, as PNG bytes."""
    width, height = int(svg.width * SCALE), svg.height * SCALE
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_font_options(_FONT_OPTIONS)
    ctx.scale(SCALE, SCALE)
    _draw(ctx, svg)
    surface.flush()
    rows = np.frombuffer(surface.get_data(), np.uint8).reshape(height, surface.get_stride())[:, :width * 4]
    if not _SWAP:  # big-endian: A, R, G, B in memory
        rows = rows.reshape(height, width, 4)[:, :, [1, 2, 3, 0]].reshape(height, width * 4)
    return encode(rows, width, height)
