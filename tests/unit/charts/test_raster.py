"""PNG charts: the Svg's drawing replayed with cairo at 2x and the PNG encoder."""

import re

from allium.lib.charts import svg as svg_module
from allium.lib.charts.svg import GREEN, RED, TEXT, Svg

from .fixtures import OVERLOADED, SPIKE, decode, history, needs_png, np, raster, relay, writer

pytestmark = needs_png


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


def test_every_color_the_charts_name_or_cover_an_area_with_is_in_the_palette():
    """A color added to the charts must be added to PALETTE too (scripts/chart_palette.py), or it shifts."""
    drawn = []
    busy = relay("A", **OVERLOADED)  # overload marker, spike callout, off-scale markers
    charts = writer([busy, relay("B")], {"A": history(SPIKE, [100] * 21), "B": history([90 + i for i in range(21)])},
                    {"A": [999] * 180})
    charts._save = lambda directory, name, draw, *args: drawn.append(draw(*args)) or 0
    charts.relay(busy, None)
    charts.contact([0, 1], None)
    drawn = [svg for svg in drawn if svg]
    assert len(drawn) == 3
    # Every color svg.py defines or a drawing call names...
    fields = [*vars(svg_module).values(), *(field for svg in drawn for op in svg.ops for field in op)]
    named = {v[1:] for v in fields if isinstance(v, str) and re.fullmatch("#[0-9a-f]{6}", v)}
    assert len(named) >= 14 and sorted(named - set(raster.PALETTE)) == []
    # ...and every blend that covers an area (translucent bands and legend swatches).
    for svg in drawn:
        _surface, rows, width, height = raster.render(svg, 2)
        colors, counts = np.unique(np.ascontiguousarray(rows).view(">u4") >> 8, return_counts=True)  # 0xRRGGBB
        areas = ("%06x" % c for c in colors[counts > 0.002 * width * height])
        assert [c for c in areas if c not in raster.PALETTE] == []
