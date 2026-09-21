#!/usr/bin/env bash
# emulator/interface/gpio.cpp uses the libgpiod v2 C++ API (chip::prepare_request(),
# line_settings). Ubuntu 24.04's apt package is still v1.6, which doesn't have that
# API at all. This script is idempotent: it checks the installed version first and
# only builds v2 from upstream source (Meson) if apt gave us something older.
#
# Requires meson, ninja-build and pkg-config on top of a normal build toolchain.
set -euo pipefail

REQUIRED_MAJOR=2
LIBGPIOD_REF="v2.3.1"

installed_version="$(pkg-config --modversion libgpiodcxx 2>/dev/null \
    || pkg-config --modversion libgpiod 2>/dev/null \
    || echo "0")"
installed_major="${installed_version%%.*}"

if [ "${installed_major}" -ge "${REQUIRED_MAJOR}" ] 2>/dev/null; then
    echo "libgpiod ${installed_version} already satisfies >= ${REQUIRED_MAJOR}.0, skipping build"
    exit 0
fi

echo "libgpiod ${installed_version} is older than ${REQUIRED_MAJOR}.0, building ${LIBGPIOD_REF} from source"

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

git clone --depth 1 --branch "${LIBGPIOD_REF}" https://github.com/brgl/libgpiod.git "${workdir}/libgpiod"
cd "${workdir}/libgpiod"
meson setup build --prefix=/usr/local -Dbindings-cxx=enabled -Dtools=disabled -Dtests=disabled
ninja -C build
sudo ninja -C build install
sudo ldconfig
