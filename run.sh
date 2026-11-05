#!/usr/bin/env bash
# TFlow - Linux Launcher
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/target/release/tflow" ]; then
    exec "$DIR/target/release/tflow" "$@"
elif command -v tflow &>/dev/null; then
    exec tflow "$@"
else
    cargo run --release -- "$@"
fi
