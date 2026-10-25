#!/usr/bin/env bash
# The `process` of every integration scenario (tests/e2e/*.json): starts the edge under test against
# the stand and stays in the foreground, its output being what a scenario's stdout.expect reads.
# `emulator/cli.py run` provides the UART pty as $MES_UART_<PORT>; ci/stand.py provides STAND_EDGE_CONF
# (the generated broker config). EDGE selects where edge runs, so one scenario file serves both:
#   host  the edge binary built here (EDGE_BIN), reading the pty directly
#   qemu  the edge inside the Yocto image (not wired up yet; #25)
set -euo pipefail

case "${EDGE:-host}" in
host)
    exec "${EDGE_BIN:?EDGE_BIN: path of the built edge binary}" \
        --uart "${MES_UART_SENSOR:?scenario needs devices.uart.sensor}" \
        --config "${STAND_EDGE_CONF:?STAND_EDGE_CONF: set by ci/stand.py}"
    ;;
qemu)
    echo "stand-edge: EDGE=qemu is not implemented yet" >&2
    exit 2
    ;;
*)
    echo "stand-edge: EDGE must be host or qemu, got '${EDGE}'" >&2
    exit 2
    ;;
esac
