#!/usr/bin/env bash
# Builds core-image-minimal for the pinned machine (yocto/kas.yml). Uses a local `kas`
# if present (CI), otherwise kas-container + Docker (a Mac). Output: build/yocto/tmp/deploy/images/.
# Heavy: first run is hours of machine time and tens of GB of disk. See docs/CI.md.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p build # kas creates KAS_BUILD_DIR non-recursively
export KAS_BUILD_DIR="$PWD/build/yocto"
KAS_VERSION="5.5"

if command -v kas >/dev/null; then
    exec kas build yocto/kas.yml
fi

command -v docker >/dev/null || { echo "need kas (pip install kas==${KAS_VERSION}) or docker" >&2; exit 1; }
script="build/kas-container-${KAS_VERSION}"
mkdir -p build
[ -x "$script" ] || {
    curl -fsSL "https://raw.githubusercontent.com/siemens/kas/${KAS_VERSION}/kas-container" -o "$script"
    chmod +x "$script"
}
exec "$script" build yocto/kas.yml
