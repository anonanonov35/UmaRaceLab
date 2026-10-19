"""Download the official static IL2CPP inspector to an ignored local tools directory."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1]
target = root / ".local/Il2CppDumper"
target.mkdir(parents=True, exist_ok=True)
request = urllib.request.Request("https://api.github.com/repos/Perfare/Il2CppDumper/releases/latest", headers={"User-Agent": "UmaRaceLab-recon"})
with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)
assets = [a for a in release["assets"] if "net6" in a["name"].lower() and a["name"].endswith(".zip")]
if not assets:
    raise RuntimeError("No official .NET 6 archive found: " + str([a['name'] for a in release['assets']]))
asset = assets[0]
archive = target / asset["name"]
with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as response:
    archive.write_bytes(response.read())
with zipfile.ZipFile(archive) as z:
    for item in z.infolist():
        dest = (target / item.filename).resolve()
        if not dest.is_relative_to(target.resolve()):
            raise ValueError("Unsafe archive member")
    z.extractall(target)
record = {"release": release["tag_name"], "url": asset["browser_download_url"],
          "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
(target / "provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
