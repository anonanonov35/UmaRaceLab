from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

STATS = ("speed", "stamina", "power", "guts", "wisdom")
GRADES = "GFEDCBAS"
STRATEGIES = {1: "Лидер / Front", 2: "Преследование / Pace", 3: "Поздний рывок / Late", 4: "Замыкающий / End"}
APTITUDE_GROUPS = {
    'surface': ('turf', 'dirt'),
    'distance': ('sprint', 'mile', 'medium', 'long'),
    'strategy': ('front', 'pace', 'late', 'end'),
}
APTITUDE_KEYS = tuple(key for group in APTITUDE_GROUPS.values() for key in group)


@dataclass
class Runner:
    name: str = "Новый билд"
    chara_id: int = 0
    speed: int = 1000
    stamina: int = 800
    power: int = 900
    guts: int = 400
    wisdom: int = 600
    strategy: int = 2
    distance_aptitude: str = "A"
    surface_aptitude: str = "A"
    strategy_aptitude: str = "A"
    mood: int = 3
    skills: list[int] = field(default_factory=list)
    unique_level: int = 1
    outfit_id: int = 0
    card_rarity: int = 0  # 0: legacy file, resolve from the selected card/owned unique.
    aptitudes: dict[str, str] = field(default_factory=dict)
    popularity: int = 1
    team: int = 0
    career_wins: int = 0
    fan_count: int = 0
    aoharu_speed: int = 0
    aoharu_stamina: int = 0
    aoharu_power: int = 0
    aoharu_guts: int = 0
    aoharu_wisdom: int = 0

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 100:
            raise ValueError("Имя билда: от 1 до 100 символов")
        for key in STATS:
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= 5000:
                raise ValueError(f"{key}: нужно целое число от 1 до 5000")
        if self.strategy not in STRATEGIES or type(self.strategy) is not int:
            raise ValueError("Неизвестная стратегия")
        if any(not isinstance(a, str) or len(a) != 1 or a not in GRADES for a in (self.distance_aptitude, self.surface_aptitude, self.strategy_aptitude)):
            raise ValueError("Пригодность должна быть от G до S")
        if type(self.mood) is not int or self.mood not in range(1, 6):
            raise ValueError("Настроение: от 1 до 5")
        if type(self.chara_id) is not int or self.chara_id < 0:
            raise ValueError("Некорректный ID персонажа")
        if type(self.unique_level) is not int or self.unique_level not in range(1, 7):
            raise ValueError("Уровень уникального навыка: 1–6")
        if type(self.card_rarity) is not int or self.card_rarity not in range(6):
            raise ValueError('Редкость персонажа: от 1 до 5 звёзд')
        if not isinstance(self.aptitudes, dict) or (self.aptitudes and set(self.aptitudes) != set(APTITUDE_KEYS)):
            raise ValueError('Таблица пригодностей должна содержать все 10 значений')
        if any(not isinstance(a, str) or len(a) != 1 or a not in GRADES for a in self.aptitudes.values()):
            raise ValueError("Пригодность должна быть от G до S")
        if not isinstance(self.skills, list) or any(type(s) is not int or s <= 0 for s in self.skills):
            raise ValueError("Навыки: список положительных целых ID")
        if len(self.skills) > 100 or len(set(self.skills)) != len(self.skills):
            raise ValueError("В билде не более 100 навыков, без повторений")
        for key,limit in [("outfit_id",9999999),("popularity",18),("team",18),("career_wins",100),("fan_count",999999999), *[("aoharu_"+k,100000) for k in STATS]]:
            value=getattr(self,key)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"{key}: нужно целое число от 0 до {limit}")

    def race_aptitudes(self, course: dict) -> dict[str, str]:
        """Old builds keep their three grades until edited into the full table."""
        if not self.aptitudes:
            return {'distance': self.distance_aptitude, 'surface': self.surface_aptitude,
                    'strategy': self.strategy_aptitude}
        distance = course['distance']
        distance_key = 'sprint' if distance <= 1400 else 'mile' if distance <= 1800 else 'medium' if distance <= 2400 else 'long'
        return {'distance': self.aptitudes[distance_key],
                'surface': self.aptitudes['turf' if course['ground'] == 1 else 'dirt'],
                'strategy': self.aptitudes[APTITUDE_GROUPS['strategy'][self.strategy - 1]]}


@dataclass(frozen=True)
class RaceConfig:
    course_id: int
    seed: int = 42
    ground_condition: int = 1
    weather: int = 1
    season: int = 3
    time_of_day: int = 2
    grade: int = 100

    def validate(self) -> None:
        if type(self.course_id) is not int or self.course_id <= 0:
            raise ValueError("Выберите трассу")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("Seed: целое число от 0 до 4294967295")
        if any(type(v) is not int or v not in range(1, 5) for v in (self.ground_condition, self.weather, self.season)):
            raise ValueError("Неизвестные условия гонки")
        if type(self.time_of_day) is not int or self.time_of_day not in range(0,6):
            raise ValueError("Неизвестное время суток")
        if type(self.grade) is not int or self.grade not in (100,200,300,400,500,600,700,800):
            raise ValueError("Неизвестный класс гонки")


def save_builds(path: Path, runners: list[Runner]) -> None:
    if not 1 <= len(runners) <= 18:
        raise ValueError("Нужно от 1 до 18 участников")
    for r in runners:
        r.validate()
    content = json.dumps({"schema_version": 1, "runners": [asdict(r) for r in runners]}, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def load_builds(path: Path) -> list[Runner]:
    if path.stat().st_size > 2_000_000:
        raise ValueError("Файл билдов слишком большой")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Неподдерживаемая версия файла билдов")
    items = payload.get("runners")
    if not isinstance(items, list) or not 1 <= len(items) <= 18:
        raise ValueError("Нужно от 1 до 18 участников")
    try:
        runners = [Runner(**item) for item in items]
        for r in runners:
            r.validate()
    except (TypeError, KeyError, AttributeError) as e:
        raise ValueError("Некорректная структура билда") from e
    return runners
