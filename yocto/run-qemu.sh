#!/usr/bin/env bash
# Boots the image built by yocto/build.sh and logs the serial console to
# build/yocto/boot.log. Interactive by default (exit QEMU with Ctrl-A X).
# With BOOT_TIMEOUT=<seconds> it is a check instead: exits 0 once the login prompt (and
# BOOT_EXPECT, if set) appears, 1 on timeout. Needs Linux; uses KVM when /dev/kvm is available.
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

# Pass the .qemuboot.conf itself, not "qemux86-64 core-image-minimal": given a MACHINE, runqemu
# (scarthgap 5.0.20) reads a machine-level `bitbake -e` that has no IMAGE_LINK_NAME and fails with
# "IMAGE_LINK_NAME wasn't set to find corresponding .qemuboot.conf file".
qemuboot="$KAS_BUILD_DIR/tmp/deploy/images/qemux86-64/core-image-minimal-qemux86-64.rootfs.qemuboot.conf"
[ -f "$qemuboot" ] || { echo "no $qemuboot; build the image first (yocto/build.sh)" >&2; exit 1; }

kvm=""
[ -w /dev/kvm ] && kvm="kvm"
# slirp = user-mode networking, no root or tap devices needed.
cmd="runqemu $qemuboot nographic slirp ${kvm} ${QEMU_EXTRA:-}"

if [ -z "${BOOT_TIMEOUT:-}" ]; then
    exec kas shell yocto/kas.yml -c "$cmd" | tee "$log"
fi

kas shell yocto/kas.yml -c "$cmd" >"$log" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null; pkill -f qemu-system 2>/dev/null' EXIT
# BOOT_EXPECT: one more fixed string that must appear in the log besides the login prompt.
expect="${BOOT_EXPECT:-login:}"
for _ in $(seq "$BOOT_TIMEOUT"); do
    if grep -q "login:" "$log" && grep -qF "$expect" "$log"; then
        echo "booted to login prompt, found \"$expect\", log: $log"
        exit 0
    fi
    kill -0 $pid 2>/dev/null || break
    sleep 1
done
echo "no login prompt and \"$expect\" within ${BOOT_TIMEOUT}s; tail of $log:" >&2
tail -30 "$log" >&2
exit 1
