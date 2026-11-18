"""Unit tests for ci/stand.py (lab 5): the expected-frames computation, the frame classification,
the junit.xml writer and the expected-vs-received comparison.

Docstring format of a test: "UT-CI-XX <input> | <expected> | <class>" (the table in the lab report is built from it).
Stdlib only: no docker, no mosquitto, no network; subprocess, sockets and the broker are mocked.
"""

import contextlib
import importlib.util
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

CI_DIR = Path(__file__).resolve().parent
REPO = CI_DIR.parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stand = load_module("stand_under_test", CI_DIR / "stand.py")

ROOT = "mesh-a/7F10/21A0"
SERIAL, USER, DEST, SEQ = 430572065, 1001, 2055410180, 471
E2E_HEX = ("0100000504d701000080abe0662102aa1900000000e9030000000000000412837a00000000"
           "580e54007850335f3b21ee7a6c16824603")


def frame(version=1, mtype=0, size=54, serial=SERIAL, user=USER, dest=DEST, seq=SEQ):
    """A LMash frame of `size` bytes with the header fields at the protocol offsets."""
    raw = bytearray(54)
    raw[0], raw[1] = version, mtype
    struct.pack_into("<I", raw, 5, seq)
    struct.pack_into("<Q", raw, 13, serial)
    struct.pack_into("<Q", raw, 21, user)
    struct.pack_into("<Q", raw, 29, dest)
    return bytes(raw[:size]) if size <= 54 else bytes(raw) + b"\0" * (size - 54)


def send(data, port="sensor"):
    return {"action": "uart.send", "port": port, "hex": data.hex()}


def line_for(data, root=ROOT, kind="telemetry"):
    dest = struct.unpack_from("<Q", data, 29)[0]
    serial = struct.unpack_from("<Q", data, 13)[0]
    return f"{root}/{kind}/to/{dest:016X}/from/{serial:016X} {data.hex()}"


class ExpectedLines(unittest.TestCase):
    def test_valid_telemetry_frame(self):
        """UT-CI-01 scenario: одно uart.send, 54 байта, version=1, messageType=0 (dest=2055410180, serial=430572065) | одна строка 'mesh-a/7F10/21A0/telemetry/to/000000007A831204/from/0000000019AA0221 <hex 108 символов>' | успешный"""
        data = frame()
        self.assertEqual(
            stand.expected_lines({"events": [send(data)]}, ROOT),
            ["mesh-a/7F10/21A0/telemetry/to/000000007A831204/from/0000000019AA0221 " + data.hex()])

    def test_real_e2e_01_scenario_message_event(self):
        """UT-CI-02 события message (wireHex) из tests/e2e/E2E-01-telemetry.json | ровно одна строка, payload = wireHex, топик .../telemetry/to/000000007A831204/from/0000000019AA0221 | успешный"""
        scenario = stand.cli.load_json(str(REPO / "tests" / "e2e" / "E2E-01-telemetry.json"))
        self.assertEqual(stand.expected_lines(scenario, ROOT),
                         [f"{ROOT}/telemetry/to/000000007A831204/from/0000000019AA0221 {E2E_HEX}"])

    def test_command_frame_topic_uses_command(self):
        """UT-CI-03 кадр 54 байта, messageType=1 (COMMAND) | топик содержит '/command/to/', а не '/telemetry/' | успешный"""
        data = frame(mtype=1)
        self.assertEqual(stand.expected_lines({"events": [send(data)]}, ROOT), [line_for(data, kind="command")])

    def test_frame_length_53_is_not_expected(self):
        """UT-CI-04 кадр длиной 53 байта (version=1, type=0) | [] (кадр не должен дойти до брокера) | граничный"""
        self.assertEqual(stand.expected_lines({"events": [send(frame(size=53))]}, ROOT), [])

    def test_frame_length_54_is_expected(self):
        """UT-CI-05 кадр длиной 54 байта (version=1, type=0) | ровно 1 строка | граничный"""
        self.assertEqual(len(stand.expected_lines({"events": [send(frame(size=54))]}, ROOT)), 1)

    def test_frame_length_55_is_not_expected(self):
        """UT-CI-06 кадр длиной 55 байт (version=1, type=0) | [] | граничный"""
        self.assertEqual(stand.expected_lines({"events": [send(frame(size=55))]}, ROOT), [])

    def test_empty_payload_is_not_expected(self):
        """UT-CI-07 uart.send с hex='' (0 байт) | [] | граничный"""
        self.assertEqual(stand.expected_lines({"events": [send(b"")]}, ROOT), [])

    def test_version_0_is_not_expected(self):
        """UT-CI-08 кадр 54 байта, version=0 | [] | граничный"""
        self.assertEqual(stand.expected_lines({"events": [send(frame(version=0))]}, ROOT), [])

    def test_version_1_is_expected(self):
        """UT-CI-09 кадр 54 байта, version=1 | 1 строка | граничный"""
        self.assertEqual(len(stand.expected_lines({"events": [send(frame(version=1))]}, ROOT)), 1)

    def test_version_2_is_not_expected(self):
        """UT-CI-10 кадр 54 байта, version=2 (как в E2E-02) | [] | граничный"""
        self.assertEqual(stand.expected_lines({"events": [send(frame(version=2))]}, ROOT), [])

    def test_unknown_message_type_is_not_expected(self):
        """UT-CI-11 кадр 54 байта, version=1, messageType=2 и 255 | [] | отрицательный"""
        for kind in (2, 255):
            with self.subTest(messageType=kind):
                self.assertEqual(stand.expected_lines({"events": [send(frame(mtype=kind))]}, ROOT), [])

    def test_order_of_frames_is_preserved(self):
        """UT-CI-12 три валидных кадра подряд: seq-кадры с dest 3, 1, 2 | строки в том же порядке 3, 1, 2 (не отсортированы) | успешный"""
        frames = [frame(dest=3), frame(dest=1, mtype=1), frame(dest=2)]
        got = stand.expected_lines({"events": [send(f) for f in frames]}, ROOT)
        self.assertEqual(got, [line_for(frames[0]), line_for(frames[1], kind="command"), line_for(frames[2])])

    def test_invalid_frames_between_valid_are_skipped(self):
        """UT-CI-13 последовательность: валидный A, version=2, 53 байта, валидный B | ровно 2 строки: A, B | успешный"""
        a, b = frame(dest=10), frame(dest=20)
        events = [send(a), send(frame(version=2)), send(frame(size=53)), send(b)]
        self.assertEqual(stand.expected_lines({"events": events}, ROOT), [line_for(a), line_for(b)])

    def test_non_uart_events_are_ignored(self):
        """UT-CI-14 события stdout.expect и can.send, без uart.send | [] | успешный"""
        events = [{"action": "stdout.expect", "text": "x"}, {"action": "can.send", "id": 1, "hex": "00"}]
        self.assertEqual(stand.expected_lines({"events": events}, ROOT), [])

    def test_scenario_without_events_key(self):
        """UT-CI-15 scenario={} (нет ключа events) | [] | граничный"""
        self.assertEqual(stand.expected_lines({}, ROOT), [])

    def test_topic_root_slashes_are_stripped(self):
        """UT-CI-16 root='/mes/smoke/' | топик начинается с 'mes/smoke/telemetry/to/' | граничный"""
        line = stand.expected_lines({"events": [send(frame())]}, "/mes/smoke/")[0]
        self.assertTrue(line.startswith("mes/smoke/telemetry/to/"), line)

    def test_ids_are_uppercase_zero_padded_16_digits(self):
        """UT-CI-17 dest=0xABC, serial=0 | 'to/0000000000000ABC/from/0000000000000000' | граничный"""
        line = stand.expected_lines({"events": [send(frame(dest=0xABC, serial=0))]}, ROOT)[0]
        self.assertIn("/to/0000000000000ABC/from/0000000000000000 ", line)

    def test_max_ids_use_all_64_bits(self):
        """UT-CI-18 dest=serial=2**64-1 | 'to/FFFFFFFFFFFFFFFF/from/FFFFFFFFFFFFFFFF' | граничный"""
        top = 2 ** 64 - 1
        line = stand.expected_lines({"events": [send(frame(dest=top, serial=top))]}, ROOT)[0]
        self.assertIn("/to/FFFFFFFFFFFFFFFF/from/FFFFFFFFFFFFFFFF ", line)

    def test_payload_hex_is_lowercase_and_exact(self):
        """UT-CI-19 hex в верхнем регистре 'AB..' в сценарии | в строке payload в нижнем регистре, побайтно равен исходным байтам | граничный"""
        data = frame(dest=0xAB, serial=0xCD)
        event = {"action": "uart.send", "port": "sensor", "hex": data.hex().upper()}
        line = stand.expected_lines({"events": [event]}, ROOT)[0]
        self.assertEqual(line.split(" ", 1)[1], data.hex())

    def test_event_without_payload_is_a_cli_error(self):
        """UT-CI-20 uart.send без hex/text/message | исключение cli.CliError | отрицательный"""
        with self.assertRaises(stand.cli.CliError):
            stand.expected_lines({"events": [{"action": "uart.send", "port": "sensor"}]}, ROOT)


class ExpectedAppLines(unittest.TestCase):
    def test_telemetry_frame(self):
        """UT-CI-21 TELEMETRY-кадр userId=1001, sequence=471 | ['[1001], seq=471'] | успешный"""
        self.assertEqual(stand.expected_app_lines({"events": [send(frame())]}), ["[1001], seq=471"])

    def test_command_frame_is_not_logged_by_app(self):
        """UT-CI-22 COMMAND-кадр (messageType=1) | [] | отрицательный"""
        self.assertEqual(stand.expected_app_lines({"events": [send(frame(mtype=1))]}), [])

    def test_invalid_frames_are_not_logged_by_app(self):
        """UT-CI-23 кадры 53/55 байт, version=0, version=2, messageType=2 | [] | граничный"""
        events = [send(frame(size=53)), send(frame(size=55)), send(frame(version=0)),
                  send(frame(version=2)), send(frame(mtype=2))]
        self.assertEqual(stand.expected_app_lines({"events": events}), [])

    def test_order_and_values(self):
        """UT-CI-24 два кадра: (user=7, seq=2), (user=2**64-1, seq=2**32-1) | ['[7], seq=2', '[18446744073709551615], seq=4294967295'] | граничный"""
        events = [send(frame(user=7, seq=2)), send(frame(user=2 ** 64 - 1, seq=2 ** 32 - 1))]
        self.assertEqual(stand.expected_app_lines({"events": events}),
                         ["[7], seq=2", "[18446744073709551615], seq=4294967295"])

    def test_real_e2e_02_scenario(self):
        """UT-CI-25 tests/e2e/E2E-02-bad-version.json | ['[1001], seq=471'] (кадр version=2 отброшен) | успешный"""
        scenario = stand.cli.load_json(str(REPO / "tests" / "e2e" / "E2E-02-bad-version.json"))
        self.assertEqual(stand.expected_app_lines(scenario), ["[1001], seq=471"])


class ReadEnv(unittest.TestCase):
    def write(self, text):
        fd, name = tempfile.mkstemp(suffix=".env")
        self.addCleanup(os.unlink, name)
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        return Path(name)

    def test_parses_pairs_skips_comments_and_blanks(self):
        """UT-CI-26 файл: '# c', пустая строка, '  A=1  ', 'B=two words' | {'A': '1', 'B': 'two words'} | успешный"""
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stand.read_env(self.write("# c\n\n  A=1  \nB=two words\n")), {"A": "1", "B": "two words"})

    def test_value_may_contain_equals_sign(self):
        """UT-CI-27 'K=a=b' | {'K': 'a=b'} | граничный"""
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stand.read_env(self.write("K=a=b\n")), {"K": "a=b"})

    def test_environment_overrides_file(self):
        """UT-CI-28 'BROKER_PORT=8883' в файле и BROKER_PORT=9999 в окружении | {'BROKER_PORT': '9999'} | успешный"""
        with mock.patch.dict(os.environ, {"BROKER_PORT": "9999"}):
            self.assertEqual(stand.read_env(self.write("BROKER_PORT=8883\n")), {"BROKER_PORT": "9999"})

    def test_empty_file(self):
        """UT-CI-29 пустой файл | {} | граничный"""
        self.assertEqual(stand.read_env(self.write("")), {})

    def test_line_without_equals_becomes_empty_value(self):
        """UT-CI-30 строка 'JUSTKEY' без '=' | {'JUSTKEY': ''} (как реализовано, без ошибки) | граничный"""
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stand.read_env(self.write("JUSTKEY\n")), {"JUSTKEY": ""})

    def test_missing_file(self):
        """UT-CI-31 несуществующий путь | исключение FileNotFoundError | отрицательный"""
        with self.assertRaises(FileNotFoundError):
            stand.read_env(Path("/nonexistent/stand.env"))

    def test_real_stand_env_has_required_keys(self):
        """UT-CI-32 emulator/stand/stand.env без переопределений | BROKER_PORT='8883', TOPIC_ROOT='mesh-a/7F10/21A0', APP_USER='app' | успешный"""
        with mock.patch.dict(os.environ, {}, clear=True):
            env = stand.read_env(REPO / "emulator" / "stand" / "stand.env")
        self.assertEqual((env["BROKER_PORT"], env["TOPIC_ROOT"], env["APP_USER"]), ("8883", ROOT, "app"))


class FindTool(unittest.TestCase):
    def test_found_on_path(self):
        """UT-CI-33 shutil.which('mosquitto') -> '/usr/bin/mosquitto' | '/usr/bin/mosquitto' | успешный"""
        with mock.patch.object(stand.shutil, "which", return_value="/usr/bin/mosquitto"):
            self.assertEqual(stand.find_tool("mosquitto"), "/usr/bin/mosquitto")

    def test_falls_back_to_sbin(self):
        """UT-CI-34 нет в PATH, есть в sbin | второй вызов which с path из SBIN, возвращает '/usr/sbin/mosquitto' | успешный"""
        answers = [None, "/usr/sbin/mosquitto"]
        with mock.patch.object(stand.shutil, "which", side_effect=answers) as which:
            self.assertEqual(stand.find_tool("mosquitto"), "/usr/sbin/mosquitto")
        self.assertEqual(which.call_args_list[1].kwargs["path"], os.pathsep.join(stand.SBIN))

    def test_missing_everywhere(self):
        """UT-CI-35 нет ни в PATH, ни в sbin | None | отрицательный"""
        with mock.patch.object(stand.shutil, "which", return_value=None):
            self.assertIsNone(stand.find_tool("mosquitto"))


class WaitForAndPort(unittest.TestCase):
    def test_wait_for_true_immediately(self):
        """UT-CI-36 условие сразу True, timeout=1 | возврат None без исключения | успешный"""
        self.assertIsNone(stand.wait_for(lambda: True, 1, "x"))

    def test_wait_for_becomes_true_later(self):
        """UT-CI-37 условие False, False, True; timeout=5 | возврат без исключения, условие вызвано 3 раза | успешный"""
        answers = iter([False, False, True])
        calls = []
        stand.wait_for(lambda: calls.append(1) or next(answers), 5, "x")
        self.assertEqual(len(calls), 3)

    def test_wait_for_times_out(self):
        """UT-CI-38 условие всегда False, timeout=0.1 | StandError 'timed out after 0.1 s waiting for the thing' | отрицательный"""
        with self.assertRaises(stand.StandError) as caught:
            stand.wait_for(lambda: False, 0.1, "the thing")
        self.assertEqual(str(caught.exception), "timed out after 0.1 s waiting for the thing")

    def test_wait_for_zero_timeout_never_checks(self):
        """UT-CI-39 timeout=0 и условие True | StandError (условие не проверяется, дедлайн уже наступил) | граничный"""
        with self.assertRaises(stand.StandError):
            stand.wait_for(lambda: True, 0, "x")

    def test_port_open_when_connect_ex_is_zero(self):
        """UT-CI-40 socket.connect_ex -> 0 | True | успешный"""
        with mock.patch.object(stand.socket, "socket") as sock:
            sock.return_value.__enter__.return_value.connect_ex.return_value = 0
            self.assertTrue(stand.port_open(8883))

    def test_port_closed_when_connect_ex_is_nonzero(self):
        """UT-CI-41 socket.connect_ex -> 111 (refused) | False | отрицательный"""
        with mock.patch.object(stand.socket, "socket") as sock:
            sock.return_value.__enter__.return_value.connect_ex.return_value = 111
            self.assertFalse(stand.port_open(8883))


class BashHelper(unittest.TestCase):
    def test_success(self):
        """UT-CI-42 subprocess.run -> returncode 0 | None, вызван bash -c со строкой, содержащей 'set -euo pipefail' и lib.sh | успешный"""
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(stand.subprocess, "run", return_value=done) as run:
            self.assertIsNone(stand.bash("stand_generate a b"))
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["bash", "-c"])
        self.assertIn("set -euo pipefail", command[2])
        self.assertIn("lib.sh", command[2])
        self.assertTrue(command[2].endswith("stand_generate a b"))

    def test_failure_raises_stand_error_with_stderr(self):
        """UT-CI-43 returncode 1, stderr ' boom ' | StandError 'lib.sh: stand_generate a b: boom' | отрицательный"""
        failed = subprocess.CompletedProcess([], 1, "", " boom \n")
        with mock.patch.object(stand.subprocess, "run", return_value=failed), \
                self.assertRaises(stand.StandError) as caught:
            stand.bash("stand_generate a b")
        self.assertEqual(str(caught.exception), "lib.sh: stand_generate a b: boom")


class RunCli(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def fake_run(self, text="", returncode=0):
        def run(command, **kwargs):
            kwargs["stdout"].write(text)
            return subprocess.CompletedProcess(command, returncode)
        return run

    def test_success_returns_empty_string(self):
        """UT-CI-44 cli.py run завершился с кодом 0 | '' (пустая строка = нет проблемы) | успешный"""
        with mock.patch.object(stand.subprocess, "run", side_effect=self.fake_run("ok\n")):
            self.assertEqual(stand.run_cli(Path("s.json"), self.dir), "")
        self.assertEqual((self.dir / "emu.log").read_text(), "ok\n")

    def test_nonzero_exit_reports_code_and_tail_of_15_lines(self):
        """UT-CI-45 код выхода 3, emu.log из 20 строк 'line0'..'line19' | строка 'cli.py run exited with 3:' и хвост 'line5'..'line19', без 'line4' | граничный"""
        log = "".join(f"line{i}\n" for i in range(20))
        with mock.patch.object(stand.subprocess, "run", side_effect=self.fake_run(log, 3)):
            problem = stand.run_cli(Path("s.json"), self.dir)
        self.assertTrue(problem.startswith("cli.py run exited with 3:\n"), problem)
        self.assertIn("line5", problem.splitlines())
        self.assertIn("line19", problem.splitlines())
        self.assertNotIn("line4", problem.splitlines())

    def test_timeout_message(self):
        """UT-CI-46 STAND_TIMEOUT=5, subprocess.run бросает TimeoutExpired | 'cli.py run did not finish within 5 s' | отрицательный"""
        boom = subprocess.TimeoutExpired("cli", 5)
        with mock.patch.dict(os.environ, {"STAND_TIMEOUT": "5"}), \
                mock.patch.object(stand.subprocess, "run", side_effect=boom) as run:
            self.assertEqual(stand.run_cli(Path("s.json"), self.dir), "cli.py run did not finish within 5 s")
        self.assertEqual(run.call_args.kwargs["timeout"], 5.0)

    def test_child_gets_edge_conf_and_fwcfg_dirs(self):
        """UT-CI-47 directory=<tmp> | в окружении дочернего процесса STAND_EDGE_CONF=<tmp>/edge.conf, QEMU_FWCFG_DIR=<tmp>/fwcfg; команда [python, cli.py, 'run', путь] | успешный"""
        with mock.patch.object(stand.subprocess, "run", side_effect=self.fake_run()) as run:
            stand.run_cli(Path("s.json"), self.dir)
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["STAND_EDGE_CONF"], str(self.dir / "edge.conf"))
        self.assertEqual(env["QEMU_FWCFG_DIR"], str(self.dir / "fwcfg"))
        command = run.call_args.args[0]
        self.assertEqual([command[0], Path(command[1]).name, command[2], command[3]],
                         [sys.executable, "cli.py", "run", "s.json"])


class FakeBroker:
    def __init__(self, lines):
        self.lines = lines

    def received_lines(self):
        return list(self.lines)


class FakeAndroid:
    def __init__(self, stored):
        self.stored = stored

    def stored_lines(self):
        return list(self.stored)


def instant_wait_for(condition, timeout, what):
    if not condition():
        raise stand.StandError("timeout")


class CheckDelivery(unittest.TestCase):
    def check(self, received, expected, android=None, expected_app=()):
        with mock.patch.object(stand, "wait_for", side_effect=instant_wait_for), \
                mock.patch.object(stand.time, "sleep"):
            return stand.check_delivery(FakeBroker(received), android, list(expected), list(expected_app))

    def test_identical_passes(self):
        """UT-CI-48 expected=['t1 aa','t2 bb'], received=['t1 aa','t2 bb'] | '' | успешный"""
        self.assertEqual(self.check(["t1 aa", "t2 bb"], ["t1 aa", "t2 bb"]), "")

    def test_nothing_arrived_is_failure(self):
        """UT-CI-49 expected=['t1 aa'], received=[] | непустое сообщение, начинается с 'broker saw different messages', содержит 'received: []' | отрицательный"""
        problem = self.check([], ["t1 aa"])
        self.assertTrue(problem.startswith("broker saw different messages"), problem)
        self.assertIn("received: []", problem)

    def test_extra_message_is_failure(self):
        """UT-CI-50 expected=['t1 aa'], received=['t1 aa','t1 aa'] | сообщение о расхождении | отрицательный"""
        self.assertIn("different messages", self.check(["t1 aa", "t1 aa"], ["t1 aa"]))

    def test_expected_nothing_and_nothing_arrived_passes(self):
        """UT-CI-51 expected=[] (только невалидные кадры), received=[] | '' | граничный"""
        self.assertEqual(self.check([], []), "")

    def test_expected_nothing_but_something_arrived_fails(self):
        """UT-CI-52 expected=[], received=['t1 aa'] (невалидный кадр дошёл) | сообщение о расхождении | отрицательный"""
        self.assertIn("different messages", self.check(["t1 aa"], []))

    def test_wrong_order_fails(self):
        """UT-CI-53 expected=['t1 aa','t2 bb'], received=['t2 bb','t1 aa'] | сообщение о расхождении | отрицательный"""
        self.assertIn("different messages", self.check(["t2 bb", "t1 aa"], ["t1 aa", "t2 bb"]))

    def test_single_byte_difference_fails(self):
        """UT-CI-54 payload отличается одним байтом: 'aa..00' против 'aa..01' | сообщение о расхождении | граничный"""
        self.assertIn("different messages", self.check(["t " + "aa" * 53 + "01"], ["t " + "aa" * 53 + "00"]))

    def test_wrong_topic_fails(self):
        """UT-CI-55 тот же payload, другой топик | сообщение о расхождении | отрицательный"""
        self.assertIn("different messages", self.check(["other aa"], ["t1 aa"]))

    def test_lists_both_sides_in_message(self):
        """UT-CI-56 expected=['e1'], received=['r1'] | сообщение содержит \"expected: ['e1']\" и \"received: ['r1']\" | успешный"""
        problem = self.check(["r1"], ["e1"])
        self.assertIn("expected: ['e1']", problem)
        self.assertIn("received: ['r1']", problem)

    def test_app_check_skipped_without_android(self):
        """UT-CI-57 брокер совпал, android=None, expected_app=['[1], seq=1'] | '' (проверка приложения не выполняется) | успешный"""
        self.assertEqual(self.check(["t aa"], ["t aa"], None, ["[1], seq=1"]), "")

    def test_app_stored_expected_lines_passes(self):
        """UT-CI-58 брокер совпал, приложение сохранило ['[1], seq=1'] | '' | успешный"""
        self.assertEqual(self.check(["t aa"], ["t aa"], FakeAndroid(["[1], seq=1"]), ["[1], seq=1"]), "")

    def test_app_stored_nothing_fails(self):
        """UT-CI-59 брокер совпал, ожидается ['[1], seq=1'], приложение сохранило [] | сообщение 'the app stored different frames' | отрицательный"""
        problem = self.check(["t aa"], ["t aa"], FakeAndroid([]), ["[1], seq=1"])
        self.assertTrue(problem.startswith("the app stored different frames"), problem)

    def test_broker_failure_has_priority_over_app_check(self):
        """UT-CI-60 брокер не совпал и приложение не совпало | сообщение про брокера ('broker saw different messages') | граничный"""
        problem = self.check([], ["t aa"], FakeAndroid([]), ["[1], seq=1"])
        self.assertTrue(problem.startswith("broker saw different messages"), problem)


class RunScenario(unittest.TestCase):
    def setUp(self):
        self.SCENARIO = {"devices": {"uart": {"sensor": {}}}, "events": [send(frame()), send(frame(version=2))]}
        self.ENV = {"TOPIC_ROOT": ROOT, "BROKER_PORT": "8883"}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "out"
        self.path = Path(tmp.name) / "s1.json"
        import json
        self.path.write_text(json.dumps(self.SCENARIO))

    def run_it(self, cli_result="", delivery="", apk=None):
        broker = mock.MagicMock()
        broker.return_value.__enter__.return_value = "broker"
        with mock.patch.object(stand, "Broker", broker), \
                mock.patch.object(stand, "run_cli", return_value=cli_result) as run_cli, \
                mock.patch.object(stand, "check_delivery", return_value=delivery) as delivery_mock, \
                mock.patch.object(stand, "Android") as android:
            return stand.run_scenario(self.path, self.out, self.ENV, apk), run_cli, delivery_mock, android

    def test_success_writes_expected_txt(self):
        """UT-CI-61 сценарий из 2 кадров (валидный, version=2), run_cli и check_delivery успешны | '' и expected.txt с одной строкой + '\\n' | успешный"""
        result, _, delivery, _ = self.run_it()
        self.assertEqual(result, "")
        self.assertEqual((self.out / "s1" / "expected.txt").read_text(), line_for(frame()) + "\n")
        self.assertEqual(delivery.call_args.args[2], [line_for(frame())])

    def test_cli_failure_skips_delivery_check(self):
        """UT-CI-62 run_cli вернул 'boom' | результат 'boom', check_delivery не вызывался | отрицательный"""
        result, _, delivery, _ = self.run_it(cli_result="boom")
        self.assertEqual(result, "boom")
        delivery.assert_not_called()

    def test_delivery_failure_is_returned(self):
        """UT-CI-63 run_cli успешен, check_delivery вернул 'mismatch' | 'mismatch' | отрицательный"""
        self.assertEqual(self.run_it(delivery="mismatch")[0], "mismatch")

    def test_stale_directory_is_replaced(self):
        """UT-CI-64 каталог out/s1 уже содержит old.txt | после запуска old.txt нет | граничный"""
        (self.out / "s1").mkdir(parents=True)
        (self.out / "s1" / "old.txt").write_text("stale")
        self.run_it()
        self.assertFalse((self.out / "s1" / "old.txt").exists())

    def test_android_stopped_even_when_cli_fails(self):
        """UT-CI-65 передан apk, run_cli вернул 'boom' | Android.start вызван, Android.stop вызван (finally), результат 'boom' | граничный"""
        result, _, _, android = self.run_it(cli_result="boom", apk=Path("a.apk"))
        self.assertEqual(result, "boom")
        android.return_value.start.assert_called_once()
        android.return_value.stop.assert_called_once()

    def test_no_android_without_apk(self):
        """UT-CI-66 apk=None | класс Android не создаётся | успешный"""
        self.assertEqual(self.run_it()[3].call_count, 0)

    def test_invalid_scenario_file_raises_cli_error(self):
        """UT-CI-67 файл сценария с неизвестным ключом верхнего уровня | исключение cli.CliError | отрицательный"""
        self.path.write_text('{"bogus": 1}')
        with self.assertRaises(stand.cli.CliError):
            stand.run_scenario(self.path, self.out, self.ENV)


class WriteJunit(unittest.TestCase):
    def render(self, results):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            stand.write_junit(results, path)
            raw = path.read_bytes()
            return raw, ET.fromstring(raw)

    def test_all_pass(self):
        """UT-CI-68 два результата без проблем | testsuite name='stand' tests='2' failures='0', нет элементов failure; time='1.50' | успешный"""
        _, suite = self.render([("E2E-01", 1.5, ""), ("E2E-02", 0.0, "")])
        self.assertEqual((suite.tag, suite.get("name"), suite.get("tests"), suite.get("failures")),
                         ("testsuite", "stand", "2", "0"))
        self.assertEqual(suite.findall(".//failure"), [])
        first = suite.findall("testcase")[0]
        self.assertEqual((first.get("classname"), first.get("name"), first.get("time")), ("e2e", "E2E-01", "1.50"))

    def test_failure_count(self):
        """UT-CI-69 три результата, два с проблемой | tests='3' failures='2', ровно 2 элемента failure | успешный"""
        _, suite = self.render([("a", 1, ""), ("b", 1, "bad"), ("c", 1, "worse")])
        self.assertEqual((suite.get("tests"), suite.get("failures")), ("3", "2"))
        self.assertEqual(len(suite.findall(".//failure")), 2)

    def test_failure_message_is_first_line_and_text_is_whole(self):
        """UT-CI-70 проблема 'first line\\nsecond line' | failure message='first line', text='first line\\nsecond line' | успешный"""
        _, suite = self.render([("a", 1, "first line\nsecond line")])
        failure = suite.find(".//failure")
        self.assertEqual(failure.get("message"), "first line")
        self.assertEqual(failure.text, "first line\nsecond line")

    def test_failure_is_inside_the_right_testcase(self):
        """UT-CI-71 результаты ok, bad | failure только внутри testcase name='bad' | успешный"""
        _, suite = self.render([("ok", 1, ""), ("bad", 1, "x")])
        cases = {case.get("name"): case for case in suite.findall("testcase")}
        self.assertIsNone(cases["ok"].find("failure"))
        self.assertIsNotNone(cases["bad"].find("failure"))

    def test_empty_results(self):
        """UT-CI-72 results=[] | well-formed XML, tests='0' failures='0', нет testcase | граничный"""
        _, suite = self.render([])
        self.assertEqual((suite.get("tests"), suite.get("failures"), len(suite)), ("0", "0", 0))

    def test_special_characters_are_escaped(self):
        """UT-CI-73 проблема 'a < b & \"c\" > d' и имя 'x<&>' | XML разбирается, значения восстанавливаются без искажений | граничный"""
        problem = 'a < b & "c" > d'
        _, suite = self.render([("x<&>", 1, problem)])
        self.assertEqual(suite.find("testcase").get("name"), "x<&>")
        self.assertEqual(suite.find(".//failure").text, problem)

    def test_unicode_text_and_utf8_declaration(self):
        """UT-CI-74 проблема на русском 'не пришло ничего' | файл в UTF-8, начинается с XML-декларации encoding='utf-8', текст восстанавливается | успешный"""
        raw, suite = self.render([("a", 1, "не пришло ничего")])
        self.assertTrue(raw.startswith(b"<?xml version='1.0' encoding='utf-8'?>"))
        self.assertEqual(suite.find(".//failure").text, "не пришло ничего")

    def test_time_is_rounded_to_two_digits(self):
        """UT-CI-75 seconds=0.004 и 12.3456 | time='0.00' и '12.35' | граничный"""
        _, suite = self.render([("a", 0.004, ""), ("b", 12.3456, "")])
        self.assertEqual([c.get("time") for c in suite.findall("testcase")], ["0.00", "12.35"])

    def test_blank_line_problem_still_counts_as_failure(self):
        """UT-CI-76 проблема '\\n' (непустая строка из одного перевода строки) | failures='1', message='' | граничный"""
        _, suite = self.render([("a", 1, "\n")])
        self.assertEqual(suite.get("failures"), "1")
        self.assertEqual(suite.find(".//failure").get("message"), "")


class BrokerHelpers(unittest.TestCase):
    def setUp(self):
        self.ENV = {"BROKER_PORT": "8883", "TOPIC_ROOT": ROOT}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_received_lines_skips_blank_lines(self):
        """UT-CI-77 received.txt = 'a 01\\n\\nb 02\\n' | ['a 01', 'b 02'] | успешный"""
        (self.dir / "received.txt").write_text("a 01\n\nb 02\n")
        self.assertEqual(stand.Broker(self.dir, self.ENV).received_lines(), ["a 01", "b 02"])

    def test_received_lines_empty_file_means_nothing_arrived(self):
        """UT-CI-78 received.txt пуст | [] | граничный"""
        (self.dir / "received.txt").write_text("")
        self.assertEqual(stand.Broker(self.dir, self.ENV).received_lines(), [])

    def test_start_refuses_a_busy_port(self):
        """UT-CI-79 порт 8883 уже открыт (port_open=True) | StandError 'port 8883 is already in use; a broker is already running here' | отрицательный"""
        with mock.patch.object(stand, "port_open", return_value=True), \
                self.assertRaises(stand.StandError) as caught:
            stand.Broker(self.dir, self.ENV).start()
        self.assertEqual(str(caught.exception), "port 8883 is already in use; a broker is already running here")

    def test_enter_cleans_up_when_start_fails(self):
        """UT-CI-80 start() добавил процесс и бросил StandError | исключение пробрасывается, процесс terminate() вызван | граничный"""
        broker = stand.Broker(self.dir, self.ENV)
        process = mock.MagicMock()

        def failing_start():
            broker.processes.append(process)
            raise stand.StandError("nope")

        with mock.patch.object(broker, "start", side_effect=failing_start), \
                self.assertRaises(stand.StandError):
            broker.__enter__()
        process.terminate.assert_called_once()

    def test_exit_kills_a_process_that_does_not_stop(self):
        """UT-CI-81 wait(timeout=5) бросает TimeoutExpired | вызваны terminate() и затем kill() | граничный"""
        broker = stand.Broker(self.dir, self.ENV)
        process = mock.MagicMock()
        process.wait.side_effect = subprocess.TimeoutExpired("mosquitto", 5)
        broker.processes.append(process)
        broker.__exit__()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()

    def test_exit_does_not_kill_a_process_that_stops(self):
        """UT-CI-82 wait() возвращается сразу | terminate() вызван, kill() не вызван | успешный"""
        broker = stand.Broker(self.dir, self.ENV)
        process = mock.MagicMock()
        broker.processes.append(process)
        broker.__exit__()
        process.terminate.assert_called_once()
        process.kill.assert_not_called()


class AndroidHelpers(unittest.TestCase):
    def make(self):
        return stand.Android(Path("app.apk"), Path("."))

    def test_stored_lines_extracts_text_after_marker(self):
        """UT-CI-83 logcat с двумя строками 'Телеметрия сохранена от бойца [1001], seq=471' и посторонней строкой | ['[1001], seq=471', '[7], seq=2'] | успешный"""
        text = ("I/MqttTransport: Подписка оформлена на: x\n"
                "I/MqttTransport: Телеметрия сохранена от бойца [1001], seq=471 \n"
                "I/MqttTransport: Телеметрия сохранена от бойца [7], seq=2\n")
        android = self.make()
        with mock.patch.object(android, "logcat", return_value=text):
            self.assertEqual(android.stored_lines(), ["[1001], seq=471", "[7], seq=2"])

    def test_stored_lines_empty_log(self):
        """UT-CI-84 пустой logcat | [] | граничный"""
        android = self.make()
        with mock.patch.object(android, "logcat", return_value=""):
            self.assertEqual(android.stored_lines(), [])

    def test_adb_nonzero_raises(self):
        """UT-CI-85 adb install -> returncode 1, stderr 'no device' | StandError 'adb install x: no device' | отрицательный"""
        failed = subprocess.CompletedProcess([], 1, "", "no device\n")
        with mock.patch.object(stand.subprocess, "run", return_value=failed), \
                self.assertRaises(stand.StandError) as caught:
            self.make().adb("install", "x")
        self.assertEqual(str(caught.exception), "adb install x: no device")

    def test_adb_check_false_returns_stdout(self):
        """UT-CI-86 adb returncode 1, stdout 'partial', check=False | 'partial' без исключения | граничный"""
        failed = subprocess.CompletedProcess([], 1, "partial", "err")
        with mock.patch.object(stand.subprocess, "run", return_value=failed):
            self.assertEqual(self.make().adb("logcat", check=False), "partial")


class MainEntryPoint(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.out = self.tmp / "out"
        self.edge = self.tmp / "edge"
        self.edge.write_text("")

    def run_main(self, argv, scenario_results=None, tools=True, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        environ = {"EDGE_BIN": str(self.edge)}
        environ.update(env or {})

        def fake_run_scenario(path, out, env_, apk=None):
            result = scenario_results[path.stem]
            if isinstance(result, Exception):
                raise result
            (out / path.stem).mkdir(parents=True, exist_ok=True)
            (out / path.stem / "received.txt").write_text("t/x 00\n")
            return result

        with mock.patch.dict(os.environ, environ), \
                mock.patch.object(stand, "find_tool", return_value="/bin/x" if tools else None), \
                mock.patch.object(stand, "run_scenario", side_effect=fake_run_scenario), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = stand.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_all_pass_exit_0_and_junit_written(self):
        """UT-CI-87 два сценария, оба проходят | код 0, на stdout 'PASS a' и 'PASS b', junit.xml: tests=2 failures=0 | успешный"""
        code, out, _ = self.run_main(["run", "a.json", "b.json", "--out", str(self.out)], {"a": "", "b": ""})
        suite = ET.parse(self.out / "junit.xml").getroot()
        self.assertEqual((code, suite.get("tests"), suite.get("failures")), (0, "2", "0"))
        self.assertIn("PASS a", out)
        self.assertIn("PASS b", out)

    def test_one_failure_exit_1(self):
        """UT-CI-88 сценарий a проходит, b падает с 'bad' | код 1, 'FAIL b' и текст 'bad' на stdout, junit failures=1 | отрицательный"""
        code, out, _ = self.run_main(["run", "a.json", "b.json", "--out", str(self.out)], {"a": "", "b": "bad"})
        suite = ET.parse(self.out / "junit.xml").getroot()
        self.assertEqual((code, suite.get("failures")), (1, "1"))
        self.assertIn("FAIL b", out)
        self.assertIn("bad", out)

    def test_stand_error_becomes_failure_not_crash(self):
        """UT-CI-89 run_scenario бросает StandError('no broker') | код 1, в junit failure message='no broker' | отрицательный"""
        code, _, _ = self.run_main(["run", "a.json", "--out", str(self.out)], {"a": stand.StandError("no broker")})
        failure = ET.parse(self.out / "junit.xml").getroot().find(".//failure")
        self.assertEqual((code, failure.get("message")), (1, "no broker"))

    def test_missing_tools_exit_2(self):
        """UT-CI-90 mosquitto/openssl не найдены | код 2, на stderr 'stand: missing on PATH: mosquitto, mosquitto_sub, openssl, bash' | отрицательный"""
        code, _, err = self.run_main(["run", "a.json", "--out", str(self.out)], {}, tools=False)
        self.assertEqual(code, 2)
        self.assertIn("stand: missing on PATH: mosquitto, mosquitto_sub, openssl, bash", err)

    def test_android_requires_adb(self):
        """UT-CI-91 --android app.apk и нет adb | код 2, в сообщении 'adb' | отрицательный"""
        code, _, err = self.run_main(["run", "a.json", "--android", "app.apk", "--out", str(self.out)], {}, tools=False)
        self.assertEqual(code, 2)
        self.assertIn(", adb", err)

    def test_edge_bin_must_exist_in_host_mode(self):
        """UT-CI-92 EDGE по умолчанию (host), EDGE_BIN указывает на несуществующий файл | код 2, 'stand: EDGE_BIN must point at the built edge binary' | отрицательный"""
        code, _, err = self.run_main(["run", "a.json", "--out", str(self.out)], {},
                                     env={"EDGE_BIN": str(self.tmp / "none")})
        self.assertEqual(code, 2)
        self.assertIn("EDGE_BIN must point at the built edge binary", err)

    def test_qemu_mode_does_not_need_edge_bin(self):
        """UT-CI-93 EDGE=qemu, EDGE_BIN не существует, сценарий проходит | код 0 | граничный"""
        code, _, _ = self.run_main(["run", "a.json", "--out", str(self.out)], {"a": ""},
                                   env={"EDGE": "qemu", "EDGE_BIN": str(self.tmp / "none")})
        self.assertEqual(code, 0)

    def test_scenarios_are_required(self):
        """UT-CI-94 командная строка 'run' без сценариев | SystemExit с кодом 2 (argparse) | отрицательный"""
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            stand.main(["run"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
