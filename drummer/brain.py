#!/usr/bin/env python3
"""The AI drummer's brain: listens to the first layer, then writes a new, varied drum pattern
for every pass through the loop.

    Pd [drummer]  <-- TCP 127.0.0.1:9312 (FUDI) -->  this process

Listening (drummer/listen.py). While the first layer records (or for one pass after a rebonk)
Pd sends the onsets it hears, then asks for a reading:

    listen <src 0 = first layer, 1 = rebonk> <ms into the loop when listening started>;
    on <ms> <strength> <brightness 0-10> <midi 0/1>;      (one per onset)
    heard <loop-ms> <tapped-bpm or 0> <src> <groove>;
    fix <loop-ms> <tapped-bpm> <-1 = half, 1 = double, 0> <feel 0-3> <groove> <bars> <1 = next meter>;
      -> drmfeel <bpm> <swing %> <groove> <feel> <scope: 0 = song, 1 = this part>;

Playing. At the start of every loop Pd asks for the pattern of the NEXT loop:

    loop <steps> <step-ms> <groove> <density 0-1> <humanize 0-1> <loop-number> <layers> <auto-fills> <part>;

(part 0 = verse, 1 = chorus: busier, ride instead of hats, a crash on every pass). The groove sets
the meter: 4/4 bars are 16 steps, 3/4 and 6/8 bars 12.

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
from grooves import GROOVES, FILLS, FILLS6, FILL_LEAD, ACCENT, meter_of, KICK, SNARE, HAT, OPEN, RIM, TOM_HI, TOM_LO, RIDE
from listen import Ears, FEELS

PERSIST = 0.7          # chance a decoration keeps last pass's choice (the rest are rolled again)
TURNAROUND = 1.6       # decorations on the last beat of the loop are this much likelier


def density_scale(chance, density):
    """Decoration chance at a density: 0 = none, 0.5 = as written, 1 = about 2.5x."""
    if chance >= 1:
        return 1.0
    return min(0.95, chance * (2 * density) ** 1.3)


CHORUS_LIFT = 0.25     # the chorus plays this much busier than the verse


def intensity(density, layers, part=0):
    """Density as the band grows: busier with more layers playing, calmer with fewer,
    and busier in the chorus."""
    if layers > 0:
        density += 0.1 * (min(layers, 6) - 2)
    return max(0.0, min(1.0, density + CHORUS_LIFT * (part == 1)))


def phrase_bars(bars, density):
    """Bars between automatic fills: 4 when busy, else 8, fitted to the loop so a fill
    always lands on the loop's end or divides it evenly."""
    p = 4 if density >= 0.6 else 8
    if bars <= p:
        return bars * max(1, round(p / bars))
    return p if bars % p == 0 else bars


class Drummer:
    """Keeps the state that makes one pass follow on from the last."""

    def __init__(self, rng):
        self.rng = rng
        self.ears = Ears()
        self.key = None            # (steps, groove): a change starts the groove afresh
        self.on = {}               # (bar, role, step) -> decoration played on the last pass
        self.drift = [0.0] * 8     # per-sound timing drift, ms (a human drifts, not jumps)
        self.cache = {}            # loop number -> the state before it, so a repeat request
                                   # (a knob moved) recomputes that loop instead of evolving twice

    def pattern(self, steps, step_ms, groove, density, humanize, loop_no, layers=0, autofill=1, part=0):
        """The pattern of one pass: (groove name, velocities, offsets), 8 per 16th step.
        The groove sets the meter: bars of 16 steps (4/4) or 12 (3/4, 6/8)."""
        steps = max(12, min(256, int(steps)))
        groove = int(groove) % len(GROOVES)
        _, S, Q, _ = meter_of(groove)               # steps per bar, per beat
        key = (steps, groove, part)
        if key != self.key:
            self.key, self.on, self.drift, self.cache = key, {}, [0.0] * 8, {}
        if loop_no in self.cache:
            self.on, self.drift = dict(self.cache[loop_no][0]), list(self.cache[loop_no][1])
            self.rng.setstate(self.cache[loop_no][2])
        else:
            self.cache = {loop_no: (dict(self.on), list(self.drift), self.rng.getstate())}
        rng = self.rng
        name = GROOVES[groove][0]
        hits = self.ears.groove_for(groove)
        density = intensity(density, layers, part)
        bars = max(1, steps // S)
        vel = [0] * (steps * 8)
        off = [0.0] * (steps * 8)

        # 1. which hits play: the backbone always, decorations rolled with memory
        for bar in range(bars):
            last_bar = bar == bars - 1
            for role, lst in hits.items():
                for step, v, chance in lst:
                    p = density_scale(chance, density)
                    if chance < 1:
                        if last_bar and step >= S - Q:
                            p = min(0.95, p * TURNAROUND)
                        k = (bar, role, step)
                        if k in self.on and rng.random() < PERSIST:
                            play = self.on[k]
                        else:
                            play = rng.random() < p
                        self.on[k] = play
                        if not play:
                            continue
                    i = (bar * S + step) * 8 + role
                    if i < len(vel):
                        vel[i] = max(vel[i], v)
        # low density thins the backbone hats to the beat
        if density < 0.2:
            for s in range(steps):
                if s % Q:
                    for role in (HAT, RIDE):
                        if vel[s * 8 + role] and vel[s * 8 + KICK] == 0 and vel[s * 8 + SNARE] == 0:
                            vel[s * 8 + role] = 0
        # a big band (4+ layers) and busy, or the chorus: hats move to the ride
        if (layers >= 4 and density >= 0.6 or part == 1) and name in ('rock', 'half-time', '3/4 rock'):
            for s in range(steps):
                h = vel[s * 8 + HAT]
                if h:
                    vel[s * 8 + RIDE], vel[s * 8 + HAT] = max(vel[s * 8 + RIDE], h), 0

        # 2. phrasing: a fill every 4 or 8 bars and an accent on the downbeat after it,
        # else now and then an open hat on the loop's last off-beat
        filled_end = False
        if autofill:
            phrase = phrase_bars(bars, density)
            for bar in range(bars):
                n = loop_no * bars + bar
                if n and n % phrase == 0:
                    self.accent(vel, bar * S)
                if (n + 1) % phrase == 0:
                    self.fill(vel, bar * S, S, Q, density)
                    filled_end = filled_end or bar == bars - 1
        if part == 1:                                # the chorus crashes in on every pass
            self.accent(vel, 0)
        s = steps - 2
        if not filled_end and vel[s * 8 + HAT] and rng.random() < 0.5 + 0.3 * density:
            vel[s * 8 + OPEN], vel[s * 8 + HAT] = vel[s * 8 + HAT], 0

        # 3. humanize: velocities breathe, timing drifts (kick tight, snare a touch behind),
        # and the whole kit leans with the player's push (measured when listening)
        spread = {KICK: 0.5, SNARE: 0.8, HAT: 1.0, OPEN: 1.0, RIM: 0.9, TOM_HI: 0.9, TOM_LO: 0.9, RIDE: 1.0}
        lean = {SNARE: 3.0, RIM: 2.0}
        push = 0.5 * self.ears.push * humanize
        limit = min(25.0, 0.45 * step_ms)
        for s in range(steps):
            for role in range(8):
                i = s * 8 + role
                if not vel[i]:
                    continue
                sigma = humanize * 8.0 * spread[role]
                self.drift[role] = 0.7 * self.drift[role] + rng.gauss(0, sigma)
                t = self.drift[role] + humanize * lean.get(role, 0.0) + push
                off[i] = round(max(-limit, min(limit, t)), 1)
                v = vel[i] * (1 + rng.gauss(0, 0.12 * humanize))
                if role in (HAT, RIDE) and s % 2:          # off-beat cymbals a little softer
                    v *= 1 - 0.1 * humanize
                vel[i] = int(max(1, min(127, round(v))))
        return name, vel, off

    def fill(self, vel, bar0, S, Q, density):
        """A fill on the last beat of the bar starting at step bar0 (S steps a bar, Q a beat),
        or the last two beats of 4/4 and 3/4 when busy. The kit stops for it (except a kick
        to lead in)."""
        shape = self.rng.choice(FILLS6 if Q == 6 else FILLS)
        two = Q == 4 and density >= 0.75 and self.rng.random() < 0.6
        last = bar0 + S - Q
        start = last - Q if two else last
        for s in range(start, bar0 + S):
            for r in range(8):
                vel[s * 8 + r] = 0
        if two:
            for role, k, v in FILL_LEAD:
                vel[(start + k) * 8 + role] = v
        for role, k, v in shape:
            i = (last + k) * 8 + role
            vel[i] = max(vel[i], v)

    def accent(self, vel, s):
        """The downbeat after a fill: a big kick and the open hat (crash)."""
        for role, v in ACCENT:
            vel[s * 8 + role] = max(vel[s * 8 + role], v)
        vel[s * 8 + HAT] = 0


# ---------------- FUDI over TCP ----------------

def fmt(x):
    return str(int(x)) if float(x).is_integer() else f'{x:.1f}'


def messages(name_vel_off, steps, loop_no):
    _, vel, off = name_vel_off
    return ('drmnext 0 ' + ' '.join(map(fmt, vel)) + ';\n'
            + 'drmnexttime 0 ' + ' '.join(map(fmt, off)) + ';\n'
            + f'drmready {steps} {loop_no};\n')


def feel_message(reading, feel, scope):
    """drmfeel <bpm> <swing> <groove> <feel> <scope>: scope 0 = the whole song (both parts),
    1 = only the part playing (a rebonk)."""
    bpm, swing, groove = reading
    return f'drmfeel {bpm:.3f} {int(swing)} {int(groove)} {int(feel)} {int(scope)};\n'


def handle(drummer, a, log=None):
    """One message from Pd (a list of words) -> the reply to send back ('' for none)."""
    ears = drummer.ears
    try:
        cmd, x = a[0], [float(v) for v in a[1:]]
    except (IndexError, ValueError):
        return ''
    if cmd == 'loop' and len(x) >= 6:
        steps, step_ms, groove, density, humanize, loop_no = x[:6]
        layers, autofill, part = (x[6:] + [0, 1, 0][len(x) - 6:])[:3]
        t0 = time.perf_counter()
        pat = drummer.pattern(int(steps), step_ms, int(groove), density, humanize, int(loop_no),
                              int(layers), int(autofill), int(part))
        if log:
            log(f'loop {int(loop_no)}: {pat[0]}{" (chorus)" if part else ""}, {int(steps)} steps, density '
                f'{density:.2f}, humanize {humanize:.2f}, layers {int(layers)}, '
                f'{(time.perf_counter() - t0) * 1000:.1f} ms')
        return messages(pat, int(steps), int(loop_no))
    if cmd == 'listen' and len(x) >= 2:
        ears.listen(x[0], x[1])
    elif cmd == 'on' and len(x) >= 4:
        ears.onset(*x[:4])
    elif cmd == 'heard' and len(x) >= 4:
        n = len(ears.onsets)
        if log:
            log('onsets (ms strength brightness midi): ' + '  '.join(
                f'{t:.0f} {w:.0f} {b:.1f} {int(m)}' for t, w, b, m in ears.onsets))
        t0 = time.perf_counter()
        src = int(x[2])
        r = ears.analyse(x[0], x[1], src, int(x[3]))
        if log:
            log(f'heard {n} onsets in {x[0]:.0f} ms: {ears.meter}, {r[0]:.1f} bpm, swing {r[1]} %, push '
                f'{ears.push:+.1f} ms, {GROOVES[r[2]][0]}, {(time.perf_counter() - t0) * 1000:.1f} ms')
        return feel_message(r, ears.feel, 1 if src == 1 else 0)
    elif cmd == 'fix' and len(x) >= 6 and x[0] > 0:
        meter_step = int(x[6]) if len(x) >= 7 else 0
        r = ears.fix(x[0], x[1], int(x[2]), int(x[3]), int(x[4]), x[5], meter_step)
        if log:
            log(f'fix: {ears.meter}, {r[0]:.1f} bpm, {FEELS[ears.feel]} {r[1]} %, {GROOVES[r[2]][0]}')
        return feel_message(r, ears.feel, 0 if meter_step else 1)
    return ''


def serve(port, rng, verbose):
    drummer = Drummer(rng)
    log = (lambda t: print(t, flush=True)) if verbose else None
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
                out = ''.join(handle(drummer, m.split(), log) for m in msgs)
                if out:
                    sock.sendall(out.encode())
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
    # one brain per Pd: a second one would answer every request twice
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(('127.0.0.1', args.port + 1))
    except OSError:
        sys.exit(f'drummer brain: another one is already running (port {args.port + 1} is taken)')
    try:
        serve(args.port, random.Random(args.seed), args.verbose)
    except KeyboardInterrupt:
        pass
