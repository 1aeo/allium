"""The notice allium.py prints when an optional feature's packages are missing, and its install commands."""

import os
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from allium.lib import optional_deps as deps
from tests.unit.charts.fixtures import needs_png

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PNG = deps.FEATURES["png"]
APT_ALL = "sudo apt install " + " ".join(PNG["apt"] + PNG["system"])  # Debian/Ubuntu's own python3
APT_SYSTEM = "sudo apt install " + " ".join(PNG["system"])  # what pip cannot install
WITHOUT = "💡 To build without them and without this notice: --chart-format svg (SVG charts) or --no-charts"


def read(*path):
    with open(os.path.join(ROOT, *path), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def debian(monkeypatch):
    """Debian/Ubuntu's own python3, as cron runs it: apt's python3-* packages, no pip."""
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(sys, "path", sys.path + [deps.DEBIAN_PACKAGES])


@pytest.fixture
def venv(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/srv/allium/venv/bin/python3")
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != deps.DEBIAN_PACKAGES])


def test_debian_python_gets_one_apt_command(debian):
    assert APT_ALL == "sudo apt install python3-cairocffi python3-numpy libcairo2 fonts-dejavu-core"
    assert deps.install_hints("png") == ["💡 Install them for /usr/bin/python3: " + APT_ALL, WITHOUT]


def test_venv_gets_its_own_pip_then_apt_for_what_pip_cannot_install(venv):
    assert os.path.isabs(deps.REQUIREMENTS) and os.path.isfile(deps.REQUIREMENTS)
    assert deps.install_hints("png") == [
        "💡 Install them for /srv/allium/venv/bin/python3: /srv/allium/venv/bin/python3 -m pip install -r "
        + deps.REQUIREMENTS,
        "💡 Then the system packages pip cannot install, on Debian/Ubuntu: sudo apt install libcairo2 fonts-dejavu-core",
        WITHOUT]


def test_default_writes_svg_and_says_how_to_get_png(debian, monkeypatch, capsys):
    monkeypatch.setattr(deps, "missing", lambda feature: "No module named 'cairocffi'")
    notice = deps.check("png", asked=False)
    assert notice == ["⚠️ PNG charts need cairocffi, numpy and the cairo library (No module named 'cairocffi'); "
                      "writing SVG charts"] + deps.install_hints("png")
    assert capsys.readouterr().out == "\n".join(notice) + "\n"


def test_asked_for_png_stops_with_the_same_hints(debian, monkeypatch, capsys):
    monkeypatch.setattr(deps, "missing", lambda feature: "No module named 'numpy'")
    with pytest.raises(SystemExit) as stop:
        deps.check("png", asked=True)
    assert stop.value.code == "\n".join(["❌ PNG charts need cairocffi, numpy and the cairo library "
                                         "(No module named 'numpy')"] + deps.install_hints("png"))
    assert capsys.readouterr().out == ""


def test_installed_is_quiet_except_under_progress(monkeypatch, capsys):
    monkeypatch.setattr(deps, "missing", lambda feature: None)
    monkeypatch.setitem(sys.modules, "cairocffi", SimpleNamespace(__version__="1.7.1"))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(__version__="2.2.4"))
    assert deps.check("png", asked=True) == []
    assert capsys.readouterr().out == ""
    assert deps.check("png", asked=False, show_progress=True) == []
    assert capsys.readouterr().out == "✅ PNG charts: cairocffi 1.7.1, numpy 2.2.4 found\n"


def test_missing_keeps_the_first_line_of_the_error(monkeypatch):
    def no_cairo(name, package):
        raise OSError('no library called "cairo-2" was found\nno library called "cairo" was found')
    monkeypatch.setattr(deps, "importlib", SimpleNamespace(import_module=no_cairo))
    assert deps.missing("png") == 'no library called "cairo-2" was found'


def test_missing_names_the_absent_module(monkeypatch):
    monkeypatch.setitem(PNG, "probe", ".no_such_module")
    assert deps.missing("png") == "No module named 'allium.lib.no_such_module'"


@needs_png
def test_missing_is_none_when_png_charts_work():
    assert deps.missing("png") is None


def test_requirements_txt_files_every_package():
    """A package added to config/requirements.txt gets filed in optional_deps, so a missing one is announced."""
    def name(package):
        return re.sub(r"[-_.]+", "-", package).lower()
    listed = {name(re.match(r"[A-Za-z0-9._-]+", line.strip()).group())
              for line in read("config", "requirements.txt").splitlines()
              if line.strip() and not line.lstrip().startswith(("#", "-"))}
    filed = deps.REQUIRED + deps.SPEEDUPS + tuple(p for spec in deps.FEATURES.values() for p in spec["packages"])
    assert listed == {name(p) for p in filed}, "file each package in allium/lib/optional_deps.py"


@pytest.mark.parametrize("path", [("README.md",), ("config", "requirements.txt"),
                                  ("docs", "user-guide", "troubleshooting.md"), ("setup.sh",)])
def test_install_docs_give_the_same_commands(path):
    """Where people install allium, the docs name what pip cannot install, and apt's packages for the system python3."""
    text = read(*path)
    assert APT_SYSTEM in text
    if path != ("setup.sh",):  # setup.sh always makes a virtualenv
        assert all(package in text for package in PNG["apt"])


def test_the_way_out_uses_options_allium_accepts():
    source = read("allium", "allium.py")
    for option in re.findall(r"--[a-z-]+", PNG["without"]):
        assert f'"{option}"' in source
    assert 'choices=("png", "svg")' in source


@pytest.mark.parametrize("options, code, shown", [
    (["--chart-format", "png"], 1, "❌ PNG charts need cairocffi, numpy and the cairo library ("),
    ([], 0, "⚠️ PNG charts need cairocffi, numpy and the cairo library ("),
    (["--chart-format", "svg"], 0, None),
    (["--no-charts"], 0, None),
])
def test_allium_checks_before_fetching(tmp_path, options, code, shown):
    """allium.py with cairocffi unimportable, stopped where it would start fetching."""
    script = ("import runpy, sys\n"
              "sys.path.insert(0, '.')\n"
              "sys.modules['cairocffi'] = None\n"
              "import lib.coordinator\n"
              "lib.coordinator.create_relay_set_with_coordinator = lambda *a, **k: sys.exit(0)\n"
              "sys.argv = ['allium.py'] + sys.argv[1:]\n"
              "runpy.run_path('allium.py', run_name='__main__')\n")
    out = tmp_path / "www"
    run = subprocess.run([sys.executable, "-c", script] + options + ["--out", str(out)],
                         cwd=os.path.join(ROOT, "allium"), capture_output=True, text=True, timeout=25)
    assert run.returncode == code, run.stderr
    if shown is None:
        assert "PNG charts" not in run.stdout + run.stderr
    else:
        assert shown in (run.stderr if code else run.stdout)
        assert "--no-charts" in (run.stderr if code else run.stdout)
    assert out.exists() == (code == 0)  # an explicit png stops before making the output directory
