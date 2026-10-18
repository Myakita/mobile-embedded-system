"""Persistent interactive controller for the emulator's Linux virtual devices."""

from __future__ import annotations

import json
import os
import pty
import shlex
import sys
import tempfile
import time
import tty
from contextlib import ExitStack
from pathlib import Path

import cli
from lmash_v1 import ProtocolError, from_json


HELP = """Commands:
  up can [interface]             create or attach vcan (default vcan0)
  up uart <name>                 create a PTY and print its device path
  up i2c <address> [device]      create or attach i2c-stub
  up gpio [name] [lines]         create or attach gpio-sim
  down <can|uart|i2c|gpio> [name]
  list                           show active interfaces
  load <scenario.json>           create devices and replay mock events
  load <v1.json> <uart-name>      send a 54-byte LMash v1 message to UART
  help
  quit

Scenario events: can.send (id, hex, extended), uart.send (port, message/hex/text),
i2c.set/expect (register, value), gpio.set/expect (line, value), after_ms.
The message property accepts a protocol v1 vector or its fields object.
"""


class Emulator:
    def __init__(self) -> None:
        self.resources: dict[str, tuple[object, ExitStack, str]] = {}

    def close(self) -> None:
        for key in list(self.resources):
            self.down(key)

    def up(self, kind: str, name: str, config: dict) -> None:
        key = f"{kind}:{name}"
        if key in self.resources:
            raise cli.CliError(f"{key} is already active")
        stack = ExitStack()
        try:
            if kind == "can":
                value = cli.setup_can(config, stack)
                description = value
            elif kind == "uart":
                work = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="mes-uart-")))
                master, slave = pty.openpty()
                stack.callback(os.close, master)
                try:
                    tty.setraw(slave)
                    link = work / name
                    link.symlink_to(os.ttyname(slave))
                finally:
                    os.close(slave)
                value = master
                description = str(link)
            elif kind == "i2c":
                value = cli.setup_i2c(config)
                description = f"{value[0]} address 0x{value[1]:02x}"
            elif kind == "gpio":
                value = cli.setup_gpio(config, stack)
                description = "/dev/" + (value / "bank0/chip_name").read_text().strip()
            else:
                raise cli.CliError(f"unknown interface {kind}")
        except BaseException:
            stack.close()
            raise
        self.resources[key] = (value, stack, description)
        print(f"{key}: {description}")

    def down(self, key: str) -> None:
        if key not in self.resources:
            raise cli.CliError(f"{key} is not active")
        _, stack, _ = self.resources.pop(key)
        stack.close()
        print(f"down {key}")

    def runtime(self) -> dict:
        runtime: dict = {"uart": {}}
        for key, (value, _, _) in self.resources.items():
            kind, name = key.split(":", 1)
            if kind == "uart":
                runtime["uart"][name] = value
            else:
                runtime[kind] = value
        return runtime

    def load(self, path: str, target: str | None) -> None:
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise cli.CliError(f"{path}: {error}") from error
        if target is not None:
            key = f"uart:{target}"
            if key not in self.resources:
                raise cli.CliError(f"{key} is not active")
            try:
                wire = from_json(document)
            except ProtocolError as error:
                raise cli.CliError(f"{path}: {error}") from error
            os.write(self.resources[key][0], wire)
            print(f"sent LMash v1 ({len(wire)} bytes) to {key}")
            return
        config = cli.validate(document)
        if "process" in config:
            raise cli.CliError("process is available with 'run', not with 'shell load'")
        for kind, options in config.get("devices", {}).items():
            if kind == "uart":
                for name in options:
                    if f"uart:{name}" not in self.resources:
                        self.up("uart", name, {})
            else:
                name = options.get("interface", "vcan0") if kind == "can" else (
                    options.get("name", "mes-cli") if kind == "gpio" else "stub"
                )
                if f"{kind}:{name}" not in self.resources:
                    self.up(kind, name, options)
        runtime = self.runtime()
        if "can" in config.get("devices", {}):
            interface = config["devices"]["can"].get("interface", "vcan0")
            runtime["can"] = self.resources[f"can:{interface}"][0]
        if "gpio" in config.get("devices", {}):
            name = config["devices"]["gpio"].get("name", "mes-cli")
            runtime["gpio"] = self.resources[f"gpio:{name}"][0]
        for index, event in enumerate(config.get("events", [])):
            if event["action"] == "stdout.expect":
                raise cli.CliError("stdout.expect requires 'run', not 'shell load'")
            time.sleep(event.get("after_ms", 0) / 1000)
            try:
                cli.execute_event(event, runtime)
            except (cli.CliError, OSError) as error:
                raise cli.CliError(f"events[{index}] ({event['action']}): {error}") from error
            print(f"PASS events[{index}] {event['action']}")

    def command(self, line: str) -> bool:
        args = shlex.split(line)
        if not args:
            return True
        verb, *rest = args
        if verb in ("quit", "exit"):
            return False
        if verb == "help":
            print(HELP)
        elif verb == "list":
            for key, (_, _, description) in self.resources.items():
                print(f"{key}: {description}")
        elif verb == "load" and len(rest) in (1, 2):
            self.load(rest[0], rest[1] if len(rest) == 2 else None)
        elif verb == "up" and rest:
            kind, *values = rest
            if kind == "can" and len(values) <= 1:
                name = values[0] if values else "vcan0"
                self.up(kind, name, {"interface": name, "create": True})
            elif kind == "uart" and len(values) == 1:
                self.up(kind, values[0], {})
            elif kind == "i2c" and len(values) in (1, 2):
                config = {"address": cli.number(values[0], "address", 0x7f), "create": True}
                if len(values) == 2:
                    config["device"] = values[1]
                self.up(kind, "stub", config)
            elif kind == "gpio" and len(values) <= 2:
                name = values[0] if values else "mes-cli"
                count = cli.number(values[1], "lines", 256) if len(values) == 2 else 8
                self.up(kind, name, {"name": name, "lines": count, "create": True})
            else:
                raise cli.CliError("usage: up can|uart|i2c|gpio ... (see help)")
        elif verb == "down" and rest:
            kind, *values = rest
            if kind not in ("can", "uart", "i2c", "gpio") or len(values) > 1:
                raise cli.CliError("usage: down can|uart|i2c|gpio [name]")
            default = {"can": "vcan0", "i2c": "stub", "gpio": "mes-cli"}
            if kind == "uart" and not values:
                raise cli.CliError("down uart requires a name")
            self.down(f"{kind}:{values[0] if values else default[kind]}")
        else:
            raise cli.CliError("unknown command or arguments (see help)")
        return True


def repl() -> int:
    emulator = Emulator()
    try:
        while True:
            try:
                line = input("emu> ")
            except EOFError:
                break
            try:
                if not emulator.command(line):
                    break
            except (cli.CliError, OSError, ValueError) as error:
                print(f"emu: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print()
    finally:
        emulator.close()
    return 0
