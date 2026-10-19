"""Historical 0.1 parser retained for compatibility tests.

The current application's condition/support gate is the WASM audit in engine.py.
Do not use this deliberately limited parser to classify current game skills.
"""
from __future__ import annotations
from dataclasses import dataclass
import operator
import re

STATIC_KEYS = {"running_style", "ground_type", "ground_condition", "weather", "season", "rotation", "distance_type", "track_id"}
DYNAMIC_KEYS = {"phase", "distance_rate", "remain_distance", "hp_per", "accumulatetime"}
OPS = {"==": operator.eq, "!=": operator.ne, ">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}
TERM = re.compile(r"([a-z_]+)(==|!=|>=|<=|>|<)(-?\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class Condition:
    alternatives: tuple
    keys: frozenset[str]

    def matches(self, context: dict[str, float]) -> bool:
        return any(all(OPS[op](context[key], value) for key, op, value in terms) for terms in self.alternatives)


def parse_condition(text: str, static_only: bool = False) -> Condition:
    if text == "":
        return Condition(((),), frozenset())
    alternatives, keys = [], set()
    for branch in text.split("@"):
        terms = []
        for token in branch.split("&"):
            match = TERM.fullmatch(token.strip())
            if not match:
                raise ValueError(f"Не поддерживается условие: {token}")
            key, op, raw = match.groups()
            if key not in (STATIC_KEYS if static_only else STATIC_KEYS | DYNAMIC_KEYS):
                raise ValueError(f"Не поддерживается условие: {key}")
            terms.append((key, op, float(raw)))
            keys.add(key)
        alternatives.append(tuple(terms))
    return Condition(tuple(alternatives), frozenset(keys))


def skill_support(skill: dict) -> tuple[bool, str]:
    """Unsupported skills are blocked, never silently dropped from a simulation."""
    try:
        if skill["rarity"] not in (1, 2):
            raise ValueError("Уникальный/особый навык: масштабирование по уровню ещё не восстановлено")
        if skill.get("condition_2") or any(skill.get(f"ability_type_2_{i}", 0) for i in range(1, 4)):
            raise ValueError("Вторая ветка эффекта ещё не поддерживается")
        if skill.get("precondition_1"):
            raise ValueError("Предусловие с памятью активации ещё не поддерживается")
        condition = parse_condition(skill["condition_1"])
        effects = []
        for i in range(1, 4):
            kind = skill[f"ability_type_1_{i}"]
            if not kind:
                continue
            if kind not in (1, 2, 3, 4, 5, 9, 27, 31):
                raise ValueError(f"Не поддерживается эффект типа {kind}")
            if skill[f"target_type_1_{i}"] != 1 or skill.get(f"target_value_1_{i}", 0) != 0:
                raise ValueError("Эффекты на других участников ещё не поддерживаются")
            if skill.get(f"additional_activate_type_1_{i}", 0):
                raise ValueError("Дополнительный тип активации ещё не поддерживается")
            if kind in (1, 2, 3, 4, 5) and condition.keys - STATIC_KEYS:
                raise ValueError("Пассивный эффект требует неподдерживаемой динамической активации")
            effects.append(kind)
        if not effects:
            raise ValueError("Нет поддерживаемого эффекта")
        # Mixed stat/active skills require a more complete lifecycle.
        if any(k <= 5 for k in effects) and any(k > 5 for k in effects):
            raise ValueError("Смешанный пассивный/активный эффект ещё не поддерживается")
        return True, "Базовый эффект; экспериментальная модель"
    except (ValueError, KeyError) as e:
        return False, str(e)
