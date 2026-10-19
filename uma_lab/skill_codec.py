"""Master-data -> public engine boundary, preserving levels and all raw branches."""
from __future__ import annotations
import re
from .models import Runner,STATS

def effective_stat(raw: float) -> float:
    return 1200 + (raw-1200)//2 if raw>1200 else raw

def tier(table: list[dict], threshold: str, value: float) -> float:
    return next((r['Multiply'] for r in table if value<r[threshold]), table[-1]['Multiply'])

def skill_payload(skill: dict, runner: Runner, data) -> dict:
    params=getattr(getattr(data,'catalog',None),'parameters',{}).get('Skill',{})
    alternatives=[]
    for branch in (1,2):
        effects=[]
        for i in (1,2,3):
            prefix=f'{branch}_{i}'
            kind=skill.get('ability_type_'+prefix,0)
            if not kind:
                continue
            value=skill['float_ability_value_'+prefix]
            level=runner.unique_level if skill['rarity'] in (3,4,5) else 1
            coefficient=getattr(data,'skill_levels',{}).get((kind,level),1.)
            level_usage=skill.get('ability_value_level_usage_'+prefix,1)
            if level_usage==1:
                value*=coefficient
            elif level_usage==3:
                value*=2-coefficient
            usage=skill.get('ability_value_usage_'+prefix,1)
            multiplier=None
            # Unlike scraped datasets, the local master stores raw values: select
            # the tier from the actual build, never assume the maximum 1.2x tier.
            if usage in (3,4,5,6,7):
                total=getattr(runner,'aoharu_'+STATS[usage-3])
                multiplier=tier(params['TeamTotalStatusCoefAscArray'],'StatusThreshold',total)
            elif usage==10:
                multiplier=tier(params['RaceWinCountCoefAscArray'],'WinCountThreshold',runner.career_wins)
            elif usage==12:
                multiplier=tier(params['FanCountCoefAscArray'],'FanCountThreshold',runner.fan_count)
            elif usage==13:
                multiplier=tier(params['MaximumRawStatusCoefAscArray'],'BaseStatusThreshold',max(getattr(runner,k) for k in STATS))
            elif usage==2:
                multiplier=min(1.2,1+.01*len(runner.skills))
            if multiplier is not None:
                value*=multiplier
            effect={'type':kind,'modifier':value,'target':skill['target_type_'+prefix],
                    'valueUsage':usage,'valueLevelUsage':level_usage}
            if multiplier is not None:
                effect['preAppliedMultiplier']=multiplier
            effects.append(effect)
        if effects:
            usage=skill.get('ability_time_usage_'+str(branch),1)
            hp_table=params.get('TimeRemainHpCoefAscArray2' if usage==7 else 'TimeRemainHpCoefAscArray',[])
            tiers=[[r.get('HpThreshold',r.get('RemainHpThreshold',0)),r['Multiply']] for r in hp_table]
            # Preserve the source table's key spelling rather than infer tiers.
            if hp_table:
                threshold=next(k for k in hp_table[0] if k!='Multiply')
                tiers=[[r[threshold],r['Multiply']] for r in hp_table]
            tiers=(tiers+[[1e12,tiers[-1][1] if tiers else 1.]]*8)[:8]
            alternatives.append({'baseDuration':skill['float_ability_time_'+str(branch)],
                                 'cooldownTime':skill.get('float_cooldown_time_'+str(branch),5000000),
                                 'condition':skill['condition_'+str(branch)] or 'always==1',
                                 'precondition':skill.get('precondition_'+str(branch)) or None,'effects':effects,
                                 'runtime':{'timeUsage':usage,'additionalTypes':[skill.get(f'additional_activate_type_{branch}_{i}',0) for i in (1,2,3)],
                                            'hpTiers':tiers,'distancePer':params.get('AbilityTimeDiffDistanceTopCoefPerDistance',62.5),
                                            'distanceMin':params.get('AbilityTimeDiffDistanceTopCoefMin',.8),
                                            'distanceMax':params.get('AbilityTimeDiffDistanceTopCoefMax',1.6),
                                            'extensionSeconds':params.get('OrderUpAddAbilityTime',1.),'maxExtensions':params.get('OrderUpAddAbilityTimeMaxCount',3)}})
    return {'skillId':str(skill['id']),'rarity':skill['rarity'],
            'tags':[int(n) for n in re.findall(r'\d+',str(skill.get('tag_id','')))],'alternatives':alternatives}

def fidelity_issues(skill: dict) -> list[str]:
    issues=[]
    expressions=' '.join(skill.get(k,'') or '' for k in ('condition_1','condition_2','precondition_1','precondition_2'))
    for token in ('is_behind_in','is_surrounded','visiblehorse'):
        if token in expressions:
            issues.append(f'Условие {token}: текущая семантика приближена, нативная версия не восстановлена')
    if any(skill.get('ability_time_usage_'+str(b),1)!=1 and any(skill.get(f'ability_type_{b}_{i}',0) for i in (1,2,3)) for b in (1,2)):
        issues.append('Динамическая длительность реализована; требуется сравнение с кадрами игры')
    if any(skill.get(f'additional_activate_type_{b}_{i}',0) for b in (1,2) for i in (1,2,3)):
        issues.append('Дополнительные эффекты реализованы; требуется сравнение с кадрами игры')
    return issues
