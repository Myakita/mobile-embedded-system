#!/usr/bin/env bash
# Boots the Yocto image and logs the serial console to build/yocto/boot.log. Interactive by
# default (exit QEMU with Ctrl-A X). With BOOT_TIMEOUT=<seconds> it is a check instead: exits 0
# once the login prompt (and BOOT_EXPECT, if set) appears, 1 on timeout. Uses KVM when /dev/kvm
# is writable.
#
# Where the image comes from:
#   default          the tree built by yocto/build.sh, started with runqemu inside `kas shell`;
#                    needs Linux and kas (QEMU does not run in Docker Desktop on a Mac)
#   IMAGE_DIR=<dir>  bzImage and rootfs.ext4 (or rootfs.ext4.zst) as the yocto-image CI artifact
#                    ships them, started with the host's qemu-system-x86_64: no kas and no Yocto
#                    tree, so it also works where the image was never built (make fullstand, also
#                    on a Mac, where without KVM it runs under TCG and boots slowly)
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
mkdir -p build # kas creates KAS_BUILD_DIR non-recursively
log=build/yocto/boot.log
mkdir -p "$(dirname "$log")"

kvm=""
[ -w /dev/kvm ] && kvm="kvm"

# The stand's hooks into the guest (ci/stand.py, docs/TESTING.md); both optional:
#   QEMU_UART=<tty path>   a host tty (the emulator's pty) wired to the guest as an extra serial port.
#                          An explicit isa-serial device on I/O port 0x2e8, not another "-serial":
#                          the two the image already uses are ttyS0 (console) and ttyS1 (null). The
#                          guest finds it by port address (yocto/meta-mes edge.init).
#   QEMU_FWCFG_DIR=<dir>   every file in it becomes fw_cfg entry opt/mes/<name>, readable in the guest
#                          under /sys/firmware/qemu_fw_cfg/by_name/opt/mes/<name>/raw.
params=""
if [ -n "${QEMU_UART:-}" ]; then
    params="$params -chardev serial,id=mesuart,path=$QEMU_UART -device isa-serial,chardev=mesuart,iobase=0x2e8,irq=3"
fi
if [ -n "${QEMU_FWCFG_DIR:-}" ]; then
    for file in "$QEMU_FWCFG_DIR"/*; do
        params="$params -fw_cfg name=opt/mes/$(basename "$file"),file=$file"
    done
fi
params="${params# }"

if [ -n "${IMAGE_DIR:-}" ]; then
    command -v qemu-system-x86_64 >/dev/null || { echo "run-qemu.sh: IMAGE_DIR needs qemu-system-x86_64 on PATH" >&2; exit 1; }
    rootfs="$IMAGE_DIR/rootfs.ext4"
    if [ ! -f "$rootfs" ] && [ -f "$rootfs.zst" ]; then
        zstd -dqf "$rootfs.zst" -o "$rootfs" || exit 1
    fi
    [ -f "$rootfs" ] && [ -f "$IMAGE_DIR/bzImage" ] || { echo "run-qemu.sh: no bzImage and rootfs.ext4[.zst] in $IMAGE_DIR" >&2; exit 1; }
    # What runqemu runs for this image (boot.log of image.yml run 40192650949), without its
    # host-specific parts (port forwards, tftp, usb). slirp: the host is 10.0.2.2 to the guest.
    # -snapshot keeps the artifact's rootfs unchanged, so a run can be repeated.
    cmd="qemu-system-x86_64 -nographic -snapshot ${kvm:+-enable-kvm} -cpu IvyBridge -machine q35,i8042=off -smp 2 -m 256"
    cmd="$cmd -serial mon:stdio -serial null"
    cmd="$cmd -netdev user,id=net0 -device virtio-net-pci,netdev=net0"
    cmd="$cmd -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0"
    cmd="$cmd -drive file=$rootfs,if=virtio,format=raw -kernel $IMAGE_DIR/bzImage"
    cmd="$cmd -append 'root=/dev/vda rw ip=dhcp console=ttyS0 console=ttyS1 tsc=reliable no_timer_check rcupdate.rcu_expedited=1 swiotlb=0'"
    [ -n "$params" ] && cmd="$cmd $params"
    runner=(bash -c)
else
    if ! command -v kas >/dev/null; then
        echo "run-qemu.sh needs kas on the host (pip install kas==5.5), or IMAGE_DIR=<dir> with a yocto-image artifact; QEMU does not run in Docker Desktop on a Mac" >&2
        exit 1
    fi
    export KAS_BUILD_DIR="$PWD/build/yocto"
    # Pass the .qemuboot.conf itself, not "qemux86-64 core-image-minimal": given a MACHINE, runqemu
    # (scarthgap 5.0.20) reads a machine-level `bitbake -e` that has no IMAGE_LINK_NAME and fails with
    # "IMAGE_LINK_NAME wasn't set to find corresponding .qemuboot.conf file".
    qemuboot="$KAS_BUILD_DIR/tmp/deploy/images/qemux86-64/core-image-minimal-qemux86-64.rootfs.qemuboot.conf"
    [ -f "$qemuboot" ] || { echo "no $qemuboot; build the image first (yocto/build.sh)" >&2; exit 1; }
    # slirp = user-mode networking, no root or tap devices needed; the host is 10.0.2.2 to the guest.
    cmd="runqemu $qemuboot nographic slirp ${kvm} ${QEMU_EXTRA:-}"
    [ -n "$params" ] && cmd="$cmd qemuparams=\"$params\""
    runner=(kas shell yocto/kas.yml -c)
fi

if [ -z "${BOOT_TIMEOUT:-}" ]; then
    exec "${runner[@]}" "$cmd" | tee "$log"
fi

"${runner[@]}" "$cmd" >"$log" 2>&1 &
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
