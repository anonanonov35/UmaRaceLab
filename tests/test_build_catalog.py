from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from uma_lab.build_catalog import card_catalog, bind_variant, find_variant, owned_unique, add_build_skill
from uma_lab.models import APTITUDE_KEYS, Runner, load_builds, save_builds
from uma_lab.engine import runner_payload


def fixture():
    from uma_lab.build_catalog import APTITUDE_COLUMNS
    cards=[{'id':41,'chara_id':7,'default_rarity':1},{'id':89,'chara_id':7,'default_rarity':3}]
    rarities=[]
    for card,stars,link in [(41,1,90),(41,2,90),(41,3,91),(89,3,92)]:
        rarities.append({'card_id':card,'rarity':stars,'skill_set':link,**{v:7 for v in APTITUDE_COLUMNS.values()}})
    skills={101:{'id':101,'rarity':3,'group_id':10},202:{'id':202,'rarity':5,'group_id':20},
            303:{'id':303,'rarity':5,'group_id':30},404:{'id':404,'rarity':1,'group_id':40},
            501:{'id':501,'rarity':1,'group_id':50},502:{'id':502,'rarity':2,'group_id':50}}
    sets=[{'id':90,'skill_id1':101},{'id':91,'skill_id1':202},{'id':92,'skill_id1':303}]
    variants=card_catalog(cards,rarities,sets,skills,{(4,41):'[Base] Test',(4,89):'[Other] Test'})
    return SimpleNamespace(skills=skills,variants=variants)


class BuildCatalogTests(unittest.TestCase):
    def test_real_relations_not_id_arithmetic(self):
        data=fixture()
        base=bind_variant(Runner(),data,41,3,reset_aptitudes=True)
        self.assertEqual((base.chara_id,base.outfit_id,base.card_rarity),(7,41,3))
        self.assertEqual(base.skills,[202])
        self.assertEqual(base.aptitudes,{key:'A' for key in APTITUDE_KEYS})
        self.assertEqual(owned_unique(bind_variant(base,data,89,3),data),303)

    def test_rarity_changes_unique_and_preserves_trained_input(self):
        data=fixture()
        old=Runner(name='Trained',chara_id=7,speed=1800,skills=[202,404,501],unique_level=6)
        before=asdict(old)
        new=bind_variant(old,data,41,1)
        self.assertEqual(new.skills,[101,404,501])
        self.assertEqual((new.speed,new.name,new.unique_level),(1800,'Trained',6))
        self.assertEqual(asdict(old),before)

    def test_legacy_inference_uses_owned_unique_and_preserves_grades(self):
        data=fixture()
        old=Runner(chara_id=7,skills=[303],distance_aptitude='S',surface_aptitude='D',strategy_aptitude='B')
        self.assertEqual(find_variant(old,data)['id'],89)
        new=bind_variant(old,data)
        self.assertEqual((new.outfit_id,new.card_rarity),(89,3))
        self.assertEqual(new.aptitudes['mile'],'S')
        self.assertEqual(new.aptitudes['dirt'],'D')
        self.assertEqual(new.aptitudes['pace'],'B')
        low=bind_variant(Runner(chara_id=7,skills=[101]),data)
        self.assertEqual((low.card_rarity,low.skills),(1,[101]))

    def test_missing_explicit_version_and_star_profile_fail(self):
        data=fixture()
        for runner,variant,stars in [(Runner(),999,3),(Runner(),89,1),(Runner(outfit_id=999),None,None)]:
            with self.subTest(variant=variant,stars=stars),self.assertRaises(ValueError):
                bind_variant(runner,data,variant,stars)
        data.variants[0]['profiles'][3]['unique_skill_id']=None
        with self.assertRaises(ValueError):bind_variant(Runner(),data,41,3)

    def test_foreign_full_unique_rejected_inherited_retained_upgrade_replaces(self):
        data=fixture()
        runner=bind_variant(Runner(skills=[404,501]),data,41,3)
        with self.assertRaises(ValueError):add_build_skill(runner,303,data)
        new=add_build_skill(runner,502,data)
        self.assertEqual(set(new.skills),{202,404,502})
        self.assertIn(501,runner.skills)

    def test_new_fields_roundtrip_and_legacy_files(self):
        data=fixture()
        runner=bind_variant(Runner(speed=1500,unique_level=6),data,89,3)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'build.json'
            save_builds(path,[runner])
            self.assertEqual(load_builds(path),[runner])
            path.write_text('{"schema_version":1,"runners":[{"name":"Old","distance_aptitude":"S"}]}',encoding='utf-8')
            old=load_builds(path)[0]
            self.assertEqual(old.aptitudes,{})
            self.assertEqual(old.race_aptitudes({'ground':1,'distance':1600})['distance'],'S')

    def test_table_validated_as_complete_grades(self):
        for grades in ({'mile':'A'},{key:'Z' for key in APTITUDE_KEYS},None):
            with self.subTest(grades=grades),self.assertRaises(ValueError):replace(Runner(),aptitudes=grades).validate()

    def test_course_and_strategy_select_appropriate_table_cells(self):
        grades={key:'A' for key in APTITUDE_KEYS}
        grades.update(sprint='G',mile='S',medium='B',long='D',turf='C',dirt='F',front='E',end='S')
        runner=Runner(aptitudes=grades,strategy=4)
        expected=[(1400,'G'),(1401,'S'),(1800,'S'),(1801,'B'),(2400,'B'),(2401,'D')]
        for distance,grade in expected:
            with self.subTest(distance=distance):
                self.assertEqual(runner.race_aptitudes({'distance':distance,'ground':2}),{'distance':grade,'surface':'F','strategy':'S'})
        payload=runner_payload(runner,0,SimpleNamespace(skills={}),{'distance':1600,'ground':1})
        self.assertEqual(payload['aptitudes'],{'distance':0,'surface':3,'strategy':0})


if __name__=='__main__':unittest.main()
