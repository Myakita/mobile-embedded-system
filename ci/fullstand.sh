#!/usr/bin/env bash
# `make fullstand`: bring the whole stand up from the artifacts CI built, and run its scenarios on this
# machine -- the Yocto image in QEMU with edge inside, a TLS broker, the emulator CLI on edge's UART
# and, when an Android emulator is running, the pinned app. Nothing is built here, so no Yocto, no
# Gradle. Linux or macOS; without KVM (always on a Mac) QEMU runs under TCG and boots slowly.
#
#   RUN=latest|<id>     the stand.yml run whose stand-bundle to use (default: latest successful)
#   ANDROID=auto|skip   auto: use the Android emulator adb sees, if any; skip: scenarios without the app
#   STAND_TIMEOUT=<s>   per scenario, default 300; raise it where QEMU is slow
#
# Results: build/stand/junit.xml and build/stand/<scenario>/ (logs, received/expected, logcat, app.png).
# Instructions and requirements: docs/CI.md, "Полный стенд".
set -euo pipefail

cd "$(dirname "$0")/.."

# mosquitto, the broker, lives in sbin (/usr/sbin, or /opt/homebrew/sbin with Homebrew): not on a user's PATH.
PATH="$PATH:/opt/homebrew/sbin:/usr/local/sbin:/usr/sbin:/sbin"

missing=0
need()
{
    if ! command -v "$1" >/dev/null; then
        echo "fullstand: $1 not found ($2)" >&2
        missing=1
    fi
}
need gh "https://cli.github.com, then: gh auth login"
need qemu-system-x86_64 "Linux: apt install qemu-system-x86; macOS: brew install qemu"
need mosquitto "Linux: apt install mosquitto mosquitto-clients; macOS: brew install mosquitto"
need mosquitto_sub "Linux: apt install mosquitto-clients; macOS: brew install mosquitto"
need openssl "Linux: apt install openssl"
need zstd "Linux: apt install zstd; macOS: brew install zstd"
[ "$missing" = 0 ] || exit 1

if command -v sha256sum >/dev/null; then
    sums() { sha256sum -c "$@"; }
else
    sums() { shasum -a 256 -c "$@"; }
fi

run="${RUN:-latest}"
if [ "$run" = latest ]; then
    run=$(gh run list --workflow stand.yml --status success --limit 1 --json databaseId --jq '.[0].databaseId')
    [ -n "$run" ] || { echo "fullstand: no successful stand.yml run to take a bundle from" >&2; exit 1; }
fi
bundle=build/stand-bundle
echo "==> stand-bundle of stand.yml run $run"
rm -rf "$bundle"
gh run download "$run" -n stand-bundle -D "$bundle"
(cd "$bundle" && sums SHA256SUMS)
cat "$bundle/revisions.txt"

# The scenarios come from this checkout, the image and app from the bundle: say so when they differ.
for pair in "system:." "mobile_app:mobile_app" "protocol:protocol"; do
    key="${pair%%:*}"
    have=$(git -C "${pair#*:}" rev-parse HEAD 2>/dev/null || true)
    want=$(sed -n "s/^$key=//p" "$bundle/revisions.txt")
    [ -z "$want" ] || [ "$have" = "$want" ] || echo "note: $key is ${have:-unknown} here, the bundle was built from $want"
done

apk_args=()
if [ "${ANDROID:-auto}" = skip ]; then
    echo "==> ANDROID=skip: scenarios without the app"
elif command -v adb >/dev/null && adb devices | grep -q 'device$'; then
    echo "==> Android emulator found: the app takes part"
    apk_args=(--android "$bundle/app-debug.apk")
else
    echo "==> no Android emulator visible to adb: scenarios without the app (start one, or ANDROID=skip to silence this)"
fi

echo "==> scenarios (EDGE=qemu, image from the bundle)"
EDGE=qemu IMAGE_DIR="$PWD/$bundle" python3 ci/stand.py run ${apk_args[@]+"${apk_args[@]}"} tests/e2e/*.json
