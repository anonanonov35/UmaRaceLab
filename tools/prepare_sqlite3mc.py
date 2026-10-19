"""Fetch the official read-only resource-index reader dependency into .local/."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1]
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "UmaRaceLab"}), timeout=45) as response:
        return response.read()
r = json.loads(fetch("https://api.github.com/repos/utelle/SQLite3MultipleCiphers/releases/tags/v2.6.1"))
asset = next(a for a in r["assets"] if a["name"].endswith("-win64.zip") and "icu" not in a["name"])
blob = fetch(asset["browser_download_url"])
target = root / ".local/sqlite3mc"
target.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(blob)) as z:
    for item in z.infolist():
        if item.is_dir():
            continue
        out = (target / item.filename).resolve()
        if not out.is_relative_to(target.resolve()):
            raise ValueError("Unsafe archive entry")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(z.read(item))
(target / "provenance.json").write_text(json.dumps({"tag":r["tag_name"],"url":asset["browser_download_url"],"sha256":hashlib.sha256(blob).hexdigest()}, indent=2), encoding="utf-8")
print(r["tag_name"], [p.name for p in target.iterdir()])
