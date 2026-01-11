"""
Pytest configuration file.

This file is automatically loaded by pytest and configures:
- Python path to include the project root
- Pre-loads allium package to avoid import conflicts
- Common fixtures for tests
"""

import sys
import os
from pathlib import Path
import importlib.util

# Get the absolute path to the project root
project_root = Path(__file__).parent.parent.absolute()
project_root_str = str(project_root)

# Ensure project root is at the start of sys.path
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
elif sys.path.index(project_root_str) != 0:
    sys.path.remove(project_root_str)
    sys.path.insert(0, project_root_str)

# Also add tests directory to path for test_utils imports
tests_dir = str(Path(__file__).parent.absolute())
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# Critical: Pre-load allium as a PACKAGE before any test imports
# This prevents Python from treating allium/allium.py as the 'allium' module
# instead of allium/__init__.py as the 'allium' package
if 'allium' not in sys.modules:
    allium_init = project_root / 'allium' / '__init__.py'
    spec = importlib.util.spec_from_file_location('allium', str(allium_init),
                                                   submodule_search_locations=[str(project_root / 'allium')])
    allium_module = importlib.util.module_from_spec(spec)
    sys.modules['allium'] = allium_module
    spec.loader.exec_module(allium_module)

# Also set PYTHONPATH for subprocess calls
os.environ['PYTHONPATH'] = project_root_str + os.pathsep + os.environ.get('PYTHONPATH', '')
