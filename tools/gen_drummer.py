"""Generates piLooper/drummer.pd: the AI drummer (player, fixed grooves, link to the brain, pads as controls).

The drummer plays the selected drum kit (instrument banks 0-3; it keeps the last kit while a
synth is selected) in time with the loop. Its output goes to s~ drummer-out, which audio-IO
adds after the loopers, so it is heard but never recorded.

Timing: on every loop start [r f] it works out the bars in the loop (from the tapped tempo, or
by assuming roughly 100 bpm 4/4 when the loop is free-length) and steps through it in 16ths.
Each step is prepared one 16th AHEAD (drmP = the step being prepared) and its hits are sent
through [pipe] with delay = one step + swing + the hit's own timing offset, so a hit can land
a little early or late (humanize). The very first step after the loop starts plays at once.

Patterns, 8 values per step (one per kit sound, 0 = silent, else the velocity):
  drmbase      the fixed one-bar groove (drummer/grooves.py), used when the brain isn't running
  drmgroove    the brain's pattern for this pass (whole loop), with drmtime = offsets in ms
  drmnext      the brain's pattern for the next pass (drmnexttime); copied in at the loop start
The brain (drummer/brain.py) connects to TCP 127.0.0.1:9312. At every loop start Pd asks it
for the next pass ("loop <steps> <step-ms> <groove> <density> <humanize> <pass> <layers>");
it answers "drmnext 0 ...", "drmnexttime 0 ...", "drmready <steps> <pass>". When it is late or gone,
Pd repeats the pattern it has. drmSrc says where the step comes from: 0 fixed, 1 this pass, 2 next.

Messages:
  drummer-mode 0/1    on = the drummer plays and the drum pads become its controls
  drummer-pause       pause (at the next beat) / resume (at the next bar line)
  drummer-fill        a fill on the last beat of the bar, and an accent on the next downbeat
  drummer-rebonk      change up the groove (for now: the next groove in the library)
  drummer-level 0-1, drummer-density 0-1, drummer-humanize 0-1,
  drummer-swing 50-75 (% position of the off-beat 8th; 50 = straight)
  drummer-test-pad N  same as hitting pad N in drummer mode (tests)
Pads in drummer mode (both pad maps, on the pads' MIDI channel = the tap pad's channel, so
only when that is a real channel, not 0 = any):
  pad 1 pause / resume, pad 2 fill, pad 3 rebonk. tapFilter keeps them out of the instruments.
Kit sounds (roles): 0 kick, 1 snare, 2 hat closed, 3 hat open, 4 rimshot, 5 tom high, 6 tom low, 7 ride.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'drummer'))
from pdgen import Patch
from grooves import GROOVES, FILL, ACCENT, fixed_bar

BRAIN_PORT = 9312
p = Patch(1500, 1100)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
esc = lambda t: t.replace(' ', '\\ ')
p.text('AI drummer. See tools/gen_drummer.py (this file is generated).', 20, 5)

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

def fill_table():
    v = [0] * 32
    for role, hits in FILL.items():
        for step, vel in hits:
            v[step * 8 + role] = vel
    return ' '.join(map(str, v))

def want_update(src, outlet, x, y):
    """recompute drmWant; while the loop clock is stopped, act on it at once."""
    t = O('t b b', x, y); C(src, t, outlet)
    C(t, O('expr drmMode && !drmPaused', x + 60, y + 25), 1); C(last(), O('v drmWant', x + 60, y + 50))
    C(t, O('expr if(drmRun, drmAct, drmWant)', x, y + 75), 0); C(last(), O('t b f', x, y + 100)); tt = last()
    C(tt, O('v drmAct', x + 60, y + 125), 1); C(tt, O('s $0-status', x, y + 125), 0)

def setter(recv, name, lo, hi, ask, x, y):
    """[r recv] -> clip -> value name; optionally ask the brain again."""
    r = O(f'r {recv}', x, y); c = O(f'clip {lo} {hi}', x, y + 25); C(r, c)
    t = O('t b f', x, y + 50); C(c, t)
    C(t, O(f'v {name}', x + 60, y + 75), 1)
    if ask:
        C(t, O('s $0-ask', x, y + 75), 0)

# ---------------- kit tables, arrays, defaults (at startup) ----------------
lb = O('loadbang', 20, 30)
files = [(k, r, f) for k, kit in enumerate(KITS) for r, f in enumerate(kit)]
lt = O('t b b b b' + ' b' * len(files), 20, 55); C(lb, lt)
sf = O('soundfiler', 20, 400)
for i, (k, r, f) in enumerate(files):
    x, y = 20 + (i % 8) * 170, 90 + (i // 8) * 70
    O(f'table drk-{k}-{r}', 1380, 30 + i * 22)
    m = M(f'symbol {f}', x, y); C(lt, m, 4 + i)
    w = O('file which', x, y + 22); C(m, w)                 # silent when the file is missing
    C(w, O('list split 1', x, y + 44)); C(last(), M(f'read -resize $1 drk-{k}-{r}', x + 80, y + 44))
    C(last(), sf)
for i, (name, size) in enumerate([('drmbase', 128), ('drmfillpat', 32), ('drmgroove', 2048),
                                  ('drmtime', 2048), ('drmnext', 2048), ('drmnexttime', 2048)]):
    O(f'table {name} {size}', 1200, 30 + i * 22)
C(lt, M(f'; drmfillpat 0 {fill_table()}; drmSw 50; drmKit 0; drummer-level 0.5; drmDens 0.5; drmHum 0.3; '
        'drmMode 0; drmPaused 0; drmWant 0; drmAct 0; drmRun 0; drmFillP 0; drmFill 0; drmFm 0; drmAcc 0; '
        'drmBrain 0; drmGlen 0; drmReadyN 0; drmUp 0; drmLoop 0; drmN 0', 20, 440), 3)
C(lt, M('0', 400, 440), 2); C(last(), O('s $0-groove', 400, 465))
C(lt, M(f'listen {BRAIN_PORT} 127.0.0.1', 460, 465), 1); brainListen = last()
C(lt, O('s $0-status', 460, 440), 0)
# the value variables, so the names exist for expr
VALUES = ['drmSw', 'drmKit', 'drmMode', 'drmPaused', 'drmWant', 'drmAct', 'drmRun', 'drmFillP', 'drmFill',
          'drmFm', 'drmAcc', 'drmS', 'drmN', 'drmBeat', 'drmStep', 'drmLen', 'drmBpm', 'drmG', 'drmP', 'drmSrc',
          'drmBase', 'drmSwD', 'drmBrain', 'drmGlen', 'drmReadyN', 'drmUp', 'drmLoop', 'drmLayers', 'drmDens',
          'drmHum', 'drmLS']
for i, n in enumerate(VALUES):
    O(f'v {n}', 1200 + (i // 16) * 90, 170 + (i % 16) * 22)

# selected kit: banks 0-3; keep the last kit while a synth is selected
C(O('r bankSelect', 600, 440), O('moses 4', 600, 465)); C(last(), O('v drmKit', 600, 490))

# ---------------- controls ----------------
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

# groove: rebonk steps through the library; the fixed bar goes to drmbase, the brain is asked again
reb = O('r drummer-rebonk', 700, 520)
C(reb, O(f'expr (drmG+1) % {len(GROOVES)}', 700, 545)); C(last(), O('s $0-groove', 700, 570))
grv = O('r $0-groove', 700, 600)
gt = O('t b b f f', 700, 625); C(grv, gt)
C(gt, O('v drmG', 860, 650), 3)
gs = O('sel ' + ' '.join(str(i) for i in range(len(GROOVES))), 700, 650); C(gt, gs, 2)
gname = O('symbol', 700, 800)
for i, (name, groove) in enumerate(GROOVES):
    gm = M(f'; drmbase 0 {" ".join(map(str, fixed_bar(groove)))}', 700 + i * 120, 680)
    nm = M(f'symbol {esc(name)}', 700 + i * 120, 760)
    t = O('t b b', 700 + i * 120, 665); C(gs, t, i); C(t, gm, 1); C(t, nm, 0)
    C(nm, gname, 0, 1)
C(gt, O('s $0-ask', 860, 675), 1)
C(gt, O('s $0-status', 900, 650), 0)

lvl = O('r drummer-level', 1000, 520)
lvlLine = O('vline~', 1000, 570); C(lvl, M('$1 30', 1000, 545)); C(last(), lvlLine)
setter('drummer-swing', 'drmSw', 50, 75, False, 1100, 520)
setter('drummer-density', 'drmDens', 0, 1, True, 1100, 620)
setter('drummer-humanize', 'drmHum', 0, 1, True, 1100, 720)
C(O('r looper-layers', 1000, 620), O('v drmLayers', 1000, 645))

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

# ---------------- the brain (drummer/brain.py) on TCP 127.0.0.1:9312 ----------------
net = O('netreceive', 1700, 545); C(brainListen, net)
nr = O('route drmnext drmnexttime drmready', 1700, 570); C(net, nr)
C(nr, O('s drmnext', 1700, 595), 0); C(nr, O('s drmnexttime', 1780, 595), 1)
# "drmready <steps> <pass>": only the pass Pd is waiting for (a reply to a request made just
# before a loop boundary would otherwise be played one pass late)
C(nr, O('expr if($f2 == drmLoop+1, $f1, drmReadyN)', 1880, 595), 2); C(last(), O('v drmReadyN', 1880, 620))
# connections: 1 = brain up. When it goes away, stop waiting for its next pattern.
nc = O('t b b f', 1700, 620); C(net, nc, 1, 0)
C(nc, O('v drmUp', 1800, 645), 2)
C(nc, O('expr if(drmUp, drmReadyN, 0)', 1750, 670), 1); C(last(), O('v drmReadyN', 1750, 695))
C(nc, O('t b b', 1700, 720), 0); ct = last()
C(ct, O('s $0-ask', 1760, 745), 1); C(ct, O('s $0-status', 1700, 745), 0)
# ask for the next pass: loop <steps> <step-ms> <groove> <density> <humanize> <pass> <layers>
ask = O('r $0-ask', 1700, 790)
C(ask, O('expr drmUp && drmN > 0', 1700, 815)); asel = O('sel 1', 1700, 840); C(last() - 1, asel)
ax = O('expr drmN; drmStep; drmG; drmDens; drmHum; drmLoop+1; drmLayers', 1700, 865); C(asel, ax)
apk = O('pack f f f f f f f', 1700, 890)
for i in range(7):
    C(ax, apk, i, i)
C(apk, O('list prepend send loop', 1700, 915)); C(last(), O('list trim', 1700, 940)); C(last(), net)

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
ft = O('t b b b b b b', 1250, 625); C(rsel, ft, 0)
# 5: bars in the loop: from the tempo, else ~100 bpm in 4/4; more than 16 bars plays half-time
bars = O('expr if(drmBpm>0, max(1, rint(drmLen*drmBpm/240000)), max(1, rint(drmLen/2400)))', 1250, 650)
C(ft, bars, 5)
bx = O('expr if($f1>16, rint($f1/2), $f1)*16', 1250, 675); C(bars, bx)
nt = O('t f f', 1250, 700); C(bx, nt)
C(nt, O('v drmN', 1350, 725), 1)
sx = O('expr drmLen/$f1', 1250, 725); C(nt, sx, 0)
stt = O('t f f f', 1250, 750); C(sx, stt)
C(stt, O('* 4', 1350, 775), 2); C(last(), O('v drmBeat', 1350, 800))
C(stt, O('v drmStep', 1420, 775), 1)
C(stt, met, 0, 1)
# 4: the brain's next pass becomes this pass (if it is ready and fits the loop); otherwise
# keep the brain's pattern if it still fits, else play the fixed groove
rdy = O('expr drmReadyN == drmN', 1500, 650); C(ft, rdy, 4)
rys = O('sel 1 0', 1500, 675); C(rdy, rys)
cp = O('t b b b', 1500, 700); C(rys, cp, 0)
C(cp, O('array get drmnext', 1600, 725), 2); C(last(), O('array set drmgroove', 1600, 750))
C(cp, O('array get drmnexttime', 1600, 775), 1); C(last(), O('array set drmtime', 1600, 800))
C(cp, M('; drmBrain 1; drmReadyN 0', 1500, 725), 0)
C(cp, O('v drmN', 1500, 750), 0); C(last(), O('v drmGlen', 1500, 775))
C(rys, O('expr drmBrain && drmGlen == drmN', 1560, 700), 1); C(last(), O('v drmBrain', 1560, 725))
# 3: pass number (0 = the first after the clock starts)
C(ft, O('expr if(drmRun, drmLoop+1, 0)', 1400, 650), 3); C(last(), O('v drmLoop', 1400, 675))
# 2: restart the step counter, ask the brain for the next pass
C(ft, O('t b b', 1300, 650), 2); fr = last()
C(fr, M('0', 1300, 675), 1); C(last(), cnt, 0, 1)
C(fr, O('s $0-ask', 1330, 675), 0)
# 1: when the clock starts, play step 0 at once (later loops prepared it a step ahead)
C(ft, O('v drmRun', 1150, 650), 1); fz = O('sel 0', 1150, 675); C(last() - 1, fz)
fs = O('t b b b', 1150, 700); C(fz, fs)
C(fs, M('; drmRun 1; drmP 0; drmBase 0', 1150, 725), 2)
C(fs, O('v drmBrain', 1100, 750), 1); C(last(), O('v drmSrc', 1100, 775))
C(fs, O('s $0-prep', 1150, 800), 0)
# 0: start the 16ths
C(ft, met, 0)
C(ft, O('s $0-status', 1150, 825), 0)

stop = O('t b b b', 1100, 880)
C(O('r stop', 1100, 830), stop); C(O('r clearAll', 1170, 830), stop); C(rsel, stop, 1)
pipe = O('pipe 0', 1250, 1150)
C(stop, M('stop', 1250, 905), 2); C(last(), met)
C(stop, M('clear', 1300, 905), 2); C(last(), pipe)
C(stop, M('; drmRun 0; drmFillP 0; drmFill 0; drmReadyN 0', 1100, 905), 1)
C(stop, O('t b', 1100, 930), 0); want_update(last(), 0, 1100, 955)

# ---------------- each 16th: prepare the NEXT step ----------------
tick = O('t f f', 1250, 860); C(cnt, tick)
C(tick, O('v drmS', 1350, 885), 1)
inN = O('expr $f1 < drmN', 1250, 885); C(tick, inN, 0)
gate = O('sel 1', 1250, 910); C(inN, gate)
tt = O('t b b', 1250, 925); C(gate, tt)
# the step after this one wraps to step 0 of the next pass, which comes from drmnext if ready
nx = O('expr (drmS+1) % drmN; if(drmS+1 >= drmN, if(drmReadyN == drmN, 2, drmBrain), drmBrain); drmStep',
       1350, 925)
C(tt, nx, 1)
C(nx, O('v drmBase', 1700, 950), 2); C(nx, O('v drmSrc', 1600, 950), 1); C(nx, O('v drmP', 1500, 950), 0)
C(tt, O('s $0-prep', 1250, 950), 0)

prep = O('r $0-prep', 1250, 975)
st = O('t b b b b b', 1250, 1000); C(prep, st)
# 4: pause at a beat, resume at a bar line
C(st, O('expr if(drmP%16==0, drmWant, if(drmP%4==0, drmWant && drmAct, drmAct))', 1500, 1025), 4)
C(last(), O('t f f', 1500, 1050)); at = last()
C(at, O('v drmAct', 1600, 1075), 1)
C(at, O('change', 1500, 1075), 0); C(last(), O('s $0-status', 1500, 1100))
# 3: fills (accent on the downbeat after a fill, the fill plays on the last beat of the bar)
C(st, O('t b b b b', 1700, 1025), 3); ft2 = last()
C(ft2, O('expr if(drmP%16==0, drmFill, 0)', 1850, 1050), 3); C(last(), O('v drmAcc', 1850, 1075))
C(ft2, O('expr if(drmP%16==0, 0, if(drmP%16==12 && drmFillP, 1, drmFill))', 1800, 1100), 2)
C(last(), O('v drmFill', 1800, 1125))
C(ft2, O('expr if(drmP%16==12, 0, drmFillP)', 1750, 1150), 1); C(last(), O('v drmFillP', 1750, 1175))
C(ft2, O('expr drmFill && drmP%16 >= 12', 1700, 1200), 0); C(last(), O('v drmFm', 1700, 1225))
# 2: swing: the off-beat 8th moves to drmSw % of the beat, the 16ths in between follow
C(st, O('expr if(drmP%4==2, (drmSw-50)/100*drmBeat, if(drmP%2==1, (drmSw-50)/200*drmBeat, 0))', 1900, 1025), 2)
C(last(), O('v drmSwD', 1900, 1050))
# 1: the step's hits (only while active)
C(st, O('v drmAct', 1250, 1025), 1); hs = O('sel 1', 1250, 1050); C(last() - 1, hs)
ht = O('t b b b', 1250, 1075); C(hs, ht)
# downbeat accent after a fill (after the groove's hits, so its velocity wins)
C(ht, O('v drmAcc', 1400, 1100), 0); asl = O('sel 1', 1400, 1125); C(last() - 1, asl)
acct = O('t b b', 1400, 1150); C(asl, acct)
C(acct, O('v drmBase', 1460, 1175), 1); C(last(), pipe, 0, 1)
C(acct, M(', '.join(str(r * 128 + v) for r, v in ACCENT), 1400, 1175), 0); C(last(), pipe)
# roles 0-7: velocity (fill, fixed groove, this pass or the next), role*128 (the fixed groove
# opens the hi-hat on the loop's last off-beat; the brain does its own), delay
rl = O('until', 1250, 1100); C(ht, M('8', 1250, 1090), 1); C(last(), rl)
rc = O('f', 1250, 1125); C(rl, rc); C(rc, O('+ 1', 1300, 1125)); C(last(), rc, 0, 1)
C(ht, M('0', 1300, 1075), 2); C(last(), rc, 0, 1)
I = 'drmP*8+$f1'
ex = O(f'expr if(drmFm, drmfillpat[max(0, drmP%16-12)*8+$f1], if(drmSrc==0, drmbase[(drmP%16)*8+$f1], '
       f'if(drmSrc==1, drmgroove[{I}], drmnext[{I}]))); '
       'if(!drmFm && drmSrc==0 && drmP==drmN-2 && $f1==2, 3, $f1)*128; '
       f'max(0, drmBase + drmSwD + if(drmFm || drmSrc==0, 0, if(drmSrc==1, drmtime[{I}], drmnexttime[{I}])))',
       1250, 1150)
C(rc, ex)
add = O('+', 1250, 1190)
C(ex, pipe, 2, 1)
C(ex, add, 1, 1)
C(ex, O('moses 1', 1250, 1170), 0); C(last(), add, 1, 0)
C(add, pipe)
C(pipe, O('s drummer-hit', 1250, 1215))

# ---------------- voices ----------------
level = O('*~', 20, 1300); fade = O('*~', 20, 1330)
fadeLine = O('vline~', 80, 1305)
C(level, fade); C(lvlLine, level, 0, 1); C(fadeLine, fade, 0, 1)
C(O('r loopFade', 80, 1280), fadeLine)
C(lt, M('1', 160, 1280), 2); C(last(), fadeLine)
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
# playing: "<groove> - <bpm> bpm", plus "- fixed" while the brain isn't running (no variation)
pl = O('t b b b', 620, 1520); C(cs, pl, 3)
ppk = O('pack s f', 620, 1570)
C(pl, O('expr rint(600000/drmBeat)/10', 760, 1545), 2); C(last(), ppk, 0, 1)
C(pl, O('v drmUp', 900, 1545), 1); upt = O('t f f', 900, 1570); C(last() - 1, upt)
fixed, live = O('spigot', 620, 1620), O('spigot', 820, 1620)
C(upt, O('== 0', 900, 1595), 1); C(last(), fixed, 0, 1); C(upt, live, 0, 1)
C(pl, gname, 0); C(gname, ppk, 0, 0)
pt2 = O('t l l', 620, 1595); C(ppk, pt2); C(pt2, fixed, 1, 0); C(pt2, live, 0, 0)
C(fixed, M('color #2e7d32 #ffffff, label $1\\ -\\ $2\\ bpm\\ -\\ fixed', 620, 1645)); C(last(), cnv)
C(live, M('color #2e7d32 #ffffff, label $1\\ -\\ $2\\ bpm', 820, 1645)); C(last(), cnv)

p.save(os.path.join(HERE, '..', 'piLooper', 'drummer.pd'))
