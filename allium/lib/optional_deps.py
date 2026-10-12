"""Optional packages: the feature each one enables, and the commands that install it.

allium.py calls check() for a feature before fetching anything. When the
feature's packages are missing it says what failed, prints commands that
install them for the Python that is running, and names the options that build
without them. A package added to config/requirements.txt is filed here too, in
REQUIRED, SPEEDUPS or a FEATURES entry: tests/unit/test_optional_deps.py fails
until it is.
"""

import importlib
import os
import shlex
import sys
import sysconfig

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
# Absolute, so the commands work from any directory (cron runs allium.py from allium/).
REQUIREMENTS = os.path.join(ROOT, "config", "requirements.txt")
VENV = os.path.join(ROOT, "venv")  # where setup.sh makes one
REQUIRED = ("Jinja2",)  # allium does not start without these
SPEEDUPS = ("zlib-ng",)  # used when installed, skipped without a word
# Debian and Ubuntu's own python3 imports apt's python3-* packages from here; a virtualenv does not.
DEBIAN_PACKAGES = "/usr/lib/python3/dist-packages"

FEATURES = {
    "png": {
        "name": "PNG charts",
        "needs": "cairocffi, numpy and the cairo library",
        "probe": ".charts.raster",  # imports both; cairocffi raises OSError without the cairo library
        "packages": ("cairocffi", "numpy"),  # in config/requirements.txt
        "apt": ("python3-cairocffi", "python3-numpy"),  # the same packages for Debian/Ubuntu's own python3
        "system": ("libcairo2", "fonts-dejavu-core"),  # pip cannot install the cairo library or the chart font
        "fallback": "writing SVG charts",
        "without": "--chart-format svg (SVG charts) or --no-charts",
    },
}


def missing(feature):
    """Why ``feature`` cannot run on this Python, on one line, or None when it can."""
    try:
        importlib.import_module(FEATURES[feature]["probe"], __package__)
    except ImportError as e:
        return " ".join(str(e).split()) or type(e).__name__
    except OSError as e:  # cairocffi's: a line per library name it looked up, then why each file did not load
        lines = str(e).splitlines() or [type(e).__name__]
        why = [line for line in lines if not line.startswith("no library called")] or lines
        return why[0].split(".  Additionally")[0]
    return None


def externally_managed():
    """True for a distribution's Python, outside a virtualenv, that refuses pip installs (PEP 668)."""
    return sys.prefix == sys.base_prefix and os.path.isfile(
        os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED"))


def install_hints(feature):
    """Pasteable lines that install ``feature``'s packages for this Python, then the options that build without them."""
    spec = FEATURES[feature]
    python = shlex.quote(sys.executable or "python3")
    if DEBIAN_PACKAGES in sys.path:  # pip is missing or refused here (PEP 668): apt has every package
        hints = ["Install them for %s: sudo apt install %s" % (python, " ".join(spec["apt"] + spec["system"]))]
    else:
        pip = "-m pip install -r " + shlex.quote(REQUIREMENTS)
        if externally_managed():  # another distribution's python3 (Alpine, Arch) or Homebrew's
            venv = shlex.quote(os.path.join(VENV, "bin", "python3"))
            hints = ["pip refuses to install into %s (PEP 668): use the system package manager, or a virtualenv "
                     "whose python3 then runs allium.py: %s -m venv %s && %s %s"
                     % (python, python, shlex.quote(VENV), venv, pip)]
        else:  # a virtualenv, or a Python of its own
            hints = ["Install them for %s: %s %s" % (python, python, pip)]
        if spec["system"]:
            hints.append("Then the system packages pip cannot install, on Debian/Ubuntu: sudo apt install "
                         + " ".join(spec["system"]))
    hints.append("To build without them and without this notice: " + spec["without"])
    return ["💡 " + hint for hint in hints]


def check(feature, asked, show_progress=False):
    """Check ``feature``'s packages before fetching anything.

    Installed: returns [] (and a ✅ line under --progress). Missing: stops when
    the feature was asked for by name; otherwise prints the notice and returns
    its lines, for allium.py to print again at the end of the run.
    """
    spec = FEATURES[feature]
    error = missing(feature)
    if error is None:
        if show_progress:
            found = ("%s %s" % (name, getattr(sys.modules.get(name), "__version__", "")) for name in spec["packages"])
            print("✅ %s: %s found" % (spec["name"], ", ".join(f.strip() for f in found)))
        return []
    needs = "%s need %s (%s)" % (spec["name"], spec["needs"], error)
    if asked:
        sys.exit("\n".join(["❌ " + needs] + install_hints(feature)))
    notice = ["⚠️ %s; %s" % (needs, spec["fallback"])] + install_hints(feature)
    print("\n".join(notice))
    return notice
