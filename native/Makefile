# Builds the native TLS backend (Go + uTLS) as a C-shared library that the
# Python package loads via ctypes. Output lands in ../gakido/_native/.
#
#   make            # build the shared library for the host platform
#   make test       # run the Go tests (live fingerprint check)
#   make clean      # remove build artifacts

GO ?= go
# The pinned dependencies target Go 1.22; GOTOOLCHAIN=local prevents an
# automatic toolchain download when a dependency declares a newer go directive.
export GOTOOLCHAIN ?= local
export CGO_ENABLED := 1

OUT_DIR := ../gakido/_native
LIB_BASE := libgakido_tls

UNAME_S := $(shell uname -s)
ifeq ($(OS),Windows_NT)
	LIB_EXT := dll
else ifeq ($(UNAME_S),Darwin)
	LIB_EXT := dylib
else
	LIB_EXT := so
endif

LIB := $(OUT_DIR)/$(LIB_BASE).$(LIB_EXT)

.PHONY: all build test clean

all: build

build:
	@mkdir -p $(OUT_DIR)
	$(GO) build -buildmode=c-shared -trimpath -o $(LIB) .
	@echo "built $(LIB)"

test:
	$(GO) test ./...

clean:
	rm -f $(OUT_DIR)/$(LIB_BASE).dll $(OUT_DIR)/$(LIB_BASE).dylib \
	      $(OUT_DIR)/$(LIB_BASE).so $(OUT_DIR)/$(LIB_BASE).h
