"""Regression tests for the allium command-line entrypoint."""

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
