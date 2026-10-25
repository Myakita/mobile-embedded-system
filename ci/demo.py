"""`make demo`: the whole stand kept up and driven from one prompt, for showing it to somebody.

Picks what this machine can run -- edge in QEMU (image from `make fullstand`'s bundle), edge on the host
(Linux), or, failing both, frames published straight to the broker -- and the Android app only on an
emulator. Everything listens on 127.0.0.1 and is torn down on exit, Ctrl-C included.

    make demo                    interactive: send frames, see what broker, edge and app each got
    make demo-check              the same chain scripted, exit code 0/1 (docker-check runs it)
    DEMO_EDGE=qemu|host|broker   force the edge side;   ANDROID=skip   leave the app out
Guide for the team: docs/DEMO.md.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path[:0] = [str(HERE), str(REPO / "emulator")]

import cli
import lmash_v1
import shell
import stand

BUNDLE = REPO / "build" / "stand-bundle"
MOCK = REPO / "emulator" / "mocks" / "telemetry-v1.json"
FIRST_SEQUENCE = 1000
READY = "edge: reading frames from"
BROKER, EDGE, APP = "брокер", "edge", "приложение"

HELP = """Команды:
  t [ключ=значение ...]   телеметрия, например: t pulseBpm=130 temperatureX100=3900
  b                       битый кадр (версия 2): edge должен его отбросить, брокер промолчать
  n [N]                   серия из N кадров (по умолчанию 5)
  s                       что сейчас запущено
  h                       эта подсказка          q   выход (всё остановится)"""


def pick_emulator(adb_devices: str) -> str | None:
    """Serial of the first running Android *emulator*; never a phone: the app's data gets wiped."""
    for line in adb_devices.splitlines()[1:]:
        serial, _, state = line.partition("\t")
        if serial.startswith("emulator-") and state.strip() == "device":
            return serial
    return None


def choose_edge(forced: str | None, qemu_ready: bool, host_ready: bool) -> str:
    if forced:
        return forced
    return "qemu" if qemu_ready else "host" if host_ready else "broker"


def bundle_ready() -> bool:
    rootfs = (BUNDLE / "rootfs.ext4").exists() or (
        (BUNDLE / "rootfs.ext4.zst").exists() and stand.find_tool("zstd") is not None)
    return (BUNDLE / "bzImage").exists() and rootfs


def fetch_bundle() -> None:
    """No image or APK yet: take the CI stand-bundle, as `make fullstand` does (own repo, ~52 MiB)."""
    gh = shutil.which("gh")
    if gh is None or subprocess.run([gh, "auth", "status"], capture_output=True, check=False).returncode != 0:
        print("  образа нет, а gh не авторизован: `gh auth login` и запустите снова (или `make fullstand`)")
        return
    print("  скачиваю stand-bundle из CI (~52 МиБ) ...")
    subprocess.run(["bash", str(HERE / "fullstand.sh")], env=dict(os.environ, BUNDLE_ONLY="1"), check=False)


def find_emulator() -> tuple[str | None, str]:
    """(serial, why not) of the Android emulator the app can use."""
    adb = stand.find_tool("adb")
    if os.environ.get("ANDROID") == "skip":
        return None, "ANDROID=skip"
    if adb is None:
        return None, "нет adb (Android SDK)"
    out = subprocess.run([adb, "devices"], capture_output=True, text=True, check=False).stdout
    serial = pick_emulator(out)
    return (serial, "") if serial else (None, "эмулятор не запущен (`adb devices` пуст или только телефон)")


def plan(fetch: bool) -> dict:
    forced = os.environ.get("DEMO_EDGE")
    if forced not in (None, "qemu", "host", "broker"):
        sys.exit(f"DEMO_EDGE: qemu, host или broker, а не {forced!r}")
    missing = [tool for tool in ("mosquitto", "mosquitto_sub", "mosquitto_pub", "openssl")
               if stand.find_tool(tool) is None]
    if missing:
        sys.exit(f"demo: нет {', '.join(missing)} (Linux: apt install mosquitto mosquitto-clients openssl; Mac: brew install mosquitto)")
    serial, why_no_app = find_emulator()
    has_qemu = shutil.which("qemu-system-x86_64") is not None
    if fetch and (serial or (has_qemu and forced in (None, "qemu"))) and not bundle_ready():
        fetch_bundle()
    if serial and not (BUNDLE / "app-debug.apk").exists():
        serial, why_no_app = None, "нет APK (build/stand-bundle)"
    host_ready = sys.platform.startswith("linux") and Path(os.environ.get("EDGE_BIN", "")).is_file()
    edge = choose_edge(forced, has_qemu and bundle_ready(), host_ready)
    return {"edge": edge, "serial": serial, "why_no_app": why_no_app}


def describe(wanted: dict) -> None:
    edge = {"qemu": "образ Linux в QEMU", "host": "edge на этой машине",
            "broker": "без edge: кадры публикуются в брокер напрямую"}[wanted["edge"]]
    print("Что будет запущено:")
    print("  брокер MQTT (TLS, только 127.0.0.1)    да")
    print(f"  edge                                   {edge}")
    print(f"  приложение Android                     {wanted['serial'] or 'нет: ' + wanted['why_no_app']}")


class Demo:
    """What is running, and the way to push a frame into it."""

    def __init__(self) -> None:
        self.env: dict = {}
        self.broker = None
        self.android = None
        self.edge = "broker"
        self.edge_proc = None
        self.edge_log: Path | None = None
        self.emulator = shell.Emulator()
        self.uart_path = ""
        self.events: list = []
        self.sent: set = set()
        self.sequence = FIRST_SEQUENCE
        self.seen: dict = {}

    def master(self) -> int:
        return self.emulator.resources["uart:sensor"][0]


def start_edge(demo: Demo, work: Path, mode: str) -> None:
    log = work / "edge.log"
    env = dict(os.environ, EDGE=mode, MES_UART_SENSOR=demo.uart_path, STAND_EDGE_CONF=str(work / "edge.conf"),
               QEMU_FWCFG_DIR=str(work / "fwcfg"), IMAGE_DIR=str(BUNDLE))
    with log.open("w") as out:
        proc = subprocess.Popen(["bash", str(HERE / "stand-edge.sh")], stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    try:
        if mode == "qemu":
            print("  загружаю образ в QEMU (на Mac без KVM — несколько секунд) ...")
        stand.wait_for(lambda: READY in log.read_text(errors="replace") or proc.poll() is not None,
                       180 if mode == "qemu" else 20, "edge to open the UART")
        if READY not in log.read_text(errors="replace"):
            tail = " | ".join(log.read_text(errors="replace").splitlines()[-3:])
            raise stand.StandError(f"edge завершился: {tail}")
    except BaseException:
        cli.stop_process(proc)
        raise
    demo.edge_proc, demo.edge_log, demo.edge = proc, log, mode


def start_app(stack: ExitStack, demo: Demo, work: Path) -> None:
    android = stand.Android(BUNDLE / "app-debug.apk", work)
    try:
        android.start(demo.broker)
        demo.android = android
    except stand.StandError as error:
        print(f"! приложение не запустилось: {error}\n  продолжаю без него")
    finally:
        stack.callback(android.stop)


def start(stack: ExitStack, wanted: dict) -> Demo:
    demo = Demo()
    work = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="mes-demo-")))
    if os.geteuid() == 0:
        # mosquitto run as root drops to its own user while reading the config, and that user must be
        # able to walk into the (test-only) certificates; a 0700 temp dir stops it. Docker, CI.
        work.chmod(0o755)
    demo.env = stand.read_env(REPO / "emulator" / "stand" / "stand.env")
    os.environ["STAND_BIND"] = "127.0.0.1"
    os.environ["EDGE"] = "qemu" if wanted["edge"] == "qemu" else "host"
    if wanted["serial"]:
        os.environ["ANDROID_SERIAL"] = wanted["serial"]
    demo.broker = stack.enter_context(stand.Broker(work, demo.env, with_app=bool(wanted["serial"])))
    stack.callback(demo.emulator.close)
    demo.emulator.up("uart", "sensor", {})
    demo.uart_path = demo.emulator.resources["uart:sensor"][2]
    if wanted["edge"] != "broker":
        try:
            start_edge(demo, work, wanted["edge"])
            stack.callback(cli.stop_process, demo.edge_proc)
        except stand.StandError as error:
            print(f"! edge ({wanted['edge']}) не поднялся: {error}\n  продолжаю без него: кадры идут прямо в брокер")
    if wanted["serial"]:
        start_app(stack, demo, work)
    demo.seen = {name: len(lines) for name, lines in sources(demo).items()}
    return demo


def sources(demo: Demo) -> dict:
    found = {BROKER: demo.broker.received_lines()}
    if demo.edge_log is not None:
        text = demo.edge_log.read_text(errors="replace")
        found[EDGE] = [line.strip() for line in text.splitlines() if line.strip().startswith("edge:")]
    if demo.android is not None:
        found[APP] = demo.android.stored_lines()
    return found


def shown(demo: Demo, name: str, line: str) -> str:
    if name == BROKER:
        topic, _, hex_payload = line.partition(" ")
        same = ", совпадает с отправленным" if hex_payload in demo.sent else ""
        return f"{topic} ({len(hex_payload) // 2} байт{same})"
    return line


def report(demo: Demo, want_broker: int, patience: float) -> None:
    """Wait for the expected arrivals, then print only what is new since the last call."""
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        now = sources(demo)
        waiting_for = [name for name in (BROKER, APP) if name in now]
        if want_broker and all(len(now[name]) - demo.seen[name] >= want_broker for name in waiting_for):
            break
        time.sleep(0.2)
    for name, lines in sources(demo).items():
        for line in lines[demo.seen[name]:]:
            print(f"  {name:<11} {shown(demo, name, line)}")
        demo.seen[name] = len(lines)


def make_frame(demo: Demo, overrides: dict) -> bytes:
    base = json.loads(MOCK.read_text(encoding="utf-8"))["fields"]
    wire = lmash_v1.from_json({**base, "sequence": demo.sequence, **overrides})
    demo.sequence += 1
    return wire


def publish(demo: Demo, wire: bytes) -> None:
    """No edge: do what it would, publish the frame as the edge user."""
    scenario = {"events": [{"action": "uart.send", "port": "sensor", "hex": wire.hex()}]}
    generated = demo.broker.generated
    for line in stand.expected_lines(scenario, demo.env["TOPIC_ROOT"]):
        result = subprocess.run(
            [stand.find_tool("mosquitto_pub"), "-h", "127.0.0.1", "-p", demo.env["BROKER_PORT"],
             "--cafile", str(generated / "certs" / "ca.crt"), "-u", demo.env["EDGE_USER"],
             "-P", demo.env["EDGE_PASS"], "-i", "demo-edge", "-t", line.split(" ", 1)[0], "-q", "1", "-s"],
            input=wire, capture_output=True, check=False)
        if result.returncode != 0:
            raise stand.StandError(f"mosquitto_pub: {result.stderr.decode(errors='replace').strip()}")


def deliver(demo: Demo, wire: bytes) -> None:
    demo.events.append({"action": "uart.send", "port": "sensor", "hex": wire.hex()})
    demo.sent.add(wire.hex())
    if demo.edge == "broker":
        publish(demo, wire)
    else:
        os.write(demo.master(), wire)


def parse_overrides(args: str) -> dict:
    out: dict = {}
    for token in args.split():
        key, sep, value = token.partition("=")
        if not sep:
            raise ValueError(f"ожидал ключ=значение, получил {token!r}")
        out[key] = int(value) if value.lstrip("-").isdigit() else value
    return out


def cmd_telemetry(demo: Demo, args: str) -> None:
    overrides = parse_overrides(args)
    wire = make_frame(demo, overrides)
    changed = "".join(f" {key}={value}" for key, value in overrides.items())
    print(f"-> телеметрия seq={demo.sequence - 1}{changed}")
    deliver(demo, wire)
    report(demo, 1, 8)


def cmd_bad(demo: Demo, _args: str) -> None:
    wire = make_frame(demo, {})
    print("-> битый кадр: версия протокола 2")
    deliver(demo, b"\x02" + wire[1:])
    if demo.edge == "broker":
        print("  (без edge такой кадр просто не публикуется: edge отбросил бы его)")
    report(demo, 0, 1.5)


def cmd_burst(demo: Demo, args: str) -> None:
    count = int(args) if args.strip().isdigit() else 5
    print(f"-> серия из {count} кадров")
    for _ in range(count):
        deliver(demo, make_frame(demo, {}))
        time.sleep(0.2)
    report(demo, count, 10 + count)


def cmd_status(demo: Demo, _args: str) -> None:
    alive = demo.edge_proc is not None and demo.edge_proc.poll() is None
    print(f"  edge: {demo.edge}{'' if demo.edge == 'broker' or alive else ' (ЗАВЕРШИЛСЯ)'}; "
          f"брокер: 127.0.0.1:{demo.env['BROKER_PORT']}, корень {demo.env['TOPIC_ROOT']}; "
          f"приложение: {'да' if demo.android else 'нет'}")


HANDLERS = {"t": cmd_telemetry, "b": cmd_bad, "n": cmd_burst, "s": cmd_status}


def menu(demo: Demo) -> int:
    print(f"\nГотово. Брокер, {'edge' if demo.edge != 'broker' else 'публикация вместо edge'}"
          f"{', приложение' if demo.android else ''} запущены.\n{HELP}")
    while True:
        try:
            line = input("demo> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        command, _, args = line.partition(" ")
        if command in ("q", "quit", "exit"):
            return 0
        if command in ("h", "help", "?"):
            print(HELP)
        elif command in HANDLERS:
            try:
                HANDLERS[command](demo, args)
            except (ValueError, lmash_v1.ProtocolError, stand.StandError, OSError) as error:
                print(f"  ошибка: {error}")
        elif command:
            print("  не знаю такую команду, h — подсказка")


def auto(demo: Demo) -> int:
    """Rehearsal without a keyboard: valid, invalid, valid; the broker must have exactly the valid two."""
    for handler in (cmd_telemetry, cmd_bad, cmd_telemetry):
        handler(demo, "")
    scenario = {"events": demo.events}
    problem = stand.check_delivery(demo.broker, demo.android, stand.expected_lines(scenario, demo.env["TOPIC_ROOT"]),
                                   stand.expected_app_lines(scenario))
    print(f"demo-check: {'FAIL ' + problem if problem else 'OK'}")
    return 1 if problem else 0


def interrupt(_signum, _frame) -> None:
    raise KeyboardInterrupt


def main(argv: list) -> int:
    scripted = "--auto" in argv
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    wanted = plan(fetch=not scripted)
    describe(wanted)
    try:
        with ExitStack() as stack:
            demo = start(stack, wanted)
            return auto(demo) if scripted else menu(demo)
    except stand.StandError as error:
        print(f"demo: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ndemo: прервано, всё остановлено")
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
