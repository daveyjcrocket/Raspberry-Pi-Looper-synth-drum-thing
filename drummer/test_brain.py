#!/usr/bin/env python3
"""Checks for the AI drummer's brain and ears (no Pd needed):  python3 drummer/test_brain.py"""
import os, random, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import Drummer, messages, handle, phrase_bars
from grooves import GROOVES, KICK, SNARE, HAT, OPEN, RIDE, TOM_HI, TOM_LO, METERS, meter_of, grooves_in
from listen import Ears, grid, grid68


def hits(vel):
    return sum(1 for v in vel if v)


class BrainTest(unittest.TestCase):
    def test_backbone_always_plays(self):
        for g, (name, groove) in enumerate(GROOVES):
            S = meter_of(g)[1]
            d = Drummer(random.Random(g))
            for k in range(8):
                _, vel, _ = d.pattern(2 * S, 125, g, 0.0, 0.0, k, autofill=0)
                for role, lst in groove.items():
                    for step, v, chance in lst:
                        if chance >= 1 and role in (KICK, SNARE):
                            for bar in range(2):
                                self.assertTrue(vel[(bar * S + step) * 8 + role], f'{name} {role} {step}')

    def test_density_adds_hits(self):
        counts = []
        for dens in (0.0, 0.5, 1.0):
            counts.append(sum(hits(Drummer(random.Random(s)).pattern(64, 125, 3, dens, 0.3, 0)[1]) for s in range(20)))
        self.assertLess(counts[0], counts[1]); self.assertLess(counts[1], counts[2])

    def test_passes_vary_but_stay_close(self):
        d = Drummer(random.Random(7))
        pats = [d.pattern(32, 125, 0, 0.6, 0.0, k, autofill=0)[1] for k in range(12)]
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

    def test_auto_fills_every_phrase(self):
        d = Drummer(random.Random(2))
        self.assertEqual(phrase_bars(2, 0.5), 8)
        self.assertEqual(phrase_bars(2, 0.7), 4)
        self.assertEqual(phrase_bars(3, 0.7), 3)
        self.assertEqual(phrase_bars(16, 0.5), 8)
        filled = []
        for k in range(8):                                               # 2-bar loop, density 0.5: every 8 bars
            vel = d.pattern(32, 125, 0, 0.5, 0.0, k)[1]
            toms_or_rolls = [s for s in range(32) if vel[s * 8 + TOM_HI] or vel[s * 8 + TOM_LO]
                             or (s % 16 >= 12 and vel[s * 8 + SNARE] >= 70 and not vel[s * 8 + HAT])]
            filled.append(any(s >= 28 for s in toms_or_rolls))
            if k == 4:                                                   # the downbeat after the fill
                self.assertGreaterEqual(vel[0 * 8 + OPEN], 100)
        self.assertEqual(filled, [False, False, False, True, False, False, False, True])
        off = Drummer(random.Random(2))
        for k in range(8):
            vel = off.pattern(32, 125, 0, 0.5, 0.0, k, autofill=0)[1]
            self.assertFalse(any(vel[s * 8 + TOM_LO] for s in range(32)))

    def test_fills_in_three_and_six_eight(self):
        for name, S, last_beat in (('waltz', 12, range(8, 12)), ('6/8 ballad', 12, range(6, 12))):
            g = [n for n, _ in GROOVES].index(name)
            d = Drummer(random.Random(4))
            vel = [d.pattern(2 * S, 125, g, 0.5, 0.0, k)[1] for k in range(4)][3]   # 2 bars: fill at pass 4
            fill = {s for s in range(2 * S) if vel[s * 8 + TOM_HI] or vel[s * 8 + TOM_LO] or vel[s * 8 + SNARE] >= 80}
            self.assertTrue(fill & {S + s for s in last_beat}, (name, sorted(fill)))
            self.assertFalse(any(vel[(S + s) * 8 + HAT] for s in last_beat), name)   # the kit stops for it

    def test_chorus_is_bigger(self):
        def count(part):
            return sum(hits(Drummer(random.Random(s)).pattern(32, 125, 0, 0.4, 0.0, 1, 2, 0, part)[1]) for s in range(30))
        self.assertLess(count(0), count(1))
        vel = Drummer(random.Random(0)).pattern(32, 125, 0, 0.4, 0.0, 1, 2, 0, 1)[1]
        self.assertTrue(any(vel[s * 8 + RIDE] for s in range(32)))                   # rock's chorus: ride
        self.assertGreaterEqual(vel[0 * 8 + OPEN], 100)                                # and a crash in

    def test_layers_raise_the_intensity(self):
        def count(layers):
            return sum(hits(Drummer(random.Random(s)).pattern(32, 125, 0, 0.5, 0.0, 0, layers, 0)[1]) for s in range(30))
        self.assertLess(count(1), count(3))
        self.assertLess(count(3), count(6))
        vel = Drummer(random.Random(0)).pattern(32, 125, 0, 0.7, 0.0, 0, 5, 0)[1]     # a big band: ride, not hats
        self.assertTrue(any(vel[s * 8 + RIDE] for s in range(32)))
        self.assertFalse(any(vel[s * 8 + HAT] for s in range(32)))

    def test_message_protocol(self):
        d = Drummer(random.Random(0))
        self.assertEqual(handle(d, ['bogus', 'x']), '')
        self.assertTrue(handle(d, 'loop 32 125 0 0.5 0.3 0 2 1'.split()).endswith('drmready 32 0;\n'))
        self.assertTrue(handle(d, 'loop 32 125 0 0.5 0.3 1 2'.split()).endswith('drmready 32 1;\n'))
        handle(d, 'listen 0 0'.split())
        for t, w, b, m in synth(120, 2, 50, rng=random.Random(0)):
            handle(d, ['on', str(t), str(w), str(b), str(m)])
        reply = handle(d, 'heard 4000 0 0 4'.split())
        self.assertTrue(reply.startswith('drmfeel 120.000 50 ') and reply.endswith(' 0 0;\n'), reply)
        g = reply.split()[3]
        self.assertEqual(handle(d, 'fix 4000 0 -1 0 0 2'.split()), 'drmfeel 60.000 50 %s 0 1;\n' % g)
        self.assertTrue(handle(d, 'fix 4000 0 1 3 0 1'.split()).startswith('drmfeel 120.000 67 '))
        self.assertTrue(handle(d, 'loop 24 125 5 0.5 0.3 2 2 1 1'.split()).endswith('drmready 24 2;\n'))
        meter = handle(d, 'fix 4000 0 0 0 0 2 1'.split()).split()                 # next meter: 3/4
        self.assertEqual(meter[-1], '0;')
        self.assertIn(int(meter[3]), grooves_in('3/4'))
        self.assertEqual(d.ears.meter, '3/4')


def synth3(meter, bpm, bars, rng, kind='eighths'):
    """Onsets of a 3/4 or 6/8 loop: 8ths with the meter's accents (3/4: every quarter,
    6/8: every dotted quarter), or quarters only (a 'waltz')."""
    S, Q, bpb = METERS[meter]
    beat = 60000 / bpm
    pos = grid68(beat) if meter == '6/8' else grid(beat, 50)
    out = []
    for b in range(bars * bpb):
        for k in range(0, Q, 2):
            if kind == 'waltz' and k:
                continue
            w = (100 if k == 0 else 55) * rng.uniform(0.85, 1.1)
            out.append((b * beat + pos[k] + rng.gauss(0, 4), w, 2 if k == 0 and b % bpb == 0 else 7, 1))
    return out


def synth(bpm, bars, swing, kind='8ths', rng=None, slop=8.0, low_on=(0, 8)):
    """Onsets of a played loop: 8ths, 16ths, sparse or floor (a low hit on every beat)."""
    rng = rng or random.Random(0)
    beat = 60000 / bpm
    pos = grid(beat, swing)
    out = []
    for b in range(bars * 4):
        for k in range(4):
            st = (b % 4) * 4 + k
            if kind in ('8ths', 'floor') and k % 2 or kind == 'quarters' and k:
                continue
            if kind == 'sparse' and st not in (0, 6, 10):
                continue
            if kind == '16ths' and k and rng.random() < 0.3:
                continue
            low = st in low_on or kind == 'floor' and k == 0
            w = (100 if k == 0 else 70 if k == 2 else 50) * rng.uniform(0.8, 1.1)
            out.append((b * beat + pos[k] + rng.gauss(0, slop / 2), w, 2 if low else 7, 1))
    return out


class EarsTest(unittest.TestCase):
    def read(self, ons, length, tap=0):
        e = Ears()
        e.listen(0, 0)
        for o in ons:
            e.onset(*o)
        bpm, swing, groove = e.analyse(length, tap, 0, 0)
        return e, bpm, swing, GROOVES[groove][0]

    def test_tempo_and_swing(self):
        rng = random.Random(4)
        for bpm in (85, 96, 110, 124):
            for swing in (50, 58, 62):
                for bars in (1, 2, 4):
                    _, b, s, _ = self.read(synth(bpm, bars, swing, rng=rng), bars * 240000 / bpm)
                    self.assertAlmostEqual(b, bpm, delta=0.5, msg=(bpm, swing, bars))
                    self.assertLessEqual(abs(s - swing), 3, (bpm, swing, bars, s))

    def test_meters(self):
        rng = random.Random(9)
        for meter, kind, bpms in (('3/4', 'eighths', (90, 120, 150)), ('3/4', 'waltz', (90, 120)),
                                  ('6/8', 'eighths', (50, 65, 80))):
            bpb = METERS[meter][2]
            for bpm in bpms:
                for bars in (1, 2, 4):
                    e, b, _, name = self.read(synth3(meter, bpm, bars, rng, kind), bars * bpb * 60000 / bpm)
                    self.assertEqual(e.meter, meter, (meter, kind, bpm, bars))
                    self.assertAlmostEqual(b, bpm, delta=0.5, msg=(meter, kind, bpm, bars))
                    self.assertIn([n for n, _ in GROOVES].index(name), grooves_in(meter))
        e, _, _, _ = self.read(synth(100, 2, 50, '8ths', rng), 4800)
        self.assertEqual(e.meter, '4/4')

    def test_tap_sets_the_bars(self):
        ons = [(t, w, b, m) for t, w, b, m in synth(70, 4, 50, 'quarters')]     # quarters: 70 or 140?
        _, b, _, _ = self.read(ons, 4 * 240000 / 70, tap=139)
        self.assertAlmostEqual(b, 140, delta=0.5)

    def test_midi_and_its_audio_echo_count_once(self):
        e = Ears()
        e.listen(0, 0)
        e.onset(1000, 100, 2, 1)
        e.onset(1014, 80, 3, 0)                                          # bonk~ hears the same note
        e.onset(1510, 80, 7, 0)
        from listen import prepare
        self.assertEqual([round(t) for t, _, _ in prepare(e.onsets, 4000)], [1000, 1500])

    def test_kick_ring_is_not_a_note(self):
        from listen import prepare
        ons = [(10, 94, 4.3, 0), (117, 21, 3.7, 0), (275, 38, 7.1, 0), (300, 30, 7.0, 0)]
        self.assertEqual([round(t) for t, _, _ in prepare(ons, 3200)], [0, 265, 290])

    def test_rebonk_offset_folds_into_the_loop(self):
        e = Ears()
        e.listen(1, 3000)                                                # listening started 3 s into a 4 s loop
        e.onset(1510, 90, 7, 0)
        from listen import prepare
        self.assertEqual([round(t) for t, _, _ in prepare(e.onsets, 4000)], [500])

    def test_groove_choice(self):
        rng = random.Random(5)
        self.assertEqual(self.read(synth(100, 2, 50, '16ths', rng), 4800)[3], 'funk')
        self.assertEqual(self.read(synth(120, 2, 50, 'floor', rng), 4000)[3], 'four on the floor')
        self.assertEqual(self.read(synth(100, 2, 50, 'sparse', rng), 4800)[3], 'half-time')
        self.assertEqual(self.read(synth(100, 2, 66, '8ths', rng), 4800)[3], 'ride')
        self.assertEqual(self.read(synth(100, 2, 50, '8ths', rng), 4800)[3], 'rock')

    def test_rebonk_changes_the_groove(self):
        e = Ears()
        for src in (0, 1):
            e.listen(src, 0)
            for o in synth(100, 2, 50, '8ths', random.Random(6)):
                e.onset(*o)
            g = e.analyse(4800, 0, src, 0)[2]
            self.assertEqual(GROOVES[g][0], 'rock' if src == 0 else GROOVES[g][0])
        self.assertNotEqual(g, 0)                                        # rebonk while rock plays: not rock
        self.assertIn(g, grooves_in('4/4'))                              # ... but still 4/4

    def test_kick_follows_low_accents(self):
        e, _, _, name = self.read(synth(100, 2, 50, '8ths', random.Random(7), low_on=(0, 6, 8, 14)), 4800)
        kicks = {s for s, _, _ in e.groove_for(e.groove)[KICK]}
        self.assertTrue({6, 14} <= kicks, kicks)


if __name__ == '__main__':
    unittest.main()
