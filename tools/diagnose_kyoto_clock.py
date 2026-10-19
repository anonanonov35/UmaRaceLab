"""Compare calculated/scoreboard clocks using the user's saved builds.

Read-only with respect to all builds and game files. Only the diagnostic report
is written. The supplied observed interval is a report, not a fitting target.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from dataclasses import replace
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uma_lab.data import GameData,DEFAULT_INSTALL
from uma_lab.models import load_builds,RaceConfig
from uma_lab.engine import simulate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--builds',type=Path,default=Path('local/autosave-builds.json'))
    parser.add_argument('--runs',type=int,default=24)
    parser.add_argument('--output',type=Path,default=Path('local/kyoto1600-clock-report.json'))
    args=parser.parse_args()
    if not 1<=args.runs<=200:parser.error('--runs must be between 1 and 200')
    data=GameData(DEFAULT_INSTALL);data.ensure_course_catalog()
    input_hash=hashlib.sha256(args.builds.read_bytes()).hexdigest()
    master_hash=hashlib.sha256(data.path.read_bytes()).hexdigest()
    originals=load_builds(args.builds)
    # Match the reported conditions in a copy, preserving the actual saved file.
    runners=[replace(r,mood=5,skills=r.skills.copy()) for r in originals]
    differences=[{'runner':r.name,'saved_mood':r.mood,'test_mood':5} for r in originals if r.mood!=5]
    def run(seed):
        result=simulate(runners,RaceConfig(10804,seed=seed,ground_condition=1,weather=1,season=3),data)
        winner=min(range(len(runners)),key=lambda i:result.finish_times[i])
        return {'seed':seed,'winner':runners[winner].name,'raw':result.finish_times[winner],
                'scaled':result.scaled_finish_times[winner],'board':result.display_finish_times[winner],
                'correction':result.display_clock['correction']}
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,range(args.runs)))
    def stats(key):
        values=[row[key] for row in rows]
        return {'min':min(values),'max':max(values),'mean':statistics.mean(values)}
    unique_warnings=[]
    for r in originals:
        full=[sid for sid in r.skills if data.skills[sid]['rarity'] in (3,4,5)]
        if len(full)>1:
            unique_warnings.append({'runner':r.name,'full_unique_skills':full,'note':'Check whether a foreign unique should be its inherited counterpart; builds are not edited.'})
    report={'course':10804,'runs':args.runs,'model':'contested-local-0.2.1','builds_sha256':input_hash,
            'database_sha256':master_hash,'conditions':{'ground':1,'weather':1,'season':3,'mood':5,'runners':len(runners)},
            'input_differences':differences,'observed_game_interval_reported_by_user':[89.,91.5],
            'build_warnings':unique_warnings,
            'stats':{key:stats(key) for key in ('raw','scaled','board')},'winner_counts':dict(Counter(row['winner'] for row in rows)),
            'rows':rows,'warning':'Scoreboard correction is not validation of physical accuracy; native presentation RNG is unverified.'}
    assert input_hash==hashlib.sha256(args.builds.read_bytes()).hexdigest()
    assert master_hash==hashlib.sha256(data.path.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows',)},ensure_ascii=True))


if __name__=='__main__':main()
