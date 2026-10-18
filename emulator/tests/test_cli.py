"""Privilege-free checks for the CLI and protocol-vector injection."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli
import shell
from lmash_v1 import ProtocolError, from_json


TELEMETRY = {
    "version": 1, "messageType": "TELEMETRY", "commandType": "NONE",
    "flags": 5, "ttl": 4, "sequence": 471, "timestamp": 1726000000,
    "deviceSerial": 430572065, "userId": 1001, "destinationId": 2055410180,
    "temperatureX100": 3672, "pulseBpm": 84, "pressureSys": 120,
    "pressureDia": 80, "latitudeE7": 557539123, "longitudeE7": 376208110,
    "headingCdeg": 18050, "positionQuality": 3,
}
WIRE = "0100000504d701000080abe0662102aa1900000000e9030000000000000412837a00000000580e54007850335f3b21ee7a6c16824603"
COMMAND_WIRE = "010103000466000000b2abe0662102aa1900000000e9030000000000000412837a000000000000000000000000000000000000000000"


class CliTests(unittest.TestCase):
    def test_bundled_mocks(self):
        mocks = Path(__file__).resolve().parents[1] / "mocks"
        for path in sorted(mocks.glob("*.json")):
            with self.subTest(path=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                if "fields" in document:
                    self.assertEqual(len(from_json(document)), 54)
                else:
                    cli.validate(document)

        protocol_vectors = Path(__file__).resolve().parents[2] / "protocol" / "vectors"
        if protocol_vectors.is_dir():
            for name in ("telemetry-v1.json", "command-return-v1.json"):
                with self.subTest(protocol_vector=name):
                    self.assertEqual(
                        json.loads((mocks / name).read_text(encoding="utf-8")),
                        json.loads((protocol_vectors / name).read_text(encoding="utf-8")),
                    )

    def test_v1_matches_protocol_vector(self):
        vector = {"name": "telemetry-v1", "payloadSize": 54, "wireHex": WIRE, "fields": TELEMETRY}
        self.assertEqual(from_json(vector), bytes.fromhex(WIRE))
        with self.assertRaisesRegex(ProtocolError, "wireHex"):
            from_json({**vector, "wireHex": "00" * 54})
        command = {key: TELEMETRY[key] for key in (
            "version", "flags", "ttl", "sequence", "timestamp", "deviceSerial",
            "userId", "destinationId"
        )}
        command.update(messageType="COMMAND", commandType="RETURN", flags=0, sequence=102,
                       timestamp=1726000050)
        self.assertEqual(from_json(command), bytes.fromhex(COMMAND_WIRE))

    def test_uart_load_delivers_v1_bytes(self):
        emulator = shell.Emulator()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "vector.json"
            path.write_text(json.dumps({"fields": TELEMETRY, "wireHex": WIRE}))
            try:
                emulator.up("uart", "sensor", {})
                device = emulator.resources["uart:sensor"][2]
                with open(device, "rb", buffering=0) as receiver:
                    emulator.load(str(path), "sensor")
                    self.assertEqual(receiver.read(54), bytes.fromhex(WIRE))
            finally:
                emulator.close()

    def test_scenario_accepts_v1_message_and_checks_target(self):
        scenario = {"devices": {"uart": {"sensor": {}}}, "events": [
            {"action": "uart.send", "port": "sensor", "message": TELEMETRY}
        ]}
        cli.validate(scenario)
        self.assertEqual(cli.payload(scenario["events"][0]), bytes.fromhex(WIRE))
        emulator = shell.Emulator()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scenario.json"
            path.write_text(json.dumps(scenario))
            try:
                emulator.up("uart", "sensor", {})
                with open(emulator.resources["uart:sensor"][2], "rb", buffering=0) as receiver:
                    emulator.load(str(path), None)
                    self.assertEqual(receiver.read(54), bytes.fromhex(WIRE))
            finally:
                emulator.close()
        scenario["events"][0]["port"] = "missing"
        with self.assertRaisesRegex(cli.CliError, "unknown UART port"):
            cli.validate(scenario)


if __name__ == "__main__":
    unittest.main()
