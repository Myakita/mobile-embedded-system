"""Structural tests of the integration scenarios tests/e2e/*.json (lab 5).

Every scenario must pass emulator/cli.py validate and follow docs/TESTING.md: it starts the edge through
ci/stand-edge.sh and its first event waits for `edge: reading frames from` (not `edge: connected to`, which edge
prints before it opens the tty). The negative tests show that the validator and the first-event rule do reject
broken scenarios.

Docstring format of a test: "UT-CI-XX <input> | <expected> | <class>".
"""

import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

CI_DIR = Path(__file__).resolve().parent
REPO = CI_DIR.parent
E2E_DIR = REPO / "tests" / "e2e"
FIRST_EXPECT = "edge: reading frames from"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


cli = load_module("cli_under_test", REPO / "emulator" / "cli.py")
stand = load_module("stand_for_scenarios", CI_DIR / "stand.py")


def scenario_files():
    return sorted(E2E_DIR.glob("*.json"))


def first_event_problem(scenario):
    """Returns why the scenario violates the docs/TESTING.md start rule, or '' (the rule as documented)."""
    events = scenario.get("events") or []
    if not events:
        return "no events"
    first = events[0]
    if first.get("action") != "stdout.expect":
        return "first event is not stdout.expect"
    if not str(first.get("text", "")).startswith(FIRST_EXPECT):
        return "first expect is not 'edge: reading frames from'"
    if scenario.get("process") != ["bash", "ci/stand-edge.sh"]:
        return "process is not ci/stand-edge.sh"
    return ""


class RealScenarios(unittest.TestCase):
    def test_scenarios_exist(self):
        """UT-CI-156 каталог tests/e2e | найдены ровно файлы E2E-01-telemetry.json и E2E-02-bad-version.json | успешный"""
        self.assertEqual([p.name for p in scenario_files()], ["E2E-01-telemetry.json", "E2E-02-bad-version.json"])

    def test_names_follow_id_pattern(self):
        """UT-CI-157 имена файлов tests/e2e/*.json | каждое соответствует 'E2E-NN-<имя>.json', идентификаторы NN уникальны | успешный"""
        ids = []
        for path in scenario_files():
            match = re.fullmatch(r"(E2E-\d{2})-[a-z0-9-]+\.json", path.name)
            self.assertIsNotNone(match, path.name)
            ids.append(match.group(1))
        self.assertEqual(len(ids), len(set(ids)))

    def test_valid_json_and_passes_cli_validate_in_process(self):
        """UT-CI-158 каждый сценарий через json.load + cli.validate | validate возвращает словарь, исключения нет | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                self.assertIsInstance(cli.validate(json.loads(path.read_text(encoding="utf-8"))), dict)

    def test_passes_cli_validate_command(self):
        """UT-CI-159 'python3 emulator/cli.py validate <сценарий>' для каждого файла | код выхода 0, stdout 'valid scenario' | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                done = subprocess.run([sys.executable, str(REPO / "emulator" / "cli.py"), "validate", str(path)],
                                      capture_output=True, text=True, timeout=60, check=False)
                self.assertEqual((done.returncode, done.stdout.strip()), (0, "valid scenario"), done.stderr)

    def test_first_event_waits_for_reading_frames(self):
        """UT-CI-160 events[0] каждого сценария | action='stdout.expect', text начинается с 'edge: reading frames from' (не 'edge: connected to') | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                first = json.loads(path.read_text(encoding="utf-8"))["events"][0]
                self.assertEqual(first["action"], "stdout.expect")
                self.assertTrue(first["text"].startswith(FIRST_EXPECT), first["text"])
                self.assertNotIn("connected to", first["text"])

    def test_first_expect_timeout_is_long_enough_for_qemu(self):
        """UT-CI-161 events[0].timeout_ms | 180000 (3 мин на загрузку образа в QEMU по docs/TESTING.md) | граничный"""
        for path in scenario_files():
            with self.subTest(path.name):
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["events"][0]["timeout_ms"], 180000)

    def test_process_is_stand_edge_script_and_script_exists(self):
        """UT-CI-162 поле process | ['bash', 'ci/stand-edge.sh'], файл ci/stand-edge.sh существует | успешный"""
        self.assertTrue((REPO / "ci" / "stand-edge.sh").is_file())
        for path in scenario_files():
            with self.subTest(path.name):
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["process"], ["bash", "ci/stand-edge.sh"])

    def test_first_event_rule_holds_for_all(self):
        """UT-CI-163 правило первого события и process для всех сценариев | пустая строка (нарушений нет) | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                self.assertEqual(first_event_problem(json.loads(path.read_text(encoding="utf-8"))), "")

    def test_uart_events_use_a_declared_port(self):
        """UT-CI-164 каждый uart.send | port='sensor', объявленный в devices.uart | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                scenario = json.loads(path.read_text(encoding="utf-8"))
                for event in scenario["events"]:
                    if event["action"] == "uart.send":
                        self.assertIn(event["port"], scenario["devices"]["uart"])

    def test_only_documented_actions_are_used(self):
        """UT-CI-165 actions во всех сценариях | подмножество {'stdout.expect', 'uart.send'} | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                actions = {e["action"] for e in json.loads(path.read_text(encoding="utf-8"))["events"]}
                self.assertLessEqual(actions, {"stdout.expect", "uart.send"})

    def test_e2e_01_expectations(self):
        """UT-CI-166 E2E-01-telemetry.json | 3 события; один uart.send 54 байта version=1 type=0; stand.expected_lines даёт 1 строку, expected_app_lines ['[1001], seq=471']; последний expect 'edge: published 54 bytes' | успешный"""
        scenario = cli.load_json(str(E2E_DIR / "E2E-01-telemetry.json"))
        self.assertEqual(len(scenario["events"]), 3)
        sends = [cli.payload(e) for e in scenario["events"] if e["action"] == "uart.send"]
        self.assertEqual([(len(d), d[0], d[1]) for d in sends], [(54, 1, 0)])
        self.assertEqual(len(stand.expected_lines(scenario, "mesh-a/7F10/21A0")), 1)
        self.assertEqual(stand.expected_app_lines(scenario), ["[1001], seq=471"])
        self.assertEqual(scenario["events"][-1]["text"], "edge: published 54 bytes")

    def test_e2e_02_bad_version_then_valid(self):
        """UT-CI-167 E2E-02-bad-version.json | 2 uart.send по 54 байта: первый version=2, второй version=1; expect 'unsupported LMash version 2'; брокер должен увидеть только 1 кадр (второй) | успешный"""
        scenario = cli.load_json(str(E2E_DIR / "E2E-02-bad-version.json"))
        sends = [cli.payload(e) for e in scenario["events"] if e["action"] == "uart.send"]
        self.assertEqual([(len(d), d[0]) for d in sends], [(54, 2), (54, 1)])
        self.assertIn("edge: dropped frame: unsupported LMash version 2",
                      [e.get("text") for e in scenario["events"]])
        lines = stand.expected_lines(scenario, "mesh-a/7F10/21A0")
        self.assertEqual(lines, [f"mesh-a/7F10/21A0/telemetry/to/000000007A831204/from/0000000019AA0221 {sends[1].hex()}"])

    def test_wirehex_matches_encoded_fields(self):
        """UT-CI-168 message.wireHex и message.fields в каждом сценарии | байты по fields (lmash_v1.from_json) равны bytes.fromhex(wireHex), длина 54 | успешный"""
        for path in scenario_files():
            with self.subTest(path.name):
                for event in json.loads(path.read_text(encoding="utf-8"))["events"]:
                    if "message" in event:
                        message = event["message"]
                        self.assertEqual(len(bytes.fromhex(message["wireHex"])), 54)
                        self.assertEqual(cli.payload(event), bytes.fromhex(message["wireHex"]))


class BrokenScenarios(unittest.TestCase):
    def base(self):
        return copy.deepcopy(json.loads((E2E_DIR / "E2E-01-telemetry.json").read_text(encoding="utf-8")))

    def test_unknown_top_level_key_rejected(self):
        """UT-CI-169 в сценарий добавлен ключ 'expect' | cli.CliError 'scenario: unknown fields: expect' | отрицательный"""
        scenario = self.base()
        scenario["expect"] = []
        with self.assertRaisesRegex(cli.CliError, "scenario: unknown fields: expect"):
            cli.validate(scenario)

    def test_unknown_action_rejected(self):
        """UT-CI-170 events[0].action='broker.expect' | cli.CliError 'unsupported action' | отрицательный"""
        scenario = self.base()
        scenario["events"][0]["action"] = "broker.expect"
        with self.assertRaisesRegex(cli.CliError, "unsupported action"):
            cli.validate(scenario)

    def test_unknown_uart_port_rejected(self):
        """UT-CI-171 uart.send с port='other' | cli.CliError 'unknown UART port' | отрицательный"""
        scenario = self.base()
        scenario["events"][1]["port"] = "other"
        with self.assertRaisesRegex(cli.CliError, "unknown UART port"):
            cli.validate(scenario)

    def test_uart_event_without_device_rejected(self):
        """UT-CI-172 удалён блок devices | cli.CliError 'devices.uart is missing' | отрицательный"""
        scenario = self.base()
        del scenario["devices"]
        with self.assertRaisesRegex(cli.CliError, "devices.uart is missing"):
            cli.validate(scenario)

    def test_stdout_expect_requires_process(self):
        """UT-CI-173 удалено поле process, остался stdout.expect | cli.CliError 'stdout.expect requires process' | отрицательный"""
        scenario = self.base()
        del scenario["process"]
        with self.assertRaisesRegex(cli.CliError, "stdout.expect requires process"):
            cli.validate(scenario)

    def test_empty_expect_text_rejected(self):
        """UT-CI-174 stdout.expect с text='' | cli.CliError 'expected a nonempty string' | граничный"""
        scenario = self.base()
        scenario["events"][0]["text"] = ""
        with self.assertRaisesRegex(cli.CliError, "nonempty string"):
            cli.validate(scenario)

    def test_timeout_upper_bound(self):
        """UT-CI-175 timeout_ms=3600000 и 3600001 | 3600000 принимается, 3600001 даёт CliError 'must be between 0 and 3600000' | граничный"""
        scenario = self.base()
        scenario["events"][0]["timeout_ms"] = 3600000
        cli.validate(scenario)
        scenario["events"][0]["timeout_ms"] = 3600001
        with self.assertRaisesRegex(cli.CliError, "must be between 0 and 3600000"):
            cli.validate(scenario)

    def test_negative_timeout_rejected(self):
        """UT-CI-176 timeout_ms=-1 | cli.CliError 'must be between 0' | граничный"""
        scenario = self.base()
        scenario["events"][0]["timeout_ms"] = -1
        with self.assertRaisesRegex(cli.CliError, "must be between 0"):
            cli.validate(scenario)

    def test_invalid_hex_rejected(self):
        """UT-CI-177 uart.send hex='zz' | cli.CliError 'invalid hexadecimal bytes' | отрицательный"""
        scenario = self.base()
        scenario["events"][1] = {"action": "uart.send", "port": "sensor", "hex": "zz"}
        with self.assertRaisesRegex(cli.CliError, "invalid hexadecimal bytes"):
            cli.validate(scenario)

    def test_payload_needs_exactly_one_source(self):
        """UT-CI-178 uart.send с hex и text одновременно | cli.CliError 'exactly one of hex, text and message' | отрицательный"""
        scenario = self.base()
        scenario["events"][1] = {"action": "uart.send", "port": "sensor", "hex": "00", "text": "x"}
        with self.assertRaisesRegex(cli.CliError, "exactly one of hex, text and message"):
            cli.validate(scenario)

    def test_message_with_bad_version_is_rejected_by_codec(self):
        """UT-CI-179 message.fields.version=2 (вместо hex) | cli.CliError 'version: expected 1' (поэтому E2E-02 задан через hex) | отрицательный"""
        scenario = self.base()
        scenario["events"][1]["message"]["fields"]["version"] = 2
        with self.assertRaisesRegex(cli.CliError, "version: expected 1"):
            cli.validate(scenario)

    def test_load_json_rejects_malformed_file(self):
        """UT-CI-180 файл с текстом '{not json' | cli.CliError | отрицательный"""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
            handle.write("{not json")
            handle.flush()
            with self.assertRaises(cli.CliError):
                cli.load_json(handle.name)

    def test_first_event_rule_rejects_connected_to(self):
        """UT-CI-181 events[0].text='edge: connected to broker' | first_event_problem = \"first expect is not 'edge: reading frames from'\" | отрицательный"""
        scenario = self.base()
        scenario["events"][0]["text"] = "edge: connected to broker"
        self.assertEqual(first_event_problem(scenario), "first expect is not 'edge: reading frames from'")

    def test_first_event_rule_rejects_uart_send_first(self):
        """UT-CI-182 первым событием стоит uart.send | 'first event is not stdout.expect' | отрицательный"""
        scenario = self.base()
        scenario["events"].insert(0, scenario["events"].pop(1))
        self.assertEqual(first_event_problem(scenario), "first event is not stdout.expect")

    def test_first_event_rule_rejects_empty_events(self):
        """UT-CI-183 events=[] | 'no events' | граничный"""
        scenario = self.base()
        scenario["events"] = []
        self.assertEqual(first_event_problem(scenario), "no events")

    def test_first_event_rule_rejects_other_process(self):
        """UT-CI-184 process=['bash', 'other.sh'] | 'process is not ci/stand-edge.sh' | отрицательный"""
        scenario = self.base()
        scenario["process"] = ["bash", "other.sh"]
        self.assertEqual(first_event_problem(scenario), "process is not ci/stand-edge.sh")


if __name__ == "__main__":
    unittest.main()
