"""Validate the card editor against the installed DB on a private copy of builds."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import shutil
import sys
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uma_lab.gui import RaceLab
from uma_lab.build_catalog import add_build_skill, owned_unique
from uma_lab.models import load_builds
from uma_lab.engine import runner_payload
from tools.capture_tk_window import capture


def main():
    source=ROOT/'local/autosave-builds.json'
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None
    folder=ROOT/'local/ui-builder-040'
    folder.mkdir(exist_ok=True)
    if source.exists():shutil.copyfile(source,folder/'autosave-builds.json')
    (folder/'settings.json').write_text(json.dumps({'language':'ru','theme':'light'}),encoding='utf-8')
    errors=[]
    root=tk.Tk()
    root.report_callback_exception=lambda *args:errors.append(str(args))
    try:
        app=RaceLab(root,local_dir=folder)
        app._error=lambda error:errors.append(str(error))
        assert app.data is not None,getattr(app,'initial_error','No database')
        before=hashlib.sha256(app.data.path.read_bytes()).hexdigest()
        for variant in app.data.variants:
            for profile in variant['profiles'].values():
                assert profile['unique_skill_id'] in app.data.skills,variant
        def select(vid):
            app.character_var.set(next(label for label,value in app.character_labels.items() if value==vid))
            app._variant_changed();root.update()
        def shot(name,window=root):
            root.update();capture(window,ROOT/'local'/name)
        # These names/IDs are asserted from this local DB, not used as production mappings.
        select(100601)
        first=owned_unique(app.runners[0],app.data)
        assert app.data.skills[first]['name']=='Triumphant Pulse'
        app.form_vars['speed'].set('unfinished')
        select(100602)
        assert app.form_vars['speed'].get()=='unfinished'
        second=owned_unique(app.runners[0],app.data)
        assert app.data.skills[second]['name']=='Festive Miracle' and first not in app.runners[0].skills
        select(106101)
        app.form_vars['card_rarity'].set('1');app._rarity_changed()
        assert app.data.skills[owned_unique(app.runners[0],app.data)]['name']=='Call Me King'
        app.form_vars['card_rarity'].set('3');app._rarity_changed()
        assert app.data.skills[owned_unique(app.runners[0],app.data)]['name']=='Prideful King'
        for key,value in dict(name='King Halo / Kyoto',speed=802,stamina=757,power=735,guts=627,wisdom=505,
                              unique_level=6,turf='A',dirt='G',sprint='A',mile='S',medium='A',long='A',
                              front='F',pace='A',late='A',end='D').items():app.form_vars[key].set(str(value))
        app.form_vars['strategy'].set(app.strategies[2])
        app.form_vars['mood'].set(app.moods[4])
        app._commit_runner()
        unique=owned_unique(app.runners[0],app.data)
        # Add named examples and check the three visual kinds.
        for name in ('Professor of Curvature','Standard Distance','Non-Standard Distance','Spring Runner','Winter Runner','Focus'):
            matches=[sid for sid,s in app.data.skills.items() if name.casefold() in s['name'].casefold() and s['rarity'] in (1,2)]
            if matches:app.runners[0]=add_build_skill(app.runners[0],min(matches),app.data)
        app._refresh_skills();app._navigate(1);root.update()
        assert {item['kind'] for item in app.runner_skills.items}=={'unique','gold','normal'}
        app.runner_skills.selection_set(0)
        app._remove_skill()
        assert unique in app.runners[0].skills
        app._apply_runner()
        assert load_builds(folder/'autosave-builds.json')==app.runners
        payload=runner_payload(app.runners[0],0,app.data,app.data.course(10804))
        assert payload['outfitId']=='106101' and payload['aptitudes']=={'distance':0,'surface':1,'strategy':1},payload['aptitudes']
        assert any(s['skillId']==str(unique) for s in payload['skills'])
        shot('ui-builder-light-ru.png')
        for kind in ('unique','gold','normal'):
            sid=next(item['id'] for item in app.runner_skills.items if item['kind']==kind)
            app._show_skill_details(sid);root.update()
            window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
            shot('ui-builder-detail-'+kind+'.png',window);window.destroy()
        # Theme/language switches retain all ten raw cells and incomplete numeric input.
        app.form_vars['speed'].set('unfinished')
        raw={key:var.get() for key,var in app.form_vars.items()}
        runner_before=asdict(app.runners[0])
        app._toggle_theme();root.update()
        assert raw=={key:var.get() for key,var in app.form_vars.items()}
        assert asdict(app.runners[0])==runner_before
        app.form_vars['speed'].set('802')
        shot('ui-builder-dark-ru.png')
        app._change_language('en');root.update()
        root.geometry('1100x780');root.update();time.sleep(.1);root.update()
        assert app.runner_skills.canvas.winfo_height()>=app.runner_skills.card_height+8
        app.build_form_canvas.yview_moveto(1);root.update()
        fraction=app.build_form_canvas.yview()[0]
        app._change_language('ru');root.update()
        assert abs(app.build_form_canvas.yview()[0]-fraction)<.02
        app._change_language('en');root.update()
        app._see_build_field(app.character_combo);root.update()
        assert app.build_form_canvas.yview()[0]<.05
        shot('ui-builder-dark-small-en.png')
        app._open_skills();root.update()
        window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        professor=next(item['id'] for item in app.runner_skills.items if item['kind']=='gold')
        tree=app.skill_picker_tree
        tree.selection_set(str(professor));tree.see(str(professor));tree.event_generate('<<TreeviewSelect>>');root.update()
        shot('ui-builder-library-dark-en.png',window)
        foreign=str(second)
        tree.selection_set(foreign);tree.event_generate('<<TreeviewSelect>>');root.update()
        assert str(app.skill_picker_add['state'])=='disabled'
        window.destroy()
        # A real race verifies the full build reaches the engine and keeps the same selected unique.
        app.course_var.set(next(label for label,value in app.course_labels.items() if value==10804))
        app._preview_course();app._run()
        deadline=time.monotonic()+30
        while app.busy and time.monotonic()<deadline:root.update();time.sleep(.02)
        assert app.result is not None,app.notice.get()
        assert app.result.runners[0]['outfit_id']==106101
        assert unique in app.result.runners[0]['skills'] and app.result.runners[0]['aptitudes']['mile']=='S'
        assert not errors,errors
        assert before==hashlib.sha256(app.data.path.read_bytes()).hexdigest()
        if source_hash:assert source_hash==hashlib.sha256(source.read_bytes()).hexdigest()
        report={'variants':len(app.data.variants),'profiles':sum(len(v['profiles']) for v in app.data.variants),
                'unique_links_complete':True,'oguri_versions_distinct':True,'king_star_skill_changes':True,
                'aptitudes_and_unique_in_race':True,'themes':['light','dark'],'languages':['ru','en'],
                'legacy_builds_loaded':True,'source_builds_unchanged':True,'database_unchanged':True,'callback_errors':errors}
        (ROOT/'local/ui-builder-040-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:root.destroy()


if __name__=='__main__':main()
