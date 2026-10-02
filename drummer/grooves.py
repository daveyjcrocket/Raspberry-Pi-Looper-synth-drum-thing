"""The AI drummer's groove library, shared by tools/gen_drummer.py (Pd's fixed fallback grooves)
and drummer/brain.py (the grooves it varies every pass).

Each groove is one 4/4 bar of 16ths: {role: [(step, velocity, chance), ...]}.
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
]

# A one-beat fill (last beat of a bar), as {role: [(step-in-the-beat, velocity)]}, and the
# accent on the downbeat after it. Pd plays this when the fill pad is hit.
FILL = {KICK: [(0, 100)], SNARE: [(0, 95), (1, 75)], TOM_HI: [(2, 105)], TOM_LO: [(3, 115)]}
ACCENT = [(KICK, 115), (OPEN, 105)]


def fixed_bar(groove):
    """The fixed (no-brain) version of a groove: 16 steps x 8 roles of velocities."""
    v = [0] * (16 * 8)
    for role, hits in groove.items():
        for step, vel, chance in hits:
            if chance >= 0.5:
                v[step * 8 + role] = vel
    return v
