"""Setup script for Gakido with conditional C extension."""
import os
import sys
from setuptools import Extension, setup

# Only build C extension on non-Windows platforms
# The C extension uses Unix-specific headers (arpa/inet.h, netdb.h, etc.)
ext_modules = []
if sys.platform != "win32":
    ext_modules = [
        Extension(
            "gakido.gakido_core",
            sources=["gakido/core.c"],
        )
    ]

setup(
    ext_modules=ext_modules,
)
