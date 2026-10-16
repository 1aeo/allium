"""Regression tests for the allium command-line entrypoint."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_empty_relays_exit_before_site_generation(tmp_path):
    """An empty details document exits with status 1 without generating a site."""
    generator_called = tmp_path / "generator_called"
    script = textwrap.dedent("""\
        import runpy
        import sys
        from pathlib import Path
        from types import SimpleNamespace

        import lib.coordinator
        import lib.site_generator

        marker = Path(sys.argv[2])
        lib.coordinator.create_relay_set_with_coordinator = (
            lambda *args, **kwargs: SimpleNamespace(json={"relays": []})
        )
        lib.site_generator.generate_site = (
            lambda *args, **kwargs: marker.write_text("called", encoding="utf-8")
        )
        sys.argv = ["allium.py", "--out", sys.argv[1], "--no-charts"]
        runpy.run_path("allium.py", run_name="__main__")
    """)

    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "www"), str(generator_called)],
        cwd=Path(__file__).resolve().parents[2] / "allium",
        capture_output=True,
        text=True,
        timeout=25,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "the Onionoo details data has no relays" in result.stdout
    assert not generator_called.exists()


def test_every_build_drops_the_chart_tree_and_charts_layout_writes_there(tmp_path):
    """Each build, before any page and whatever its own layout (also with --no-charts), removes the charts/relay
    and charts/contact an earlier --chart-layout charts build wrote; --chart-layout charts then points the chart
    writer and the pages at charts/, also when SVG stands in for PNG."""
    script = textwrap.dedent("""\
        import os
        import runpy
        import sys
        from types import SimpleNamespace

        sys.modules["cairocffi"] = None  # no PNG charts: SVG stands in
        import lib.coordinator
        import lib.site_generator
        import lib.workers
        from lib.page_writer import ENV

        lib.workers.CACHE_DIR = os.environ["CHART_TEST_CACHE"]  # an SVG build's sweep() empties the chart cache

        def generate_site(relay_set, args, log):
            writer = getattr(relay_set, "chart_writer", None)
            print("layout=%s writer=%s chart_root=%r cleared=%s" % (
                args.chart_layout, writer and (writer.root, writer.ext), ENV.globals["chart_root"],
                not os.path.exists(os.path.join(args.output_dir, "charts"))))

        lib.coordinator.create_relay_set_with_coordinator = lambda *args, **kwargs: SimpleNamespace(
            json={"relays": [{"fingerprint": "A" * 40}]}, bandwidth_data={"relays": []}, uptime_data=None)
        lib.site_generator.generate_site = generate_site
        sys.argv = ["allium.py"] + sys.argv[1:]
        runpy.run_path("allium.py", run_name="__main__")
    """)
    out = tmp_path / "www"
    # A PNG drawing version, which an SVG build drops: from the test's own chart cache, not the checkout's
    version = tmp_path / "cache" / "charts" / ("0" * 16)
    version.mkdir(parents=True)
    for options, shown in (([], "layout=beside writer=(None, 'svg') chart_root='' cleared=True"),
                           (["--chart-layout", "charts"],
                            "layout=charts writer=(%r, 'svg') chart_root='charts/' cleared=True" % str(out / "charts")),
                           (["--no-charts"], "layout=beside writer=None chart_root='' cleared=True")):
        for kind, name in (("relay", "A" * 40), ("contact", "h" * 32)):
            (out / "charts" / kind / name).mkdir(parents=True)
            (out / "charts" / kind / name / "bandwidth-1m.png").write_bytes(b"from an earlier build")
        result = subprocess.run(
            [sys.executable, "-c", script, "--out", str(out)] + options,
            cwd=Path(__file__).resolve().parents[2] / "allium",
            capture_output=True,
            text=True,
            timeout=25,
            env=dict(os.environ, CHART_TEST_CACHE=str(tmp_path / "cache")),
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert shown in result.stdout
        assert not (out / "charts").exists()  # nothing else was in it
    assert not version.exists()
