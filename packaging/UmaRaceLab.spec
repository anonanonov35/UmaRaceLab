# Build on Windows x64 with: python -m PyInstaller packaging/UmaRaceLab.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root=Path(SPECPATH).parent
unity_data,unity_bins,unity_imports=collect_all('UnityPy')
datas=unity_data+[
    (str(root/'uma_lab/locales'),'uma_lab/locales'),
    (str(root/'uma_lab/bridge.mjs'),'uma_lab'),
    (str(root/'vendor/honse-sim/uma_sim_wasm.js'),'vendor/honse-sim'),
    (str(root/'vendor/honse-sim/uma_sim_wasm_bg.wasm'),'vendor/honse-sim'),
    (str(root/'vendor/honse-sim/package.json'),'vendor/honse-sim'),
    (str(root/'runtime/DEPENDENCIES.json'),'runtime'),
]
binaries=unity_bins+[(str(root/'runtime/node.exe'),'runtime'),(str(root/'runtime/sqlite3mc_x64.dll'),'runtime')]
a=Analysis([str(root/'packaging/windows_entry.py')],pathex=[str(root)],binaries=binaries,datas=datas,
           hiddenimports=unity_imports+['tools.build_course_catalog','tools.index_assets'],
           excludes=['pytest','IPython','matplotlib','numpy','pandas'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='UmaRaceLab',console=False,debug=False,
        strip=False,upx=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='UmaRaceLab')
