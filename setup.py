"""
Build script for gakido C extension.

Reads metadata from pyproject.toml to ensure consistency.
"""

import sys
from pathlib import Path
from setuptools import Extension, setup

# Use tomllib (Python 3.11+) or tomli (older versions)
import tomllib

# Read metadata from pyproject.toml (single source of truth)
pyproject_path = Path(__file__).parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject = tomllib.load(f)

project = pyproject["project"]

# Define the C extension
native_ext = Extension(
    "gakido.gakido_core",
    sources=["gakido/core.c"],
)

setup(
    name=project["name"],
    version=project["version"],
    description=project["description"],
    python_requires=project["requires-python"],
    ext_modules=[native_ext],
)
