"""Check both native themes on private build copies; requires the installed game."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab.gui import RaceLab
from tools.capture_tk_window import capture

source=ROOT/'local/autosave-builds.json'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
folder=ROOT/'local/ui-theme-031'
folder.mkdir(exist_ok=True)
shutil.copyfile(source,folder/'autosave-builds.json')
(folder/'settings.json').write_text(json.dumps({'language':'ru','theme':'light','custom_setting':'preserve-me'}),encoding='utf-8')
errors=[]
root=tk.Tk()
root.report_callback_exception=lambda *args:errors.append(str(args))
app=RaceLab(root,local_dir=folder)
database_hash=hashlib.sha256(app.data.path.read_bytes()).hexdigest()
app.course_var.set(next(k for k,v in app.course_labels.items() if v==10804))
app._preview_course();root.update();app._run()
deadline=time.monotonic()+30
while app.busy and time.monotonic()<deadline:
    root.update();time.sleep(.02)
assert app.result is not None,app.notice.get()
before=app.result.to_dict()
private_hash=hashlib.sha256((folder/'autosave-builds.json').read_bytes()).hexdigest()
app.seek.set(40)
app.result_diagnostics.set(True);app._result_columns()
app.form_vars['speed'].set('unfinished-edit')
app.runner_skills.selection_set(0)
app._toggle_theme();root.update()
assert app.theme_name=='dark'
assert app.form_vars['speed'].get()=='unfinished-edit'
assert app.result.to_dict()==before and app.playhead==40
assert app.runner_skills.curselection()==(0,)
assert app.result_diagnostics.get()
assert hashlib.sha256((folder/'autosave-builds.json').read_bytes()).hexdigest()==private_hash
app.form_vars['speed'].set(str(app.runners[app.active_runner].speed))
app.result_diagnostics.set(False);app._result_columns()
root.update()
assert app.event_list.winfo_width()>=180
assert app.results_tree.column('name','width')>=155
assert abs(sum(app.results_tree.column(key,'width') for key in app.results_tree['displaycolumns'])-app.results_tree.winfo_width())<=5

def shot(window,name):
    root.update()
    capture(window,ROOT/'local'/name)

def dark_controls():
    assert app.event_list.cget('background')==app.palette['surface']
    assert app.runner_skills.cget('background')==app.palette['surface']
    assert app.model_text.cget('background')==app.palette['surface']
    assert app.track_views.top.cget('background')==app.palette['surface']
    style=ttk.Style(root)
    assert style.lookup('Primary.TButton','foreground')==app.palette['on_accent']
    assert style.lookup('Treeview','fieldbackground')==app.palette['surface']
    popdown=root.tk.call('ttk::combobox::PopdownWindow',str(app.course_combo))
    assert root.tk.call(str(popdown)+'.f.l','cget','-background')==app.palette['surface']

dark_controls();shot(root,'ui-theme-dark-race-ru.png')
app._navigate(1);root.update();shot(root,'ui-theme-dark-builds-ru.png')
app._open_skills();root.update()
window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
shot(window,'ui-theme-dark-skills-ru.png');window.destroy()
app._navigate(2);root.update();shot(root,'ui-theme-dark-accuracy-ru.png')
app._change_language('en');root.update()
assert app.theme_name=='dark' and app.tr.language=='en'
dark_controls()
app._navigate(0);root.update();shot(root,'ui-theme-dark-race-en.png')
root.geometry('1100x780');root.update();time.sleep(.1);root.update()
shot(root,'ui-theme-dark-small-en.png')
app._toggle_theme();root.update()
assert app.theme_name=='light' and app.tr.language=='en'
assert app.result.to_dict()==before
shot(root,'ui-theme-light-small-en.png')

# Verify a theme switch while calculation is pending using a controlled worker.
import uma_lab.gui as gui_module
original=gui_module.simulate
release=threading.Event()
def delayed(*args,**kwargs):
    assert release.wait(10)
    return original(*args,**kwargs)
gui_module.simulate=delayed
app._run();app._toggle_theme();root.update()
assert app.busy and app.theme_name=='dark'
assert str(app.run_button['state'])=='disabled'
release.set()
deadline=time.monotonic()+30
while app.busy and time.monotonic()<deadline:
    root.update();time.sleep(.02)
gui_module.simulate=original
assert not app.busy and app.result.to_dict()==before
assert source_hash==hashlib.sha256(source.read_bytes()).hexdigest()
assert database_hash==hashlib.sha256(app.data.path.read_bytes()).hexdigest()
assert not errors,errors
settings=json.loads((folder/'settings.json').read_text(encoding='utf-8'))
assert settings['theme']=='dark' and settings['language']=='en'
assert settings['custom_setting']=='preserve-me'
root.destroy()

second=tk.Tk();second.withdraw()
reopened=RaceLab(second,local_dir=folder)
assert reopened.theme_name=='dark' and reopened.tr.language=='en'
assert reopened.palette['surface']=='#222426'
second.destroy()
report={'themes':['light','dark'],'languages':['ru','en'],'race_and_form_preserved':True,
        'preferences_survive_reopening':True,'source_builds_unchanged':True,
        'database_unchanged':True,'callback_errors':errors}
(ROOT/'local/ui-theme-031-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report))
