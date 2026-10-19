"""Broad integration checks against the user's current read-only installation.

This checks coverage and numerical invariants, not agreement with the game.
Extracted courses/conditions and traces are never copied into source control.
"""
from collections import Counter
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uma_lab.data import GameData,DEFAULT_INSTALL
from uma_lab.engine import audit_catalog,simulate
from uma_lab.models import RaceConfig,Runner

def run():
    data=GameData(DEFAULT_INSTALL);data.ensure_course_catalog()
    before=hashlib.sha256(data.path.read_bytes()).hexdigest()
    audit=audit_catalog(data)
    assert not audit['unknown_conditions'],audit['unknown_conditions']
    assert not audit['conditionErrors'],audit['conditionErrors']
    outside={int(s['skillId']) for s in audit['effects']}
    assert outside=={1000011,1000012},outside
    for sid in outside:
        try:simulate([Runner(skills=[sid])],RaceConfig(10606),data)
        except ValueError as error:assert 'вне текущей модели' in str(error)
        else:raise AssertionError(f'{sid} silently lost its effects')
    courses=[];unavailable=[]
    for row in data.courses:
        try:course=data.course(row['id'])
        except ValueError as error:
            unavailable.append({'id':row['id'],'error':str(error)});continue
        g=course['geometry'];D=course['distance']
        assert len(g['points'])==1001
        assert all(math.isfinite(v) for p in g['points'] for v in p)
        for key in ['corners','slopes']:
            assert all(0<=s['start']<=D and s['length']>0 for s in g[key]),(row['id'],key)
        result=simulate([Runner(speed=1800,stamina=1500),Runner(strategy=4,power=1500)],RaceConfig(course['id']),data)
        assert all(math.isfinite(t) and t>0 for t in result.finish_times)
        assert all(s['distance']==D for s in result.frames[-1]['runners'])
        courses.append(course['id'])
    # Every ordinary skill crosses the real DTO and contested field, separately
    # owned by a runner. Lack of activation is reported, not called a failure:
    # a single course/strategy cannot satisfy every skill's prerequisites.
    ids=[sid for sid in data.skills if sid not in outside]
    activations=Counter()
    for start in range(0,len(ids),18):
        group=ids[start:start+18]
        runners=[Runner(name=f'Coverage {sid}',chara_id=1001+i%90,speed=1700,stamina=1500,power=1500,wisdom=1200,strategy=i%4+1,skills=[sid],unique_level=6) for i,sid in enumerate(group)]
        result=simulate(runners,RaceConfig(10606,seed=42+start),data)
        for event in result.events:
            if event['kind']=='skill-activated' and event.get('skill_id'):
                activations[int(event['skill_id'].split('-')[0])]+=1
    after=hashlib.sha256(data.path.read_bytes()).hexdigest()
    assert before==after
    report={'database_sha256':before,'master_skills':len(data.skills),'ordinary_skill_inputs_checked':len(ids),
            'condition_parse_errors':audit['conditionErrors'],'unmodeled_scenario_skills':sorted(outside),
            'courses_raced':courses,'unavailable_courses':unavailable,'ordinary_skills_activated_in_coverage_scenarios':len(activations),
            'skills_not_activated_in_these_scenarios':[sid for sid in ids if sid not in activations],
            'database_unchanged':before==after,'warning':'Coverage and invariants do not measure native-game accuracy.'}
    output=Path('local/integration-report.json');output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('local/skill-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['courses_raced','skills_not_activated_in_these_scenarios']},ensure_ascii=False))

if __name__=='__main__':run()
