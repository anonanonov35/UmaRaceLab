"""Launch/capture/close only the executable process created by this test."""
from pathlib import Path
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.capture_tk_window import capture
from uma_lab.models import Runner, save_builds


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,default=ROOT/'build/frozen/UmaRaceLab/UmaRaceLab.exe')
    parser.add_argument('--game',type=Path,required=True)
    args=parser.parse_args()
    folder=ROOT/'build/frozen-gui-test';folder.mkdir(parents=True,exist_ok=True)
    save_builds(folder/'autosave-builds.json',[Runner(name='Release preview',chara_id=1006,speed=1500)])
    (folder/'settings.json').write_text(json.dumps({'language':'ru','theme':'dark','database_path':str(args.game.resolve())}),encoding='utf-8')
    env=os.environ.copy();env['UMA_LAB_DATA_DIR']=str(folder)
    env['PATH']=str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32')
    for name in ('PYTHONPATH','PYTHONHOME','UMA_LAB_NODE'):env.pop(name,None)
    executable=args.executable.resolve()
    process=subprocess.Popen([str(executable)],cwd=executable.parent,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    user=C.WinDLL('user32',use_last_error=True)
    callback_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback_type,W.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    user.IsWindowVisible.argtypes=[W.HWND]
    user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    found=[]
    def own_window(hwnd,_):
        pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if pid.value==process.pid and user.IsWindowVisible(hwnd):
            title=C.create_unicode_buffer(300);user.GetWindowTextW(hwnd,title,300)
            if title.value.startswith('Uma Race Lab / '):found.append(hwnd)
        return True
    callback=callback_type(own_window)
    try:
        deadline=time.monotonic()+25
        while not found and process.poll() is None and time.monotonic()<deadline:
            user.EnumWindows(callback,0);time.sleep(.1)
        assert found,'Frozen GUI did not open; inspect build/frozen-gui-test/startup-error.log'
        time.sleep(.8)
        class OwnWindow:
            def update_idletasks(self):pass
            def winfo_id(self):return found[0]
        capture(OwnWindow(),ROOT/'build/frozen-ui.png')
        user.PostMessageW(found[0],0x0010,0,0)  # WM_CLOSE, only our known child process.
        assert process.wait(timeout=10)==0
        assert not (folder/'startup-error.log').exists()
        print('Frozen GUI opened, captured and closed cleanly; isolated build/frozen-gui-test data')
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)


if __name__=='__main__':main()
