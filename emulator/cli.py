#!/usr/bin/env python3
"""Drive the Linux virtual peripherals used by the integration emulator.

The standard library handles CAN and PTYs. i2c-stub is accessed with i2c-tools;
gpio-sim's documented sysfs attributes drive and observe its lines.
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tty
from contextlib import ExitStack
from pathlib import Path

from lmash_v1 import ProtocolError, from_json

GPIO_CONFIG = Path("/sys/kernel/config/gpio-sim")
I2C_SYS = Path("/sys/bus/i2c/devices")
GPIO_DEVICES = Path("/sys/devices/platform")


class CliError(Exception):
    pass


def number(value: object, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise CliError(f"{label}: expected an integer")
    try:
        result = int(value, 0) if isinstance(value, str) else value
    except ValueError as error:
        raise CliError(f"{label}: invalid integer {value!r}") from error
    if not 0 <= result <= maximum:
        raise CliError(f"{label}: must be between 0 and {maximum}")
    return result


def fields(obj: object, allowed: set[str], label: str) -> dict:
    if not isinstance(obj, dict):
        raise CliError(f"{label}: expected a JSON object")
    unknown = set(obj) - allowed
    if unknown:
        raise CliError(f"{label}: unknown fields: {', '.join(sorted(unknown))}")
    return obj


def payload(event: dict) -> bytes:
    if sum(key in event for key in ("hex", "text", "message")) != 1:
        raise CliError("event: specify exactly one of hex, text and message")
    if "message" in event:
        try:
            return from_json(event["message"])
        except ProtocolError as error:
            raise CliError(f"event.message: {error}") from error
    if "hex" in event:
        if not isinstance(event["hex"], str):
            raise CliError("event.hex: expected a string")
        try:
            return bytes.fromhex(event["hex"])
        except ValueError as error:
            raise CliError("event.hex: invalid hexadecimal bytes") from error
    if not isinstance(event["text"], str):
        raise CliError("event.text: expected a string")
    return event["text"].encode("utf-8")


def validate(config: object) -> dict:
    config = fields(config, {"devices", "process", "events"}, "scenario")
    devices = fields(config.get("devices", {}), {"can", "uart", "i2c", "gpio"}, "devices")
    if "can" in devices:
        can = fields(devices["can"], {"interface", "create"}, "devices.can")
        if not isinstance(can.get("interface", "vcan0"), str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,15}", can.get("interface", "vcan0")
        ):
            raise CliError("devices.can.interface: invalid interface name")
        if not isinstance(can.get("create", False), bool):
            raise CliError("devices.can.create: expected a boolean")
    if "uart" in devices:
        if not isinstance(devices["uart"], dict):
            raise CliError("devices.uart: expected a JSON object")
        uart = devices["uart"]
        for name, options in uart.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
                raise CliError(f"devices.uart: invalid port name {name!r}")
            fields(options, set(), f"devices.uart.{name}")
    if "i2c" in devices:
        i2c = fields(devices["i2c"], {"address", "device", "create"}, "devices.i2c")
        if "address" not in i2c:
            raise CliError("devices.i2c.address is required")
        number(i2c["address"], "devices.i2c.address", 0x7F)
        if "device" in i2c and not isinstance(i2c["device"], str):
            raise CliError("devices.i2c.device: expected a path")
        if not isinstance(i2c.get("create", False), bool):
            raise CliError("devices.i2c.create: expected a boolean")
    if "gpio" in devices:
        gpio = fields(devices["gpio"], {"name", "lines", "create"}, "devices.gpio")
        if not isinstance(gpio.get("name", "mes-cli"), str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,40}", gpio.get("name", "mes-cli")
        ):
            raise CliError("devices.gpio.name: invalid simulator name")
        if number(gpio.get("lines", 8), "devices.gpio.lines", 256) == 0:
            raise CliError("devices.gpio.lines: must be at least 1")
        if not isinstance(gpio.get("create", False), bool):
            raise CliError("devices.gpio.create: expected a boolean")
    command = config.get("process")
    if command is not None and (not isinstance(command, list) or not command or
                                any(not isinstance(arg, str) or not arg for arg in command)):
        raise CliError("process: expected a nonempty array of command arguments")
    events = config.get("events", [])
    if not isinstance(events, list):
        raise CliError("events: expected an array")
    allowed = {"can.send": {"id", "hex", "extended"},
               "uart.send": {"port", "hex", "text", "message"},
               "i2c.set": {"register", "value"},
               "i2c.expect": {"register", "value"},
               "gpio.set": {"line", "value"},
               "gpio.expect": {"line", "value"},
               "stdout.expect": {"text", "timeout_ms"}}
    peripheral = {"can", "uart", "i2c", "gpio"}
    for index, item in enumerate(events):
        event = fields(item, set().union(*allowed.values(), {"action", "after_ms"}), f"events[{index}]")
        action = event.get("action")
        if action not in allowed:
            raise CliError(f"events[{index}].action: unsupported action {action!r}")
        fields(event, allowed[action] | {"action", "after_ms"}, f"events[{index}]")
        number(event.get("after_ms", 0), "event.after_ms", 3600000)
        kind = action.split(".")[0]
        if kind in peripheral and kind not in devices:
            raise CliError(f"events[{index}]: devices.{kind} is missing")
        if kind == "can":
            number(event.get("id"), "event.id", 0x1FFFFFFF)
            data = payload(event)
            if len(data) > 8:
                raise CliError("event.hex: classic CAN frame holds at most 8 bytes")
            if not isinstance(event.get("extended", False), bool):
                raise CliError("event.extended: expected a boolean")
            if not event.get("extended", False) and number(event["id"], "event.id", 0x1FFFFFFF) > 0x7FF:
                raise CliError("event.id: standard CAN ID exceeds 0x7ff; set extended=true")
        elif kind == "uart":
            if event.get("port") not in devices["uart"]:
                raise CliError(f"events[{index}].port: unknown UART port")
            payload(event)
        elif kind == "i2c":
            number(event.get("register"), "event.register", 255)
            number(event.get("value"), "event.value", 255)
        elif kind == "gpio":
            number(event.get("line"), "event.line", devices["gpio"].get("lines", 8) - 1)
            number(event.get("value"), "event.value", 1)
        elif kind == "stdout":
            if command is None:
                raise CliError("stdout.expect requires process")
            if not isinstance(event.get("text"), str) or not event["text"]:
                raise CliError("event.text: expected a nonempty string")
            number(event.get("timeout_ms", 5000), "event.timeout_ms", 3600000)
    return config


def run_command(*args: str) -> str:
    try:
        result = subprocess.run(args, text=True, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise CliError(f"missing program: {args[0]}") from error
    except subprocess.CalledProcessError as error:
        raise CliError(f"{' '.join(args)}: {error.stderr.strip() or error.stdout.strip()}") from error
    return result.stdout.strip()


def module(name: str, *options: str) -> None:
    run_command("modprobe", name, *options)


def setup_can(config: dict, stack: ExitStack) -> str:
    interface = config.get("interface", "vcan0")
    if config.get("create", False):
        module("vcan")
        if not Path("/sys/class/net", interface).exists():
            run_command("ip", "link", "add", "dev", interface, "type", "vcan")
            stack.callback(run_command, "ip", "link", "delete", "dev", interface)
        run_command("ip", "link", "set", "dev", interface, "up")
    if not Path("/sys/class/net", interface).exists():
        raise CliError(f"CAN interface {interface} does not exist (set devices.can.create=true)")
    return interface


def find_i2c_stub() -> Path:
    buses = []
    for name in I2C_SYS.glob("i2c-*/name"):
        if "stub" in name.read_text().lower():
            buses.append(Path("/dev") / name.parent.name)
    if len(buses) != 1:
        raise CliError(f"expected one i2c-stub bus, found {len(buses)}; specify devices.i2c.device")
    return buses[0]


def setup_i2c(config: dict) -> tuple[Path, int]:
    address = number(config["address"], "devices.i2c.address", 0x7F)
    if config.get("create", False):
        if Path("/sys/module/i2c_stub").exists():
            if not list(I2C_SYS.glob("i2c-*/name")):
                raise CliError("i2c-stub is loaded but no I2C buses are visible")
        else:
            module("i2c-dev")
            module("i2c-stub", f"chip_addr=0x{address:02x}")
    device = Path(config["device"]) if "device" in config else find_i2c_stub()
    if not device.exists():
        raise CliError(f"I2C device {device} does not exist")
    return device, address


def gpio_root(name: str) -> Path:
    return GPIO_CONFIG / name


def setup_gpio(config: dict, stack: ExitStack) -> Path:
    root = gpio_root(config.get("name", "mes-cli"))
    if config.get("create", False) and not root.exists():
        module("gpio-sim")
        if not GPIO_CONFIG.exists():
            run_command("mount", "-t", "configfs", "none", "/sys/kernel/config")
        root.mkdir()
        bank = root / "bank0"
        try:
            bank.mkdir()
            (bank / "num_lines").write_text(str(config.get("lines", 8)))
            (root / "live").write_text("1")
        except OSError:
            try:
                (root / "live").write_text("0")
            except OSError:
                pass
            if bank.exists():
                bank.rmdir()
            root.rmdir()
            raise
        stack.callback(remove_gpio, root)
    if not root.exists():
        raise CliError(f"gpio-sim {root} does not exist (set devices.gpio.create=true)")
    if (root / "live").read_text().strip() != "1":
        raise CliError(f"gpio-sim {root} is not live")
    return root


def remove_gpio(root: Path) -> None:
    (root / "live").write_text("0")
    (root / "bank0").rmdir()
    root.rmdir()


def gpio_attribute(root: Path, line: int, attribute: str) -> Path:
    dev_name = (root / "dev_name").read_text().strip()
    candidates = list((GPIO_DEVICES / dev_name).glob(f"gpiochip*/sim_gpio{line}/{attribute}"))
    if len(candidates) != 1:
        raise CliError(f"gpio-sim line {line} has no unique {attribute} attribute")
    return candidates[0]


def i2c_set(device: Path, address: int, register: int, value: int) -> None:
    bus = device.name.removeprefix("i2c-")
    run_command("i2cset", "-y", bus, f"0x{address:02x}", f"0x{register:02x}", f"0x{value:02x}", "b")


def i2c_get(device: Path, address: int, register: int) -> int:
    bus = device.name.removeprefix("i2c-")
    return int(run_command("i2cget", "-y", bus, f"0x{address:02x}", f"0x{register:02x}", "b"), 0)


def can_send(interface: str, identifier: int, data: bytes, extended: bool = False) -> None:
    if not hasattr(socket, "AF_CAN"):
        raise CliError("CAN requires Linux")
    import struct

    frame_id = identifier | (0x80000000 if extended else 0)
    frame = struct.pack("=IB3x8s", frame_id, len(data), data.ljust(8, b"\0"))
    with socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as channel:
        channel.bind((interface,))
        channel.send(frame)


def wait_for_output(log: Path, expected: str, timeout_ms: int, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() <= deadline:
        if expected in log.read_text(errors="replace"):
            return
        if process.poll() is not None:
            break
        time.sleep(0.02)
    raise CliError(f"process output did not contain {expected!r} within {timeout_ms} ms")


def execute_event(event: dict, runtime: dict) -> None:
    action = event["action"]
    if action == "can.send":
        can_send(runtime["can"], number(event["id"], "event.id", 0x1FFFFFFF), payload(event), event.get("extended", False))
    elif action == "uart.send":
        os.write(runtime["uart"][event["port"]], payload(event))
    elif action == "i2c.set":
        i2c_set(*runtime["i2c"], number(event["register"], "event.register", 255), number(event["value"], "event.value", 255))
    elif action == "i2c.expect":
        actual = i2c_get(*runtime["i2c"], number(event["register"], "event.register", 255))
        expected = number(event["value"], "event.value", 255)
        if actual != expected:
            raise CliError(f"I2C register {event['register']}: expected {expected:#x}, got {actual:#x}")
    elif action == "gpio.set":
        line = number(event["line"], "event.line", 255)
        value = number(event["value"], "event.value", 1)
        gpio_attribute(runtime["gpio"], line, "pull").write_text("pull-up" if value else "pull-down")
    elif action == "gpio.expect":
        line = number(event["line"], "event.line", 255)
        actual = int(gpio_attribute(runtime["gpio"], line, "value").read_text().strip())
        expected = number(event["value"], "event.value", 1)
        if actual != expected:
            raise CliError(f"GPIO line {line}: expected {expected}, got {actual}")
    elif action == "stdout.expect":
        wait_for_output(runtime["log"], event["text"], event.get("timeout_ms", 5000), runtime["process"])


def run_scenario(config: dict) -> None:
    with ExitStack() as stack:
        work = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="mes-emulator-")))
        runtime: dict = {"uart": {}}
        devices = config.get("devices", {})
        if "can" in devices:
            runtime["can"] = setup_can(devices["can"], stack)
        if "i2c" in devices:
            runtime["i2c"] = setup_i2c(devices["i2c"])
            print(f"I2C: {runtime['i2c'][0]}", flush=True)
        if "gpio" in devices:
            runtime["gpio"] = setup_gpio(devices["gpio"], stack)
            print(f"GPIO: /dev/{(runtime['gpio'] / 'bank0/chip_name').read_text().strip()}", flush=True)
        environment = os.environ.copy()
        for name in devices.get("uart", {}):
            master, slave = pty.openpty()
            stack.callback(os.close, master)
            tty.setraw(slave)
            link = work / name
            link.symlink_to(os.ttyname(slave))
            os.close(slave)
            runtime["uart"][name] = master
            environment[f"MES_UART_{name.upper()}"] = str(link)
            print(f"UART {name}: {link}", flush=True)
        if "can" in runtime:
            environment["MES_CAN_INTERFACE"] = runtime["can"]
        if "i2c" in runtime:
            environment["MES_I2C_DEVICE"] = str(runtime["i2c"][0])
        if "gpio" in runtime:
            environment["MES_GPIO_CHIP"] = "/dev/" + (runtime["gpio"] / "bank0/chip_name").read_text().strip()
        if "process" in config:
            runtime["log"] = work / "process.log"
            output = stack.enter_context(runtime["log"].open("w"))
            process = subprocess.Popen(config["process"], stdout=output, stderr=subprocess.STDOUT,
                                       env=environment, start_new_session=True)
            runtime["process"] = process
            stack.callback(stop_process, process)
        try:
            for index, event in enumerate(config.get("events", [])):
                time.sleep(event.get("after_ms", 0) / 1000)
                execute_event(event, runtime)
                print(f"PASS events[{index}] {event['action']}", flush=True)
            if "process" in runtime and runtime["process"].poll() not in (None, 0):
                raise CliError(f"process exited with code {runtime['process'].returncode}")
        except (CliError, OSError) as error:
            raise CliError(f"events[{index}] ({event['action']}): {error}") from error
        finally:
            if "log" in runtime:
                print(runtime["log"].read_text(errors="replace"), end="", flush=True)


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as source:
            return validate(json.load(source))
    except (OSError, json.JSONDecodeError) as error:
        raise CliError(f"{path}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Control CAN, UART, I2C and gpio-sim mock peripherals")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("shell", help="interactive emu> virtual interface orchestrator")
    for command in ("validate", "run"):
        commands.add_parser(command).add_argument("scenario", help="JSON scenario file")
    can = commands.add_parser("can-send", help="send a classic CAN frame")
    can.add_argument("interface")
    can.add_argument("id")
    can.add_argument("hex")
    can.add_argument("--extended", action="store_true")
    uart = commands.add_parser("uart-send", help="write bytes to a PTY")
    uart.add_argument("device")
    data = uart.add_mutually_exclusive_group(required=True)
    data.add_argument("--text")
    data.add_argument("--hex")
    for command in ("i2c-set", "i2c-get"):
        sub = commands.add_parser(command)
        sub.add_argument("device")
        sub.add_argument("address")
        sub.add_argument("register")
        if command == "i2c-set":
            sub.add_argument("value")
    for command in ("gpio-set", "gpio-get"):
        sub = commands.add_parser(command, help="drive an input or read a gpio-sim line")
        sub.add_argument("name", help="gpio-sim configfs device name")
        sub.add_argument("line")
        if command == "gpio-set":
            sub.add_argument("value")
    args = parser.parse_args(argv)
    try:
        if args.command == "shell":
            from shell import repl
            return repl()
        if args.command in ("validate", "run"):
            scenario = load_json(args.scenario)
            if args.command == "validate":
                print("valid scenario")
            else:
                run_scenario(scenario)
        elif args.command == "can-send":
            frame = payload({"hex": args.hex})
            if len(frame) > 8:
                raise CliError("classic CAN frame holds at most 8 bytes")
            limit = 0x1FFFFFFF if args.extended else 0x7FF
            can_send(args.interface, number(args.id, "id", limit), frame, args.extended)
        elif args.command == "uart-send":
            with open(args.device, "wb", buffering=0) as port:
                port.write(payload({"text": args.text} if args.text is not None else {"hex": args.hex}))
        elif args.command == "i2c-set":
            i2c_set(Path(args.device), number(args.address, "address", 0x7F),
                    number(args.register, "register", 255), number(args.value, "value", 255))
        elif args.command == "i2c-get":
            print(f"0x{i2c_get(Path(args.device), number(args.address, 'address', 0x7F), number(args.register, 'register', 255)):02x}")
        elif args.command == "gpio-set":
            line = number(args.line, "line", 255)
            value = number(args.value, "value", 1)
            gpio_attribute(gpio_root(args.name), line, "pull").write_text("pull-up" if value else "pull-down")
        elif args.command == "gpio-get":
            print(gpio_attribute(gpio_root(args.name), number(args.line, "line", 255), "value").read_text().strip())
        return 0
    except (CliError, OSError, ValueError) as error:
        print(f"emulator-cli: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
