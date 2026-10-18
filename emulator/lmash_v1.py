"""Encode the 54-byte LMash v1 payload described by protocol/spec/lmash-v1.md."""

from __future__ import annotations

import struct


class ProtocolError(ValueError):
    pass


HEADER = (
    ("version", "B"), ("messageType", "B"), ("commandType", "B"),
    ("flags", "B"), ("ttl", "B"), ("sequence", "I"),
    ("timestamp", "I"), ("deviceSerial", "Q"), ("userId", "Q"),
    ("destinationId", "Q"),
)
TELEMETRY = (
    ("temperatureX100", "h"), ("pulseBpm", "H"), ("pressureSys", "B"),
    ("pressureDia", "B"), ("latitudeE7", "i"), ("longitudeE7", "i"),
    ("headingCdeg", "H"), ("positionQuality", "B"),
)
MESSAGE_TYPES = {"TELEMETRY": 0, "COMMAND": 1}
COMMAND_TYPES = {"NONE": 0, "CHECK_IN": 1, "HOLD": 2, "RETURN": 3}


def _integer(value: object, name: str, fmt: str) -> int:
    if type(value) is not int:
        raise ProtocolError(f"{name}: expected an integer")
    bits = struct.calcsize(fmt) * 8
    low = -(1 << (bits - 1)) if fmt in "hi" else 0
    high = (1 << (bits - 1)) - 1 if fmt in "hi" else (1 << bits) - 1
    if not low <= value <= high:
        raise ProtocolError(f"{name}: outside {bits}-bit range")
    return value


def encode(fields: object) -> bytes:
    if not isinstance(fields, dict):
        raise ProtocolError("fields: expected an object")
    kind = fields.get("messageType")
    if kind not in MESSAGE_TYPES:
        raise ProtocolError("messageType: expected TELEMETRY or COMMAND")
    command = fields.get("commandType")
    if command not in COMMAND_TYPES:
        raise ProtocolError("commandType: unknown command")
    if kind == "TELEMETRY" and command != "NONE":
        raise ProtocolError("TELEMETRY requires commandType NONE")
    if kind == "COMMAND" and command == "NONE":
        raise ProtocolError("COMMAND requires a commandType")
    allowed = {name for name, _ in HEADER + TELEMETRY}
    unknown = set(fields) - allowed
    if unknown:
        raise ProtocolError(f"fields: unknown keys: {', '.join(sorted(unknown))}")
    required = {name for name, _ in HEADER}
    if kind == "TELEMETRY":
        required.update(name for name, _ in TELEMETRY)
    missing = required - set(fields)
    if missing:
        raise ProtocolError(f"fields: missing keys: {', '.join(sorted(missing))}")
    if fields["version"] != 1:
        raise ProtocolError("version: expected 1")
    values = dict(fields)
    values["messageType"] = MESSAGE_TYPES[kind]
    values["commandType"] = COMMAND_TYPES[command]
    if kind == "COMMAND":
        for name, _ in TELEMETRY:
            if fields.get(name, 0) != 0:
                raise ProtocolError(f"{name}: COMMAND telemetry bytes must be zero")
            values[name] = 0
    layout = HEADER + TELEMETRY
    numbers = [_integer(values[name], name, fmt) for name, fmt in layout]
    return struct.pack("<" + "".join(fmt for _, fmt in layout), *numbers)


def from_json(document: object) -> bytes:
    """Accept protocol vector JSON or a plain v1 fields object."""
    if not isinstance(document, dict):
        raise ProtocolError("message: expected an object")
    if "fields" not in document:
        return encode(document)
    unknown = set(document) - {"name", "payloadSize", "wireHex", "fields"}
    if unknown:
        raise ProtocolError(f"message: unknown keys: {', '.join(sorted(unknown))}")
    wire = encode(document["fields"])
    if "payloadSize" in document and document["payloadSize"] != len(wire):
        raise ProtocolError("payloadSize: expected 54")
    if "wireHex" in document:
        if not isinstance(document["wireHex"], str) or document["wireHex"].lower() != wire.hex():
            raise ProtocolError("wireHex: differs from encoded fields")
    return wire
