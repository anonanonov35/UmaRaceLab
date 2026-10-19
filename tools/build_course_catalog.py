"""Extract course events, actual 3D lane samples and current race constants locally.

The cache and all extracted values stay outside the source repository. Reads
only resource-index/course bundles; never opens models, textures or account data.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".local/python-libs"))
from tools import index_assets
from uma_lab.courses import cache_path
from uma_lab.data import DEFAULT_INSTALL, find_database
import UnityPy


def mono_tree(row: dict, field: str) -> dict:
    raw = index_assets.asset_bytes(row)
    for obj in UnityPy.load(raw).objects:
        if obj.type.name == "MonoBehaviour":
            tree = obj.parse_as_dict()
            if field in tree:
                return tree
    raise ValueError(f"Missing {field} in {row['n']}")


def build(database: Path):
    persistent = database.parent.parent
    index_assets.PERSISTENT = persistent
    stat_before = (persistent / "meta").stat()
    rows = index_assets.read_index("SELECT n,h,e FROM a WHERE n LIKE 'race/courseeventparam/%' OR n LIKE 'race/course/%/pos/%' OR n='race/racemain/ast_race_paramdefine'")
    index = {r["n"]: r for r in rows}
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as con:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')
        con.row_factory = sqlite3.Row
        courses = [dict(r) for r in con.execute("SELECT * FROM race_course_set")]
        statuses = {r["course_set_status_id"]: [r["target_status_1"],r["target_status_2"]] for r in con.execute("SELECT * FROM race_course_set_status")}
        database_sha256=hashlib.sha256(con.serialize()).hexdigest()
    parameters = mono_tree(index["race/racemain/ast_race_paramdefine"], "raceBaseSpeedBaseSpeed")
    result, errors = {}, []
    for course in courses:
        cid = course["id"]
        try:
            row = index[f"race/courseeventparam/{cid}/pfb_prm_race{cid}"]
            tree = mono_tree(row, "courseParams")
            geometry = {"distance": course["distance"], "corners": [], "straights": [], "slopes": [],
                        "events": tree["courseParams"], "sources": {"events": row["h"]},
                        "course_set_status": [s for s in statuses.get(course["course_set_status_id"], []) if s],
                        "lane_max": course["float_lane_max"] / 10000,
                        "move_lane_point": None}
            pending = None
            for event in sorted(tree["courseParams"], key=lambda e:e["_distance"]):
                kind, values, start = event["_paramType"], event["_values"], event["_distance"]
                if kind == 0:
                    geometry["corners"].append({"start":start,"length":values[1],"number":values[0]})
                elif kind == 11:
                    geometry["slopes"].append({"start":start,"length":values[1],"slope":values[0]})
                elif kind == 2 and values[0] == 1:
                    pending = (start, values[1])
                elif kind == 2 and values[0] == 2:
                    if pending is None:
                        raise ValueError("Unpaired straight endpoint")
                    geometry["straights"].append({"start":pending[0],"end":start,"frontType":pending[1]})
                    pending = None
                elif kind == 7:
                    geometry["move_lane_point"] = start
            if geometry["move_lane_point"] is None:
                geometry["move_lane_point"] = geometry["corners"][0]["start"] if geometry["corners"] else 0.
            filename = f"race/course/{course['race_track_id']}/pos/an_pos_race{course['race_track_id']}_00_{course['distance']:04d}_{course['ground']-1:02d}_{max(0,course['inout']-1)}_0"
            if filename not in index:
                raise ValueError("Missing exact lane animation " + filename)
            lane_row = index[filename]
            lane = mono_tree(lane_row, "key")
            if lane["Distance"] != course["distance"]:
                raise ValueError("Lane animation distance mismatch")
            key = lane["key"]
            arrays = [key[k] for k in ("valueX","valueZ","valueY")]
            if len({len(a) for a in arrays}) != 1 or len(arrays[0]) < 2:
                raise ValueError("Invalid lane samples")
            geometry["points"] = [list(xyz) for xyz in zip(*arrays)]
            if len(key['rotation'])!=len(geometry['points']):
                raise ValueError('Rotation sample count mismatch')
            geometry['rotations']=[[q[k] for k in ('x','y','z','w')] for q in key['rotation']]
            geometry["sources"]["lane"] = lane_row["h"]
            result[str(cid)] = geometry
        except (KeyError, ValueError, FileNotFoundError) as e:
            result[str(cid)] = {"error":str(e)}
            errors.append((cid,str(e)))
    after = (persistent / "meta").stat()
    if (stat_before.st_size,stat_before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        raise ValueError("Resource index changed while extracting; retry after the game update")
    payload = {"schema":2,"index_signature":[after.st_size,after.st_mtime_ns],"database":str(database),
               'database_sha256':database_sha256,
               "parameters":parameters,"courses":result,"parameter_source":index["race/racemain/ast_race_paramdefine"]["h"]}
    out = cache_path(database)
    out.parent.mkdir(parents=True,exist_ok=True)
    temporary=out.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    temporary.replace(out)
    print(f"Course geometry: {len(result)-len(errors)}/{len(result)}; cache: {out}")
    for cid,error in errors:
        print(cid,error)
    return payload


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game",type=Path,default=DEFAULT_INSTALL)
    args=p.parse_args()
    build(find_database(args.game))
