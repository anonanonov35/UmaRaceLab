"""The game DB is always opened in read-only mode; no connection is held during races."""
from __future__ import annotations
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import struct
from .courses import CourseCatalog
from .race_margins import read_finish_rules
from .build_catalog import card_catalog

DEFAULT_INSTALL = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby")


def find_database(path: Path) -> Path:
    candidates = [path] if path.is_file() else [
        path / "UmamusumePrettyDerby_Data/Persistent/master/master.mdb",
        path / "master/master.mdb", path / "master.mdb",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError("Не найдена master.mdb. Выберите папку установленной игры или сам файл базы.")


class GameData:
    def __init__(self, path: Path):
        self.path = find_database(path)
        self.reload()

    def _source_signature(self):
        main = self.path.stat()
        wal = Path(str(self.path) + "-wal")
        try:
            wal_stat = wal.stat()
            wal_signature = (wal_stat.st_size, wal_stat.st_mtime_ns)
        except FileNotFoundError:
            wal_signature = None
        return main.st_size, main.st_mtime_ns, wal_signature

    def reload(self) -> None:
        # Retry once if an updater replaced the DB between reading and hashing.
        for attempt in range(2):
            before = self._source_signature()
            with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
                c.execute("PRAGMA query_only=ON")
                c.execute("BEGIN")
                c.row_factory = sqlite3.Row
                def rows(table: str) -> list[dict]:
                    return [dict(r) for r in c.execute('SELECT * FROM "' + table + '"')]
                texts = {(r["category"], r["index"]): r["text"] for r in rows("text_data")}
                characters = [{"id": r["id"], "name": texts.get((6, r["id"]), str(r["id"]))} for r in rows("chara_data")]
                courses = rows("race_course_set")
                for course in courses:
                    course["name"] = texts.get((35, course["race_track_id"]), f"Track {course['race_track_id']}")
                skills = {r["id"]: r for r in rows("skill_data")}
                for sid, skill in skills.items():
                    skill["name"] = texts.get((47, sid), f"Skill {sid}")
                    skill["description"] = texts.get((48, sid), "")
                rates = {name: {r["id"]: r for r in rows(name)} for name in (
                    "race_proper_distance_rate", "race_proper_ground_rate",
                    "race_proper_runningstyle_rate", "race_motivation_rate")}
                tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                levels = {(r["ability_type"],r["level"]): r["float_ability_value_coef"] / 10000 for r in rows("skill_level_value")} if "skill_level_value" in tables else {}
                cards = rows("card_data") if "card_data" in tables else []
                rarities = rows('card_rarity_data') if 'card_rarity_data' in tables else []
                skill_sets = rows('skill_set') if 'skill_set' in tables else []
                # SQLite serializes this read transaction, including any committed WAL pages.
                # The hash identifies the exact DB snapshot that supplied all parameters.
                sha = hashlib.sha256(c.serialize()).hexdigest()
            after = self._source_signature()
            if before == after:
                self.characters, self.courses, self.skills, self.rates = characters, courses, skills, rates
                self.fingerprint = sha
                self.source_signature = after
                self.skill_levels = levels
                self.variants = card_catalog(cards, rarities, skill_sets, skills, texts)
                self.catalog = CourseCatalog(self.path,self.fingerprint)
                metadata = self.path.parents[2] / 'il2cpp_data/Metadata/global-metadata.dat' if len(self.path.parents)>2 else None
                self.finish_rules, self.finish_rules_error = None, None
                if metadata is not None and metadata.is_file():
                    try:
                        self.finish_rules = read_finish_rules(metadata)
                    except (ValueError, OSError, IndexError, struct.error) as error:
                        self.finish_rules_error = str(error)
                break
        else:
            raise ValueError("Игра обновляет базу. Повторите обновление справочника после завершения загрузки.")

    def course(self, course_id: int) -> dict:
        for course in self.courses:
            if course["id"] == course_id:
                result = course.copy()
                if self.catalog.payload:
                    result["geometry"] = self.catalog.get(course_id)
                return result
        raise ValueError(f"В базе нет трассы {course_id}")

    def ensure_course_catalog(self):
        self.catalog=CourseCatalog(self.path,self.fingerprint)
        if not self.catalog.payload:
            from tools.build_course_catalog import build
            build(self.path)
            self.catalog=CourseCatalog(self.path,self.fingerprint)
            if not self.catalog.payload:
                raise ValueError('Данные изменились во время извлечения трасс. Обновите справочник и повторите расчёт.')

    def rate(self, table: str, key: int, column: str = "proper_rate") -> float:
        return self.rates[table][key][column] / 10000

    def changed(self) -> bool:
        return self._source_signature() != self.source_signature

    def course_label(self, course: dict) -> str:
        surface = {1: "трава", 2: "грунт"}.get(course["ground"], str(course["ground"]))
        turn = {1: "правый", 2: "левый", 4: "прямой"}.get(course["turn"], str(course["turn"]))
        return f"{course['name']} · {course['distance']} м · {surface} · {turn} · #{course['id']}"
