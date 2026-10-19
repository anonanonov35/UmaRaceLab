"""Read-only card -> star rarity -> skill set links; no arithmetic skill-ID guesses."""
from dataclasses import replace
from .models import APTITUDE_GROUPS, GRADES

APTITUDE_COLUMNS = {
    'turf': 'proper_ground_turf', 'dirt': 'proper_ground_dirt',
    'sprint': 'proper_distance_short', 'mile': 'proper_distance_mile',
    'medium': 'proper_distance_middle', 'long': 'proper_distance_long',
    'front': 'proper_running_style_nige', 'pace': 'proper_running_style_senko',
    'late': 'proper_running_style_sashi', 'end': 'proper_running_style_oikomi',
}
UNIQUE_RARITIES = (3, 4, 5)


def card_catalog(cards, rarities, skill_sets, skills, texts):
    sets = {row['id']: row for row in skill_sets}
    profiles = {}
    for row in rarities:
        source = sets.get(row['skill_set'], {})
        unique = [source[key] for key in source if key.startswith('skill_id')
                  and skills.get(source[key], {}).get('rarity') in UNIQUE_RARITIES]
        # Missing/ambiguous links stay unavailable rather than inventing a skill.
        profiles.setdefault(row['card_id'], {})[row['rarity']] = {
            'unique_skill_id': unique[0] if len(unique) == 1 else None,
            'skill_set_id': row['skill_set'],
            'aptitudes': {key: GRADES[row[column] - 1] for key, column in APTITUDE_COLUMNS.items()},
        }
    return [{'id': row['id'], 'chara_id': row['chara_id'],
             'name': texts.get((4, row['id']), str(row['id'])),
             'display_name': (texts[(6,row['chara_id'])]+' '+texts[(5,row['id'])]
                              if (6,row['chara_id']) in texts and (5,row['id']) in texts
                              else texts.get((4,row['id']),str(row['id']))),
             'default_rarity': row.get('default_rarity', 3), 'profiles': profiles.get(row['id'], {})}
            for row in cards]


def find_variant(runner, data):
    if runner.outfit_id:
        return next((v for v in data.variants if v['id'] == runner.outfit_id), None)
    candidates = sorted((v for v in data.variants if v['chara_id'] == runner.chara_id), key=lambda v: v['id'])
    matches = [v for v in candidates if any(p['unique_skill_id'] in runner.skills for p in v['profiles'].values())]
    return matches[0] if len(matches) == 1 else next(iter(candidates), None)


def legacy_aptitudes(runner):
    return {key: getattr(runner, group + '_aptitude') for group, keys in APTITUDE_GROUPS.items() for key in keys}


def bind_variant(runner, data, variant_id=None, rarity=None, reset_aptitudes=False):
    variant = next((v for v in data.variants if v['id'] == variant_id), None) if variant_id is not None else find_variant(runner, data)
    if variant is None:
        if variant_id or runner.outfit_id:
            raise ValueError('Выбранной версии умы нет в подключённой базе')
        return replace(runner, skills=runner.skills.copy(), aptitudes=runner.aptitudes.copy())
    profiles = variant['profiles']
    stars = rarity if rarity is not None else runner.card_rarity
    if not stars:
        matches = [k for k, p in sorted(profiles.items()) if p['unique_skill_id'] in runner.skills]
        stars = matches[0] if matches else max(3, variant['default_rarity'])
    if stars not in profiles or not profiles[stars]['unique_skill_id']:
        raise ValueError('В базе нет однозначной связи версии умы с уникальным навыком для этой редкости')
    profile = profiles[stars]
    skills = [sid for sid in runner.skills if data.skills.get(sid, {}).get('rarity') not in UNIQUE_RARITIES]
    skills.insert(0, profile['unique_skill_id'])
    aptitudes = profile['aptitudes'].copy() if reset_aptitudes else (runner.aptitudes.copy() or legacy_aptitudes(runner))
    return replace(runner, chara_id=variant['chara_id'], outfit_id=variant['id'], card_rarity=stars,
                   skills=skills, aptitudes=aptitudes)


def owned_unique(runner, data):
    variant = find_variant(runner, data)
    return variant['profiles'].get(runner.card_rarity, {}).get('unique_skill_id') if variant else None


def add_build_skill(runner, sid, data):
    skill = data.skills[sid]
    if skill.get('rarity') in UNIQUE_RARITIES and sid != owned_unique(runner, data):
        raise ValueError('Этот уникальный навык принадлежит другой версии умы. Выберите унаследованный навык.')
    # A learned gold/white upgrade replaces the previous tier of the same group.
    group = skill.get('group_id')
    skills = [old for old in runner.skills if old != sid and
              (not group or data.skills.get(old, {}).get('group_id') != group)]
    skills.append(sid)
    result = replace(runner, skills=skills, aptitudes=runner.aptitudes.copy())
    result.validate()
    return result
