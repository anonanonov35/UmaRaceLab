"""Inspect only course geometry and parameters, keeping extracted data outside Git."""
from pathlib import Path
import json
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".local/python-libs"))
from tools.index_assets import read_index, asset_bytes
import UnityPy

OUT = Path(tempfile.gettempdir()) / "uma-race-lab-build25384634"
rows = read_index("SELECT n,h,e FROM a WHERE n='race/courseeventparam/10606/pfb_prm_race10606' OR n LIKE 'race/course/10006/pos/%2400%' OR n='race/racemain/ast_race_paramdefine'")
for index,row in enumerate(rows):
    env = UnityPy.load(asset_bytes(row))
    result = []
    print("RESOURCE",row['n'])
    for obj in env.objects:
        if obj.type.name in {"MonoBehaviour", "AnimationClip", "MonoScript", "Transform"}:
            tree = obj.parse_as_dict()
            print(obj.type.name, obj.path_id, [(k, (len(v) if isinstance(v,(dict,list)) else str(v)[:50])) for k,v in tree.items()][:28])
            result.append({"type": obj.type.name, "id": obj.path_id, "tree": tree})
    (OUT / f"course-research-{index}.json").write_text(json.dumps({"resource":row,"objects":result},ensure_ascii=False,indent=2),encoding="utf-8")
