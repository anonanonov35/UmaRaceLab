"""Small local research report; results stay in ignored local/."""
import json
from pathlib import Path
import sqlite3

p = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby\UmamusumePrettyDerby_Data\Persistent\master\master.mdb")
with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as c:
    c.row_factory = sqlite3.Row
    tables = ["race_proper_distance_rate", "race_proper_runningstyle_rate", "race_proper_ground_rate", "race_motivation_rate"]
    report = {t: [dict(r) for r in c.execute("SELECT * FROM " + t)] for t in tables}
    report["text_samples"] = [dict(r) for r in c.execute('SELECT category, "index", text FROM text_data WHERE category IN (6, 47, 48, 75, 119) LIMIT 15')]
    report["skills"] = [dict(r) for r in c.execute("SELECT * FROM skill_data LIMIT 12")]
    report["conditions"] = [r[0] for r in c.execute("SELECT DISTINCT condition_1 FROM skill_data LIMIT 80")]
    report["counts"] = {t: c.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in ["skill_data", "race_course_set", "chara_data", "card_data"]}
out = Path("local/db-research.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k,v in report.items() if k not in {"skills", "text_samples"}}, ensure_ascii=True))
