"""Fetch pinned public reference sources; never downloads any game binaries or assets."""
import io
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".local/references"
DEST.mkdir(parents=True, exist_ok=True)
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "UmaRaceLab-static-research"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

for repo, sha, folder in [("jalbarrang/torena-sim", "6ebb31f0466242395b316ee1d5933f057dfe8ec7", "torena-sim"), ("alpha123/uma-tools", "c330bbb7acf34c36595254f5dcd1f18497bebf3a", "uma-tools"), ("katboi01/UmaViewer", "07f82e9fa08f23c1cda3a9be3045a09372eae8bb", "UmaViewer")]:
    url = f"https://codeload.github.com/{repo}/zip/{sha}"
    archive = zipfile.ZipFile(io.BytesIO(fetch(url)))
    target = DEST / folder
    target.mkdir(exist_ok=True)
    prefix = archive.namelist()[0]
    # Only source, documentation and schemas. No game data/assets or binary outputs.
    count = 0
    for item in archive.infolist():
        relative = item.filename[len(prefix):]
        if not relative or item.is_dir():
            continue
        if Path(relative).suffix.lower() not in {".rs", ".ts", ".js", ".cs", ".md", ".toml", ".pl", ".pm"} and Path(relative).name not in {"LICENSE", "Cargo.lock"}:
            continue
        out = (target / relative).resolve()
        if not out.is_relative_to(target.resolve()):
            raise ValueError("Unsafe archive path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(archive.read(item))
        count += 1
    (target / "SOURCE.json").write_text(json.dumps({"repo": repo, "sha": sha, "url": url}, indent=2), encoding="utf-8")
    print(repo, sha, count, "source files")

meta = json.loads(fetch("https://registry.npmjs.org/honse-sim/0.13.0"))
print("npm package", meta["version"], meta["dist"]["tarball"])
(DEST / "honse-sim-package.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
blob = fetch(meta["dist"]["tarball"])
target = ROOT / ".local/honse-sim"
target.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
    for item in archive.getmembers():
        if not item.isfile():
            continue
        relative = Path(item.name).relative_to("package")
        out = (target / relative).resolve()
        if not out.is_relative_to(target.resolve()):
            raise ValueError("Unsafe package path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(archive.extractfile(item).read())
print("package installed locally", target)
