"""Reproduce the frozen consumer wheel's portable ZIP creator-format policy.

Only the central-directory creator-system byte becomes0 (DOS/FAT attribute
format). That format is independent of the physical build host. Compressed
members, local headers, timestamps, names and all other bytes are preserved.
The original complete SHA-256 remains mandatory; raw builds are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

POLICY = "consumer-wheel-central-creator-system-zero-v1"


def canonical_bytes(raw):
    if len(raw) < 22 or len(raw) > 64 * 1024**2:
        raise ValueError("Expected a bounded ordinary consumer wheel")
    end = raw.rfind(b"PK\x05\x06")
    if end < 0 or end + 22 != len(raw):
        raise ValueError("Expected one ordinary ZIP without a trailing comment")
    fields = struct.unpack_from("<4s4H2LH", raw, end)
    if (
        fields[1:3] != (0, 0)
        or fields[3] != fields[4]
        or not 0 < fields[4] < 0xFFFF
        or fields[7] != 0
    ):
        raise ValueError("Unsupported split, empty, ZIP64 or commented archive")
    size, position = fields[5:7]
    if position <= 0 or size <= 0 or position + size != end:
        raise ValueError("Central directory bounds differ")
    output = bytearray(raw)
    changes = []
    for _ in range(fields[4]):
        if position + 46 > end or raw[position : position + 4] != b"PK\x01\x02":
            raise ValueError("Central directory record differs")
        creator = raw[position + 5]
        if creator not in (0, 3):
            raise ValueError("Unsupported ZIP creator attribute format")
        if creator != 0:
            changes.append(position + 5)
            output[position + 5] = 0
        name, extra, comment = struct.unpack_from("<3H", raw, position + 28)
        position += 46 + name + extra + comment
    if position != end:
        raise ValueError("Central directory size/count differs")
    # Reconstructing this mask proves that no payload/header byte outside the
    # declared creator positions can be changed by the operation.
    return bytes(output), changes, fields[4]


def normalize(wheel, expected_sha256, output, receipt):
    if wheel.is_symlink() or not wheel.is_file() or output.exists() or receipt.exists():
        raise ValueError("Preserve original and earlier build/normalization files")
    raw = wheel.read_bytes()
    canonical, changes, members = canonical_bytes(raw)
    digest = hashlib.sha256(canonical).hexdigest()
    if digest != expected_sha256:
        raise ValueError(
            "Canonical build does not match the original complete wheel hash"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(canonical)
    if output.read_bytes() != canonical or wheel.read_bytes() != raw:
        raise ValueError("Raw build or canonical readback changed")
    result = {
        "schema": "equiframe.consumer-wheel-rebuild-normalization.v1",
        "policy": POLICY,
        "creator_system": 0,
        "creator_system_is_build_host_claim": False,
        "raw_wheel_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_wheel_sha256": digest,
        "expected_wheel_sha256": expected_sha256,
        "size_bytes": len(raw),
        "members": members,
        "changed_central_directory_positions": changes,
        "changed_bytes": len(changes),
        "raw_wheel_preserved": True,
        "payload_or_other_header_bytes_changed": False,
    }
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("wheel", "output", "receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = normalize(args.wheel, args.expected_sha256, args.output, args.receipt)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
