#!/usr/bin/env python3
"""Runs integration scenarios (tests/e2e/*.json, format in docs/TESTING.md) against a throwaway broker.

Per scenario: generate certs and credentials (emulator/stand/lib.sh), start mosquitto with TLS + ACL,
subscribe as the app user, run `emulator/cli.py run <scenario>` -- which starts the edge through
ci/stand-edge.sh and feeds it the scenario's events -- then check that the broker saw exactly the
valid LMash v1 frames the scenario sent, byte for byte and in order. A frame that is not valid
LMash v1 (wrong size, version or messageType) is expected NOT to arrive.

With --android <apk> an Android emulator (adb) joins: the app is installed with the broker config
and must log every valid TELEMETRY frame as stored, so the whole chain -- emulator, edge, broker,
app -- is checked in one run.

Output: <out>/<scenario>/{emu.log,broker.log,expected.txt,received.txt[,logcat.txt,app.png]} and <out>/junit.xml.
Exit code 1 if any scenario fails. Needs mosquitto, mosquitto_sub, openssl, bash and python3.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "emulator"))

import cli  # noqa: E402  (needs the path above)

PACKAGE = "com.example.mobile_embedded_system"
LOG_TAG = "MqttTransport"
SUBSCRIBER_ID = "stand-sub"
FRAME_SIZE = 54
DESTINATION_AT, SERIAL_AT, SEQUENCE_AT, USER_AT = 29, 13, 5, 21
MESSAGE_TYPES = {0: "telemetry", 1: "command"}


class StandError(Exception):
    pass


def read_env(path: Path) -> dict:
    """KEY=VALUE lines of emulator/stand/stand.env, overridable from the environment."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = os.environ.get(key, value)
    return values


def expected_lines(scenario: dict, root: str) -> list:
    """What the broker must see: "<topic> <payload hex>" per valid LMash v1 frame sent over UART.

    Written against the protocol (struct offsets), not against edge's C++, so the two check each other.
    """
    lines = []
    for event in scenario.get("events", []):
        if event["action"] != "uart.send":
            continue
        data = cli.payload(event)
        if len(data) != FRAME_SIZE or data[0] != 1 or data[1] not in MESSAGE_TYPES:
            continue
        (destination,) = struct.unpack_from("<Q", data, DESTINATION_AT)
        (serial,) = struct.unpack_from("<Q", data, SERIAL_AT)
        topic = f"{root.strip('/')}/{MESSAGE_TYPES[data[1]]}/to/{destination:016X}/from/{serial:016X}"
        lines.append(f"{topic} {data.hex()}")
    return lines


def expected_app_lines(scenario: dict) -> list:
    """What the app logs per valid TELEMETRY frame (MqttTransportManager: "... [userId], seq=N")."""
    lines = []
    for event in scenario.get("events", []):
        if event["action"] != "uart.send":
            continue
        data = cli.payload(event)
        if len(data) != FRAME_SIZE or data[0] != 1 or data[1] != 0:
            continue
        (user,) = struct.unpack_from("<Q", data, USER_AT)
        (sequence,) = struct.unpack_from("<I", data, SEQUENCE_AT)
        lines.append(f"[{user}], seq={sequence}")
    return lines


def bash(script: str) -> None:
    lib = REPO / "emulator" / "stand" / "lib.sh"
    result = subprocess.run(["bash", "-c", f'set -euo pipefail; . "{lib}"; {script}'], capture_output=True, text=True)
    if result.returncode != 0:
        raise StandError(f"lib.sh: {script}: {result.stderr.strip()}")


def wait_for(condition, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise StandError(f"timed out after {timeout:g} s waiting for {what}")


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


class Android:
    """The app on an already running Android emulator (adb), configured for the stand broker."""

    def __init__(self, apk: Path, directory: Path) -> None:
        self.apk, self.dir = apk, directory
        self.files = f"/sdcard/Android/data/{PACKAGE}/files/stand"

    def adb(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(["adb", *args], capture_output=True, text=True)
        if check and result.returncode != 0:
            raise StandError(f"adb {' '.join(args)}: {(result.stderr or result.stdout).strip()}")
        return result.stdout

    def logcat(self) -> str:
        return self.adb("logcat", "-d", "-s", f"{LOG_TAG}:V", check=False)

    def start(self, broker: "Broker") -> None:
        """Fresh app data (empty dedup cache and database), config pushed, app running."""
        self.adb("wait-for-device")
        self.adb("install", "-r", "-g", str(self.apk))
        self.adb("shell", "pm", "clear", PACKAGE)
        # One launch first: the app-specific external directory must exist before the shell writes into it.
        self.adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")
        time.sleep(3)
        self.adb("shell", "am", "force-stop", PACKAGE)
        self.adb("shell", "mkdir", "-p", self.files)
        self.adb("push", str(broker.app_dir / "broker.properties"), f"{self.files}/broker.properties")
        self.adb("push", str(broker.app_dir / "ca.crt"), f"{self.files}/ca.crt")
        self.adb("logcat", "-c")
        self.adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")
        subscription = f"{broker.env['TOPIC_ROOT']}/#"
        wait_for(lambda: f"Подписка оформлена на: {subscription}" in self.logcat(), 90, "the app to subscribe")

    def stored_lines(self) -> list:
        return [line.split("Телеметрия сохранена от бойца ", 1)[1].strip()
                for line in self.logcat().splitlines() if "Телеметрия сохранена от бойца " in line]

    def stop(self) -> None:
        (self.dir / "logcat.txt").write_text(self.logcat())
        # What the screen shows at the end, for a human looking at the report.
        shot = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True)
        if shot.returncode == 0 and shot.stdout:
            (self.dir / "app.png").write_bytes(shot.stdout)
        self.adb("shell", "am", "force-stop", PACKAGE, check=False)


class Broker:
    """mosquitto with the generated TLS + ACL config, and a subscriber on the whole topic root."""

    def __init__(self, directory: Path, env: dict, with_app: bool = False) -> None:
        self.dir, self.env, self.with_app = directory, env, with_app
        self.generated = directory / "generated"
        self.processes: list = []

    def __enter__(self) -> "Broker":
        port = int(self.env["BROKER_PORT"])
        if port_open(port):
            raise StandError(f"port {port} is already in use; a broker is already running here")
        bash(f'stand_generate "{self.generated}" "{self.generated}"')
        self.write_edge_config()
        if self.with_app:
            self.write_app_config()
        self.broker_log = open(self.dir / "broker.log", "w")
        self.processes.append(subprocess.Popen(
            ["mosquitto", "-c", str(self.generated / "mosquitto.conf")], stdout=self.broker_log, stderr=subprocess.STDOUT))
        wait_for(lambda: port_open(port), 15, "the broker to listen")
        self.received = open(self.dir / "received.txt", "w")
        root = self.env["TOPIC_ROOT"]
        self.processes.append(subprocess.Popen(
            ["mosquitto_sub", "-h", "127.0.0.1", "-p", str(port), "--cafile", str(self.generated / "certs" / "ca.crt"),
             "-u", self.env["APP_USER"], "-P", self.env["APP_PASS"], "-i", SUBSCRIBER_ID, "-t", f"{root}/#",
             "-q", "1", "-F", "%t %x"], stdout=self.received, stderr=subprocess.STDOUT))
        # The subscription must exist before anything is published: nothing is retained.
        pattern = re.compile(rf"{SUBSCRIBER_ID} \d+ {re.escape(root)}/#")
        wait_for(lambda: pattern.search((self.dir / "broker.log").read_text()) is not None, 15, "the subscription")
        return self

    def write_app_config(self) -> None:
        """broker.properties and ca.crt for the app; the emulator reaches the host as 10.0.2.2."""
        self.app_dir = self.dir / "app"
        self.app_dir.mkdir()
        bash(f'stand_app_conf "{self.app_dir / "broker.properties"}" 10.0.2.2')
        shutil.copy(self.generated / "certs" / "ca.crt", self.app_dir / "ca.crt")

    def write_edge_config(self) -> None:
        """edge.conf for edge on this host, or -- EDGE=qemu -- the files QEMU hands the guest."""
        if os.environ.get("EDGE", "host") == "host":
            bash(f'stand_edge_conf "{self.dir / "edge.conf"}" 127.0.0.1 "{self.generated}/certs/ca.crt"')
            return
        # The guest reaches the broker on the host as 10.0.2.2 (QEMU user networking) and finds the
        # CA where edge.init puts it, /etc/edge/ca.crt. Both names are on the cert's SAN.
        self.fwcfg = self.dir / "fwcfg"
        self.fwcfg.mkdir()
        bash(f'stand_edge_conf "{self.fwcfg / "edge.conf"}" 10.0.2.2 /etc/edge/ca.crt')
        shutil.copy(self.generated / "certs" / "ca.crt", self.fwcfg / "ca.crt")

    def received_lines(self) -> list:
        return [line for line in (self.dir / "received.txt").read_text().splitlines() if line]

    def __exit__(self, *_exc) -> None:
        for process in reversed(self.processes):
            process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        self.broker_log.close()
        self.received.close()


def run_cli(path: Path, directory: Path) -> str:
    """Runs the scenario with emulator/cli.py; returns "" or why that failed."""
    child_env = dict(os.environ, STAND_EDGE_CONF=str(directory / "edge.conf"), QEMU_FWCFG_DIR=str(directory / "fwcfg"))
    timeout = float(os.environ.get("STAND_TIMEOUT", "300"))
    command = [sys.executable, str(REPO / "emulator" / "cli.py"), "run", str(path)]
    with open(directory / "emu.log", "w") as log:
        try:
            result = subprocess.run(command, env=child_env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"cli.py run did not finish within {timeout:g} s"
    if result.returncode != 0:
        tail = "\n".join((directory / "emu.log").read_text(errors="replace").splitlines()[-15:])
        return f"cli.py run exited with {result.returncode}:\n{tail}"
    return ""


def check_delivery(broker: Broker, android: "Android | None", expected: list, expected_app: list) -> str:
    """The broker saw exactly `expected`; with an emulator, the app also stored every valid TELEMETRY frame."""
    # Delivery to the subscriber trails edge's PUBACK; then give a stray extra message a moment to show up.
    try:
        wait_for(lambda: len(broker.received_lines()) >= len(expected), 10, f"{len(expected)} message(s) at the broker")
    except StandError:
        pass
    time.sleep(1)
    received = broker.received_lines()
    if received != expected:
        return "broker saw different messages than the scenario sent\n  expected: %s\n  received: %s" % (expected, received)
    if android is None:
        return ""
    try:
        wait_for(lambda: len(android.stored_lines()) >= len(expected_app), 30, f"{len(expected_app)} stored frame(s) in the app")
    except StandError:
        pass
    stored = android.stored_lines()
    if stored != expected_app:
        return "the app stored different frames than the scenario sent (logcat.txt)\n  expected: %s\n  stored: %s" % (expected_app, stored)
    return ""


def run_scenario(path: Path, out: Path, env: dict, apk: "Path | None" = None) -> str:
    """Returns "" on success, otherwise why the scenario failed."""
    scenario = cli.load_json(str(path))
    expected = expected_lines(scenario, env["TOPIC_ROOT"])
    directory = out / path.stem
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    (directory / "expected.txt").write_text("".join(line + "\n" for line in expected))

    with Broker(directory, env, with_app=apk is not None) as broker:
        android = Android(apk, directory) if apk is not None else None
        try:
            if android is not None:
                android.start(broker)
            return run_cli(path, directory) or check_delivery(broker, android, expected, expected_app_lines(scenario))
        finally:
            if android is not None:
                android.stop()


def write_junit(results: list, path: Path) -> None:
    failures = sum(1 for _, _, problem in results if problem)
    suite = ET.Element("testsuite", name="stand", tests=str(len(results)), failures=str(failures))
    for name, seconds, problem in results:
        case = ET.SubElement(suite, "testcase", classname="e2e", name=name, time=f"{seconds:.2f}")
        if problem:
            ET.SubElement(case, "failure", message=problem.splitlines()[0]).text = problem
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["run"])
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=REPO / "build" / "stand")
    parser.add_argument("--android", type=Path, metavar="APK",
                        help="also install this APK on the running Android emulator and require it to store every frame")
    args = parser.parse_args(argv)

    tools = ["mosquitto", "mosquitto_sub", "openssl", "bash"] + (["adb"] if args.android else [])
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        print(f"stand: missing on PATH: {', '.join(missing)} (Linux: apt install mosquitto mosquitto-clients openssl)", file=sys.stderr)
        return 2
    if os.environ.get("EDGE", "host") == "host" and not Path(os.environ.get("EDGE_BIN", "")).is_file():
        print("stand: EDGE_BIN must point at the built edge binary (make e2e sets it)", file=sys.stderr)
        return 2

    env = read_env(REPO / "emulator" / "stand" / "stand.env")
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for path in args.scenarios:
        started = time.monotonic()
        try:
            problem = run_scenario(path, args.out, env, args.android)
        except (StandError, cli.CliError, OSError) as error:
            problem = str(error)
        results.append((path.stem, time.monotonic() - started, problem))
        print(f"{'FAIL' if problem else 'PASS'} {path.stem} ({results[-1][1]:.1f} s)")
        if problem:
            print("     " + problem.replace("\n", "\n     "))
    write_junit(results, args.out / "junit.xml")
    return 1 if any(problem for _, _, problem in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
