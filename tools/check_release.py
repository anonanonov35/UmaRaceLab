"""Audit versioned source before packing; never walks ignored research/user folders."""
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_PARTS={'.git','.local','local','.venv','runtime','dist','build','__pycache__','node_modules'}
PRIVATE_SUFFIXES={'.mdb','.db','.sqlite','.sqlite3','.dll','.exe','.dat','.pyc','.pem','.key','.pfx','.p12','.zip'}
TOKEN_PATTERN=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:proj-)?[A-Za-z0-9_-]{35,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def validate_source(name,blob):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(p in PRIVATE_PARTS for p in path.parts):
        raise ValueError('Private/unsafe source path: '+name)
    if path.name.startswith('.env') or path.suffix.lower() in PRIVATE_SUFFIXES:
        raise ValueError('Disallowed source file: '+name)
    if TOKEN_PATTERN.search(blob):raise ValueError('Possible private credential in '+name)
    if re.search(rb'[A-Za-z]:[/\\]Users[/\\][^/\\\s`]+',blob):
        raise ValueError('Personal absolute path in '+name)
    if len(blob)>10_000_000:raise ValueError('Unexpected large source file: '+name)


def source_files(root=ROOT):
    names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
    files=[]
    for name in filter(None,names):
        path=root/name
        if path.is_symlink() or not path.is_file():raise ValueError('Missing/link source: '+name)
        validate_source(name,path.read_bytes())
        files.append(name)
    for required in ('LICENSE','README.md','THIRD_PARTY.md','vendor/honse-sim/source/Cargo.lock'):
        if required not in files:raise ValueError('Missing release source: '+required)
    return sorted(files)


if __name__=='__main__':print(f'Release source audit: {len(source_files())} files; no private folders, game files or account credentials')
