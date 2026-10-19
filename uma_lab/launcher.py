"""Desktop entry point plus a no-account release health check."""
import argparse
import json
from pathlib import Path
import sys
import traceback

from . import __version__
from .paths import user_data_dir


def self_test(game=None):
    import tkinter as tk
    from .engine import run_bridge, simulate
    from .models import Runner, RaceConfig
    from .data import GameData
    from .i18n import Translator
    from .theme import apply_theme
    checks=[]
    root=tk.Tk();root.withdraw()
    try:
        for theme in ('light','dark'):apply_theme(root,theme)
        root.update_idletasks();checks.append('tk-light-dark')
    finally:root.destroy()
    assert Translator('en')('Характеристики')=='Stats'
    checks.append('localization')
    audit=run_bridge({'action':'audit','skills':[]})
    assert audit['conditions']
    checks.append('bundled-node-wasm')
    result={'version':__version__,'ok':True,'checks':checks}
    if game is not None:
        data=GameData(Path(game));data.ensure_course_catalog()
        available=[c for c in data.courses if not data.catalog.payload['courses'].get(str(c['id']),{}).get('error')]
        assert available
        course=next((c for c in available if c['id']==10804),available[0])
        race=simulate([Runner(name='Release self-test')],RaceConfig(course['id']),data)
        assert race.finish_times[0]>0
        checks.append('installed-game-courses-and-race')
        result.update(courses=len(available),course_id=course['id'],finish_time=race.finish_times[0],database_sha256=data.fingerprint)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(prog='Uma Race Lab')
    parser.add_argument('--self-test',action='store_true',help='Check Tk, translations and bundled engine, then exit')
    parser.add_argument('--game',type=Path,help='Optional installed game/master.mdb for the self-test')
    parser.add_argument('--report',type=Path,help='Write the self-test JSON report here')
    args=parser.parse_args(argv)
    if args.self_test:
        try:report=self_test(args.game)
        except Exception as error:report={'version':__version__,'ok':False,'error':str(error),'traceback':traceback.format_exc()}
        path=args.report or user_data_dir()/'self-test.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if sys.stdout is not None:print(json.dumps(report,ensure_ascii=False))
        return 0 if report['ok'] else 1
    try:
        from .gui import main as open_gui
        open_gui()
        return 0
    except Exception:
        folder=user_data_dir();folder.mkdir(parents=True,exist_ok=True)
        log=folder/'startup-error.log';log.write_text(traceback.format_exc(),encoding='utf-8')
        from tkinter import messagebox
        messagebox.showerror('Uma Race Lab','Startup failed. Details / Подробности:\n'+str(log))
        return 1
