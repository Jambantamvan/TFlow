#!/usr/bin/env bash
# TFlow - Docker / Podman Runner Script
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Allow local root/container to connect to X server
if command -v xhost >/dev/null 2>&1; then
    xhost +local:root >/dev/null 2>&1 || true
    xhost +si:localuser:root >/dev/null 2>&1 || true
fi

# Detect container runtime (docker or podman)
if command -v docker >/dev/null 2>&1; then
    DOCKER_CMD="docker"
elif command -v podman >/dev/null 2>&1; then
    DOCKER_CMD="podman"
else
    echo "Error: Neither Docker nor Podman is installed."
    echo "Please install Docker (or Podman) to use this containerized launcher."
    exit 1
fi

echo "=============================================="
echo "         TFlow - Container Launcher           "
echo "=============================================="
echo "Using container engine: $DOCKER_CMD"

# Build image if it does not exist
if ! $DOCKER_CMD image inspect tflow:latest >/dev/null 2>&1; then
    echo "Building container image 'tflow:latest'..."
    $DOCKER_CMD build -t tflow:latest .
fi

echo "Launching TFlow GUI in container..."
$DOCKER_CMD run --rm -it \
    --name tflow \
    --net=host \
    --privileged \
    -e DISPLAY="$DISPLAY" \
    -e XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v /sys:/sys:rw \
    -v /proc:/proc:rw \
    -v /dev/port:/dev/port:rw \
    tflow:latest "$@"
