"""Read-only game/UI smoke on a private copy of local builds; writes screenshots under local/."""
from pathlib import Path
import hashlib,json,shutil,sys,time,re
import tkinter as tk
from tkinter import ttk,messagebox

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab.gui import RaceLab
from PIL import ImageGrab

source=ROOT/'local/autosave-builds.json'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
folder=ROOT/'local/ui-design-030';folder.mkdir(exist_ok=True)
shutil.copyfile(source,folder/'autosave-builds.json')
(folder/'settings.json').write_text(json.dumps({'language':'ru','custom_setting':'preserve-me'}),encoding='utf-8')
errors=[]
root=tk.Tk();root.report_callback_exception=lambda *args:errors.append(str(args))
app=RaceLab(root,local_dir=folder)
database_hash=hashlib.sha256(app.data.path.read_bytes()).hexdigest()
app.course_var.set(next(k for k,v in app.course_labels.items() if v==10804));app._preview_course()
root.update();app._run()
deadline=time.monotonic()+30
while app.busy and time.monotonic()<deadline:root.update();time.sleep(.02)
assert app.result is not None,app.notice.get()
app.seek.set(40);root.update()

def shot(name):
    root.update()
    x,y=root.winfo_rootx(),root.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(ROOT/'local'/name)

shot('ui-design-race-ru.png')
before=app.result.to_dict();playhead=app.playhead
form_before=app.form_vars['speed'].get()
app.form_vars['speed'].set('invalid-edit')
app._change_language('en');root.update()
assert app.tr.language=='en'
assert app.form_vars['speed'].get()=='invalid-edit'
assert app.playhead==playhead
assert app.result.to_dict()==before
assert app.course_labels[app.course_var.get()]==10804
assert app.ground_var.get()=='Firm' and app.season_var.get()=='Autumn'
assert json.loads((folder/'settings.json').read_text())['custom_setting']=='preserve-me'
app.form_vars['speed'].set(form_before)
shot('ui-design-race-en.png')

def widgets(w):
    for child in w.winfo_children():yield child;yield from widgets(child)

def visible_strings():
    found=[]
    for w in widgets(root):
        if not w.winfo_viewable():continue
        if isinstance(w,tk.Text):found.append(w.get('1.0','end'))
        elif isinstance(w,tk.Listbox):found.extend(w.get(0,'end'))
        elif isinstance(w,tk.Canvas):
            found.extend(w.itemcget(i,'text') for i in w.find_all() if w.type(i)=='text')
        elif isinstance(w,ttk.Treeview):
            found.extend(w.heading(key)['text'] for key in w['columns'])
            for item in w.get_children():found.extend(map(str,w.item(item,'values')))
        else:
            if 'text' in w.keys():found.append(w.cget('text'))
            if 'textvariable' in w.keys() and w.cget('textvariable'):
                try:found.append(root.getvar(w.cget('textvariable')))
                except tk.TclError:pass
    return [s for s in found if isinstance(s,str) and re.search('[А-Яа-яЁё]',s)]

leaks={'race':visible_strings()}
app._navigate(1);root.update();shot('ui-design-builds-en.png')
leaks['builds']=visible_strings()
app._open_skills();root.update()
window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
leaks['skills']=visible_strings()
window.destroy()
app._race_options();root.update()
window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
leaks['conditions']=visible_strings();window.destroy()
app._advanced_runner();root.update()
window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
leaks['advanced']=visible_strings();window.destroy()
app._navigate(2);root.update();shot('ui-design-accuracy-en.png')
leaks['accuracy']=visible_strings()
app._change_language('ru');root.update()
assert app.result.to_dict()==before
assert app.form_vars['speed'].get()==form_before
app._navigate(1);root.update();shot('ui-design-builds-ru.png')
root.geometry('1100x780');root.update();time.sleep(.1);root.update();shot('ui-design-small-builds-ru.png')
app._navigate(0);root.update();shot('ui-design-small-race-ru.png')
# Switch while a background run is pending, preserving its original inputs.
import uma_lab.gui as gui_module
original_simulate=gui_module.simulate
import threading
release=threading.Event()
def slow_simulate(*args,**kwargs):
    assert release.wait(10), "UI did not release the test worker"
    return original_simulate(*args,**kwargs)
gui_module.simulate=slow_simulate
app._run();app._change_language('en');root.update()
assert app.busy and str(app.run_button['state'])=='disabled',(app.busy,str(app.run_button['state']))
release.set()
deadline=time.monotonic()+30
while app.busy and time.monotonic()<deadline:root.update();time.sleep(.02)
gui_module.simulate=original_simulate
assert not app.busy and app.result.to_dict()==before
assert source_hash==hashlib.sha256(source.read_bytes()).hexdigest()
assert database_hash==hashlib.sha256(app.data.path.read_bytes()).hexdigest()
(ROOT/'local/ui-design-030-report.json').write_text(json.dumps({'leaks':leaks,'errors':errors,'result_preserved':before==app.result.to_dict(),'source_builds_unchanged':True,'database_unchanged':True},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'leaks':leaks,'errors':errors},ensure_ascii=False))
assert not errors,errors
assert all(not values for values in leaks.values()),leaks
app._change_language('en')
root.update()
root.destroy()
second=tk.Tk()
second.withdraw()
reopened=RaceLab(second,local_dir=folder)
assert reopened.tr.language=='en'
assert reopened.settings['custom_setting']=='preserve-me'
second.destroy()
print('Language preference survives reopening; game DB unchanged.')
