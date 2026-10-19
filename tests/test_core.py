from dataclasses import asdict, replace
import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from uma_lab.conditions import parse_condition, skill_support
from uma_lab.engine import base_speed, phase_at, simulate
from uma_lab.models import RaceConfig, Runner, load_builds, save_builds
from uma_lab.data import GameData
from tools.compare_trace import compare


class FixtureData:
    fingerprint = "synthetic-test-fixture"
    def __init__(self):
        self.skills = {}
    def course(self, key):
        return {"id": key, "distance": 2000, "ground": 1, "turn": 1, "race_track_id": 1, "name": "Synthetic flat test",
                'geometry':{'distance':2000,'points':[[0,0,0],[2000,0,0]],'corners':[],
                            'straights':[{'start':0,'end':2000,'frontType':1}],'slopes':[]}}
    def rate(self, table, key, column="proper_rate"):
        if table == "race_motivation_rate":
            return (0, .96, .98, 1., 1.02, 1.04)[key]
        if table == "race_proper_distance_rate":
            return (0, .1, .2, .4, .6, .8, .9, 1., 1.05)[key] if column == "proper_rate_speed" else (0, .4, .5, .6, 1., 1., 1., 1., 1.)[key]
        return (0, .1, .3, .5, .7, .8, .9, 1., 1.05)[key]


def skill(kind=27, condition="remain_distance<=300", value=3500):
    s = {"id": 1, "group_id": 1, "rarity": 1, "name": "Synthetic test effect", "condition_1": condition,
         "condition_2": "", "precondition_1": "", "activate_lot": 0, "float_ability_time_1": 50000}
    for slot in range(1, 4):
        s[f"ability_type_1_{slot}"] = kind if slot == 1 else 0
        s[f"target_type_1_{slot}"] = 1
        s[f"float_ability_value_1_{slot}"] = value if slot == 1 else 0
    return s


class LegacyConditionParserTests(unittest.TestCase):
    def test_precedence_and_or(self):
        c = parse_condition("phase>=2&hp_per<30@weather==3")
        self.assertTrue(c.matches({"phase": 1, "hp_per": 90, "weather": 3}))
        self.assertFalse(c.matches({"phase": 2, "hp_per": 40, "weather": 1}))

    def test_fail_closed(self):
        for expression in ("order<=3", "phase_random==1", "phase==1@", "__import__('os')", "phase==1|phase==2"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                parse_condition(expression)

    def test_unknown_any_branch_rejected(self):
        self.assertFalse(skill_support(skill(condition="phase>=2@blocked_front==1"))[0])

    def test_unique_and_second_branch_rejected(self):
        s = skill()
        s["rarity"] = 3
        self.assertFalse(skill_support(s)[0])
        s["rarity"] = 1
        s["condition_2"] = "phase>=2"
        self.assertFalse(skill_support(s)[0])


class ModelTests(unittest.TestCase):
    def test_build_roundtrip(self):
        runners = [Runner(name="Проверка", skills=[5, 11], unique_level=4, mood=5, speed=1500)]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "builds.json"
            save_builds(p, runners)
            self.assertEqual(load_builds(p), runners)

    def test_bad_inputs(self):
        for patch in ({"speed": 0}, {"guts": -1}, {"wisdom": float("nan")}, {"skills": [1, 1]}, {"mood": 6}, {"distance_aptitude": None}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                replace(Runner(), **patch).validate()
        with self.assertRaises(ValueError):
            RaceConfig(1, seed=-1).validate()

    def test_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "builds.json"
            p.write_text('{"schema_version":2,"runners":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_builds(p)


class EngineTests(unittest.TestCase):
    def test_reproducibility_and_not_mutating_build(self):
        runner = Runner()
        before = asdict(runner)
        d, cfg = FixtureData(), RaceConfig(1)
        a = simulate([runner], cfg, d)
        b = simulate([runner], cfg, d)
        self.assertEqual(a, b)
        self.assertEqual(before, asdict(runner))
        self.assertEqual(a.database_sha256, d.fingerprint)

    def test_seed_changes_trace(self):
        a = simulate([Runner()], RaceConfig(1, seed=1), FixtureData())
        b = simulate([Runner()], RaceConfig(1, seed=2), FixtureData())
        self.assertNotEqual(a.finish_times, b.finish_times)

    def test_frames_and_finish_invariants(self):
        result = simulate([Runner(), Runner(strategy=4)], RaceConfig(1), FixtureData())
        for idx in range(2):
            positions = [f["runners"][idx]["distance"] for f in result.frames]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(positions[-1], 2000)
            self.assertTrue(all(0 <= f["runners"][idx]["hp_ratio"] <= 1 for f in result.frames))
            self.assertLess(result.finish_times[idx], result.frames[-1]["time"] + .000001)
        json.dumps(result.to_dict(), allow_nan=False)

    def test_faster_speed_improves_flat_run(self):
        slow = simulate([Runner(speed=500)], RaceConfig(1), FixtureData())
        fast = simulate([Runner(speed=1200)], RaceConfig(1), FixtureData())
        self.assertLess(fast.finish_times[0], slow.finish_times[0])

    def test_unsupported_skill_blocks_instead_of_ignored(self):
        d = FixtureData()
        d.skills[1] = skill(condition="nonexistent_condition==1")
        with self.assertRaisesRegex(ValueError, "nonexistent_condition"):
            simulate([Runner(skills=[1])], RaceConfig(1), d)

    def test_effect_changes_outcome_and_logs_activation(self):
        d = FixtureData()
        d.skills[1] = skill(value=10000)
        baseline = simulate([Runner()], RaceConfig(1), d)
        with_skill = simulate([Runner(skills=[1])], RaceConfig(1), d)
        self.assertLess(with_skill.finish_times[0], baseline.finish_times[0])
        self.assertEqual(sum(e["kind"] == "skill-activated" for e in with_skill.events), 1)

    def test_passive_condition_is_not_unconditional(self):
        d = FixtureData()
        d.skills[1] = skill(kind=1, condition="weather==3", value=600000)
        dry = simulate([Runner(skills=[1])], RaceConfig(1), d)
        baseline = simulate([Runner()], RaceConfig(1), d)
        self.assertEqual(dry.finish_times, baseline.finish_times)

    def test_missing_skill_rejected(self):
        for r in [Runner(skills=[999])]:
            with self.assertRaises(ValueError):
                simulate([r], RaceConfig(1), FixtureData())

    def test_stats_above_1200_are_not_clamped(self):
        baseline=simulate([Runner(speed=1200,stamina=1500)],RaceConfig(1),FixtureData())
        high=simulate([Runner(speed=1800,stamina=1500)],RaceConfig(1),FixtureData())
        self.assertLess(high.finish_times[0],baseline.finish_times[0])

    def test_native_clock_has_no_negative_first_second(self):
        result=simulate([Runner()],RaceConfig(1),FixtureData())
        self.assertGreaterEqual(result.frames[0]['time'],0)
        self.assertTrue(all(a['time']<b['time'] for a,b in zip(result.frames,result.frames[1:])))

    def test_corner_and_slope_gate_the_actual_activation(self):
        class TerrainData(FixtureData):
            def course(self,key):
                c=super().course(key)
                c['geometry']['corners']=[{'start':500,'length':300}]
                c['geometry']['slopes']=[{'start':1000,'length':200,'slope':15000}]
                return c
        for condition,start,end in [('corner!=0',500,800),('slope==1',1000,1200)]:
            data=TerrainData();data.skills[1]=skill(condition=condition);data.skills[1]['rarity']=3
            result=simulate([Runner(skills=[1])],RaceConfig(1),data)
            events=[e for e in result.events if e['kind']=='skill-activated']
            self.assertEqual(len(events),1)
            self.assertGreaterEqual(events[0]['distance'],start)
            self.assertLess(events[0]['distance'],end)

    def test_conflicting_skill_levels_rejected(self):
        d = FixtureData()
        d.skills = {1: skill(), 2: skill()}
        with self.assertRaisesRegex(ValueError, "групп"):
            simulate([Runner(skills=[1, 2])], RaceConfig(1), d)

    def test_phase_boundaries(self):
        self.assertEqual(base_speed(2000), 20)
        self.assertEqual(phase_at(299.999, 1800), 0)
        self.assertEqual(phase_at(300, 1800), 1)
        self.assertEqual(phase_at(1200, 1800), 2)


class OracleTests(unittest.TestCase):
    def test_interpolation_and_missing_fields(self):
        result = {"model": "test", "frames": [{"time": t, "runners": [{"distance": t*10, "speed": 10, "hp": 100-t}]} for t in (0, 1, 2)]}
        reference = {"samples": [{"time": .5, "distance": 5}, {"time": 1.5, "distance": 15}, {"time": 3, "distance": 30}]}
        report = compare(reference, result)
        self.assertEqual(report["metrics"]["distance"]["mae"], 0)
        self.assertNotIn("hp", report["metrics"])
        self.assertEqual(report["out_of_range_samples"], 1)

    def test_invalid_reference_rejected(self):
        result = {"frames": [{"time": 0, "runners": [{"distance": 0, "speed": 3, "hp": 100}]}]}
        with self.assertRaises(ValueError):
            compare({"samples": [{"time": 5, "distance": 1}]}, result)


class DatabaseTests(unittest.TestCase):
    def create_db(self, path):
        con = sqlite3.connect(path)
        con.executescript('''
            CREATE TABLE text_data (category INTEGER, "index" INTEGER, text TEXT);
            CREATE TABLE chara_data (id INTEGER);
            CREATE TABLE race_course_set (id INTEGER, race_track_id INTEGER, distance INTEGER, ground INTEGER, turn INTEGER);
            CREATE TABLE skill_data (id INTEGER);
            CREATE TABLE race_proper_distance_rate (id INTEGER, proper_rate_speed INTEGER, proper_rate_power INTEGER);
            CREATE TABLE race_proper_ground_rate (id INTEGER, proper_rate INTEGER);
            CREATE TABLE race_proper_runningstyle_rate (id INTEGER, proper_rate INTEGER);
            CREATE TABLE race_motivation_rate (id INTEGER, motivation_rate INTEGER);
            INSERT INTO text_data VALUES (6, 1, 'Synthetic Name');
            INSERT INTO chara_data VALUES (1);
        ''')
        con.close()

    def test_read_only_catalog_does_not_change_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master.mdb"
            self.create_db(path)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            data = GameData(path)
            data.reload()
            self.assertEqual(data.characters[0]["name"], "Synthetic Name")
            self.assertFalse(data.changed())
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_committed_wal_update_is_detected_and_reflected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "master.mdb"
            self.create_db(path)
            writer = sqlite3.connect(path)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                data = GameData(path)
                old_hash = data.fingerprint
                writer.execute("UPDATE text_data SET text='Updated synthetic name'")
                writer.commit()
                self.assertTrue(data.changed())
                data.reload()
                self.assertEqual(data.characters[0]["name"], "Updated synthetic name")
                self.assertNotEqual(data.fingerprint, old_hash)
                self.assertFalse(data.changed())
            finally:
                writer.close()


if __name__ == "__main__":
    unittest.main()
