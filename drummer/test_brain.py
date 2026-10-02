#!/usr/bin/env python3
"""Checks for the AI drummer's brain (no Pd needed):  python3 drummer/test_brain.py"""
import os, random, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import Drummer, messages
from grooves import GROOVES, KICK, SNARE


def hits(vel):
    return sum(1 for v in vel if v)


class BrainTest(unittest.TestCase):
    def test_backbone_always_plays(self):
        for g, (name, groove) in enumerate(GROOVES):
            d = Drummer(random.Random(g))
            for k in range(8):
                _, vel, _ = d.pattern(32, 125, g, 0.0, 0.0, k)
                for role, lst in groove.items():
                    for step, v, chance in lst:
                        if chance >= 1 and role in (KICK, SNARE):
                            for bar in range(2):
                                self.assertTrue(vel[(bar * 16 + step) * 8 + role], f'{name} {role} {step}')

    def test_density_adds_hits(self):
        counts = []
        for dens in (0.0, 0.5, 1.0):
            counts.append(sum(hits(Drummer(random.Random(s)).pattern(64, 125, 3, dens, 0.3, 0)[1]) for s in range(20)))
        self.assertLess(counts[0], counts[1]); self.assertLess(counts[1], counts[2])

    def test_passes_vary_but_stay_close(self):
        d = Drummer(random.Random(7))
        pats = [d.pattern(32, 125, 0, 0.6, 0.0, k)[1] for k in range(12)]
        self.assertGreater(len({tuple(p) for p in pats}), 3)            # it varies
        for a, b in zip(pats, pats[1:]):                                 # but one pass follows on from the last
            diff = sum(1 for x, y in zip(a, b) if bool(x) != bool(y))
            self.assertLess(diff, 12)

    def test_humanize_bounds(self):
        d = Drummer(random.Random(1))
        _, vel, off = d.pattern(32, 125, 1, 0.5, 0.0, 0)
        self.assertTrue(all(o == 0 for o in off))                        # humanize 0 = on the grid
        _, vel, off = d.pattern(256, 40, 3, 1.0, 1.0, 1)
        self.assertTrue(all(abs(o) <= 0.45 * 40 + 1e-9 for o in off))  # never more than ~half a 16th
        self.assertTrue(all(0 <= v <= 127 for v in vel))
        self.assertTrue(any(o < 0 for o in off) and any(o > 0 for o in off))

    def test_same_pass_again_is_recomputed_not_evolved(self):
        a, b = Drummer(random.Random(3)), Drummer(random.Random(3))
        for k in range(3):
            a.pattern(32, 125, 0, 0.5, 0.3, k)
            b.pattern(32, 125, 0, 0.5, 0.3, k)
        b.pattern(32, 125, 0, 0.9, 0.3, 3)                                # a knob moved: pass 3 asked twice
        b.pattern(32, 125, 0, 0.9, 0.3, 3)
        on_before = dict(b.on)
        b.pattern(32, 125, 0, 0.9, 0.3, 3)
        self.assertEqual(set(on_before), set(b.on))

    def test_message_format(self):
        pat = Drummer(random.Random(0)).pattern(16, 125, 0, 0.5, 0.3, 5)
        text = messages(pat, 16, 5)
        lines = text.strip().split('\n')
        self.assertTrue(lines[0].startswith('drmnext 0 ') and lines[0].endswith(';'))
        self.assertEqual(len(lines[0].split()) - 2, 16 * 8)
        self.assertEqual(len(lines[1].split()) - 2, 16 * 8)
        self.assertEqual(lines[2], 'drmready 16 5;')


if __name__ == '__main__':
    unittest.main()
