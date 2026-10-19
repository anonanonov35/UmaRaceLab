"""Build the Windows directory bundle and paired source archive. Never publishes."""
from pathlib import Path
import argparse
import hashlib
from importlib import metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab import __version__
from tools.check_release import source_files


def license_files(destination):
    inventory=[]
    for dist in metadata.distributions():
        name=dist.metadata.get('Name','unknown')
        inventory.append({'name':name,'version':dist.version})
        for item in dist.files or []:
            if item.name.lower().startswith(('license','copying','notice','authors')) and '..' not in item.parts:
                source=Path(dist.locate_file(item))
                if source.is_file():
                    target=destination/'python-packages'/name/str(item)
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    base=Path(sys.base_prefix)
    for name in ('LICENSE.txt','LICENSE'):
        if (base/name).is_file():shutil.copyfile(base/name,destination/'PYTHON-LICENSE.txt');break
    import tkinter as tk
    interp=tk.Tcl()
    tcl=Path(interp.eval('info library'))
    for folder in (tcl,tcl.parent/'tk8.6'):
        for name in ('license.terms','license.txt','license'):
            if (folder/name).is_file():shutil.copyfile(folder/name,destination/(folder.name+'-LICENSE.txt'));break
    return sorted(inventory,key=lambda item:item['name'].lower())


def make_source(root=ROOT):
    files=source_files(root)
    output=root/'dist';output.mkdir(exist_ok=True)
    path=output/f'UmaRaceLab-{__version__}-source.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in files:archive.write(root/name,f'UmaRaceLab-{__version__}/'+name)
    return path


def checksums():
    folder=ROOT/'dist'
    archives=sorted(folder.glob(f'UmaRaceLab-{__version__}-*.zip'))
    (folder/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in archives),encoding='utf-8')


def build(skip_compile=False):
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise RuntimeError('Build the Windows x64 package on Windows x64 / Python 3.12 x64')
    files=source_files()
    if not (ROOT/'runtime/DEPENDENCIES.json').is_file():raise RuntimeError('Run python tools/prepare_release_deps.py first')
    if not skip_compile:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',str(ROOT/'build/frozen'),
                        '--workpath',str(ROOT/'build/pyinstaller'),str(ROOT/'packaging/UmaRaceLab.spec')],cwd=ROOT,check=True)
    bundle=ROOT/'build/frozen/UmaRaceLab'
    executable=bundle/'UmaRaceLab.exe'
    if not executable.is_file():raise RuntimeError('Frozen executable was not produced')
    for name in ('README.md','LICENSE','THIRD_PARTY.md'):
        shutil.copyfile(ROOT/name,bundle/name)
    shutil.copyfile(ROOT/'packaging/START_HERE.txt',bundle/'START_HERE.txt')
    licenses=bundle/'licenses';licenses.mkdir(exist_ok=True)
    for source in (ROOT/'packaging/licenses').iterdir():
        if source.is_file():shutil.copyfile(source,licenses/source.name)
    for source in (ROOT/'runtime').iterdir():
        if source.is_file() and 'LICENSE' in source.name:shutil.copyfile(source,licenses/source.name)
    shutil.copyfile(ROOT/'vendor/honse-sim/LICENSE',licenses/'HONSE-SIM-LICENSE.txt')
    packages=license_files(licenses)
    provenance={'version':__version__,'platform':'windows-x64','python':platform.python_version(),
                'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'dependencies':json.loads((ROOT/'runtime/DEPENDENCIES.json').read_text(encoding='utf-8')),
                'python_packages':packages,'source_files':len(files)}
    (bundle/'BUILD-INFO.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    # Use only Windows system PATH; the test must use the bundled Python/Node.
    report=ROOT/'build/frozen-self-test.json'
    env=os.environ.copy()
    for key in ('PYTHONPATH','UMA_LAB_NODE','PYTHONHOME'):env.pop(key,None)
    env['PATH']=str(Path(env.get('SystemRoot','C:/Windows'))/'System32')
    env['UMA_LAB_DATA_DIR']=str(ROOT/'build/self-test-data')
    process=subprocess.run([str(executable),'--self-test','--report',str(report)],cwd=bundle,env=env,timeout=60)
    if process.returncode or not json.loads(report.read_text(encoding='utf-8'))['ok']:
        raise RuntimeError('Frozen health check failed; see build/frozen-self-test.json')
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    archive=output/f'UmaRaceLab-{__version__}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as zipped:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():zipped.write(path,'UmaRaceLab/'+path.relative_to(bundle).as_posix())
    source=make_source();checksums()
    print(json.dumps({'windows':str(archive),'source':str(source),'frozen_self_test':'passed'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-compile',action='store_true',help='Repackage the already tested directory bundle')
    args=parser.parse_args();build(args.skip_compile)
