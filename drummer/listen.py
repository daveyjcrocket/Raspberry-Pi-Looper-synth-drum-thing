"""The AI drummer's ears: tempo, swing, push and a groove choice from the onsets of a loop.

Pd collects the onsets (bonk~ on the band, plus the exact MIDI note-ons) while the first layer
records, or for one pass after a rebonk, and the brain analyses them here. It is cheap:
the downbeat and the exact loop length are already known, so "find the tempo" is only
"how many whole 4/4 bars are in this loop", a dozen or so candidates.

Onsets: (time ms from the loop start, strength 0-1, brightness 0-10, midi 0/1).
Brightness says low (kick, bass: below LOW) or high (snare, hats, chords).
"""
import math
from grooves import GROOVES, KICK, SNARE, HAT, OPEN, RIM, RIDE

LOW = 4.5                 # brightness below this is a low hit (bonk~'s temperature: kick ~3.5, hats ~7)
AUDIO_LATENCY = 10.0      # bonk~ reports an attack about this late, ms
SIGMA = 10.0              # timing slop of a played note, ms
MIDI_ECHO = (-15.0, 30.0) # an audio onset this close to a MIDI note is that note again
RING_MS = 150.0           # a weak low onset this soon after a strong low one is its ring
BPM_LO, BPM_HI = 60, 180
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


def nearest(x, beat, pos):
    """(index 0-3 in the beat, signed error ms) of the grid point nearest x (0 <= x < beat)."""
    best = (0, x)
    for k, p in enumerate(pos + [beat]):
        e = x - p
        if abs(e) < abs(best[1]):
            best = (k % 4, e)
    return best


def score(ons, length, bars, swing):
    """How well the onsets sit on this tempo's grid, above what random onsets would score."""
    beat = length / (4 * bars)
    pos = grid(beat, swing)
    sig = min(SIGMA, beat / 12)
    chance = sig * math.sqrt(2 * math.pi) / beat
    tot = s8 = s16 = 0.0
    for t, w, _ in ons:
        x = t % beat
        e8 = min(abs(x), abs(x - beat), abs(x - pos[2]))
        e16 = min(e8, abs(x - pos[1]), abs(x - pos[3]))
        s8 += w * math.exp(-0.5 * (e8 / sig) ** 2)
        s16 += w * math.exp(-0.5 * (e16 / sig) ** 2)
        tot += w
    if not tot:
        return 0.0
    return (s8 / tot - 2 * chance) + 0.5 * (s16 / tot - 4 * chance)


def bar_options(length):
    """Whole-bar counts to try: 60-180 bpm, or the nearest when none fit."""
    opts = [b for b in range(1, MAX_BARS + 1) if BPM_LO <= 240000 * b / length <= BPM_HI]
    if not opts:
        opts = [max(1, min(MAX_BARS, round(length * 100 / 240000)))]
    return opts


def bars_for(length, bpm):
    """The bar count Pd plays for a tempo (same rounding as drummer.pd)."""
    return max(1, round(length * bpm / 240000))


def best_swing(ons, length, bars):
    """Swing 50-75 % that fits best, refined from where the off-beat 8ths really are."""
    best = max(range(50, 76), key=lambda s: (score(ons, length, bars, s), -s))
    beat = length / (4 * bars)
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


def analyse_tempo(ons, length, tap=0):
    """Bars in the loop: from the tapped tempo, else the best fit with a pull towards ~100 bpm."""
    if tap > 0:
        return min(MAX_BARS, bars_for(length, tap))
    if len(ons) < 3:
        return min(MAX_BARS, bars_for(length, 100))

    def total(b):
        bpm = 240000 * b / length
        prior = -0.15 * (math.log2(bpm / 100) / 0.6) ** 2
        if b in (1, 2, 4, 8, 16):        # loops are mostly 1, 2, 4 or 8 bars
            prior += 0.12
        return max(score(ons, length, b, s) for s in (50, 58, 62, 67)) + prior
    return max(bar_options(length), key=total)


def push_of(ons, length, bars, swing):
    """Average ms the beats are played ahead (-) or behind (+) the grid."""
    beat = length / (4 * bars)
    pos = grid(beat, swing)
    num = den = 0.0
    for t, w, _ in ons:
        k, e = nearest(t % beat, beat, pos)
        if k == 0 and abs(e) < min(30, beat / 8):
            num += w * e
            den += w
    return max(-15.0, min(15.0, num / den)) if den >= 0.5 else 0.0


def histogram(ons, length, bars, swing):
    """The onsets folded into one bar of 16ths: (low[16], high[16]), strength per bar."""
    beat = length / (4 * bars)
    pos = grid(beat, swing)
    low, high = [0.0] * 16, [0.0] * 16
    for t, w, b in ons:
        i = int(t // beat)
        x = t - i * beat
        k, _ = nearest(x, beat, pos)
        if k == 0 and x > beat / 2:          # nearest is the next beat
            i += 1
        step = (i * 4 + k) % 16
        (low if b < LOW else high)[step] += w / bars
    return low, high


def features(low, high, bars, length):
    both = [a + b for a, b in zip(low, high)]
    tot = sum(both) or 1e-9
    beats = 4
    lmax = max(low) or 1e-9
    return {
        'activity': sum(1 for v in both if v > 0.15) / beats,     # busy 16th slots per beat
        'odd16': sum(both[i] for i in range(1, 16, 2)) / tot,
        'off8': sum(both[i] for i in range(2, 16, 4)) / tot,
        'four': min(low[i] for i in (0, 4, 8, 12)) / lmax if max(low) > 0.2 else 0.0,
        'bpm': 240000 * bars / length,
    }


def choose_groove(f, swing, exclude=None):
    """Score the groove library against what was heard: 16ths -> funk, a kick on every beat ->
    four on the floor, sparse -> half-time, swung -> ride, else rock."""
    names = [n for n, _ in GROOVES]
    sc = {
        'rock': 1.0,
        'funk': 0.5 + 2.2 * f['odd16'] + (0.2 if f['activity'] >= 2.5 else 0),
        'four on the floor': 0.4 + 1.1 * f['four'],
        'half-time': 0.5 + 0.8 * max(0.0, 1.5 - f['activity']) + (0.3 if f['bpm'] > 135 else 0),
        'ride': 0.4 + 0.06 * (swing - 50),
    }
    order = sorted(range(len(names)), key=lambda i: -sc.get(names[i], 0))
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
        strong = sorted((s for s in range(16) if low[s] >= 0.5 * lmax and s not in kicks), key=lambda s: -low[s])
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
    """What the drummer heard, and the current reading of it (bars, swing, feel, groove)."""

    def __init__(self):
        self.onsets, self.offset, self.src = [], 0.0, 0
        self.length, self.bars, self.measured, self.feel = 0.0, 0, 50, 0
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
        return [self.measured, 50, self.measured if 55 <= self.measured <= 64 else 60, 67][self.feel]

    def analyse(self, length, tap, src, groove):
        """After listening: returns (bpm, swing, groove)."""
        ons = prepare(self.onsets, length)
        self.onsets = []
        if src == 0 or not self.bars or abs(length - self.length) > 1:
            self.bars = analyse_tempo(ons, length, tap)
        self.length = length
        if ons:
            self.heard = ons
            self.measured = best_swing(ons, length, self.bars)
            self.push = push_of(ons, length, self.bars, self.measured)
            low, high = histogram(ons, length, self.bars, self.measured)
            f = features(low, high, self.bars, length)
            g = choose_groove(f, self.measured, exclude=int(groove) if src == 1 else None)
            self.fitted = {g: fit_groove(GROOVES[g][1], low, high)}
            self.groove = g
        elif src == 1:            # rebonk heard nothing: just change up the groove
            self.groove = (int(groove) + 1) % len(GROOVES)
        else:
            self.groove = int(groove)
        return self.reading()

    def fix(self, length, tap, direction, feel, groove, bars):
        """The player's corrections: tempo x1/2 (-1) or x2 (+1), and the feel 0-3."""
        if abs(length - self.length) > 1 or not self.bars:
            self.length, self.bars = length, max(1, int(bars) or bars_for(length, tap or 100))
        if direction < 0 and self.bars > 1:
            self.bars = max(1, round(self.bars / 2))
        elif direction > 0 and self.bars * 2 <= MAX_BARS:
            self.bars *= 2
        self.feel = int(feel) % len(FEELS)
        if direction and self.heard:
            self.measured = best_swing(self.heard, length, self.bars)
            self.push = push_of(self.heard, length, self.bars, self.measured)
            low, high = histogram(self.heard, length, self.bars, self.measured)
            g = self.groove if self.groove is not None else int(groove)
            self.fitted = {g: fit_groove(GROOVES[g][1], low, high)}
        if self.groove is None:
            self.groove = int(groove)
        return self.reading()

    def reading(self):
        return 240000 * self.bars / self.length, self.swing(), self.groove

    def groove_for(self, g):
        """The groove to vary: the fitted one when it is the groove playing, else the library's."""
        return self.fitted.get(g, GROOVES[g][1])
