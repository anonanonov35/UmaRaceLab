"""Fetch pinned official runtime archives; verify before extracting selected files."""
from pathlib import Path
import hashlib
import io
import json
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEPENDENCIES={
    'node': {'version':'24.18.1',
             'url':'https://nodejs.org/dist/v24.18.1/node-v24.18.1-win-x64.zip',
             'sha256':'ec56b84a7551893ab2324ebdfdc4ab974a63b4781162600b68a1293cc3e53765'},
    'sqlite3mc': {'version':'2.6.1',
                  'url':'https://github.com/utelle/SQLite3MultipleCiphers/releases/download/v2.6.1/sqlite3mc-2.6.1-sqlite-3.54.0-win64.zip',
                  'sha256':'0183b85d2abc9e3418abd92736cb71355b2bc933f6cda6b56f91653e6628cd74'},
}


def download(spec):
    cache=ROOT/'.local/release-downloads'
    cache.mkdir(parents=True,exist_ok=True)
    path=cache/spec['url'].rsplit('/',1)[-1]
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=spec['sha256']:
        request=urllib.request.Request(spec['url'],headers={'User-Agent':'UmaRaceLab-build'})
        with urllib.request.urlopen(request,timeout=90) as response:blob=response.read()
        if hashlib.sha256(blob).hexdigest()!=spec['sha256']:raise ValueError('Runtime archive SHA256 mismatch')
        path.write_bytes(blob)
    return path.read_bytes()


def prepare():
    runtime=ROOT/'runtime'
    runtime.mkdir(exist_ok=True)
    for name,spec in DEPENDENCIES.items():
        with zipfile.ZipFile(io.BytesIO(download(spec))) as archive:
            if name=='node':
                prefix='node-v'+spec['version']+'-win-x64/'
                (runtime/'node.exe').write_bytes(archive.read(prefix+'node.exe'))
                (runtime/'NODE-LICENSE.txt').write_bytes(archive.read(prefix+'LICENSE'))
            else:
                for source,target in [('dll/sqlite3mc_x64.dll','sqlite3mc_x64.dll'),('LICENSE','SQLITE3MC-LICENSE.txt'),('LICENSE.spdx','SQLITE3MC-LICENSE.spdx')]:
                    (runtime/target).write_bytes(archive.read(source))
    manifest={name:{**spec,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.iterdir() if p.is_file() and
                                  (p.name.lower().startswith('node') if name=='node' else 'sqlite3mc' in p.name.lower())}}
              for name,spec in DEPENDENCIES.items()}
    (runtime/'DEPENDENCIES.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Verified Node.js and SQLite3MultipleCiphers in runtime/')


if __name__=='__main__':prepare()
