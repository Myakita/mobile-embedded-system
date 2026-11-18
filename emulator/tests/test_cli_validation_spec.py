# ruff: noqa: SIM117, SIM115
"""Specification tests for emulator/cli.py: number, fields, payload, validate, load_json,
execute_event helpers and argument handling in main(). No kernel devices, no root."""

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulator"))

import cli
from cli import CliError, fields, number, payload, validate

TELEMETRY_MSG = json.loads((ROOT / "protocol/vectors/telemetry-v1.json").read_text(encoding="utf-8"))


def scenario(events=None, **devices):
    doc = {}
    if devices:
        doc["devices"] = devices
    if events is not None:
        doc["events"] = events
    return doc


class Number(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(number(0, "x", 255), 0)
        self.assertEqual(number(255, "x", 255), 255)

    def test_out_of_range(self):
        for bad in (-1, 256):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "x: must be between 0 and 255"):
                    number(bad, "x", 255)

    def test_string_radixes(self):
        self.assertEqual(number("0x7f", "x", 255), 127)
        self.assertEqual(number("0b101", "x", 255), 5)
        self.assertEqual(number("0o17", "x", 255), 15)
        self.assertEqual(number("42", "x", 255), 42)

    def test_invalid_strings(self):
        for bad in ("", "abc", "077", "1.5", "0x"):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "invalid integer"):
                    number(bad, "x", 255)

    def test_string_out_of_range(self):
        with self.assertRaisesRegex(CliError, "must be between"):
            number("0x100", "x", 255)

    def test_wrong_types(self):
        for bad in (True, False, 1.0, None, [1], {}):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "x: expected an integer"):
                    number(bad, "x", 255)


class Fields(unittest.TestCase):
    def test_accepts_subset(self):
        obj = {"a": 1}
        self.assertIs(fields(obj, {"a", "b"}, "l"), obj)

    def test_unknown_keys_sorted(self):
        with self.assertRaisesRegex(CliError, "l: unknown fields: y, z"):
            fields({"z": 1, "y": 2}, {"a"}, "l")

    def test_non_object(self):
        for bad in (None, [], "s", 1):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "l: expected a JSON object"):
                    fields(bad, {"a"}, "l")


class Payload(unittest.TestCase):
    def test_hex(self):
        self.assertEqual(payload({"hex": "0aFF"}), b"\x0a\xff")

    def test_empty_hex(self):
        self.assertEqual(payload({"hex": ""}), b"")

    def test_hex_invalid(self):
        for bad in ("zz", "abc", "0x11"):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "event.hex: invalid hexadecimal"):
                    payload({"hex": bad})

    def test_hex_not_string(self):
        for bad in (1, None, [1]):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "event.hex: expected a string"):
                    payload({"hex": bad})

    def test_text_utf8(self):
        self.assertEqual(payload({"text": "ok"}), b"ok")
        self.assertEqual(payload({"text": "п"}), b"\xd0\xbf")
        self.assertEqual(payload({"text": ""}), b"")

    def test_text_not_string(self):
        with self.assertRaisesRegex(CliError, "event.text: expected a string"):
            payload({"text": 5})

    def test_message_vector(self):
        self.assertEqual(payload({"message": TELEMETRY_MSG}), bytes.fromhex(TELEMETRY_MSG["wireHex"]))

    def test_message_fields_only(self):
        self.assertEqual(payload({"message": TELEMETRY_MSG["fields"]}), bytes.fromhex(TELEMETRY_MSG["wireHex"]))

    def test_message_error_is_wrapped(self):
        with self.assertRaisesRegex(CliError, r"event\.message: version: expected 1"):
            payload({"message": {**TELEMETRY_MSG["fields"], "version": 2}})

    def test_message_non_object_wrapped(self):
        with self.assertRaisesRegex(CliError, r"event\.message: message: expected an object"):
            payload({"message": []})

    def test_exactly_one_source(self):
        for event in ({}, {"hex": "00", "text": "a"}, {"hex": "00", "message": {}},
                      {"text": "a", "message": {}}, {"hex": "0", "text": "a", "message": {}}):
            with self.subTest(keys=sorted(event)):
                with self.assertRaisesRegex(CliError, "exactly one of hex, text and message"):
                    payload(event)


class ScenarioTopLevel(unittest.TestCase):
    def test_empty_object_is_valid(self):
        self.assertEqual(validate({}), {})

    def test_empty_events_valid(self):
        self.assertEqual(validate({"events": []}), {"events": []})

    def test_returns_same_object(self):
        doc = scenario([])
        self.assertIs(validate(doc), doc)

    def test_non_object(self):
        for bad in (None, [], "x", 1):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "scenario: expected a JSON object"):
                    validate(bad)

    def test_unknown_top_level_key(self):
        with self.assertRaisesRegex(CliError, "scenario: unknown fields: extra"):
            validate({"extra": 1})

    def test_events_not_array(self):
        for bad in ({}, "x", None, 1):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "events: expected an array"):
                    validate({"events": bad})

    def test_devices_unknown_key(self):
        with self.assertRaisesRegex(CliError, "devices: unknown fields: spi"):
            validate({"devices": {"spi": {}}})

    def test_devices_not_object(self):
        with self.assertRaisesRegex(CliError, "devices: expected a JSON object"):
            validate({"devices": []})

    def test_bundled_mock_scenarios_valid(self):
        for name in ("can-frame", "gpio-input", "i2c-register", "uart-telemetry"):
            with self.subTest(mock=name):
                doc = json.loads((ROOT / "emulator/mocks" / f"{name}.json").read_text(encoding="utf-8"))
                self.assertIs(validate(doc), doc)


class ProcessField(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate({"process": ["echo", "hi"]})["process"], ["echo", "hi"])

    def test_invalid(self):
        for bad in ([], "echo", [""], ["a", 1], ["a", None], {}, 5, [["a"]]):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "process: expected a nonempty array"):
                    validate({"process": bad})

    def test_null_means_absent(self):
        self.assertIn("process", validate({"process": None}))


class DeviceCan(unittest.TestCase):
    def test_defaults(self):
        validate(scenario(can={}))

    def test_interface_length_boundary(self):
        validate(scenario(can={"interface": "a" * 15}))
        with self.assertRaisesRegex(CliError, "invalid interface name"):
            validate(scenario(can={"interface": "a" * 16}))

    def test_interface_invalid(self):
        for bad in ("", "bad name", "v/can", "vcan\n", 5, None):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "devices.can.interface"):
                    validate(scenario(can={"interface": bad}))

    def test_interface_allowed_chars(self):
        validate(scenario(can={"interface": "A_b-9.x"}))

    def test_create_not_bool(self):
        for bad in (1, "true", None):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "devices.can.create: expected a boolean"):
                    validate(scenario(can={"create": bad}))

    def test_unknown_key(self):
        with self.assertRaisesRegex(CliError, "devices.can: unknown fields: bitrate"):
            validate(scenario(can={"bitrate": 1}))


class DeviceUart(unittest.TestCase):
    def test_valid_ports(self):
        validate(scenario(uart={"sensor": {}, "a1_b": {}}))

    def test_empty_uart_object(self):
        validate(scenario(uart={}))

    def test_invalid_port_names(self):
        for bad in ("", "1a", "_a", "a-b", "a b", "a.b"):
            with self.subTest(name=bad):
                with self.assertRaisesRegex(CliError, "invalid port name"):
                    validate(scenario(uart={bad: {}}))

    def test_port_options_must_be_empty_object(self):
        with self.assertRaisesRegex(CliError, "devices.uart.sensor: unknown fields: baud"):
            validate(scenario(uart={"sensor": {"baud": 9600}}))

    def test_port_options_not_object(self):
        with self.assertRaisesRegex(CliError, "devices.uart.sensor: expected a JSON object"):
            validate(scenario(uart={"sensor": 1}))

    def test_uart_not_object(self):
        for bad in ([], "x", None):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "devices.uart: expected a JSON object"):
                    validate(scenario(uart=bad))


class DeviceI2c(unittest.TestCase):
    def test_address_required(self):
        with self.assertRaisesRegex(CliError, "devices.i2c.address is required"):
            validate(scenario(i2c={}))

    def test_address_boundaries(self):
        for ok in (0, 0x7F, "0x7f", "0x00"):
            with self.subTest(value=ok):
                validate(scenario(i2c={"address": ok}))
        for bad in (-1, 0x80, "0x80"):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "devices.i2c.address: must be between 0 and 127"):
                    validate(scenario(i2c={"address": bad}))

    def test_address_wrong_type(self):
        for bad in (None, 1.5, True, []):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "devices.i2c.address: expected an integer"):
                    validate(scenario(i2c={"address": bad}))

    def test_device_must_be_string(self):
        with self.assertRaisesRegex(CliError, "devices.i2c.device: expected a path"):
            validate(scenario(i2c={"address": 1, "device": 5}))
        validate(scenario(i2c={"address": 1, "device": "/dev/i2c-1"}))

    def test_create_not_bool(self):
        with self.assertRaisesRegex(CliError, "devices.i2c.create: expected a boolean"):
            validate(scenario(i2c={"address": 1, "create": 1}))

    def test_unknown_key(self):
        with self.assertRaisesRegex(CliError, "devices.i2c: unknown fields: speed"):
            validate(scenario(i2c={"address": 1, "speed": 1}))


class DeviceGpio(unittest.TestCase):
    def test_defaults(self):
        validate(scenario(gpio={}))

    def test_lines_boundaries(self):
        validate(scenario(gpio={"lines": 1}))
        validate(scenario(gpio={"lines": 256}))
        with self.assertRaisesRegex(CliError, "devices.gpio.lines: must be at least 1"):
            validate(scenario(gpio={"lines": 0}))
        with self.assertRaisesRegex(CliError, "devices.gpio.lines: must be between 0 and 256"):
            validate(scenario(gpio={"lines": 257}))
        with self.assertRaisesRegex(CliError, "devices.gpio.lines: must be between 0 and 256"):
            validate(scenario(gpio={"lines": -1}))

    def test_lines_wrong_type(self):
        with self.assertRaisesRegex(CliError, "devices.gpio.lines: expected an integer"):
            validate(scenario(gpio={"lines": 1.5}))

    def test_name_boundaries(self):
        validate(scenario(gpio={"name": "a" * 40}))
        for bad in ("a" * 41, "", "a b", "a.b", "a/b", 5):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "devices.gpio.name: invalid simulator name"):
                    validate(scenario(gpio={"name": bad}))

    def test_create_not_bool(self):
        with self.assertRaisesRegex(CliError, "devices.gpio.create: expected a boolean"):
            validate(scenario(gpio={"create": "yes"}))

    def test_unknown_key(self):
        with self.assertRaisesRegex(CliError, "devices.gpio: unknown fields: pull"):
            validate(scenario(gpio={"pull": 1}))


class Events(unittest.TestCase):
    def test_event_not_object(self):
        for bad in (None, "x", 1, []):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, r"events\[0\]: expected a JSON object"):
                    validate({"events": [bad]})

    def test_missing_action(self):
        with self.assertRaisesRegex(CliError, r"events\[0\]\.action: unsupported action None"):
            validate({"events": [{}]})

    def test_bad_action_names(self):
        for bad in ("can", "can.recv", "CAN.SEND", "", "uart.", "x.y", 5):
            with self.subTest(action=repr(bad)):
                with self.assertRaisesRegex(CliError, r"events\[0\]\.action: unsupported action"):
                    validate(scenario([{"action": bad}], can={}))

    def test_unknown_event_key(self):
        with self.assertRaisesRegex(CliError, r"events\[0\]: unknown fields: bogus"):
            validate(scenario([{"action": "can.send", "id": 1, "hex": "", "bogus": 1}], can={}))

    def test_key_of_other_action_rejected(self):
        with self.assertRaisesRegex(CliError, r"events\[0\]: unknown fields: line"):
            validate(scenario([{"action": "can.send", "id": 1, "hex": "", "line": 1}], can={}))

    def test_error_index_points_to_failing_event(self):
        good = {"action": "i2c.set", "register": 0, "value": 0}
        bad = {"action": "i2c.set", "register": 256, "value": 0}
        with self.assertRaisesRegex(CliError, "event.register"):
            validate(scenario([good, bad], i2c={"address": 1}))
        with self.assertRaisesRegex(CliError, r"events\[1\]\.action"):
            validate(scenario([good, {"action": "nope"}], i2c={"address": 1}))

    def test_device_missing_for_each_kind(self):
        events = {
            "can": {"action": "can.send", "id": 1, "hex": ""},
            "uart": {"action": "uart.send", "port": "p", "hex": ""},
            "i2c": {"action": "i2c.set", "register": 0, "value": 0},
            "gpio": {"action": "gpio.set", "line": 0, "value": 0},
        }
        for kind, event in events.items():
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(CliError, rf"events\[0\]: devices\.{kind} is missing"):
                    validate({"events": [event]})

    def test_after_ms_boundaries(self):
        event = {"action": "i2c.set", "register": 0, "value": 0}
        for ok in (0, 3600000, "0x10"):
            with self.subTest(value=ok):
                validate(scenario([{**event, "after_ms": ok}], i2c={"address": 1}))
        for bad in (-1, 3600001):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "event.after_ms: must be between 0 and 3600000"):
                    validate(scenario([{**event, "after_ms": bad}], i2c={"address": 1}))
        with self.assertRaisesRegex(CliError, "event.after_ms: expected an integer"):
            validate(scenario([{**event, "after_ms": 1.5}], i2c={"address": 1}))


class CanEvents(unittest.TestCase):
    def check(self, **event):
        validate(scenario([{"action": "can.send", **event}], can={}))

    def test_standard_id_boundary(self):
        self.check(id=0x7FF, hex="")
        self.check(id=0, hex="")
        with self.assertRaisesRegex(CliError, "standard CAN ID exceeds 0x7ff"):
            self.check(id=0x800, hex="")

    def test_extended_id_boundary(self):
        self.check(id=0x1FFFFFFF, hex="", extended=True)
        with self.assertRaisesRegex(CliError, "event.id: must be between 0 and 536870911"):
            self.check(id=0x20000000, hex="", extended=True)

    def test_id_as_string_and_negative(self):
        self.check(id="0x123", hex="11")
        with self.assertRaisesRegex(CliError, "event.id: must be between"):
            self.check(id=-1, hex="")

    def test_id_missing(self):
        with self.assertRaisesRegex(CliError, "event.id: expected an integer"):
            self.check(hex="")

    def test_data_length_boundary(self):
        self.check(id=1, hex="00" * 8)
        self.check(id=1, hex="")
        with self.assertRaisesRegex(CliError, "classic CAN frame holds at most 8 bytes"):
            self.check(id=1, hex="00" * 9)

    def test_payload_required(self):
        with self.assertRaisesRegex(CliError, "exactly one of hex, text and message"):
            self.check(id=1)

    def test_text_not_allowed_for_can(self):
        with self.assertRaisesRegex(CliError, r"events\[0\]: unknown fields: text"):
            self.check(id=1, text="a")

    def test_extended_not_bool(self):
        with self.assertRaisesRegex(CliError, "event.extended: expected a boolean"):
            self.check(id=1, hex="", extended=1)

    def test_invalid_hex(self):
        with self.assertRaisesRegex(CliError, "event.hex: invalid"):
            self.check(id=1, hex="xyz")


class UartEvents(unittest.TestCase):
    def check(self, **event):
        validate(scenario([{"action": "uart.send", **event}], uart={"sensor": {}}))

    def test_each_payload_kind(self):
        self.check(port="sensor", hex="00")
        self.check(port="sensor", text="x")
        self.check(port="sensor", message=TELEMETRY_MSG)

    def test_unknown_port(self):
        with self.assertRaisesRegex(CliError, r"events\[0\]\.port: unknown UART port"):
            self.check(port="other", hex="00")

    def test_missing_port(self):
        with self.assertRaisesRegex(CliError, "unknown UART port"):
            self.check(hex="00")

    def test_two_payload_kinds(self):
        with self.assertRaisesRegex(CliError, "exactly one"):
            self.check(port="sensor", hex="00", text="x")

    def test_invalid_message_rejected_at_validation(self):
        with self.assertRaisesRegex(CliError, "event.message: .*messageType"):
            self.check(port="sensor", message={**TELEMETRY_MSG["fields"], "messageType": "X"})

    def test_message_length_not_limited(self):
        self.check(port="sensor", hex="00" * 1000)


class I2cGpioEvents(unittest.TestCase):
    def test_i2c_register_value_boundaries(self):
        for action in ("i2c.set", "i2c.expect"):
            for key in ("register", "value"):
                for ok in (0, 255, "0xff"):
                    with self.subTest(action=action, key=key, value=ok):
                        event = {"action": action, "register": 0, "value": 0, key: ok}
                        validate(scenario([event], i2c={"address": 1}))
                for bad in (-1, 256):
                    with self.subTest(action=action, key=key, value=bad):
                        event = {"action": action, "register": 0, "value": 0, key: bad}
                        with self.assertRaisesRegex(CliError, f"event.{key}: must be between 0 and 255"):
                            validate(scenario([event], i2c={"address": 1}))

    def test_i2c_missing_value(self):
        with self.assertRaisesRegex(CliError, "event.value: expected an integer"):
            validate(scenario([{"action": "i2c.set", "register": 0}], i2c={"address": 1}))

    def test_gpio_value_boundary(self):
        for action in ("gpio.set", "gpio.expect"):
            for ok in (0, 1):
                validate(scenario([{"action": action, "line": 0, "value": ok}], gpio={}))
            with self.subTest(action=action):
                with self.assertRaisesRegex(CliError, "event.value: must be between 0 and 1"):
                    validate(scenario([{"action": action, "line": 0, "value": 2}], gpio={}))

    def test_gpio_line_boundary_default_lines(self):
        validate(scenario([{"action": "gpio.set", "line": 7, "value": 0}], gpio={}))
        with self.assertRaisesRegex(CliError, "event.line: must be between 0 and 7"):
            validate(scenario([{"action": "gpio.set", "line": 8, "value": 0}], gpio={}))

    def test_gpio_line_boundary_custom_lines(self):
        validate(scenario([{"action": "gpio.expect", "line": 0, "value": 0}], gpio={"lines": 1}))
        with self.assertRaisesRegex(CliError, "event.line: must be between 0 and 0"):
            validate(scenario([{"action": "gpio.expect", "line": 1, "value": 0}], gpio={"lines": 1}))
        validate(scenario([{"action": "gpio.set", "line": 255, "value": 1}], gpio={"lines": 256}))

    def test_gpio_negative_line(self):
        with self.assertRaisesRegex(CliError, "event.line"):
            validate(scenario([{"action": "gpio.set", "line": -1, "value": 0}], gpio={}))


class StdoutExpect(unittest.TestCase):
    def doc(self, **event):
        return {"process": ["true"], "events": [{"action": "stdout.expect", **event}]}

    def test_valid(self):
        validate(self.doc(text="ready"))

    def test_requires_process(self):
        with self.assertRaisesRegex(CliError, "stdout.expect requires process"):
            validate({"events": [{"action": "stdout.expect", "text": "x"}]})

    def test_text_required_and_nonempty(self):
        for event in ({}, {"text": ""}, {"text": 5}):
            with self.subTest(event=event):
                with self.assertRaisesRegex(CliError, "event.text: expected a nonempty string"):
                    validate(self.doc(**event))

    def test_timeout_boundaries(self):
        for ok in (0, 1, 3600000):
            with self.subTest(value=ok):
                validate(self.doc(text="x", timeout_ms=ok))
        for bad in (-1, 3600001):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(CliError, "event.timeout_ms: must be between 0 and 3600000"):
                    validate(self.doc(text="x", timeout_ms=bad))

    def test_timeout_wrong_type(self):
        for bad in (True, 1.5, None):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(CliError, "event.timeout_ms: expected an integer"):
                    validate(self.doc(text="x", timeout_ms=bad))

    def test_hex_not_allowed(self):
        with self.assertRaisesRegex(CliError, "unknown fields: hex"):
            validate(self.doc(text="x", hex="00"))


class LoadJson(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_valid_file(self):
        self.assertEqual(cli.load_json(self.write('{"events": []}')), {"events": []})

    def test_missing_file(self):
        with self.assertRaisesRegex(CliError, "no-such-file.json"):
            cli.load_json("/nonexistent/no-such-file.json")

    def test_malformed_json(self):
        path = self.write("{not json")
        with self.assertRaisesRegex(CliError, "Expecting"):
            cli.load_json(path)

    def test_empty_file(self):
        with self.assertRaises(CliError):
            cli.load_json(self.write(""))

    def test_semantic_error_propagates(self):
        with self.assertRaisesRegex(CliError, "unknown fields: x"):
            cli.load_json(self.write('{"x": 1}'))


class MainValidate(unittest.TestCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_validate_ok(self):
        code, out, err = self.run_main(["validate", self.write('{"events": []}')])
        self.assertEqual((code, out.strip(), err), (0, "valid scenario", ""))

    def test_validate_bad_scenario(self):
        code, out, err = self.run_main(["validate", self.write('{"x": 1}')])
        self.assertEqual(code, 1)
        self.assertIn("emulator-cli: ", err)
        self.assertIn("unknown fields: x", err)
        self.assertEqual(out, "")

    def test_validate_missing_file(self):
        code, _, err = self.run_main(["validate", "/nonexistent/x.json"])
        self.assertEqual(code, 1)
        self.assertIn("emulator-cli:", err)

    def test_validate_bundled_mocks(self):
        for name in ("can-frame", "gpio-input", "i2c-register", "uart-telemetry"):
            with self.subTest(mock=name):
                code, out, _ = self.run_main(["validate", str(ROOT / "emulator/mocks" / f"{name}.json")])
                self.assertEqual((code, out.strip()), (0, "valid scenario"))

    def test_can_send_rejects_long_frame_before_touching_socket(self):
        with mock.patch.object(cli, "can_send") as sender:
            code, _, err = self.run_main(["can-send", "vcan0", "0x1", "00" * 9])
        self.assertEqual(code, 1)
        self.assertIn("at most 8 bytes", err)
        sender.assert_not_called()

    def test_can_send_standard_id_limit(self):
        with mock.patch.object(cli, "can_send") as sender:
            code, _, err = self.run_main(["can-send", "vcan0", "0x800", "00"])
            self.assertEqual(code, 1)
            self.assertIn("must be between 0 and 2047", err)
            sender.assert_not_called()
            code, _, _ = self.run_main(["can-send", "vcan0", "0x7ff", "0102"])
        self.assertEqual(code, 0)
        sender.assert_called_once_with("vcan0", 0x7FF, b"\x01\x02", False)

    def test_can_send_extended_limit(self):
        with mock.patch.object(cli, "can_send") as sender:
            code, _, _ = self.run_main(["can-send", "vcan0", "0x1fffffff", "", "--extended"])
            self.assertEqual(code, 0)
            code, _, err = self.run_main(["can-send", "vcan0", "0x20000000", "", "--extended"])
        self.assertEqual(code, 1)
        self.assertIn("536870911", err)
        sender.assert_called_once_with("vcan0", 0x1FFFFFFF, b"", True)

    def test_i2c_set_argument_ranges(self):
        with mock.patch.object(cli, "i2c_set") as setter:
            code, _, err = self.run_main(["i2c-set", "/dev/i2c-9", "0x80", "0", "0"])
            self.assertEqual(code, 1)
            self.assertIn("address", err)
            code, _, _ = self.run_main(["i2c-set", "/dev/i2c-9", "0x7f", "255", "255"])
        self.assertEqual(code, 0)
        setter.assert_called_once_with(Path("/dev/i2c-9"), 0x7F, 255, 255)

    def test_gpio_set_value_range(self):
        code, _, err = self.run_main(["gpio-set", "mes", "0", "2"])
        self.assertEqual(code, 1)
        self.assertIn("value: must be between 0 and 1", err)

    def test_uart_send_writes_bytes_to_file(self):
        path = self.write("")
        code, _, _ = self.run_main(["uart-send", path, "--hex", "0aff"])
        self.assertEqual(code, 0)
        self.assertEqual(Path(path).read_bytes(), b"\x0a\xff")
        code, _, _ = self.run_main(["uart-send", path, "--text", "hi"])
        self.assertEqual(Path(path).read_bytes(), b"hi")

    def test_uart_send_invalid_hex(self):
        code, _, err = self.run_main(["uart-send", self.write(""), "--hex", "zz"])
        self.assertEqual(code, 1)
        self.assertIn("invalid hexadecimal", err)


class ExecuteEvent(unittest.TestCase):
    def test_uart_send_writes_payload_to_port(self):
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        self.addCleanup(os.close, write_fd)
        cli.execute_event({"action": "uart.send", "port": "p", "hex": "0102"}, {"uart": {"p": write_fd}})
        self.assertEqual(os.read(read_fd, 16), b"\x01\x02")

    def test_uart_send_message_is_54_bytes(self):
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, read_fd)
        self.addCleanup(os.close, write_fd)
        cli.execute_event({"action": "uart.send", "port": "p", "message": TELEMETRY_MSG}, {"uart": {"p": write_fd}})
        self.assertEqual(os.read(read_fd, 100), bytes.fromhex(TELEMETRY_MSG["wireHex"]))

    def test_can_send_forwards_arguments(self):
        with mock.patch.object(cli, "can_send") as sender:
            cli.execute_event({"action": "can.send", "id": "0x123", "hex": "1122"}, {"can": "vcan0"})
        sender.assert_called_once_with("vcan0", 0x123, b"\x11\x22", False)

    def test_can_send_extended_flag(self):
        with mock.patch.object(cli, "can_send") as sender:
            cli.execute_event({"action": "can.send", "id": 1, "hex": "", "extended": True}, {"can": "vcan0"})
        sender.assert_called_once_with("vcan0", 1, b"", True)

    def test_i2c_set_forwards_arguments(self):
        with mock.patch.object(cli, "i2c_set") as setter:
            cli.execute_event({"action": "i2c.set", "register": "0x10", "value": "0x42"},
                              {"i2c": (Path("/dev/i2c-1"), 0x50)})
        setter.assert_called_once_with(Path("/dev/i2c-1"), 0x50, 0x10, 0x42)

    def test_i2c_expect_match_and_mismatch(self):
        runtime = {"i2c": (Path("/dev/i2c-1"), 0x50)}
        event = {"action": "i2c.expect", "register": 1, "value": 0x42}
        with mock.patch.object(cli, "i2c_get", return_value=0x42):
            cli.execute_event(event, runtime)
        with mock.patch.object(cli, "i2c_get", return_value=0x41):
            with self.assertRaisesRegex(CliError, "expected 0x42, got 0x41"):
                cli.execute_event(event, runtime)

    def test_gpio_set_and_expect(self):
        with tempfile.TemporaryDirectory() as temp:
            pull, value = Path(temp, "pull"), Path(temp, "value")
            def attribute(root, line, name):
                return {"pull": pull, "value": value}[name]
            with mock.patch.object(cli, "gpio_attribute", side_effect=attribute):
                cli.execute_event({"action": "gpio.set", "line": 0, "value": 1}, {"gpio": Path(temp)})
                self.assertEqual(pull.read_text(), "pull-up")
                cli.execute_event({"action": "gpio.set", "line": 0, "value": 0}, {"gpio": Path(temp)})
                self.assertEqual(pull.read_text(), "pull-down")
                value.write_text("1\n")
                cli.execute_event({"action": "gpio.expect", "line": 0, "value": 1}, {"gpio": Path(temp)})
                with self.assertRaisesRegex(CliError, "GPIO line 0: expected 0, got 1"):
                    cli.execute_event({"action": "gpio.expect", "line": 0, "value": 0}, {"gpio": Path(temp)})

    def test_value_out_of_range_rejected_at_execution(self):
        with self.assertRaisesRegex(CliError, "event.value: must be between 0 and 1"):
            cli.execute_event({"action": "gpio.set", "line": 0, "value": 2}, {"gpio": Path("/x")})

    def test_unknown_action_is_ignored(self):
        self.assertIsNone(cli.execute_event({"action": "nope"}, {}))


class WaitForOutput(unittest.TestCase):
    class Proc:
        def __init__(self, code=None):
            self.code = code

        def poll(self):
            return self.code

    def log(self, text):
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_found_immediately(self):
        cli.wait_for_output(self.log("hello ready\n"), "ready", 1000, self.Proc())

    def test_timeout(self):
        started = time.monotonic()
        with self.assertRaisesRegex(CliError, "did not contain 'x' within 50 ms"):
            cli.wait_for_output(self.log("nothing"), "x", 50, self.Proc())
        self.assertLess(time.monotonic() - started, 2)

    def test_process_exit_stops_waiting(self):
        started = time.monotonic()
        with self.assertRaises(CliError):
            cli.wait_for_output(self.log(""), "x", 5000, self.Proc(code=0))
        self.assertLess(time.monotonic() - started, 1)

    def test_stdout_expect_event_uses_runtime_log(self):
        runtime = {"log": self.log("boot ok"), "process": self.Proc()}
        cli.execute_event({"action": "stdout.expect", "text": "boot ok", "timeout_ms": 100}, runtime)
        with self.assertRaises(CliError):
            cli.execute_event({"action": "stdout.expect", "text": "zzz", "timeout_ms": 30}, runtime)


if __name__ == "__main__":
    unittest.main()
