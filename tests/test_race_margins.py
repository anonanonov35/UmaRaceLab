import math
import unittest

from uma_lab.race_margins import CATEGORIES, build_finish_margins, format_board_time
from uma_lab.engine import simulate
from uma_lab.models import Runner, RaceConfig
from test_core import FixtureData


NATIVE_FIXTURE={'constants':{'DIFFTIME_TO_LENGTH':15.},
                'horse_length_enum':{c[0]:i for i,c in enumerate(CATEGORIES)},
                'metadata_sha256':'synthetic-test-fixture','native_bodies_recovered':False}


class FinishMarginTests(unittest.TestCase):
    def test_reference_is_previous_finisher_in_unsorted_gate_order(self):
        times=[90.7,90.,90.5]
        margins,rules=build_finish_margins(times,NATIVE_FIXTURE)
        self.assertIsNone(margins[1])
        self.assertEqual(margins[2]['previous_runner'],1)
        self.assertEqual(margins[0]['previous_runner'],2)
        self.assertAlmostEqual(margins[0]['seconds'],.2)
        self.assertAlmostEqual(margins[0]['metres'],3.)
        self.assertEqual(margins[0]['label'],'1 1/4 L')
        self.assertTrue(margins[0]['approximate'])
        self.assertIn('unverified',rules['category_status'])

    def test_photo_finish_uses_full_precision_before_table_rounding(self):
        margins,_=build_finish_margins([90.,90.009,90.027,90.067],NATIVE_FIXTURE)
        self.assertEqual([r['label'] for r in margins[1:]],['Nose','Head','Neck'])

    def test_all_model_cutoffs_and_large_margin(self):
        # Both sides of each presentation cutoff; this validates our stated
        # model, not a claim that the game's unrecovered rounding is identical.
        for index,(_,label,metres) in enumerate(CATEGORIES[:-1]):
            with self.subTest(label=label):
                below,_=build_finish_margins([1.,1.+(metres-1e-6)/15],NATIVE_FIXTURE)
                above,_=build_finish_margins([1.,1.+(metres+1e-6)/15],NATIVE_FIXTURE)
                self.assertEqual(below[1]['label'],label)
                self.assertEqual(above[1]['label'],CATEGORIES[index+1][1])
        self.assertEqual(build_finish_margins([1.,5.],NATIVE_FIXTURE)[0][1]['label'],'Distance')

    def test_missing_local_metadata_does_not_invent_native_evidence(self):
        margins,rules=build_finish_margins([90.,91.],None)
        self.assertEqual(margins,[None,None])
        self.assertIn('unavailable',rules)

    def test_board_time_format(self):
        self.assertEqual(format_board_time(89.999),'1:29.9')
        self.assertEqual(format_board_time(90.),'1:30.0')
        self.assertEqual(format_board_time(600.),'10:00.0')

    def test_native_ids_do_not_depend_on_our_category_order(self):
        native={**NATIVE_FIXTURE,'horse_length_enum':{key:123+value for key,value in NATIVE_FIXTURE['horse_length_enum'].items()}}
        margins,_=build_finish_margins([90.,90.001],native)
        self.assertEqual(margins[1]['native_enum_value'],123)

    def test_presentation_has_no_effect_on_race_or_ranking(self):
        class WithRules(FixtureData):
            finish_rules=NATIVE_FIXTURE
        runners=[Runner(speed=1800),Runner(speed=1750),Runner(speed=1200)]
        a=simulate(runners,RaceConfig(1),FixtureData())
        b=simulate(runners,RaceConfig(1),WithRules())
        self.assertEqual(a.frames,b.frames)
        self.assertEqual(a.events,b.events)
        self.assertEqual(a.finish_times,b.finish_times)
        self.assertEqual(a.display_finish_times,b.display_finish_times)
        order=sorted(range(3),key=lambda i:b.finish_times[i])
        self.assertIsNone(b.finish_margins[order[0]])
        for prev,index in zip(order,order[1:]):
            self.assertEqual(b.finish_margins[index]['previous_runner'],prev)
        for event in b.events:
            if event['kind']=='finished':
                self.assertEqual(event['time'],b.finish_times[event['runner']])

    def test_invalid_times(self):
        for times in ([],[math.nan],[math.inf],[0.],[-1.]):
            with self.subTest(times=times),self.assertRaises(ValueError):
                build_finish_margins(times,NATIVE_FIXTURE)


if __name__=='__main__':unittest.main()
