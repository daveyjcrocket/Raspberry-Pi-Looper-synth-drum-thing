#!/usr/bin/env python3
"""The AI drummer's brain: writes a new, varied drum pattern for every pass through the loop.

    Pd [drummer]  <-- TCP 127.0.0.1:9312 (FUDI) -->  this process

At the start of every loop Pd asks for the pattern of the NEXT loop:

    loop <steps> <step-ms> <groove> <density 0-1> <humanize 0-1> <loop-number> <layers>;

and the brain answers with the whole loop, 8 values per 16th step (one per kit sound):

    drmnext 0 <velocities ...>;        0 = silent, else 1-127
    drmnexttime 0 <offsets in ms ...>; timing of each hit against the grid (+ = late)
    drmready <steps> <loop-number>;

Pd plays whatever pattern it has, so the brain is never in the audio path: if it is slow,
stopped or not running, Pd repeats the last pattern (or its fixed groove).
Only the Python standard library is used. It wakes once per loop and works for a few ms.

    python3 drummer/brain.py [--port 9312] [--seed N] [--verbose]
"""
import argparse, math, os, random, socket, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grooves import GROOVES, KICK, SNARE, HAT, OPEN, RIM, TOM_HI, TOM_LO, RIDE

PERSIST = 0.7          # chance a decoration keeps last pass's choice (the rest are rolled again)
TURNAROUND = 1.6       # decorations on the last beat of the loop are this much likelier


def density_scale(chance, density):
    """Decoration chance at a density: 0 = none, 0.5 = as written, 1 = about 2.5x."""
    if chance >= 1:
        return 1.0
    return min(0.95, chance * (2 * density) ** 1.3)


class Drummer:
    """Keeps the state that makes one pass follow on from the last."""

    def __init__(self, rng):
        self.rng = rng
        self.key = None            # (steps, groove): a change starts the groove afresh
        self.on = {}               # (bar, role, step) -> decoration played on the last pass
        self.drift = [0.0] * 8     # per-sound timing drift, ms (a human drifts, not jumps)
        self.cache = {}            # loop number -> the state before it, so a repeat request
                                   # (a knob moved) recomputes that loop instead of evolving twice

    def pattern(self, steps, step_ms, groove, density, humanize, loop_no):
        steps = max(16, min(256, int(steps)))
        groove = int(groove) % len(GROOVES)
        key = (steps, groove)
        if key != self.key:
            self.key, self.on, self.drift, self.cache = key, {}, [0.0] * 8, {}
        if loop_no in self.cache:
            self.on, self.drift = dict(self.cache[loop_no][0]), list(self.cache[loop_no][1])
        else:
            self.cache = {loop_no: (dict(self.on), list(self.drift))}
        rng = self.rng
        name, hits = GROOVES[groove]
        bars = steps // 16
        vel = [0] * (steps * 8)
        off = [0.0] * (steps * 8)

        # 1. which hits play: the backbone always, decorations rolled with memory
        for bar in range(bars):
            last_bar = bar == bars - 1
            for role, lst in hits.items():
                for step, v, chance in lst:
                    p = density_scale(chance, density)
                    if chance < 1:
                        if last_bar and step >= 12:
                            p = min(0.95, p * TURNAROUND)
                        k = (bar, role, step)
                        if k in self.on and rng.random() < PERSIST:
                            play = self.on[k]
                        else:
                            play = rng.random() < p
                        self.on[k] = play
                        if not play:
                            continue
                    i = (bar * 16 + step) * 8 + role
                    vel[i] = max(vel[i], v)
        # low density thins the backbone hats to quarter notes
        if density < 0.2:
            for s in range(steps):
                if s % 4:
                    for role in (HAT, RIDE):
                        if vel[s * 8 + role] and vel[s * 8 + KICK] == 0 and vel[s * 8 + SNARE] == 0:
                            vel[s * 8 + role] = 0

        # 2. the turnaround: open the hat on the last off-beat now and then
        s = steps - 2
        if vel[s * 8 + HAT] and rng.random() < 0.5 + 0.3 * density:
            vel[s * 8 + OPEN], vel[s * 8 + HAT] = vel[s * 8 + HAT], 0
        # every 4th pass, a short pickup on the last beat (more likely when busy)
        if loop_no % 4 == 3 and rng.random() < 0.25 + 0.5 * density:
            self.pickup(vel, steps)

        # 3. humanize: velocities breathe, timing drifts (kick tight, snare a touch behind)
        spread = {KICK: 0.5, SNARE: 0.8, HAT: 1.0, OPEN: 1.0, RIM: 0.9, TOM_HI: 0.9, TOM_LO: 0.9, RIDE: 1.0}
        lean = {SNARE: 3.0, RIM: 2.0}
        limit = min(25.0, 0.45 * step_ms)
        for s in range(steps):
            for role in range(8):
                i = s * 8 + role
                if not vel[i]:
                    continue
                sigma = humanize * 8.0 * spread[role]
                self.drift[role] = 0.7 * self.drift[role] + rng.gauss(0, sigma)
                t = self.drift[role] + humanize * lean.get(role, 0.0)
                off[i] = round(max(-limit, min(limit, t)), 1)
                v = vel[i] * (1 + rng.gauss(0, 0.12 * humanize))
                if role in (HAT, RIDE) and s % 2:          # off-beat cymbals a little softer
                    v *= 1 - 0.1 * humanize
                vel[i] = int(max(1, min(127, round(v))))
        return name, vel, off

    def pickup(self, vel, steps):
        """A one-beat pickup into the loop's downbeat: snare or toms on the last 16ths."""
        rng = self.rng
        base = steps - 4
        shape = rng.choice([[SNARE, SNARE, SNARE, SNARE], [SNARE, SNARE, TOM_HI, TOM_LO], [None, SNARE, None, SNARE]])
        for k, role in enumerate(shape):
            s = base + k
            for r in (HAT, OPEN, RIDE):
                vel[s * 8 + r] = 0
            if role is not None:
                vel[s * 8 + role] = max(vel[s * 8 + role], 70 + 12 * k)


# ---------------- FUDI over TCP ----------------

def fmt(x):
    return str(int(x)) if float(x).is_integer() else f'{x:.1f}'


def messages(name_vel_off, steps, loop_no):
    _, vel, off = name_vel_off
    return ('drmnext 0 ' + ' '.join(map(fmt, vel)) + ';\n'
            + 'drmnexttime 0 ' + ' '.join(map(fmt, off)) + ';\n'
            + f'drmready {steps} {loop_no};\n')


def serve(port, rng, verbose):
    drummer = Drummer(rng)
    while True:
        try:
            sock = socket.create_connection(('127.0.0.1', port), timeout=2)
        except OSError:
            time.sleep(1)
            continue
        sock.settimeout(None)
        print(f'drummer brain: connected to Pd on port {port}', flush=True)
        buf = ''
        try:
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                buf += data.decode('utf-8', 'replace')
                *msgs, buf = buf.split(';')
                for m in msgs:
                    a = m.split()
                    if len(a) == 8 and a[0] == 'loop':
                        steps, step_ms, groove, density, humanize, loop_no, layers = map(float, a[1:])
                        t0 = time.perf_counter()
                        pat = drummer.pattern(int(steps), step_ms, int(groove), density, humanize, int(loop_no))
                        sock.sendall(messages(pat, int(steps), int(loop_no)).encode())
                        if verbose:
                            print(f'loop {int(loop_no)}: {pat[0]}, {int(steps)} steps, density {density:.2f}, '
                                  f'humanize {humanize:.2f}, {(time.perf_counter() - t0) * 1000:.1f} ms', flush=True)
        except OSError:
            pass
        sock.close()
        print('drummer brain: Pd went away, waiting for it', flush=True)
        time.sleep(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--port', type=int, default=9312)
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()
    try:
        serve(args.port, random.Random(args.seed), args.verbose)
    except KeyboardInterrupt:
        pass
