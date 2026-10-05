#!/usr/bin/env bash
# Boots the image built by yocto/build.sh and logs the serial console to
# build/yocto/boot.log. Interactive by default (exit QEMU with Ctrl-A X).
# With BOOT_TIMEOUT=<seconds> it is a check instead: exits 0 once the login prompt
# appears, 1 on timeout. Needs Linux; uses KVM when /dev/kvm is available.
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p build # kas creates KAS_BUILD_DIR non-recursively
export KAS_BUILD_DIR="$PWD/build/yocto"
log=build/yocto/boot.log
mkdir -p "$(dirname "$log")"

if ! command -v kas >/dev/null; then
    echo "run-qemu.sh needs kas on the host (pip install kas==5.5); QEMU does not run in Docker Desktop on a Mac" >&2
    exit 1
fi

kvm=""
[ -w /dev/kvm ] && kvm="kvm"
# slirp = user-mode networking, no root or tap devices needed.
cmd="runqemu qemux86-64 core-image-minimal nographic slirp ${kvm} ${QEMU_EXTRA:-}"

if [ -z "${BOOT_TIMEOUT:-}" ]; then
    exec kas shell yocto/kas.yml -c "$cmd" | tee "$log"
fi

kas shell yocto/kas.yml -c "$cmd" >"$log" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null; pkill -f qemu-system 2>/dev/null' EXIT
for _ in $(seq "$BOOT_TIMEOUT"); do
    grep -q "login:" "$log" && { echo "booted to login prompt, log: $log"; exit 0; }
    kill -0 $pid 2>/dev/null || break
    sleep 1
done
echo "no login prompt within ${BOOT_TIMEOUT}s; tail of $log:" >&2
tail -30 "$log" >&2
exit 1
