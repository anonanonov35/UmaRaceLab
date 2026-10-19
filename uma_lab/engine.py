"""Local master-data/geometry adapter for the vendored contested race engine."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess
from .models import GRADES, STATS, RaceConfig, Runner
from .skill_codec import fidelity_issues, skill_payload
from .race_clock import build_race_clock
from .race_margins import build_finish_margins
from .paths import resource_root, node_executable

ROOT = resource_root()
MODEL_VERSION = 'contested-local-0.2.2'
FRAME_DT = 0.066600002348423
LIMITATIONS = [
    'Соответствие эталонным кадрам игры ещё не измерено; формулы community требуют дальнейшей проверки.',
    'Геометрия, повороты, склоны, уровни навыков и таблицы масштабирования берутся из локальных файлов игры.',
    'Динамические длительности и дополнительные эффекты реализованы по локальным таблицам; совпадение с игрой ещё не измерено.',
    'Повторное срабатывание навыков с коротким cooldown требует дальнейшей проверки.',
    'Нативные тела функций пока не восстановлены полностью; float64/RNG и порядок операций могут отличаться.',
    'Табло победителя моделируется отдельно по лимитам трассы; точный RNG коррекции и абсолютные времена остальных участниц не восстановлены.',
    'Подписи отставания используют локальный enum и коэффициент 15; пороги, округление и цепочка вызовов нативной функции ещё не подтверждены (≈).',
]

@dataclass
class RaceResult:
    model: str
    seed: int
    database_sha256: str
    config: dict
    course: dict
    runners: list[dict]
    frames: list[dict]
    events: list[dict]
    finish_times: list[float]
    limitations: list[str]
    support_report: list[dict] = field(default_factory=list)
    engine_provenance: dict = field(default_factory=dict)
    display_finish_times: list[float|None] = field(default_factory=list)
    scaled_finish_times: list[float] = field(default_factory=list)
    display_clock: dict = field(default_factory=dict)
    finish_margins: list[dict|None] = field(default_factory=list)
    margin_rules: dict = field(default_factory=dict)
    def to_dict(self):
        return asdict(self)

def base_speed(distance: float) -> float:
    return 20 - (distance - 2000) / 1000

def phase_at(distance: float, length: float) -> int:
    return 0 if distance < length/6 else 1 if distance < length*2/3 else 2 if distance < length*5/6 else 3

def run_bridge(payload: dict) -> dict:
    node = node_executable()
    process = subprocess.run([node, str(ROOT/'uma_lab/bridge.mjs')], input=json.dumps(payload, ensure_ascii=False, allow_nan=False),
                             text=True, encoding='utf-8', capture_output=True, timeout=120,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), cwd=ROOT)
    try:
        response = json.loads(process.stdout)
    except ValueError as e:
        raise ValueError('Ошибка движка: '+process.stderr[-1200:]) from e
    if not response.get('ok'):
        raise ValueError('Ошибка движка: '+response.get('error','неизвестная ошибка'))
    return response['result']

def course_payload(course: dict) -> dict:
    g = course.get('geometry')
    if not g:
        raise ValueError('Для расчёта нужна локальная геометрия трассы. Обновите данные трасс из игры.')
    length = course['distance']
    return {'courseId':course['id'], 'raceTrackId':course['race_track_id'], 'distance':length,
            'distanceType':1 if length<=1400 else 2 if length<=1800 else 3 if length<=2400 else 4,
            'surface':course['ground'], 'turn':course['turn'], 'courseSetStatus':g.get('course_set_status',[]),
            'corners':g['corners'], 'straights':g['straights'], 'slopes':g['slopes'],
            'laneMax':g.get('lane_max',1.35), 'courseWidth':11.25, 'horseLane':.625,
            'laneChangeAcceleration':.02, 'laneChangeAccelerationPerFrame':.02*FRAME_DT,
            'maxLaneDistance':11.25*g.get('lane_max',1.35), 'moveLanePoint':g.get('move_lane_point',0),
            'worldPath':{'points':[p[:2] for p in g['points']],'rotations':g['rotations'],'clockwise':course['turn']==1} if g.get('rotations') else None,
            'isAbroad':course['race_track_id']>=10201}

def runner_payload(r: Runner, index: int, data, course: dict | None = None) -> dict:
    aptitudes = r.race_aptitudes(course) if course is not None else {
        'distance': r.distance_aptitude, 'surface': r.surface_aptitude, 'strategy': r.strategy_aptitude}
    return {'outfitId':str(r.outfit_id or r.chara_id*100+1), 'name':r.name, 'mood':r.mood-3, 'strategy':r.strategy,
            'popularity':r.popularity, 'team':r.team or None, 'gate':index,
            'stats':{('wit' if k=='wisdom' else k):getattr(r,k) for k in STATS},
            'aptitudes':{key: 7-GRADES.index(value) for key,value in aptitudes.items()},
            'skills':[skill_payload(data.skills[sid],r,data) for sid in r.skills]}

def audit_catalog(data) -> dict:
    runner = Runner()
    pool = [skill_payload(s,runner,data) for s in data.skills.values()]
    report = run_bridge({'action':'audit','skills':pool})
    known = set(report['conditions'])
    unknown = {}
    for sid,s in data.skills.items():
        tokens = set().union(*(set(re.findall(r'([a-z_0-9]+)(?:==|!=|>=|<=|>|<)',s.get(k,''))) for k in ['condition_1','condition_2','precondition_1','precondition_2']))
        if tokens-known:
            unknown[str(sid)] = sorted(tokens-known)
    report['unknown_conditions'] = unknown
    report['fidelity'] = {str(sid):fidelity_issues(s) for sid,s in data.skills.items() if fidelity_issues(s)}
    return report

def simulate(runners: list[Runner], config: RaceConfig, data) -> RaceResult:
    config.validate()
    if not 1<=len(runners)<=18:
        raise ValueError('Нужно от 1 до 18 участников')
    for r in runners:
        r.validate()
        groups = set()
        for sid in r.skills:
            if sid not in data.skills:
                raise ValueError(f'{r.name}: в базе нет навыка {sid}')
            group = data.skills[sid].get('group_id',0)
            if group and group in groups:
                raise ValueError(f'{r.name}: несколько ступеней одной группы навыков {group}')
            groups.add(group)
    course = data.course(config.course_id)
    payload = {'course':course_payload(course),
               'parameters':{'ground':config.ground_condition,'weather':config.weather,'season':config.season,'timeOfDay':config.time_of_day,'grade':config.grade},
               'runners':[runner_payload(r,i,data,course) for i,r in enumerate(runners)],
               'nsamples':1,'masterSeed':config.seed,'focusRunnerIds':list(range(len(runners)))}
    skills = [s for r in payload['runners'] for s in r['skills']]
    support = run_bridge({'action':'audit','skills':skills}) if skills else {'conditions':[],'effects':[]}
    if support.get('conditionErrors'):
        raise ValueError('Ошибка разбора условий навыков: '+str(support['conditionErrors']))
    known=set(support['conditions'])
    for s in skills:
        for alt in s['alternatives']:
            unknown=set(re.findall(r'([a-z_0-9]+)(?:==|!=|>=|<=|>|<)',alt['condition']+' '+(alt['precondition'] or '')))-known
            if unknown:
                raise ValueError(f"Навык {s['skillId']}: неизвестные условия {', '.join(sorted(unknown))}")
    dropped=[s for s in support.get('effects',[]) if s.get('droppedEffects') or s.get('fullyUnmodeled')]
    if dropped:
        raise ValueError('Есть эффекты вне текущей модели: '+', '.join(str(s['skillId']) for s in dropped)+'. Подробности — в справочнике навыков.')
    raw = run_bridge({'action':'simulate','params':payload})
    finish = {r['runnerId']:r['finishTime'] for r in raw['finishOrders'][0]}
    if len(finish)!=len(runners):
        raise ValueError('Не все участники финишировали; прогон не принят')
    focus = {r['runnerId']:r for r in raw['collected'][0]['focus']}
    samples = {i:focus[i]['samples'] for i in focus}
    maxhp = {i:max((s['health'] for s in trace),default=1.) for i,trace in samples.items()}
    frames = []
    last_index = max(len(s) for s in samples.values())
    for index in range(last_index):
        time = max(trace[min(index,len(trace)-1)]['time'] for trace in samples.values())
        states = []
        for i in range(len(runners)):
            sample = samples[i][min(index,len(samples[i])-1)]
            distance = min(course['distance'],sample['position'])
            states.append({'distance':distance,'speed':sample['speed'],'hp':max(0,sample['health']),
                           'hp_ratio':max(0,min(1,sample.get('healthRatio',sample['health']/max(1,maxhp[i])))),'lane':sample['lane'],
                           'phase':phase_at(distance,course['distance']),'spurt':False,'finished':time>=finish[i]})
        frames.append({'time':time,'runners':states})
    events = []
    text = {'skill-activated':'Навык','last-spurt':'Финишный рывок','hp-out':'Выносливость исчерпана',
            'finished':'Финиш','rushed':'Kakari','rushed-end':'Kakari завершён','dueling-start':'Борьба на прямой',
            'fully-charged':'Высвобождение силы','mid-race-start':'Mid race','late-race-start':'Late race'}
    for event in raw['eventLogs'][0]:
        detail = event.get('detail') or {}
        sid = detail.get('skillId')
        label = text.get(event['kind'],event['kind'])
        if sid:
            base = int(sid.split('-')[0]) if sid.split('-')[0].isdigit() else 0
            label = data.skills.get(base,{}).get('name',label+' '+sid)
        event_time=finish[event['runnerId']] if event['kind']=='finished' else (event['tick']+1)*FRAME_DT
        events.append({'time':event_time,'runner':event['runnerId'],'kind':event['kind'],
                       'text':label,'distance':event['position'],**({'skill_id':sid} if sid else {})})
    for event in events:
        if event['kind']=='last-spurt':
            for frame in frames:
                if frame['time']>=event['time']:
                    frame['runners'][event['runner']]['spurt'] = True
    selected_report = []
    for r in runners:
        for sid in r.skills:
            issues = fidelity_issues(data.skills[sid])
            if issues:
                selected_report.append({'runner':r.name,'skill_id':sid,'issues':issues})
    selected_report.extend(support.get('effects',[]))
    wasm = ROOT/'vendor/honse-sim/uma_sim_wasm_bg.wasm'
    provenance = {'engine':'honse-sim-0.13.0 + local amendments','wasm_sha256':hashlib.sha256(wasm.read_bytes()).hexdigest(),
                  'timestep':FRAME_DT,'geometry_sources':course['geometry'].get('sources',{})}
    scale = getattr(data.catalog,'parameters',{}).get('Global',{}).get('FinishTimeCoef',1.18) if hasattr(data,'catalog') else 1.18
    clock=build_race_clock([finish[i] for i in range(len(runners))],course,config.seed,scale)
    margins,margin_rules=build_finish_margins(clock.scaled_finish_times,getattr(data,'finish_rules',None))
    if getattr(data,'finish_rules_error',None):
        margin_rules['unavailable']=data.finish_rules_error
    return RaceResult(MODEL_VERSION,config.seed,data.fingerprint,asdict(config),course,[asdict(r) for r in runners],
                      frames,sorted(events,key=lambda e:e['time']),[finish[i] for i in range(len(runners))],
                      LIMITATIONS.copy(),selected_report,provenance,clock.display_finish_times,clock.scaled_finish_times,clock.metadata,margins,margin_rules)
