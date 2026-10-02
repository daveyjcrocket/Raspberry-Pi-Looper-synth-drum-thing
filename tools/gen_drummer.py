"""Generates piLooper/drummer.pd: the AI drummer, step 1 (player, groove library, pads as controls).

The drummer plays the selected drum kit (instrument banks 0-3; it keeps the last kit while a
synth is selected) in time with the loop. Its output goes to s~ drummer-out, which audio-IO
adds after the loopers, so it is heard but never recorded.

Timing: on every loop start [r f] it works out the bars in the loop (from the tapped tempo, or
by assuming roughly 100 bpm 4/4 when the loop is free-length), then steps through the loop in
16ths. Each 16th it reads the groove (array drmgroove: 8 values per step, one per kit sound,
0 = silent, else the velocity; drmGlen steps long, 16 for the built-in grooves) and plays the hits.
A future brain can write a longer, varied pattern into drmgroove and set drmGlen.

Messages:
  drummer-mode 0/1    on = the drummer plays and the drum pads become its controls
  drummer-pause       pause (at the next beat) / resume (at the next bar line)
  drummer-fill        a fill on the last beat of the bar, and an accent on the next downbeat
  drummer-rebonk      change up the groove (step 1: the next groove in the library)
  drummer-level 0-1, drummer-swing 50-75 (% position of the off-beat 8th; 50 = straight)
  drummer-test-pad N  same as hitting pad N in drummer mode (tests)
Pads in drummer mode (both pad maps, on the pads' MIDI channel = the tap pad's channel, so
only when that is a real channel, not 0 = any):
  pad 1 pause / resume, pad 2 fill, pad 3 rebonk. tapFilter keeps them out of the instruments.
Kit sounds (roles): 0 kick, 1 snare, 2 hat closed, 3 hat open, 4 rimshot, 5 tom high, 6 tom low, 7 ride.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1500, 1100)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
esc = lambda t: t.replace(' ', '\\ ')
p.text('AI drummer (step 1). See tools/gen_drummer.py (this file is generated).', 20, 5)

ROLES = ['kick', 'snare', 'hat closed', 'hat open', 'rimshot', 'tom high', 'tom low', 'ride']
# The kit files per bank, by role. Banks 2-3 are the user's own samples (often missing:
# a missing file just leaves that sound silent).
KITS = [[f'kits/gmrock/{f}.wav' for f in ('kick', 'snare', 'hihat_closed', 'hihat_open', 'rimshot',
                                          'tom_high', 'tom_low', 'ride')],
        [f'kits/virtuosity/{f}.wav' for f in ('kick', 'snare', 'hihat_closed', 'hihat_open', 'rimshot',
                                              'tom_high', 'tom_low', 'ride')],
        ['kick_13.wav', 'snare_13.wav', 'hh_07.wav', 'hh_08.wav', 'snare_14.wav', 'snare_15.wav',
         'kick_14.wav', 'crash_03.wav'],
        ['kick_19.wav', 'snare_19.wav', 'hh_10.wav', 'hh_11.wav', 'snare_20.wav', 'snare_21.wav',
         'kick_20.wav', 'crash_04.wav']]

def hats(vels, every=2):
    return {s: vels[(s // every) % len(vels)] for s in range(0, 16, every)}

# one-bar grooves: {role: {16th step: velocity}}
GROOVES = [
    ('rock', {0: {0: 110, 8: 100, 10: 85}, 1: {4: 110, 12: 110}, 2: hats([95, 70, 88, 70])}),
    ('half-time', {0: {0: 110, 7: 75, 10: 95}, 1: {8: 115}, 4: {14: 45}, 2: hats([95, 68, 80, 68])}),
    ('four on the floor', {0: {0: 112, 4: 108, 8: 112, 12: 108}, 1: {4: 100, 12: 100},
                           2: {0: 70, 4: 65, 8: 70, 12: 65}, 3: {2: 85, 6: 80, 10: 85, 14: 80}}),
    ('funk', {0: {0: 110, 3: 85, 10: 100}, 1: {4: 110, 7: 35, 9: 35, 12: 110, 15: 30},
              2: hats([95, 55, 75, 55], every=1)}),
    ('ride', {0: {0: 110, 10: 95}, 1: {4: 105, 12: 105}, 7: hats([100, 75, 90, 75])}),
]
FILL = {0: {0: 100}, 1: {0: 95, 1: 75}, 5: {2: 105}, 6: {3: 115}}    # last beat of the bar
ACCENT = [(0, 115), (3, 105)]                                        # next downbeat: kick + open hat

def table(pattern, steps):
    v = [0] * (steps * 8)
    for role, hits in pattern.items():
        for step, vel in hits.items():
            v[step * 8 + role] = vel
    return ' '.join(map(str, v))

# ---------------- kit tables, loaded at startup ----------------
lb = O('loadbang', 20, 30)
files = [(k, r, f) for k, kit in enumerate(KITS) for r, f in enumerate(kit)]
lt = O('t b b b' + ' b' * len(files), 20, 55); C(lb, lt)
sf = O('soundfiler', 20, 400)
for i, (k, r, f) in enumerate(files):
    x, y = 20 + (i % 8) * 170, 90 + (i // 8) * 70
    O(f'table drk-{k}-{r}', 1380, 30 + i * 22)
    m = M(f'symbol {f}', x, y); C(lt, m, 3 + i)
    w = O('file which', x, y + 22); C(m, w)                 # silent when the file is missing
    C(w, O('list split 1', x, y + 44)); C(last(), M(f'read -resize $1 drk-{k}-{r}', x + 80, y + 44))
    C(last(), sf)
# arrays, defaults
O('table drmgroove 2048', 1200, 30)
O('table drmfillpat 32', 1200, 55)
C(lt, M(f'; drmfillpat 0 {table(FILL, 4)}; drmGlen 16; drmSw 50; drmKit 0; drummer-level 0.5; '
        'drmMode 0; drmPaused 0; drmWant 0; drmAct 0; drmRun 0; drmFillP 0; drmFill 0; drmAcc 0', 20, 440), 2)
C(lt, M('0', 400, 440), 1); C(last(), O('s $0-groove', 400, 465))
C(lt, O('s $0-status', 460, 440), 0)
# the value variables, so the names exist for expr
for i, n in enumerate(['drmGlen', 'drmSw', 'drmKit', 'drmMode', 'drmPaused', 'drmWant', 'drmAct', 'drmRun',
                       'drmFillP', 'drmFill', 'drmAcc', 'drmS', 'drmN', 'drmBeat', 'drmLen', 'drmBpm', 'drmG']):
    O(f'v {n}', 1200, 90 + i * 22)

# selected kit: banks 0-3; keep the last kit while a synth is selected
C(O('r bankSelect', 600, 440), O('moses 4', 600, 465)); C(last(), O('v drmKit', 600, 490))

# ---------------- controls ----------------
def want_update(src, outlet, x, y):
    """recompute drmWant; while the loop clock is stopped, act on it at once."""
    t = O('t b b', x, y); C(src, t, outlet)
    C(t, O('expr drmMode && !drmPaused', x + 60, y + 25), 1); C(last(), O('v drmWant', x + 60, y + 50))
    C(t, O('expr if(drmRun, drmAct, drmWant)', x, y + 75), 0); C(last(), O('t b f', x, y + 100)); tt = last()
    C(tt, O('v drmAct', x + 60, y + 125), 1); C(tt, O('s $0-status', x, y + 125), 0)

mode = O('r drummer-mode', 20, 520)
mt = O('t f f', 20, 545); C(mode, mt)
C(mt, O('v drmMode', 120, 570), 1)
C(mt, M('0', 20, 570), 0); C(last(), O('t b f', 20, 595)); mp = last()
C(mp, O('v drmPaused', 80, 620), 1); want_update(mp, 0, 20, 645)
C(mt, O('s drummer-mode-pads', 200, 570), 0)        # the pad display follows

pause = O('r drummer-pause', 300, 520)
pg = O('v drmMode', 300, 545); C(pause, pg)
C(pg, O('sel 1', 300, 570)); C(last(), O('expr !drmPaused', 300, 595)); C(last(), O('t b f', 300, 620)); pp = last()
C(pp, O('v drmPaused', 360, 645), 1); want_update(pp, 0, 300, 670)

fill = O('r drummer-fill', 520, 520)
C(fill, O('expr drmAct || drmWant', 520, 545)); C(last(), O('sel 1', 520, 570))
C(last(), M('1', 520, 595)); C(last(), O('v drmFillP', 520, 620))

reb = O('r drummer-rebonk', 700, 520)
C(reb, O(f'expr (drmG+1) % {len(GROOVES)}', 700, 545)); C(last(), O('s $0-groove', 700, 570))
grv = O('r $0-groove', 700, 600)
gt = O('t f f', 700, 625); C(grv, gt)
C(gt, O('v drmG', 800, 650), 1)
gs = O('sel ' + ' '.join(str(i) for i in range(len(GROOVES))), 700, 650); C(gt, gs, 0)
gname = O('symbol', 700, 800)
for i, (name, pat) in enumerate(GROOVES):
    gm = M(f'; drmgroove 0 {table(pat, 16)}; drmGlen 16', 700 + i * 120, 680)
    nm = M(f'symbol {esc(name)}', 700 + i * 120, 760)
    t = O('t b b', 700 + i * 120, 665); C(gs, t, i); C(t, gm, 1); C(t, nm, 0)
    C(nm, gname, 0, 1)
C(gs, O('s $0-status', 700, 830), len(GROOVES))
C(gt, O('s $0-status', 900, 650), 0)

lvl = O('r drummer-level', 1000, 520)
lvlLine = O('vline~', 1000, 570); C(lvl, M('$1 30', 1000, 545)); C(last(), lvlLine)
sw = O('r drummer-swing', 1100, 520); C(sw, O('clip 50 75', 1100, 545)); C(last(), O('v drmSw', 1100, 570))

# ---------------- pads: controls in drummer mode ----------------
ni = O('notein', 20, 900)
pk = O('pack f f f', 20, 925); C(ni, pk, 2, 2); C(ni, pk, 1, 1); C(ni, pk, 0, 0)
pt = O('t l b b', 20, 950); C(pk, pt)
pe = O('expr if($f2>0 && $f1>=48 && $f1<=63 && $f5>0 && $f3==$f5 && $f1!=$f4, ($f1-48)%8+1, 0)', 20, 1000)
C(pt, O('v tap-ch', 160, 975), 2); C(last(), pe, 0, 4)
C(pt, O('v tap-note', 90, 975), 1); C(last(), pe, 0, 3)
C(pt, pe, 0, 0)
pspig = O('spigot', 20, 1025); C(pe, pspig)
C(O('r drummer-mode', 90, 1000), pspig, 0, 1)
psel = O('sel 1 2 3', 20, 1050); C(pspig, psel)
C(O('r drummer-test-pad', 120, 1025), psel)
for i, name in enumerate(['drummer-pause', 'drummer-fill', 'drummer-rebonk']):
    C(psel, O(f's {name}', 20 + i * 110, 1075), i)

# ---------------- loop clock -> 16th steps ----------------
C(O('r ms', 1250, 520), O('v drmLen', 1250, 545))
C(O('r tempo-bpm', 1350, 520), O('v drmBpm', 1350, 545))
met = O('metro 100', 1250, 800)
cnt = O('f', 1250, 830); C(met, cnt); C(cnt, O('+ 1', 1300, 830)); C(last(), cnt, 0, 1)
# Only while the loop plays (OVERDUB, PLAYING, FADING) - not while the first layer records.
# [delay 0]: the looper sets its state just after it starts the clock; same logical time.
C(O('r looper-state', 1450, 520), O('v drmLS', 1450, 545))
rf = O('r f', 1250, 575)
rd = O('delay 0', 1250, 590); C(rf, rd)
rok = O('expr drmLS>=2 && drmLS<=4 && drmLen>=100', 1150, 600); C(rd, rok)
rsel = O('sel 1 0', 1150, 612); C(rok, rsel)
ft = O('t b b b b', 1250, 625); C(rsel, ft, 0)
# bars in the loop: from the tempo, else ~100 bpm in 4/4; more than 16 bars plays half-time
bars = O('expr if(drmBpm>0, max(1, rint(drmLen*drmBpm/240000)), max(1, rint(drmLen/2400)))', 1250, 650)
C(ft, bars, 3)
bx = O('expr if($f1>16, rint($f1/2), $f1)*16', 1250, 675); C(bars, bx)
nt = O('t f f', 1250, 700); C(bx, nt)
C(nt, O('v drmN', 1350, 725), 1)
sx = O('expr drmLen/$f1', 1250, 725); C(nt, sx, 0)
stt = O('t f f', 1250, 750); C(sx, stt)
C(stt, O('* 4', 1350, 775), 1); C(last(), O('v drmBeat', 1350, 800))
C(stt, met, 0, 1)
C(ft, M('0', 1300, 650), 2); C(last(), cnt, 0, 1)
C(ft, M('1', 1150, 650), 1); C(last(), O('v drmRun', 1150, 675))
C(ft, met, 0)
C(ft, O('s $0-status', 1150, 700), 0)       # after the clock has started, so the bpm is current

stop = O('t b b b', 1100, 880)
C(O('r stop', 1100, 830), stop); C(O('r clearAll', 1170, 830), stop); C(rsel, stop, 1)
C(stop, M('stop', 1250, 905), 2); C(last(), met)
C(stop, M('; drmRun 0; drmFillP 0; drmFill 0', 1100, 905), 1)
C(stop, O('t b', 1100, 930), 0); want_update(last(), 0, 1100, 955)

# ---------------- one 16th step ----------------
tick = O('t f f', 1250, 860); C(cnt, tick)
C(tick, O('v drmS', 1350, 885), 1)
inN = O('expr $f1 < drmN', 1250, 885); C(tick, inN, 0)
gate = O('sel 1', 1250, 910); C(inN, gate)
st = O('t b b b b b b', 1250, 935); C(gate, st)
# 5: pause at a beat, resume at a bar line
C(st, O('expr if(drmS%16==0, drmWant, if(drmS%4==0, drmWant && drmAct, drmAct))', 1500, 960), 5)
C(last(), O('t f f', 1500, 985)); at = last()
C(at, O('v drmAct', 1600, 1010), 1)
C(at, O('change', 1500, 1010), 0); C(last(), O('s $0-status', 1500, 1035))
# 4: fills (accent on the downbeat after a fill, the fill starts on the last beat)
C(st, O('t b b b', 1700, 960), 4); ft2 = last()
C(ft2, O('expr if(drmS%16==0, drmFill, 0)', 1800, 985), 2); C(last(), O('v drmAcc', 1800, 1010))
C(ft2, O('expr if(drmS%16==0, 0, if(drmS%16==12 && drmFillP, 1, drmFill))', 1750, 1035), 1)
C(last(), O('v drmFill', 1750, 1060))
C(ft2, O('expr if(drmS%16==12, 0, drmFillP)', 1700, 1085), 0); C(last(), O('v drmFillP', 1700, 1110))
# 3: swing: the off-beat 8th moves to drmSw % of the beat, the 16ths in between follow
pipe = O('pipe 0', 1250, 1150)
C(st, O('expr if(drmS%4==2, (drmSw-50)/100*drmBeat, if(drmS%2==1, (drmSw-50)/200*drmBeat, 0))', 1900, 960), 3)
C(last(), pipe, 0, 1)
# 1: play the step's hits (only while active)
C(st, O('v drmAct', 1250, 960), 1); hs = O('sel 1', 1250, 985); C(last() - 1, hs)
ht = O('t b b b', 1250, 1010); C(hs, ht)
# downbeat accent after a fill (after the groove's hits, so its velocity wins)
C(ht, O('v drmAcc', 1400, 1035), 0); C(last(), O('sel 1', 1400, 1060)); accent = last()
# roles 0-7: velocity from the fill (last beat, while filling) or the groove; the last
# off-beat of the loop opens the hi-hat; out goes role*128 + velocity
rl = O('until', 1250, 1035); C(ht, M('8', 1250, 1035 - 10), 1); C(last(), rl)
rc = O('f', 1250, 1060); C(rl, rc); C(rc, O('+ 1', 1300, 1060)); C(last(), rc, 0, 1)
C(ht, M('0', 1300, 1010), 2); C(last(), rc, 0, 1)
ex = O('expr if(drmFill && drmS%16>=12, drmfillpat[(drmS%16-12)*8+$f1], drmgroove[(drmS%drmGlen)*8+$f1]); '
       'if(!(drmFill && drmS%16>=12) && drmS==drmN-2 && $f1==2, 3, $f1)*128', 1250, 1085)
C(rc, ex)
add = O('+', 1250, 1125)
C(ex, add, 1, 1)
C(ex, O('moses 1', 1250, 1105), 0); C(last(), add, 1, 0)
C(add, pipe)
C(accent, M(', '.join(str(r * 128 + v) for r, v in ACCENT), 1400, 1085)); C(last(), pipe)
C(pipe, O('s drummer-hit', 1250, 1175))

# ---------------- voices ----------------
level = O('*~', 20, 1300); fade = O('*~', 20, 1330)
fadeLine = O('vline~', 80, 1305)
C(level, fade); C(lvlLine, level, 0, 1); C(fadeLine, fade, 0, 1)
C(O('r loopFade', 80, 1280), fadeLine)
C(lt, M('1', 160, 1280), 1); C(last(), fadeLine)
C(fade, O('s~ drummer-out', 20, 1360))
for r in range(8):
    x = 20 + r * 160
    h = O('r drummer-hit', x, 1180)
    sel = O(f'expr if(int($f1/128)=={r}, $f1%128, 0)', x, 1200); C(h, sel)
    mo = O('moses 1', x, 1220); C(sel, mo)
    vt = O('t b b f', x, 1240); C(mo, vt, 1)
    play = O(f'tabplay~ drk-0-{r}', x, 1265)
    gain = O('*~', x, 1290); gl = O('vline~', x + 60, 1265)
    C(vt, O('/ 127', x + 100, 1240), 2); C(last(), gl)
    C(vt, O('v drmKit', x + 50, 1215), 1); C(last(), M(f'set drk-$1-{r}', x + 50, 1240)); C(last(), play)
    C(vt, play, 0)
    C(play, gain); C(gl, gain, 0, 1); C(gain, level)
    if r == 3:      # the closed hi-hat chokes the open one
        C(h, O('expr int($f1/128)==2', x + 80, 1200)); C(last(), O('sel 1', x + 80, 1220))
        C(last(), M('0 8', x + 80, 1240)); C(last(), gl)

# ---------------- status ----------------
sr = O('r $0-status', 20, 1420)
code = O('expr if(!drmMode, 0, if(drmPaused, if(drmAct && drmRun, 4, 1), if(!drmRun, 2, if(drmAct, 3, 5))))', 20, 1445)
C(sr, code)
cs = O('sel 0 1 2 3 4 5', 20, 1470); C(code, cs)
cnv = O('s drummer-cnv', 20, 1600)
LOOKS = [('AI drummer off - pads play the kit', '#3c3c3c', '#bdbdbd'),
         ('paused - pad 1 resumes', '#5d4037', '#ffffff'),
         ('on - waiting for a loop', '#1f3a5f', '#ffffff'),
         None,
         ('pausing on the next beat', '#f9a825', '#000000'),
         ('starting on the next bar', '#f9a825', '#000000')]
for i, look in enumerate(LOOKS):
    if look:
        C(cs, M(f'color {look[1]} {look[2]}, label {esc(look[0])}', 20 + i * 200, 1500), i)
        C(last(), cnv)
# playing: "<groove> - <bpm> bpm"
pl = O('t b b', 620, 1520); C(cs, pl, 3)
bpmx = O('expr rint(600000/drmBeat)/10', 700, 1545); C(pl, bpmx, 1)
ppk = O('pack s f', 620, 1570); C(bpmx, ppk, 0, 1)
C(pl, gname, 0); C(gname, ppk)
C(ppk, M('color #2e7d32 #ffffff, label $1\\ -\\ $2\\ bpm', 620, 1595)); C(last(), cnv)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'drummer.pd'))
