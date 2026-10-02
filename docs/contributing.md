# Contributing

- Run `pre-commit run --all-files` before pushing.
- Build docs: `make docs` (or `make docs-serve`).
- Tests: `make test`.
- Lint/format: `make lint` (ruff + ty).
- Native TLS backend (optional): `make native` builds the Go + uTLS shared
  library into `gakido/_native/` (requires a Go toolchain). `make native-test`
  runs its Go tests.
