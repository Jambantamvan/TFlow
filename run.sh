#!/usr/bin/env bash
# TUF Control Center - Linux Launcher
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
python3 "$DIR/main.py" "$@"

