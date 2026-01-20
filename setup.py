from setuptools import Extension, setup

native_ext = Extension(
    "gakido.gakido_core",
    sources=["gakido/core.c"],
)

# Metadata is defined in pyproject.toml
# This file only handles the C extension build
setup(
    ext_modules=[native_ext],
)
