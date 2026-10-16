"""The notice allium.py prints when an optional feature's packages are missing, and its install commands."""

import os
import re
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

from allium.lib import optional_deps as deps
from tests.unit.charts.fixtures import needs_png

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PNG = deps.FEATURES["png"]
APT_ALL = "sudo apt install " + " ".join(PNG["apt"] + PNG["system"])  # Debian/Ubuntu's own python3
SYSTEM_HINT = "💡 Then the system packages pip cannot install, on Debian/Ubuntu: sudo apt install " + " ".join(PNG["system"])
WITHOUT = "💡 To build without them and without this notice: --chart-format svg (SVG charts) or --no-charts"


def read(*path):
    """Text of a file in the repository."""
    with open(os.path.join(ROOT, *path), encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def managed(monkeypatch, tmp_path):
    """A distribution's own python3 outside a virtualenv, marked EXTERNALLY-MANAGED: pip refuses it (PEP 668)."""
    (tmp_path / "EXTERNALLY-MANAGED").write_text("[externally-managed]\n")
    monkeypatch.setattr(deps, "sysconfig", SimpleNamespace(get_path=lambda name: str(tmp_path)))
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != deps.DEBIAN_PACKAGES])


@pytest.fixture
def debian(managed, monkeypatch):
    """Debian/Ubuntu's own python3, as cron runs it: apt's python3-* packages, no pip."""
    monkeypatch.setattr(sys, "path", sys.path + [deps.DEBIAN_PACKAGES])


@pytest.fixture
def venv(monkeypatch):
    """allium.py run by a virtualenv's python3, where pip installs and apt's python3-* packages are not seen."""
    monkeypatch.setattr(sys, "executable", "/srv/allium/venv/bin/python3")
    monkeypatch.setattr(sys, "prefix", "/srv/allium/venv")
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != deps.DEBIAN_PACKAGES])


def test_debian_python_gets_one_apt_command(debian):
    """Debian/Ubuntu's own python3 gets every package, Python ones and system ones, from one apt command."""
    assert APT_ALL == "sudo apt install python3-cairocffi python3-numpy libcairo2 fonts-dejavu-core"
    assert deps.install_hints("png") == ["💡 Install them for /usr/bin/python3: " + APT_ALL, WITHOUT]


def test_venv_gets_its_own_pip_then_apt_for_what_pip_cannot_install(venv):
    """A virtualenv gets its own pip with the absolute requirements path, then apt for the cairo library and font."""
    assert os.path.isabs(deps.REQUIREMENTS) and os.path.isfile(deps.REQUIREMENTS)
    assert not deps.externally_managed()
    assert deps.install_hints("png") == [
        "💡 Install them for /srv/allium/venv/bin/python3: /srv/allium/venv/bin/python3 -m pip install -r "
        + shlex.quote(deps.REQUIREMENTS),
        SYSTEM_HINT,
        WITHOUT]


def test_other_externally_managed_python_gets_a_virtualenv_not_a_refused_pip(managed):
    """Alpine's, Arch's or Homebrew's python3: pip refuses it too, and apt has none of its packages."""
    assert deps.externally_managed()
    venv_python = shlex.quote(os.path.join(deps.VENV, "bin", "python3"))
    assert deps.install_hints("png") == [
        "💡 pip refuses to install into /usr/bin/python3 (PEP 668): use the system package manager, or a virtualenv "
        "whose python3 then runs allium.py: /usr/bin/python3 -m venv %s && %s -m pip install -r %s"
        % (shlex.quote(deps.VENV), venv_python, shlex.quote(deps.REQUIREMENTS)),
        SYSTEM_HINT,
        WITHOUT]


def test_default_writes_svg_and_says_how_to_get_png(debian, monkeypatch, capsys):
    """By default a missing package means SVG charts and a notice, printed and returned for the end of the run."""
    monkeypatch.setattr(deps, "missing", lambda feature: "No module named 'cairocffi'")
    notice = deps.check("png", asked=False)
    assert notice == ["⚠️ PNG charts need cairocffi, numpy and the cairo library (No module named 'cairocffi'); "
                      "writing SVG charts"] + deps.install_hints("png")
    assert capsys.readouterr().out == "\n".join(notice) + "\n"


def test_asked_for_png_stops_with_the_same_hints(debian, monkeypatch, capsys):
    """An explicit --chart-format png stops with the same hints on stderr, and prints nothing on stdout."""
    monkeypatch.setattr(deps, "missing", lambda feature: "No module named 'numpy'")
    with pytest.raises(SystemExit) as stop:
        deps.check("png", asked=True)
    assert stop.value.code == "\n".join(["❌ PNG charts need cairocffi, numpy and the cairo library "
                                         "(No module named 'numpy')"] + deps.install_hints("png"))
    assert capsys.readouterr().out == ""


def test_installed_is_quiet_except_under_progress(monkeypatch, capsys):
    """With every package installed, nothing prints but a ✅ line with their versions under --progress."""
    monkeypatch.setattr(deps, "missing", lambda feature: None)
    monkeypatch.setitem(sys.modules, "cairocffi", SimpleNamespace(__version__="1.7.1"))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(__version__="2.2.4"))
    assert deps.check("png", asked=True) == []
    assert capsys.readouterr().out == ""
    assert deps.check("png", asked=False, show_progress=True) == []
    assert capsys.readouterr().out == "✅ PNG charts: cairocffi 1.7.1, numpy 2.2.4 found\n"


# cairocffi 1.7.1's errors on Debian 13, cut after the first file it tried to load
NO_CAIRO = ('no library called "cairo-2" was found\nno library called "cairo" was found\n'
            'no library called "libcairo-2" was found\n'
            "cannot load library 'libcairo.so.2': libcairo.so.2: cannot open shared object file: No such file or "
            "directory.  Additionally, ctypes.util.find_library() did not manage to locate a library called "
            "'libcairo.so.2'\ncannot load library 'libcairo.2.dylib': libcairo.2.dylib: cannot open shared object file")
NO_PIXMAN = ('no library called "cairo-2" was found\nno library called "libcairo-2" was found\n'
             "cannot load library 'libcairo.so.2': libpixman-1.so.0: cannot open shared object file: No such file or "
             "directory.  Additionally, ctypes.util.find_library() did not manage to locate a library called "
             "'libcairo.so.2'\ncannot load library 'libcairo.2.dylib': libcairo.2.dylib: cannot open shared object file")


@pytest.mark.parametrize("error, why", [
    (OSError(NO_CAIRO), "cannot load library 'libcairo.so.2': libcairo.so.2: cannot open shared object file: "
                        "No such file or directory"),
    (OSError(NO_PIXMAN), "cannot load library 'libcairo.so.2': libpixman-1.so.0: cannot open shared object file: "
                         "No such file or directory"),  # libcairo2 is installed, but one of its own libraries is not
    (OSError('no library called "cairo-2" was found'), 'no library called "cairo-2" was found'),
    (ImportError("Error importing numpy: you should not try to import numpy from\n        its source directory; "
                 "please exit the numpy source tree, and relaunch\n        your python interpreter from there."),
     "Error importing numpy: you should not try to import numpy from its source directory; please exit the numpy "
     "source tree, and relaunch your python interpreter from there."),
])
def test_missing_says_why_on_one_line(monkeypatch, error, why):
    """The reason is one line: the file that did not load from cairocffi's OSError, or the whole ImportError."""
    def fail(name, package):
        """Fail the probe's import with the parametrized error."""
        raise error
    monkeypatch.setattr(deps, "importlib", SimpleNamespace(import_module=fail))
    assert deps.missing("png") == why


def test_missing_names_the_absent_module(monkeypatch):
    """A probe that cannot be imported is reported by its module name."""
    monkeypatch.setitem(PNG, "probe", ".no_such_module")
    assert deps.missing("png") == "No module named 'allium.lib.no_such_module'"


@needs_png
def test_missing_is_none_when_png_charts_work():
    """Where cairocffi, numpy and the cairo library load, nothing is missing."""
    assert deps.missing("png") is None


def test_requirements_txt_files_every_package():
    """A package added to config/requirements.txt gets filed in optional_deps, so a missing one is announced."""
    def name(package):
        """A package name in PEP 503 normal form, so Jinja2 and jinja2 compare equal."""
        return re.sub(r"[-_.]+", "-", package).lower()
    listed = {name(re.match(r"[A-Za-z0-9._-]+", line.strip()).group())
              for line in read("config", "requirements.txt").splitlines()
              if line.strip() and not line.lstrip().startswith(("#", "-"))}
    filed = deps.REQUIRED + deps.SPEEDUPS + tuple(p for spec in deps.FEATURES.values() for p in spec["packages"])
    assert listed == {name(p) for p in filed}, "file each package in allium/lib/optional_deps.py"


@pytest.mark.parametrize("path, system_python", [
    (("README.md",), True), (("config", "requirements.txt"), True), (("docs", "user-guide", "troubleshooting.md"), True),
    (("setup.sh",), False),  # this and the user guide's install steps always make a virtualenv
    (("docs", "user-guide", "quick-start.md"), False), (("docs", "user-guide", "configuration.md"), False),
])
def test_install_docs_give_the_same_commands(path, system_python):
    """Where people install allium, the docs name what pip cannot install, and apt's packages for the system python3."""
    apt = [line for line in read(*path).splitlines() if "sudo apt install" in line]
    assert any(all(package in line for package in PNG["system"]) for line in apt)
    if system_python:
        assert any(all(package in line for package in PNG["apt"] + PNG["system"]) for line in apt)


def test_the_way_out_uses_options_allium_accepts():
    """The options the notice names to build without the packages are ones allium.py accepts."""
    source = read("allium", "allium.py")
    for option in re.findall(r"--[a-z-]+", PNG["without"]):
        assert f'"{option}"' in source
    assert 'choices=("png", "svg")' in source


@pytest.mark.parametrize("options, code, shown, built", [
    (["--chart-format", "png"], 1, "❌ PNG charts need cairocffi, numpy and the cairo library (", None),
    ([], 0, "⚠️ PNG charts need cairocffi, numpy and the cairo library (", "charts=True chart_format=svg"),
    (["--chart-format", "svg"], 0, None, "charts=True chart_format=svg"),
    (["--no-charts"], 0, None, "charts=False"),
])
def test_allium_checks_before_fetching(tmp_path, options, code, shown, built):
    """allium.py with cairocffi unimportable, run to the end with nothing fetched and the site generator stubbed."""
    # One relay: an empty details document is broken input, and allium.py exits before the stubbed generator.
    script = ("import runpy, sys\n"
              "from types import SimpleNamespace\n"
              "sys.path.insert(0, '.')\n"
              "sys.modules['cairocffi'] = None\n"
              "import lib.coordinator, lib.site_generator\n"
              "lib.coordinator.create_relay_set_with_coordinator = lambda *a, **k: SimpleNamespace(json={'relays': [{}]})\n"
              "lib.site_generator.generate_site = lambda relay_set, args, log: print("
              "'charts=%s chart_format=%s' % (args.charts, args.chart_format))\n"
              "sys.argv = ['allium.py'] + sys.argv[1:]\n"
              "runpy.run_path('allium.py', run_name='__main__')\n")
    out = tmp_path / "www"
    run = subprocess.run([sys.executable, "-c", script] + options + ["--out", str(out)],
                         cwd=os.path.join(ROOT, "allium"), capture_output=True, text=True, timeout=25)
    assert run.returncode == code, run.stderr
    if code:  # an explicit png stops before making the output directory
        assert shown in run.stderr and "--no-charts" in run.stderr
        assert not out.exists() and "chart_format=" not in run.stdout
    elif shown:  # before fetching, and again after the build, where cron mail and a log's tail end
        before, after = run.stdout.split(built)
        assert shown in before and shown in after and "--no-charts" in after
    else:
        assert built in run.stdout and "PNG charts" not in run.stdout + run.stderr
