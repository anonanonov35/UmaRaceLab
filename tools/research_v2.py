"""Bounded, read-only research of locally installed course assets and native layout."""
from pathlib import Path
import json
import re
import sqlite3
import struct
import sys
import tempfile
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".local/python-libs"))
import pefile

GAME = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby")
DATA = GAME / "UmamusumePrettyDerby_Data"
OUT = Path(tempfile.gettempdir()) / "uma-race-lab-build25384634"
OUT.mkdir(exist_ok=True)

def pe_report():
    pe = pefile.PE(str(GAME / "GameAssembly.dll"))
    report = {"machine": hex(pe.FILE_HEADER.Machine), "imagebase": hex(pe.OPTIONAL_HEADER.ImageBase),
              "sections": [{"name": s.Name.decode(errors="replace").strip(chr(0)), "raw": s.SizeOfRawData,
                            "rva": hex(s.VirtualAddress), "entropy": round(s.get_entropy(), 3)} for s in pe.sections],
              "imports": [m.dll.decode() for m in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])],
              "exports": [e.name.decode(errors="replace") for e in getattr(pe, "DIRECTORY_ENTRY_EXPORT", type("X", (), {"symbols": []})).symbols if e.name]}
    (OUT / "pe-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PE", json.dumps({k: v for k,v in report.items() if k != "exports"}))
    print("exports", len(report["exports"]), report["exports"][:8])

def db_report():
    con = sqlite3.connect((DATA / "Persistent/master/master.mdb").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    skills = [dict(r) for r in con.execute("SELECT * FROM skill_data")]
    conditions = Counter()
    for s in skills:
        for key in ("precondition_1", "condition_1", "precondition_2", "condition_2"):
            conditions.update(re.findall(r"([a-z_0-9]+)(?:==|!=|>=|<=|>|<)", s[key]))
    effects = Counter(s[f"ability_type_{b}_{i}"] for s in skills for b in (1,2) for i in (1,2,3))
    levels = [dict(r) for r in con.execute("SELECT * FROM skill_level_value")]
    report = {"conditions": dict(conditions), "effects": dict(effects), "levels": levels,
              "status": [dict(r) for r in con.execute("SELECT * FROM race_course_set_status")],
              "value_usages": dict(Counter(s[f"ability_value_usage_{b}_{i}"] for s in skills for b in (1,2) for i in (1,2,3) if s[f"ability_type_{b}_{i}"])),
              "targets": dict(Counter(s[f"target_type_{b}_{i}"] for s in skills for b in (1,2) for i in (1,2,3) if s[f"ability_type_{b}_{i}"]))}
    (OUT / "skill-research-v2.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("skills", json.dumps({k:v for k,v in report.items() if k not in {"levels","status"}}))
    print("levels", levels[:8], "count",len(levels))

def asset_report():
    files = []
    for folder in sorted((DATA / "Persistent/dat").iterdir())[:4]:
        if folder.is_dir():
            files.extend(list(folder.iterdir())[:35])
    types = Counter()
    for file in files:
        if file.is_file():
            with file.open("rb") as f:
                head = f.read(64)
            types[repr(head[:16])] += 1
    print("asset header sample",types.most_common(10))

if __name__ == "__main__":
    pe_report()
    db_report()
    asset_report()
