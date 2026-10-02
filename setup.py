"""
Packaging hook for the optional native TLS backend.

gakido itself is pure Python. When the native backend's shared library
(``gakido/_native/libgakido_tls.{so,dylib,dll}``, built from ``native/`` with
Go) is present at build time, we ship it inside a platform-specific wheel so
``pip install`` users get the browser-accurate TLS backend without a Go
toolchain. The library is loaded via ctypes, so it is independent of the Python
version/ABI — the wheel is therefore tagged ``py3-none-<platform>`` (one wheel
per platform, not per Python version).

When the library is absent (e.g. the source distribution), the build stays pure
Python (``py3-none-any``) and the backend transparently falls back to the
stdlib path at runtime.
"""

import glob

from setuptools import setup
from setuptools.dist import Distribution

try:  # setuptools >= 70.1 vendors bdist_wheel
    from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
except ImportError:  # pragma: no cover - older setuptools
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel


def _native_library_built() -> bool:
    return bool(glob.glob("gakido/_native/libgakido_tls.*"))


class _NativeDistribution(Distribution):
    """Mark the distribution impure when the native library is bundled."""

    def has_ext_modules(self) -> bool:  # noqa: D401
        return _native_library_built()


class bdist_wheel(_bdist_wheel):
    def get_tag(self):
        _python, _abi, plat = super().get_tag()
        if _native_library_built():
            # Version-independent (ctypes), but platform-specific.
            return "py3", "none", plat
        return "py3", "none", "any"


setup(
    distclass=_NativeDistribution,
    cmdclass={"bdist_wheel": bdist_wheel},
)
