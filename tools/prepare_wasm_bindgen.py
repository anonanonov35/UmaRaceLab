"""Fetch the official version matching the vendored Cargo.lock."""
import io
from pathlib import Path
import tarfile
import tomllib
import urllib.request

root=Path(__file__).resolve().parents[1]
lock=tomllib.loads((root/'vendor/honse-sim/source/Cargo.lock').read_text(encoding='utf-8'))
version=next(p['version'] for p in lock['package'] if p['name']=='wasm-bindgen')
url=f'https://github.com/wasm-bindgen/wasm-bindgen/releases/download/{version}/wasm-bindgen-{version}-x86_64-pc-windows-msvc.tar.gz'
with urllib.request.urlopen(url,timeout=60) as response:
    raw=response.read()
target=root/'.local/wasm-bindgen'
target.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
    for entry in archive.getmembers():
        if entry.isfile():
            out=target/Path(entry.name).name
            out.write_bytes(archive.extractfile(entry).read())
print('wasm-bindgen',version)
