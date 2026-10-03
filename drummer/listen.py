"""The AI drummer's ears: tempo, swing, push and a groove choice from the onsets of a loop.

Pd collects the onsets (bonk~ on the band, plus the exact MIDI note-ons) while the first layer
records, or for one pass after a rebonk, and the brain analyses them here. It is cheap:
the downbeat and the exact loop length are already known, so "find the tempo" is only
"how many whole bars of 4/4, 3/4 or 6/8 are in this loop", a few dozen candidates.

Onsets: (time ms from the loop start, strength 0-1, brightness 0-10, midi 0/1).
Brightness says low (kick, bass: below LOW) or high (snare, hats, chords).
"""
import math
from grooves import GROOVES, METERS, METER_ORDER, GROOVE_METER, grooves_in, KICK, SNARE, HAT, OPEN, RIM, RIDE

LOW = 4.5                 # brightness below this is a low hit (bonk~'s temperature: kick ~3.5, hats ~7)
AUDIO_LATENCY = 10.0      # bonk~ reports an attack about this late, ms
SIGMA = 10.0              # timing slop of a played note, ms
MIDI_ECHO = (-15.0, 30.0) # an audio onset this close to a MIDI note is that note again
RING_MS = 150.0           # a weak low onset this soon after a strong low one is its ring
BPM_RANGE = {'4/4': (60, 180), '3/4': (60, 180), '6/8': (40, 140)}   # beats per minute
BPM_HOME = {'4/4': 100, '3/4': 100, '6/8': 70}     # the tempo a loop most likely has
METER_PRIOR = {'4/4': 0.05, '3/4': 0.0, '6/8': 0.0}
MAX_BARS = 16             # Pd plays loops longer than this half-time
FEELS = ['heard', 'straight', 'swing', 'triplet']


def prepare(onsets, length):
    """Fold into the loop, drop the audio echoes of MIDI notes, scale the strengths 0-1."""
    if length <= 0:
        return []
    midi = [(t % length, w, b) for t, w, b, m in onsets if m]
    audio = [((t - AUDIO_LATENCY) % length, w, b) for t, w, b, m in onsets if not m]
    lo, hi = MIDI_ECHO

    def echo(t):
        for mt, _, _ in midi:
            d = (t - mt + length / 2) % length - length / 2      # circular t - mt
            if lo <= d <= hi:
                return True
        return False
    audio = [o for o in audio if not echo(o[0])]
    # a weak low "attack" just after a strong low hit is the kick ringing, not a note
    keep = []
    for t, w, b in audio:
        ring = any(0 < t - pt < RING_MS and pb < LOW and b < LOW and w < 0.35 * pw for pt, pw, pb in audio)
        if not ring:
            keep.append((t, w, b))
    audio = keep
    amax = max((w for _, w, _ in audio), default=0) or 1
    out = [(t, max(0.05, min(1, w / 127)), b) for t, w, b in midi]
    out += [(t, max(0.05, min(1, w / amax)), b) for t, w, b in audio]
    return sorted(out)


def grid(beat, swing):
    """Positions in one beat (ms) of the 16ths with swing, as Pd plays them: the off-beat 8th
    at swing % of the beat, the 16ths either side moved half as far."""
    d = (swing - 50) / 100
    return [0.0, (0.25 + d / 2) * beat, swing / 100 * beat, (0.75 + d / 2) * beat]


def grid68(beat):
    """Positions in one 6/8 beat (a dotted quarter): 6 16ths, the 8ths at the even ones."""
    return [k * beat / 6 for k in range(6)]


def positions(meter, beat, swing):
    return grid68(beat) if meter == '6/8' else grid(beat, swing)


def nearest(x, beat, pos):
    """(index in the beat, signed error ms) of the grid point nearest x (0 <= x < beat)."""
    best = (0, x)
    n = len(pos)
    for k, p in enumerate(pos + [beat]):
        e = x - p
        if abs(e) < abs(best[1]):
            best = (k % n, e)
    return best


def beat_ms(length, meter, bars):
    return length / (bars * METERS[meter][2])


def bpm_of(length, meter, bars):
    return 60000 / beat_ms(length, meter, bars)


def score(ons, length, bars, swing, meter='4/4'):
    """How well the onsets sit on this tempo's grid, above what random onsets would score:
    the 8ths count fully, the 16ths half."""
    beat = beat_ms(length, meter, bars)
    pos = positions(meter, beat, swing)
    eighths = pos[0::2] if meter == '6/8' else [pos[0], pos[2]]
    sig = min(SIGMA, beat / (3 * len(pos)))
    chance = sig * math.sqrt(2 * math.pi) / beat
    tot = s8 = s16 = 0.0
    for t, w, _ in ons:
        x = t % beat
        e8 = min([abs(x - beat)] + [abs(x - p) for p in eighths])
        e16 = min([e8] + [abs(x - p) for p in pos])
        s8 += w * math.exp(-0.5 * (e8 / sig) ** 2)
        s16 += w * math.exp(-0.5 * (e16 / sig) ** 2)
        tot += w
    if not tot:
        return 0.0
    return (s8 / tot - len(eighths) * chance) + 0.5 * (s16 / tot - len(pos) * chance)


def accents(ons, length, meter, bars, swing=50):
    """How the accents fit the meter, two numbers in -1..1:
    beats: the meter's beats against the 8ths between them (3+3 for 6/8, 2+2+2 for 3/4);
    downbeat: the bar's first beat against its other beats. Low hits count more."""
    S, Q, bpb = METERS[meter]
    beat = beat_ms(length, meter, bars)
    pos = positions(meter, beat, swing)
    n = bars * bpb
    slot = {}
    for t, w, b in ons:
        j = int(t // beat)
        k, e = nearest(t - j * beat, beat, pos)
        if k == 0 and t - j * beat > beat / 2:
            j += 1
        if k % 2 == 0 and abs(e) < beat / (2 * len(pos)):
            key = (j % n, k)
            slot[key] = slot.get(key, 0.0) + w * (1.5 if b < LOW else 1.0)
    on = [slot.get((j, 0), 0.0) for j in range(n)]
    off = [slot.get((j, k), 0.0) for j in range(n) for k in range(2, len(pos), 2)]

    def contrast(a, b):
        ma, mb = sum(a) / max(1, len(a)), sum(b) / max(1, len(b))
        return (ma - mb) / (ma + mb + 1e-9)
    down = contrast(on[0::bpb], [v for j, v in enumerate(on) if j % bpb]) if bpb > 1 else 0.0
    return contrast(on, off), down


def candidates(length, meters=METER_ORDER):
    """(meter, bars) to try: whole bars at a sensible tempo, or the nearest when none fit."""
    out = []
    for m in meters:
        lo, hi = BPM_RANGE[m]
        out += [(m, b) for b in range(1, MAX_BARS + 1) if lo <= bpm_of(length, m, b) <= hi]
    return out or [('4/4', max(1, min(MAX_BARS, round(length * 100 / 240000))))]


def bars_for(length, bpm, meter='4/4'):
    """The bar count Pd plays for a tempo (same rounding as drummer.pd)."""
    return max(1, round(length * bpm / (60000 * METERS[meter][2])))


def best_swing(ons, length, bars, meter='4/4'):
    """Swing 50-75 % that fits best, refined from where the off-beat 8ths really are
    (6/8 has no swing: its 8ths are triplets already)."""
    if meter == '6/8':
        return 50
    best = max(range(50, 76), key=lambda s: (score(ons, length, bars, s, meter), -s))
    beat = beat_ms(length, meter, bars)
    pos = grid(beat, best)
    num = den = 0.0
    for t, w, _ in ons:
        k, e = nearest(t % beat, beat, pos)
        if k == 2 and abs(e) < beat / 8:
            num += w * (pos[2] + e) / beat * 100
            den += w
    s = num / den if den >= 0.5 else best
    s = max(50, min(75, s))
    return 50 if s < 54 else int(round(s))


EIGHTHS = {'4/4': 8, '3/4': 6, '6/8': 6}     # 8th notes in a bar


def pulse_score(ons, length, meter, bars, tapped=False):
    """Stage 1, the pulse: how well the grid fits, with a pull towards a likely tempo and
    1/2/4/8-bar loops. A shuffle fits 4/4's swung grid best, a full triplet stream 6/8's."""
    bpm = bpm_of(length, meter, bars)
    t = METER_PRIOR[meter]
    if not tapped:
        t += -0.15 * (math.log2(bpm / BPM_HOME[meter]) / 0.6) ** 2
        if bars in (1, 2, 4, 8, 16):        # loops are mostly 1, 2, 4 or 8 bars
            t += 0.12
    swings = (50,) if meter == '6/8' else (50, 58, 62, 67)
    return t + max(score(ons, length, bars, s, meter) for s in swings)


def meter_score(ons, length, meter, bars):
    """Stage 2, the grouping of a pulse: the accents, and the grid once more."""
    beats, down = accents(ons, length, meter, bars)
    if meter == '6/8':          # the downbeat against the bar's other quarters, as for 3/4
        down = accents(ons, length, '3/4', bars)[1]
    swings = (50,) if meter == '6/8' else (50, 58, 62)
    return (METER_PRIOR[meter] + 0.5 * beats + 0.5 * down
            + 0.5 * max(score(ons, length, bars, s, meter) for s in swings))


def regroup(ons, length, eighths):
    """The meters a loop of <eighths> 8th notes can be, in whole bars: [(meter, bars)]."""
    out = []
    for m in METER_ORDER:
        bars = eighths / EIGHTHS[m]
        if abs(bars - round(bars)) < 0.01 and 1 <= round(bars) <= MAX_BARS:
            out.append((m, round(bars)))
    return out


def analyse_tempo(ons, length, tap=0, meters=METER_ORDER):
    """(meter, bars). First the pulse (tapped, or the best fit), then the meter that groups
    it best: 4/4, 3/4 or 6/8 with the same 8th notes."""
    if len(ons) < 3:
        m = meters[0]
        bpm = tap if tap > 0 else BPM_HOME[m]
        return m, min(MAX_BARS, bars_for(length, bpm, m))
    if tap > 0:
        firsts = [(m, min(MAX_BARS, bars_for(length, tap, m))) for m in meters]
        first = max(firsts, key=lambda c: pulse_score(ons, length, c[0], c[1], True))
    else:
        first = max(candidates(length, meters), key=lambda c: pulse_score(ons, length, c[0], c[1]))
    eighths = first[1] * EIGHTHS[first[0]]
    opts = [c for c in regroup(ons, length, eighths) if c[0] in meters] or [first]
    return max(opts, key=lambda c: meter_score(ons, length, c[0], c[1]))


def push_of(ons, length, bars, swing, meter='4/4'):
    """Average ms the beats are played ahead (-) or behind (+) the grid."""
    beat = beat_ms(length, meter, bars)
    pos = positions(meter, beat, swing)
    num = den = 0.0
    for t, w, _ in ons:
        k, e = nearest(t % beat, beat, pos)
        if k == 0 and abs(e) < min(30, beat / 8):
            num += w * e
            den += w
    return max(-15.0, min(15.0, num / den)) if den >= 0.5 else 0.0


def histogram(ons, length, bars, swing, meter='4/4'):
    """The onsets folded into one bar of 16ths: (low[S], high[S]), strength per bar."""
    S, Q, _ = METERS[meter]
    beat = beat_ms(length, meter, bars)
    pos = positions(meter, beat, swing)
    low, high = [0.0] * S, [0.0] * S
    for t, w, b in ons:
        i = int(t // beat)
        x = t - i * beat
        k, _ = nearest(x, beat, pos)
        if k == 0 and x > beat / 2:          # nearest is the next beat
            i += 1
        step = (i * Q + k) % S
        (low if b < LOW else high)[step] += w / bars
    return low, high


def features(low, high, bars, length, meter='4/4'):
    S, Q, bpb = METERS[meter]
    both = [a + b for a, b in zip(low, high)]
    tot = sum(both) or 1e-9
    lmax = max(low) or 1e-9
    return {
        'activity': sum(1 for v in both if v > 0.15) / bpb,       # busy 16th slots per beat
        'odd16': sum(both[i] for i in range(1, S, 2)) / tot,
        'four': min(low[i] for i in range(0, S, Q)) / lmax if max(low) > 0.2 else 0.0,
        'bpm': 60000 * bars * bpb / length,
    }


def choose_groove(f, swing, exclude=None, meter='4/4'):
    """Score the meter's grooves against what was heard.
    4/4: 16ths -> funk, a kick on every beat -> four on the floor, sparse -> half-time,
    swung -> ride, else rock.  3/4: sparse -> waltz, swung -> jazz waltz, else 3/4 rock.
    6/8: busy -> 6/8 rock, else the ballad (6/8 blues for a change)."""
    a = f['activity']
    sc = {
        'rock': 1.0,
        'funk': 0.5 + 2.2 * f['odd16'] + (0.2 if a >= 2.5 else 0),
        'four on the floor': 0.4 + 1.1 * f['four'],
        'half-time': 0.5 + 0.8 * max(0.0, 1.5 - a) + (0.3 if f['bpm'] > 135 else 0),
        'ride': 0.4 + 0.06 * (swing - 50),
        '3/4 rock': 1.0,
        'waltz': 0.6 + 0.8 * max(0.0, 1.6 - a),
        'jazz waltz': 0.4 + 0.07 * (swing - 50),
        '6/8 ballad': 1.0,
        '6/8 rock': 0.4 + 0.3 * a,
        '6/8 blues': 0.9,
    }
    order = sorted(grooves_in(meter), key=lambda i: -sc.get(GROOVES[i][0], 0))
    for i in order:
        if i != exclude:
            return i
    return order[0]


def fit_groove(groove, low, high):
    """The groove, fitted to the player: kicks under strong low accents, and the decorations
    fill the gaps (likelier where the player is quiet, rarer where they are busy)."""
    g = {role: list(hits) for role, hits in groove.items()}
    both = [a + b for a, b in zip(low, high)]
    mx = max(both) or 0
    if mx <= 0:
        return g
    kicks = {s for s, _, _ in g.get(KICK, [])}
    lmax = max(low)
    if lmax > 0.3 * mx:
        strong = sorted((s for s in range(len(low)) if low[s] >= 0.5 * lmax and s not in kicks),
                        key=lambda s: -low[s])
        g[KICK] = g.get(KICK, []) + [(s, 95, 0.7) for s in strong[:3]]
    for role in (SNARE, HAT, OPEN, RIM, RIDE):
        if role not in g:
            continue
        out = []
        for s, v, c in g[role]:
            if c < 1:
                busy = both[s] / mx
                c = min(0.95, c * (1.4 if busy < 0.15 else 0.5 if busy > 0.6 else 1.0))
            out.append((s, v, c))
        g[role] = out
    return g


class Ears:
    """What the drummer heard, and the current reading of it (meter, bars, swing, feel, groove)."""

    def __init__(self):
        self.onsets, self.offset, self.src = [], 0.0, 0
        self.length, self.meter, self.bars, self.measured, self.feel = 0.0, '4/4', 0, 50, 0
        self.push, self.groove, self.fitted = 0.0, None, {}
        self.heard = []           # the prepared onsets of the last analysis

    def listen(self, src, offset):
        self.onsets, self.src, self.offset = [], int(src), float(offset)
        if self.src == 0:         # a new song: forget the old reading
            self.bars, self.feel, self.push, self.fitted, self.heard = 0, 0, 0.0, {}, []

    def onset(self, t, w, bright, midi):
        if self.src == 1 and t < 20 and not midi:     # bonk~ waking up mid-sound, not an attack
            return
        self.onsets.append((t + self.offset, w, bright, midi))

    def swing(self):
        if self.meter == '6/8':
            return 50
        return [self.measured, 50, self.measured if 55 <= self.measured <= 64 else 60, 67][self.feel]

    def refit(self, exclude=None, choose=True):
        """Swing, push and (if choose) the groove for the current meter and bars, from what was heard."""
        L, m, b = self.length, self.meter, self.bars
        self.measured = best_swing(self.heard, L, b, m)
        self.push = push_of(self.heard, L, b, self.measured, m)
        low, high = histogram(self.heard, L, b, self.measured, m)
        if choose:
            self.groove = choose_groove(features(low, high, b, L, m), self.measured, exclude, m)
        self.fitted = {self.groove: fit_groove(GROOVES[self.groove][1], low, high)}

    def analyse(self, length, tap, src, groove):
        """After listening: returns (bpm, swing, groove). A rebonk (src 1) keeps the meter and
        tempo and picks a different groove."""
        groove = int(groove) % len(GROOVES)
        ons = prepare(self.onsets, length)
        self.onsets = []
        if src == 0 or not self.bars or abs(length - self.length) > 1:
            self.meter, self.bars = analyse_tempo(ons, length, tap)
        else:
            self.meter = GROOVE_METER[groove]
        self.length = length
        if ons:
            self.heard = ons
            self.refit(exclude=groove if src == 1 else None)
        elif src == 1:            # rebonk heard nothing: just change up the groove
            same = grooves_in(self.meter)
            self.groove = same[(same.index(groove) + 1) % len(same)] if groove in same else same[0]
        else:
            self.groove = groove if GROOVE_METER[groove] == self.meter else grooves_in(self.meter)[0]
        return self.reading()

    def fix(self, length, tap, direction, feel, groove, bars, meter_step=0):
        """The player's corrections: tempo x1/2 (-1) or x2 (+1), the feel 0-3, and the next
        meter (4/4 -> 3/4 -> 6/8)."""
        groove = int(groove) % len(GROOVES)
        if abs(length - self.length) > 1 or not self.bars:
            self.length, self.meter = length, GROOVE_METER[groove]
            self.bars = max(1, int(bars) or bars_for(length, tap or BPM_HOME[self.meter], self.meter))
        if self.groove is None or GROOVE_METER[self.groove] != self.meter:
            self.groove = groove
        if direction < 0 and self.bars > 1:
            self.bars = max(1, round(self.bars / 2))
        elif direction > 0 and self.bars * 2 <= MAX_BARS:
            self.bars *= 2
        self.feel = int(feel) % len(FEELS)
        if meter_step:
            old, beats = self.meter, self.bars * METERS[self.meter][2]
            self.meter = METER_ORDER[(METER_ORDER.index(old) + 1) % len(METER_ORDER)]
            if {old, self.meter} == {'3/4', '6/8'}:       # same bar of 6 eighths
                pass
            else:                                           # keep the beat
                self.bars = max(1, min(MAX_BARS, round(beats / METERS[self.meter][2])))
        if direction or meter_step:
            if self.heard:
                self.refit(choose=bool(meter_step))
            elif meter_step:
                self.groove, self.fitted = grooves_in(self.meter)[0], {}
        return self.reading()

    def reading(self):
        return bpm_of(self.length, self.meter, self.bars), self.swing(), self.groove

    def groove_for(self, g):
        """The groove to vary: the fitted one when it is the groove playing, else the library's."""
        return self.fitted.get(g, GROOVES[g][1])
