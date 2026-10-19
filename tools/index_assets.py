"""Read resource-name index and bounded course assets from the user's installation."""
from __future__ import annotations
import ctypes as C
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab.paths import index_library
OUT = Path(tempfile.gettempdir()) / "uma-race-lab-build25384634"
GAME = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby")
PERSISTENT = GAME / "UmamusumePrettyDerby_Data/Persistent"


def read_index(query: str) -> list[dict]:
    lib = C.CDLL(str(index_library()))
    pointer = C.c_void_p
    lib.sqlite3_open_v2.argtypes = [C.c_char_p, C.POINTER(pointer), C.c_int, C.c_char_p]
    lib.sqlite3_close.argtypes = [pointer]
    lib.sqlite3_errmsg.argtypes = [pointer]
    lib.sqlite3_errmsg.restype = C.c_char_p
    callback_type = C.CFUNCTYPE(C.c_int, pointer, C.c_int, C.POINTER(C.c_char_p), C.POINTER(C.c_char_p))
    lib.sqlite3_exec.argtypes = [pointer, C.c_char_p, callback_type, pointer, C.POINTER(C.c_char_p)]
    db = pointer()
    # SQLITE_OPEN_READONLY; never rekey, checkpoint, or modify the source.
    rc = lib.sqlite3_open_v2(str(PERSISTENT / "meta").encode("utf-8"), C.byref(db), 1, None)
    if rc:
        raise RuntimeError("Cannot open resource index read-only")
    rows = []
    def callback(_, count, values, names):
        rows.append({names[i].decode(): values[i].decode() if values[i] else None for i in range(count)})
        return 0
    cb = callback_type(callback)
    try:
        # Public file-format interoperability parameter from alpha123/uma-tools.
        # This is not an account key; no authentication/ownership checks are involved.
        # Public Global file-format constants (UmaViewer Config.cs, pinned in THIRD_PARTY).
        # No UmaViewer code/config, personal credentials or external checkout is needed.
        key_bytes = bytes.fromhex('36236b4c2a3921755226327625503f355d77586d4071385e4c3128742959372453')
        base = bytes.fromhex('f170cea4dfcea3e1a5d8c70bd100000000')
        key = bytes(v ^ base[i % 13] for i,v in enumerate(key_bytes)).hex()
        for sql in ['PRAGMA cipher="chacha20"', f'PRAGMA hexkey="{key}"', 'PRAGMA query_only=ON', query]:
            err = C.c_char_p()
            rc = lib.sqlite3_exec(db, sql.encode(), cb, None, C.byref(err))
            if rc:
                raise RuntimeError(lib.sqlite3_errmsg(db).decode())
        return [row for row in rows if "n" in row]
    finally:
        lib.sqlite3_close(db)


def asset_bytes(row: dict) -> bytes:
    h = row["h"]
    path = PERSISTENT / "dat" / h[:2] / h
    b = bytearray(path.read_bytes())
    integer = int(row.get("e") or 0)
    master = bytes.fromhex("532B4631E4A7B9473E7CFB")
    key = bytes(m ^ k for m in master for k in (integer & ((1 << 64) - 1)).to_bytes(8, "little"))
    # The public asset format leaves the first 256 bytes intact.
    if integer:
        for i in range(256, len(b)):
            b[i] ^= key[i % len(key)]
    return bytes(b)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    rows = read_index("SELECT n,h,e FROM a WHERE n LIKE '%course%' OR n LIKE '%race%param%' OR n LIKE '%race%setting%'")
    (OUT / "course-assets-index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("matching asset entries", len(rows))
    for row in rows[:60]:
        print(row["n"], row["h"])
    sys.path.insert(0, str(ROOT / ".local/python-libs"))
    import UnityPy
    candidates = [r for r in rows if any(w in r['n'].lower() for w in ['courseparam', 'course_param', 'raceparam', 'race_param'])]
    print("parameter candidates",len(candidates))
    for row in candidates[:4]:
        raw = asset_bytes(row)
        env = UnityPy.load(raw)
        print("asset",row['n'],len(raw),[(o.type.name,o.path_id) for o in env.objects][:10])
        for obj in env.objects:
            if obj.type.name in {"TextAsset", "MonoBehaviour", "AssetBundle"}:
                try:
                    tree = obj.parse_as_dict()
                    print("tree keys",list(tree)[:25])
                    (OUT / ("asset-"+str(obj.path_id)+".json")).write_text(json.dumps(tree,ensure_ascii=False,indent=2), encoding="utf-8")
                except Exception as e:
                    print(type(e).__name__,str(e)[:150])
