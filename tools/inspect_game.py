"""Read-only installation fingerprint. No game content is copied into the repository."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct

DEFAULT_GAME = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect(game: Path) -> dict:
    data = game / "UmamusumePrettyDerby_Data"
    metadata = data / "il2cpp_data/Metadata/global-metadata.dat"
    db = data / "Persistent/master/master.mdb"
    raw = metadata.read_bytes()
    magic, version = struct.unpack_from("<II", raw)
    player = (data / "globalgamemanagers").open("rb")
    with player:
        unity = re.search(rb"20\d{2}\.\d+\.\d+[fp]\d+", player.read(1024))
    result = {
        "install": str(game.resolve()), "unity": unity.group().decode() if unity else None,
        "backend": "IL2CPP", "metadata_version": version,
        "metadata_standard_magic": magic == 0xFAB11BAF,
        "files": {str(p.relative_to(game)): {"bytes": p.stat().st_size, "sha256": digest(p)}
                  for p in [metadata, game / "GameAssembly.dll", db]},
    }
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        result["table_count"] = len(tables)
        result["race_tables"] = {}
        for name in tables:
            if name in {"chara_data", "card_data", "skill_data", "skill_set", "text_data"} or name.startswith("race_"):
                # Names originate from sqlite_master; quote them as identifiers.
                quoted = '"' + name.replace('"', '""') + '"'
                result["race_tables"][name] = {
                    "count": con.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0],
                    "columns": [r[1] for r in con.execute(f"PRAGMA table_info({quoted})")],
                }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=Path("local/installation.json"))
    args = parser.parse_args()
    report = inspect(args.game)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Unity {report['unity']}, metadata v{report['metadata_version']}, {report['table_count']} tables")
    print(args.output.resolve())
