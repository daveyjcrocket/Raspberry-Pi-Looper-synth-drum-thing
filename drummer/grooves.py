"""The AI drummer's groove library, shared by tools/gen_drummer.py (Pd's fixed fallback grooves)
and drummer/brain.py (the grooves it varies every pass).

Each groove is one bar of 16ths: {role: [(step, velocity, chance), ...]}, in its meter
(GROOVE_METER): 4/4 = 16 steps, 3/4 = 12 steps (3 beats of 4), 6/8 = 12 steps (2 dotted-quarter
beats of 6, i.e. 6 eighths). The meter of the groove playing is the drummer's meter.
chance 1 = the backbone, always played. Below 1 = decoration: the brain rolls it again on
every pass (scaled by the density knob); Pd's fixed version plays the ones at 0.5 or more.
Roles are the kit sounds, in the order of the pads.
"""

KICK, SNARE, HAT, OPEN, RIM, TOM_HI, TOM_LO, RIDE = range(8)
ROLES = ['kick', 'snare', 'hat closed', 'hat open', 'rimshot', 'tom high', 'tom low', 'ride']


def eighths(vels, chance=1.0):
    """Hits on the 8ths, cycling through vels."""
    return [(s, vels[(s // 2) % len(vels)], chance) for s in range(0, 16, 2)]


def offs(steps, vel, chance):
    return [(s, vel, chance) for s in steps]


# meter -> (16th steps per bar, steps per beat, beats per bar). 6/8 counts dotted-quarter beats.
METERS = {'4/4': (16, 4, 4), '3/4': (12, 4, 3), '6/8': (12, 6, 2)}
METER_ORDER = ['4/4', '3/4', '6/8']


GROOVES = [
    ('rock', {
        KICK: [(0, 110, 1), (8, 100, 1), (10, 85, 1), (7, 70, .2), (15, 65, .15), (3, 60, .1)],
        SNARE: [(4, 110, 1), (12, 110, 1)] + offs([7, 9], 32, .3) + offs([15], 40, .2) + offs([1], 28, .1),
        HAT: eighths([95, 70, 88, 70]) + offs([3, 11], 45, .2),
        OPEN: [(14, 75, .08)],
    }),
    ('half-time', {
        KICK: [(0, 110, 1), (10, 95, 1), (7, 75, .6), (3, 65, .15), (14, 70, .2)],
        SNARE: [(8, 115, 1)] + offs([5, 11, 15], 30, .25),
        RIM: [(14, 45, .5), (6, 40, .2)],
        HAT: eighths([95, 68, 80, 68]) + offs([5, 13], 40, .2),
        OPEN: [(6, 70, .1)],
    }),
    ('four on the floor', {
        KICK: [(0, 112, 1), (4, 108, 1), (8, 112, 1), (12, 108, 1), (15, 60, .1)],
        SNARE: [(4, 100, 1), (12, 100, 1), (14, 40, .15)],
        HAT: [(0, 70, 1), (4, 65, 1), (8, 70, 1), (12, 65, 1)] + offs([1, 5, 9, 13], 40, .25),
        OPEN: [(2, 85, 1), (6, 80, 1), (10, 85, 1), (14, 80, 1)],
    }),
    ('funk', {
        KICK: [(0, 110, 1), (3, 85, 1), (10, 100, 1), (6, 70, .25), (13, 70, .2)],
        SNARE: [(4, 110, 1), (12, 110, 1), (7, 35, .6), (9, 35, .6), (15, 30, .5), (2, 28, .2), (14, 30, .2)],
        HAT: [(s, 95 if s % 4 == 0 else 75 if s % 2 == 0 else 55, 1) for s in range(16)],
        OPEN: [(6, 75, .15), (14, 75, .15)],
    }),
    ('ride', {
        KICK: [(0, 110, 1), (10, 95, 1), (7, 70, .2), (15, 60, .15)],
        SNARE: [(4, 105, 1), (12, 105, 1)] + offs([7, 9, 15], 30, .2),
        RIDE: eighths([100, 75, 90, 75]) + offs([3, 11], 50, .15),
        HAT: offs([4, 12], 50, .5),
    }),
    # ---- 3/4 (12 steps: beats at 0, 4, 8) ----
    ('waltz', {
        KICK: [(0, 110, 1), (10, 60, .2)],
        SNARE: [(4, 70, 1), (8, 70, 1), (6, 28, .2)],
        HAT: [(0, 90, 1), (4, 75, 1), (8, 75, 1)] + offs([2, 6, 10], 50, .4),
    }),
    ('3/4 rock', {
        KICK: [(0, 110, 1), (6, 80, .5), (10, 70, .2), (3, 60, .1)],
        SNARE: [(8, 108, 1), (5, 30, .2), (11, 35, .15)],
        HAT: eighths([95, 70, 85, 70, 85, 70])[:6],
        OPEN: [(10, 75, .1)],
    }),
    ('jazz waltz', {
        KICK: [(0, 95, 1), (10, 55, .15)],
        SNARE: [(7, 30, .3), (11, 32, .25), (3, 28, .15)],
        RIDE: [(0, 100, 1), (4, 85, 1), (7, 65, .7), (8, 85, 1), (11, 60, .3)],
        HAT: [(4, 50, 1), (8, 50, 1)],
    }),
    # ---- 6/8 (12 steps: eighths at 0, 2 .. 10, dotted-quarter beats at 0 and 6) ----
    ('6/8 ballad', {
        KICK: [(0, 110, 1), (10, 70, .3), (4, 60, .15)],
        SNARE: [(6, 105, 1), (11, 30, .15)],
        HAT: [(0, 90, 1), (2, 60, 1), (4, 62, 1), (6, 85, 1), (8, 60, 1), (10, 62, 1)],
        OPEN: [(10, 70, .1)],
    }),
    ('6/8 rock', {
        KICK: [(0, 112, 1), (4, 90, 1), (8, 70, .4), (10, 85, .5)],
        SNARE: [(6, 110, 1), (9, 32, .3), (11, 35, .25)],
        HAT: [(0, 95, 1), (2, 70, 1), (4, 72, 1), (6, 90, 1), (8, 70, 1), (10, 72, 1)] + offs([5, 11], 40, .2),
        OPEN: [(10, 75, .15)],
    }),
    ('6/8 blues', {
        KICK: [(0, 105, 1), (6, 75, .4), (4, 65, .3)],
        SNARE: [(6, 105, 1), (4, 30, .35), (10, 32, .35)],
        RIDE: [(0, 100, 1), (4, 75, 1), (6, 95, 1), (10, 75, 1)] + offs([2, 8], 55, .4),
        HAT: [(6, 50, .6)],
    }),
]
GROOVE_METER = ['4/4'] * 5 + ['3/4'] * 3 + ['6/8'] * 3
assert len(GROOVE_METER) == len(GROOVES)


def meter_of(g):
    """(meter name, steps per bar, steps per beat, beats per bar) of groove index g."""
    m = GROOVE_METER[g]
    return (m,) + METERS[m]


def grooves_in(meter):
    return [i for i, m in enumerate(GROOVE_METER) if m == meter]


def next_in_meter(g):
    """The next groove of the same meter (rebonk without the brain)."""
    same = grooves_in(GROOVE_METER[g])
    return same[(same.index(g) + 1) % len(same)]

# A one-beat fill (last beat of a bar), as {role: [(step-in-the-beat, velocity)]}, and the
# accent on the downbeat after it. Pd plays this when the fill pad is hit.
FILL = {KICK: [(0, 100)], SNARE: [(0, 95), (1, 75)], TOM_HI: [(2, 105)], TOM_LO: [(3, 115)]}
# ... and in 6/8, where a beat (a dotted quarter) is 6 steps
FILL6 = {KICK: [(0, 100)], SNARE: [(0, 90), (2, 80)], TOM_HI: [(3, 95), (4, 100)], TOM_LO: [(5, 115)]}
ACCENT = [(KICK, 115), (OPEN, 105)]

# The brain's automatic fills (every 4 or 8 bars), one beat each: [(role, 16th in the beat, velocity)].
# At high density a fill starts a beat earlier with FILL_LEAD.
FILLS = [
    [(SNARE, 0, 80), (SNARE, 1, 70), (SNARE, 2, 90), (SNARE, 3, 105)],
    [(SNARE, 0, 85), (SNARE, 1, 70), (TOM_HI, 2, 100), (TOM_LO, 3, 110)],
    [(TOM_HI, 0, 95), (TOM_HI, 1, 80), (TOM_LO, 2, 100), (TOM_LO, 3, 112)],
    [(KICK, 0, 100), (SNARE, 1, 90), (KICK, 2, 95), (SNARE, 3, 108)],
    [(SNARE, 0, 95), (TOM_HI, 1, 90), (TOM_LO, 2, 100), (KICK, 2, 90), (TOM_LO, 3, 110)],
]
FILL_LEAD = [(KICK, 0, 95), (SNARE, 2, 60), (SNARE, 3, 70)]
# 6/8 fills: one dotted-quarter beat (6 steps)
FILLS6 = [
    [(SNARE, 0, 80), (SNARE, 2, 88), (SNARE, 4, 96), (SNARE, 5, 105)],
    [(SNARE, 0, 85), (TOM_HI, 2, 95), (TOM_LO, 4, 105), (TOM_LO, 5, 112)],
    [(TOM_HI, 0, 95), (TOM_HI, 1, 75), (TOM_LO, 2, 100), (SNARE, 4, 100), (KICK, 4, 90), (TOM_LO, 5, 110)],
    [(KICK, 0, 100), (SNARE, 2, 90), (KICK, 3, 85), (SNARE, 4, 100), (SNARE, 5, 108)],
]


def fixed_bar(groove):
    """The fixed (no-brain) version of a groove: 16 steps x 8 roles of velocities (a 12-step
    bar leaves the last 4 empty)."""
    v = [0] * (16 * 8)
    for role, hits in groove.items():
        for step, vel, chance in hits:
            if chance >= 0.5:
                v[step * 8 + role] = vel
    return v
