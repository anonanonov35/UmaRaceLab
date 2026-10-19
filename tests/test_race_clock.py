from copy import deepcopy
import unittest
from uma_lab.race_clock import build_race_clock
from uma_lab.engine import simulate
from uma_lab.models import RaceConfig,Runner
from test_core import FixtureData


class RaceClockTests(unittest.TestCase):
    def setUp(self):
        self.course={'id':10804,'finish_time_min':908000,'finish_time_min_random_range':10000,
                     'finish_time_max':950000,'finish_time_max_random_range':10000}

    def test_kyoto_fast_winner_gets_course_window_not_raw_scaled_time(self):
        before=deepcopy(self.course)
        raw=[76.,74.85840263962746,75.8]
        clock=build_race_clock(raw,self.course,42,1.1799999475479126)
        self.assertEqual(clock.metadata['correction'],'lower')
        self.assertAlmostEqual(clock.scaled_finish_times[1],88.33291118828092)
        self.assertGreaterEqual(clock.display_finish_times[1],89.8)
        self.assertLess(clock.display_finish_times[1],91.8)
        self.assertIsNone(clock.display_finish_times[0])
        self.assertIsNone(clock.display_finish_times[2])
        self.assertEqual(self.course,before)
        self.assertEqual(raw,[76.,74.85840263962746,75.8])

    def test_inside_bounds_and_exact_bound_do_not_redraw(self):
        for t in (90.8,92.,95.):
            clock=build_race_clock([t,t+1],self.course,12,1.)
            self.assertEqual(clock.display_finish_times[0],t)
            self.assertEqual(clock.metadata['correction'],'none')
            self.assertIsNone(clock.metadata['presentation_draw'])

    def test_slow_winner_uses_upper_window(self):
        clock=build_race_clock([120.,130.],self.course,12,1.)
        self.assertEqual(clock.metadata['correction'],'upper')
        self.assertGreaterEqual(clock.display_finish_times[0],94.)
        self.assertLess(clock.display_finish_times[0],96.)

    def test_missing_bounds_preserve_scaled_winner_without_fabricated_others(self):
        clock=build_race_clock([74.,75.],{'id':1},12,1.18)
        self.assertEqual(clock.scaled_finish_times,[74.*1.18,75.*1.18])
        self.assertEqual(clock.display_finish_times,[74.*1.18,None])
        self.assertEqual(clock.metadata['correction'],'none')

    def test_presentation_is_deterministic_and_seed_dependent(self):
        a=build_race_clock([70.,71.],self.course,42,1.18)
        self.assertEqual(a,build_race_clock([70.,71.],self.course,42,1.18))
        self.assertNotEqual(a.display_finish_times,build_race_clock([70.,71.],self.course,43,1.18).display_finish_times)
        for seed in range(64):
            value=build_race_clock([70.],self.course,seed,1.18).display_finish_times[0]
            self.assertTrue(89.8<=value<91.8)

    def test_zero_random_range_uses_the_bound(self):
        course={**self.course,'finish_time_min_random_range':0}
        self.assertEqual(build_race_clock([70.],course,42,1.).display_finish_times,[90.8])

    def test_invalid_inputs_are_rejected(self):
        for raw,coefficient in [([],1.18),([float('nan')],1.18),([-1.],1.18),([70.],0.)]:
            with self.subTest(raw=raw,coefficient=coefficient),self.assertRaises(ValueError):
                build_race_clock(raw,self.course,42,coefficient)
        with self.assertRaises(ValueError):
            build_race_clock([70.],{**self.course,'finish_time_max':800000},42,1.18)

    def test_course_presentation_cannot_change_frames_events_or_winner(self):
        bounds=self.course
        class BoundedData(FixtureData):
            def course(self,key):return {**super().course(key),**bounds}
        runners=[Runner(speed=1800),Runner(speed=1200)]
        normal=simulate(runners,RaceConfig(10804),FixtureData())
        bounded=simulate(runners,RaceConfig(10804),BoundedData())
        self.assertEqual(normal.finish_times,bounded.finish_times)
        self.assertEqual(normal.frames,bounded.frames)
        self.assertEqual(normal.events,bounded.events)
        self.assertEqual(normal.scaled_finish_times,bounded.scaled_finish_times)


if __name__=='__main__':unittest.main()
