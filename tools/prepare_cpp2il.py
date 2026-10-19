"""Download official Cpp2IL Windows x64 binary into ignored .local/."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1]
target = root / ".local/Cpp2IL"
target.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request("https://api.github.com/repos/SamboyCoding/Cpp2IL/releases?per_page=5", headers={"User-Agent": "UmaRaceLab-recon"})
with urllib.request.urlopen(request, timeout=30) as response:
    releases = json.load(response)
release = next(r for r in releases if not r["draft"])
print("release", release["tag_name"])
print("assets", [a["name"] for a in release["assets"]])
assets = [a for a in release["assets"] if a["name"].endswith("-Windows.exe")]
if not assets:
    raise RuntimeError("No Windows x64 release binary")
asset = assets[0]
archive = target / asset["name"]
with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as response:
    archive.write_bytes(response.read())
if archive.suffix == ".zip":
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (target / item.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError("Unsafe archive member")
        z.extractall(target)
record = {"release": release["tag_name"], "url": asset["browser_download_url"], "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
(target / "provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
