from setuptools import Extension, setup, find_packages

native_ext = Extension(
    "gakido.gakido_core",
    sources=["gakido/core.c"],
)

setup(
    name="gakido",
    version="0.0.1",
    description="High-performance CPython HTTP client with browser impersonation",
    packages=find_packages(),
    ext_modules=[native_ext],
    python_requires=">=3.9",
    install_requires=[
        "h2>=4.1.0",
        "brotli>=1.1.0",
    ],
)
