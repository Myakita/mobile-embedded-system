# ruff: noqa: SIM117
"""Specification tests for emulator/lmash_v1.py (LMash v1 codec, 54 bytes, little-endian).

Reference: protocol/spec/lmash-v1.md, protocol/vectors/*.json.
Equivalence classes: valid TELEMETRY, valid COMMAND, invalid structure, invalid values.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulator"))

from lmash_v1 import (
    COMMAND_TYPES,
    HEADER,
    MESSAGE_TYPES,
    TELEMETRY,
    ProtocolError,
    encode,
    from_json,
)

VECTORS = ROOT / "protocol" / "vectors"

# name -> (offset, size, signed) from the spec tables
LAYOUT = {
    "version": (0, 1, False), "messageType": (1, 1, False), "commandType": (2, 1, False),
    "flags": (3, 1, False), "ttl": (4, 1, False), "sequence": (5, 4, False),
    "timestamp": (9, 4, False), "deviceSerial": (13, 8, False), "userId": (21, 8, False),
    "destinationId": (29, 8, False), "temperatureX100": (37, 2, True),
    "pulseBpm": (39, 2, False), "pressureSys": (41, 1, False), "pressureDia": (42, 1, False),
    "latitudeE7": (43, 4, True), "longitudeE7": (47, 4, True), "headingCdeg": (51, 2, False),
    "positionQuality": (53, 1, False),
}
FREE_FIELDS = [n for n in LAYOUT if n not in ("version", "messageType", "commandType")]


def telemetry(**over):
    base = {
        "version": 1, "messageType": "TELEMETRY", "commandType": "NONE",
        "flags": 5, "ttl": 4, "sequence": 471, "timestamp": 1726000000,
        "deviceSerial": 430572065, "userId": 1001, "destinationId": 2055410180,
        "temperatureX100": 3672, "pulseBpm": 84, "pressureSys": 120,
        "pressureDia": 80, "latitudeE7": 557539123, "longitudeE7": 376208110,
        "headingCdeg": 18050, "positionQuality": 3,
    }
    base.update(over)
    return base


def command(**over):
    base = {k: v for k, v in telemetry().items() if k in dict(HEADER)}
    base.update(messageType="COMMAND", commandType="RETURN", flags=0, sequence=102)
    base.update(over)
    return base


def decode(wire):
    """Independent reference decoder built from the spec offsets."""
    out = {}
    for name, (off, size, signed) in LAYOUT.items():
        out[name] = int.from_bytes(wire[off:off + size], "little", signed=signed)
    return out


def rng(size, signed):
    bits = size * 8
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)


class WireFormat(unittest.TestCase):
    def test_telemetry_is_54_bytes(self):
        self.assertEqual(len(encode(telemetry())), 54)

    def test_command_is_54_bytes(self):
        self.assertEqual(len(encode(command())), 54)

    def test_layout_constants_cover_54_bytes(self):
        total = sum(size for _, size, _ in LAYOUT.values())
        self.assertEqual(total, 54)
        self.assertEqual(len(HEADER + TELEMETRY), len(LAYOUT))

    def test_every_field_at_spec_offset(self):
        wire = encode(telemetry())
        decoded = decode(wire)
        expected = telemetry()
        for name in FREE_FIELDS:
            with self.subTest(field=name):
                self.assertEqual(decoded[name], expected[name])
        self.assertEqual((decoded["version"], decoded["messageType"], decoded["commandType"]), (1, 0, 0))

    def test_little_endian_byte_order(self):
        wire = encode(telemetry(sequence=0x01020304))
        self.assertEqual(wire[5:9], bytes([4, 3, 2, 1]))

    def test_enum_codes(self):
        self.assertEqual(MESSAGE_TYPES, {"TELEMETRY": 0, "COMMAND": 1})
        self.assertEqual(COMMAND_TYPES, {"NONE": 0, "CHECK_IN": 1, "HOLD": 2, "RETURN": 3})

    def test_command_types_encoded(self):
        for name, code in COMMAND_TYPES.items():
            if name == "NONE":
                continue
            with self.subTest(command=name):
                wire = encode(command(commandType=name))
                self.assertEqual((wire[1], wire[2]), (1, code))

    def test_command_telemetry_area_is_zero(self):
        self.assertEqual(encode(command())[37:], bytes(17))

    def test_command_accepts_explicit_zero_telemetry_fields(self):
        extra = {name: 0 for name, _ in TELEMETRY}
        self.assertEqual(encode(command(**extra)), encode(command()))


class RoundTrip(unittest.TestCase):
    def test_telemetry_round_trip(self):
        fields = telemetry()
        decoded = decode(encode(fields))
        for name in FREE_FIELDS:
            self.assertEqual(decoded[name], fields[name], name)

    def test_command_round_trip(self):
        fields = command()
        decoded = decode(encode(fields))
        for name in ("flags", "ttl", "sequence", "timestamp", "deviceSerial", "userId", "destinationId"):
            self.assertEqual(decoded[name], fields[name], name)

    def test_encode_is_deterministic_and_does_not_mutate_input(self):
        fields = telemetry()
        snapshot = dict(fields)
        self.assertEqual(encode(fields), encode(fields))
        self.assertEqual(fields, snapshot)

    def test_all_minimum_values(self):
        fields = telemetry(**{n: rng(s, sg)[0] for n, (_, s, sg) in LAYOUT.items() if n in FREE_FIELDS})
        decoded = decode(encode(fields))
        for name in FREE_FIELDS:
            self.assertEqual(decoded[name], fields[name], name)

    def test_all_maximum_values(self):
        fields = telemetry(**{n: rng(s, sg)[1] for n, (_, s, sg) in LAYOUT.items() if n in FREE_FIELDS})
        decoded = decode(encode(fields))
        for name in FREE_FIELDS:
            self.assertEqual(decoded[name], fields[name], name)
        self.assertEqual(encode(fields)[3:5], b"\xff\xff")


class FieldBoundaries(unittest.TestCase):
    def test_min_and_max_accepted_per_field(self):
        for name in FREE_FIELDS:
            _, size, signed = LAYOUT[name]
            low, high = rng(size, signed)
            for value in (low, high):
                with self.subTest(field=name, value=value):
                    self.assertEqual(decode(encode(telemetry(**{name: value})))[name], value)

    def test_below_min_and_above_max_rejected_per_field(self):
        for name in FREE_FIELDS:
            _, size, signed = LAYOUT[name]
            low, high = rng(size, signed)
            for value in (low - 1, high + 1):
                with self.subTest(field=name, value=value):
                    with self.assertRaisesRegex(ProtocolError, f"{name}: outside"):
                        encode(telemetry(**{name: value}))

    def test_unsigned_fields_reject_negative_one(self):
        for name in FREE_FIELDS:
            if LAYOUT[name][2]:
                continue
            with self.subTest(field=name):
                with self.assertRaisesRegex(ProtocolError, "outside"):
                    encode(telemetry(**{name: -1}))

    def test_signed_fields_accept_negative_one(self):
        for name in ("temperatureX100", "latitudeE7", "longitudeE7"):
            with self.subTest(field=name):
                self.assertEqual(decode(encode(telemetry(**{name: -1})))[name], -1)

    def test_non_integer_types_rejected_per_field(self):
        for name in FREE_FIELDS:
            for bad in (1.0, "1", None, True, False, [1], b"\x01"):
                with self.subTest(field=name, value=repr(bad)):
                    with self.assertRaisesRegex(ProtocolError, f"{name}: expected an integer"):
                        encode(telemetry(**{name: bad}))

    def test_command_rejects_nonzero_telemetry_bytes(self):
        for name, _ in TELEMETRY:
            with self.subTest(field=name):
                with self.assertRaisesRegex(ProtocolError, f"{name}: COMMAND telemetry bytes must be zero"):
                    encode(command(**{name: 1}))


class HeaderValidation(unittest.TestCase):
    def test_version_other_than_1_rejected(self):
        for bad in (0, 2, 255, 256, -1):
            with self.subTest(version=bad):
                with self.assertRaisesRegex(ProtocolError, "version: expected 1"):
                    encode(telemetry(version=bad))

    def test_version_wrong_type_rejected(self):
        for bad in ("1", 1.5, None, True):
            with self.subTest(version=repr(bad)):
                with self.assertRaises(ProtocolError):
                    encode(telemetry(version=bad))

    def test_version_float_one_rejected_by_integer_check(self):
        with self.assertRaisesRegex(ProtocolError, "version: expected an integer"):
            encode(telemetry(version=1.0))

    def test_message_type_invalid(self):
        for bad in ("telemetry", "Command", "", "OTHER", 0, 1, None):
            with self.subTest(messageType=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "messageType"):
                    encode(telemetry(messageType=bad))

    def test_message_type_missing(self):
        fields = telemetry()
        del fields["messageType"]
        with self.assertRaisesRegex(ProtocolError, "messageType"):
            encode(fields)

    def test_command_type_invalid(self):
        for bad in ("return", "RESET", "", 3, None):
            with self.subTest(commandType=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "commandType: unknown command"):
                    encode(command(commandType=bad))

    def test_telemetry_requires_command_none(self):
        for cmd in ("CHECK_IN", "HOLD", "RETURN"):
            with self.subTest(commandType=cmd):
                with self.assertRaisesRegex(ProtocolError, "TELEMETRY requires commandType NONE"):
                    encode(telemetry(commandType=cmd))

    def test_command_requires_non_none_command_type(self):
        with self.assertRaisesRegex(ProtocolError, "COMMAND requires a commandType"):
            encode(command(commandType="NONE"))


class StructureValidation(unittest.TestCase):
    def test_non_object_rejected(self):
        for bad in (None, [], "text", 54, b"\x00" * 54):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "expected an object"):
                    encode(bad)

    def test_unknown_key_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "unknown keys: extra"):
            encode(telemetry(extra=1))

    def test_unknown_keys_listed_sorted(self):
        with self.assertRaisesRegex(ProtocolError, "unknown keys: a, b"):
            encode(telemetry(b=1, a=2))

    def test_missing_header_field_rejected(self):
        for name, _ in HEADER:
            if name in ("messageType", "commandType"):
                continue
            fields = telemetry()
            del fields[name]
            with self.subTest(field=name):
                with self.assertRaisesRegex(ProtocolError, f"missing keys: {name}"):
                    encode(fields)

    def test_missing_telemetry_field_rejected_for_telemetry(self):
        for name, _ in TELEMETRY:
            fields = telemetry()
            del fields[name]
            with self.subTest(field=name):
                with self.assertRaisesRegex(ProtocolError, f"missing keys: {name}"):
                    encode(fields)

    def test_missing_telemetry_fields_allowed_for_command(self):
        self.assertEqual(len(encode(command())), 54)

    def test_missing_header_field_rejected_for_command(self):
        fields = command()
        del fields["ttl"]
        with self.assertRaisesRegex(ProtocolError, "missing keys: ttl"):
            encode(fields)

    def test_empty_object_rejected(self):
        with self.assertRaises(ProtocolError):
            encode({})


class VectorFiles(unittest.TestCase):
    def vectors(self):
        files = sorted(VECTORS.glob("*.json"))
        self.assertTrue(files, "no protocol vectors found")
        return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in files]

    def test_vectors_encode_byte_for_byte(self):
        for name, doc in self.vectors():
            with self.subTest(vector=name):
                self.assertEqual(encode(doc["fields"]).hex(), doc["wireHex"])

    def test_vector_payload_size_is_54(self):
        for name, doc in self.vectors():
            with self.subTest(vector=name):
                self.assertEqual(doc["payloadSize"], 54)
                self.assertEqual(len(bytes.fromhex(doc["wireHex"])), 54)

    def test_vectors_decode_back_to_fields(self):
        for name, doc in self.vectors():
            decoded = decode(bytes.fromhex(doc["wireHex"]))
            for key in FREE_FIELDS:
                if key in doc["fields"]:
                    with self.subTest(vector=name, field=key):
                        self.assertEqual(decoded[key], doc["fields"][key])

    def test_from_json_accepts_full_vector(self):
        for name, doc in self.vectors():
            with self.subTest(vector=name):
                self.assertEqual(from_json(doc), bytes.fromhex(doc["wireHex"]))

    def test_mocks_match_protocol_vectors(self):
        for name, doc in self.vectors():
            with self.subTest(vector=name):
                mock = json.loads((ROOT / "emulator" / "mocks" / name).read_text(encoding="utf-8"))
                self.assertEqual(mock, doc)

    def test_telemetry_vector_literal_bytes(self):
        wire = encode(telemetry())
        self.assertEqual(
            wire.hex(),
            "0100000504d701000080abe0662102aa1900000000e9030000000000000412837a00000000"
            "580e54007850335f3b21ee7a6c16824603")

    def test_command_vector_literal_bytes(self):
        wire = encode(command(timestamp=1726000050))
        self.assertEqual(
            wire.hex(),
            "010103000466000000b2abe0662102aa1900000000e9030000000000000412837a00000000"
            "0000000000000000000000000000000000")


class FromJson(unittest.TestCase):
    def doc(self, **over):
        wire = encode(telemetry())
        base = {"name": "t", "payloadSize": 54, "wireHex": wire.hex(), "fields": telemetry()}
        base.update(over)
        return base

    def test_plain_fields_object_accepted(self):
        self.assertEqual(from_json(telemetry()), encode(telemetry()))

    def test_fields_only_wrapper_accepted(self):
        self.assertEqual(from_json({"fields": telemetry()}), encode(telemetry()))

    def test_wire_hex_uppercase_accepted(self):
        doc = self.doc()
        doc["wireHex"] = doc["wireHex"].upper()
        self.assertEqual(from_json(doc), encode(telemetry()))

    def test_wire_hex_mismatch_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "wireHex: differs"):
            from_json(self.doc(wireHex="00" * 54))

    def test_wire_hex_wrong_type_rejected(self):
        for bad in (None, 5, [], b"00"):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "wireHex"):
                    from_json(self.doc(wireHex=bad))

    def test_wire_hex_truncated_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "wireHex"):
            from_json(self.doc(wireHex=encode(telemetry()).hex()[:-2]))

    def test_payload_size_mismatch_rejected(self):
        for bad in (0, 53, 55, "54", None):
            with self.subTest(payloadSize=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "payloadSize: expected 54"):
                    from_json(self.doc(payloadSize=bad))

    def test_unknown_wrapper_key_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "message: unknown keys: extra"):
            from_json(self.doc(extra=1))

    def test_non_object_rejected(self):
        for bad in (None, [], "x", 1):
            with self.subTest(value=repr(bad)):
                with self.assertRaisesRegex(ProtocolError, "message: expected an object"):
                    from_json(bad)

    def test_invalid_inner_fields_propagate(self):
        with self.assertRaisesRegex(ProtocolError, "version: expected 1"):
            from_json({"fields": telemetry(version=2)})

    def test_fields_not_object_rejected(self):
        with self.assertRaisesRegex(ProtocolError, "fields: expected an object"):
            from_json({"fields": [1, 2]})

    def test_protocol_error_is_value_error(self):
        self.assertTrue(issubclass(ProtocolError, ValueError))


if __name__ == "__main__":
    unittest.main()
