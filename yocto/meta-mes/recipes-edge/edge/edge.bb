SUMMARY = "Edge service: reads CAN frames and prints one telemetry line per frame"
LICENSE = "CLOSED"

# Built from this repository's own checkout (the recipe sits four levels below the repo root),
# so the image carries exactly the rpi-app/ and emulator/interface/ code CI checked out; no
# SRCREV to keep in sync. Not externalsrc: with the build dir inside the same git repo it falls
# back to hashing the whole repo root, build/yocto and .yocto-cache included (tens of GB).
# file:// entries checksum only the listed paths.
FILESEXTRAPATHS:prepend := "${@os.path.abspath('${THISDIR}/../../../..')}:"
SRC_URI = " \
    file://CMakeLists.txt;subdir=src \
    file://emulator;subdir=src \
    file://rpi-app;subdir=src \
    file://edge.init \
"
S = "${WORKDIR}/src"

inherit cmake pkgconfig update-rc.d

DEPENDS = "libgpiod"
RDEPENDS:${PN} = "iproute2"

# Only the service; the host-side tests and emulator-example are not part of the image.
OECMAKE_TARGET_COMPILE = "edge"

do_install() {
    install -Dm 0755 ${B}/rpi-app/edge ${D}${bindir}/edge
    install -Dm 0755 ${WORKDIR}/edge.init ${D}${sysconfdir}/init.d/edge
}

INITSCRIPT_NAME = "edge"
INITSCRIPT_PARAMS = "defaults 90"
