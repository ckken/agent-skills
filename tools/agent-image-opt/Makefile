.PHONY: build check test install-local

BIN := agent-image-opt
PREFIX ?= $(HOME)/.local

build:
	cargo build --release

check:
	cargo fmt --check
	cargo check

test: check
	cargo test

install-local: build
	mkdir -p "$(PREFIX)/bin"
	install -m 755 "target/release/$(BIN)" "$(PREFIX)/bin/$(BIN)"
