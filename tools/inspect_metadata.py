"""Extract IL2CPP v31 names statically; this does not decompile native method bodies."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby\UmamusumePrettyDerby_Data\il2cpp_data\Metadata\global-metadata.dat")


def extract(path: Path) -> dict:
    raw = path.read_bytes()
    if struct.unpack_from("<II", raw) != (0xFAB11BAF, 31):
        raise ValueError("Only standard IL2CPP metadata version 31 is supported")

    def table(index: int, size: int) -> tuple[int, int]:
        offset, length = struct.unpack_from("<II", raw, 8 + index * 8)
        if offset + length > len(raw) or length % size:
            raise ValueError(f"Invalid table {index}")
        return offset, length // size

    strings, string_count = table(2, 1)
    types, type_count = table(19, 88)
    methods, method_count = table(5, 36)
    fields, field_count = table(11, 12)

    def string(index: int) -> str:
        if not 0 <= index < string_count:
            raise ValueError("String index out of range")
        start = strings + index
        end = raw.index(0, start, strings + string_count)
        return raw[start:end].decode("utf-8")

    found = []
    for i in range(type_count):
        at = types + i * 88
        name, namespace = (string(v) for v in struct.unpack_from("<II", raw, at))
        if not ("race" in name.lower() or "race" in namespace.lower() or name.startswith("MasterSkill")):
            continue
        field_start, method_start = struct.unpack_from("<ii", raw, at + 32)
        nmethods, _, nfields = struct.unpack_from("<HHH", raw, at + 64)
        if nmethods and not (0 <= method_start <= method_count - nmethods):
            raise ValueError("Method range out of bounds")
        if nfields and not (0 <= field_start <= field_count - nfields):
            raise ValueError("Field range out of bounds")
        found.append({"index": i, "name": name, "namespace": namespace,
                      "methods": [string(struct.unpack_from("<I", raw, methods + (method_start + j) * 36)[0]) for j in range(nmethods)],
                      "fields": [string(struct.unpack_from("<I", raw, fields + (field_start + j) * 12)[0]) for j in range(nfields)]})
    return {"version": 31, "total_types": type_count, "total_methods": method_count,
            "total_fields": field_count, "race_types": found, "native_bodies_recovered": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "uma-race-lab-build25384634/metadata-race.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Extracted metadata must stay outside the source repository")
    report = extract(args.metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"types": report["total_types"], "methods": report["total_methods"], "race_types": len(report["race_types"]), "output": str(output)}))
    for t in report["race_types"]:
        if any(w in t["name"].lower() for w in ["simulat", "racehorse", "raceparameter", "skillmanager", "racecondition"]):
            print(t["namespace"] + "." + t["name"], len(t["methods"]), "methods")
