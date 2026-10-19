"""Exercise our own Tk widgets and capture only our application window."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tkinter as tk
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uma_lab.gui import RaceLab

local = Path("local/ui-smoke")
local.mkdir(parents=True, exist_ok=True)
root = tk.Tk()
app = RaceLab(root, local_dir=local)
errors = []
root.report_callback_exception = lambda *args: errors.append(str(args))
assert app.data is not None, getattr(app, "initial_error", "DB missing")
before = hashlib.sha256(app.data.path.read_bytes()).hexdigest()
root.update()
app.form_vars['speed'].set('1800')
app.form_vars['unique_level'].set('6')
app._advanced_runner()
root.update()
for window in [w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]:window.destroy()
app._race_options()
root.update()
for window in [w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]:window.destroy()
app._run()
deadline = time.monotonic() + 20
while app.busy and time.monotonic() < deadline:
    root.update()
    time.sleep(.02)
assert app.result is not None, "Worker did not produce a result"
assert app.result.runners[0]['speed']==1800
assert not errors, errors
app._toggle_play()
assert app.playing
for _ in range(8):
    root.update()
    time.sleep(.02)
assert app.playhead > 0
app._toggle_play()
assert not app.playing
app._rewind()
assert app.playhead == 0
app.playhead = 55
app.seek.set(55)
app._draw()
root.update()
try:
    from PIL import ImageGrab
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save("local/ui-race.png")
    notebook = app.race_tab.master
    notebook.select(app.build_tab)
    root.update()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save("local/ui-builds.png")
    app._open_skills()
    for _ in range(15):
        root.update()
        time.sleep(.02)
    window = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    wx, wy = window.winfo_rootx(), window.winfo_rooty()
    ImageGrab.grab(bbox=(wx, wy, wx + window.winfo_width(), wy + window.winfo_height())).save("local/ui-skills.png")
    window.destroy()
except ImportError:
    print("Pillow unavailable; screenshots skipped")
app._commit_runner()
app._autosave()
after = hashlib.sha256(app.data.path.read_bytes()).hexdigest()
assert before == after, "Game database changed during smoke test"
assert not errors, errors
Path("local/first-race.json").write_text(json.dumps(app.result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
saved_result=app.result
selected=app.course_var.get()
other=next(label for label,cid in app.course_labels.items() if cid!=saved_result.course['id'] and cid not in (11201,11202))
app.course_var.set(other)
app._preview_course(object())
assert app.result is None and app.track_views.course['id']==app.course_labels[other]
app.course_var.set(selected)
app._set_result(saved_result)
print(json.dumps({"runners": len(app.runners), "courses": len(app.data.courses), "skills": len(app.data.skills), "frames": len(app.result.frames), "finish_times": app.result.finish_times, "database_unchanged": before == after, "callback_errors": errors}))
root.destroy()
