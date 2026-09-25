"""Generates piLooper/Loop.pd: one looper layer (instantiated as [Loop N]).

Continuous overdub uses two tables per layer, loop-N and loop-N-b. While a
layer records, each loop cycle plays one table and writes "that + input" into
the other, then they swap at the loop boundary [r f]. The table holding the
latest complete take is announced on loop-N-active (used by loopSave).

Messages (receive name layer-N): "rec <onset-in-samples>" starts overdubbing,
"close" stops taking input (the layer is finalized at the next boundary).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1180, 820)
O, M, C = p.obj, p.msg, p.conn

p.text('One looper layer. See tools/gen_loop.py (this file is generated).', 20, 10)
O('table loop-$1 1e+06', 20, 780)
O('table loop-$1-b 1e+06', 200, 780)

# ---------------- audio ----------------
play = O('tabplay~ loop-$1', 20, 420)
inp = O('r~ input', 200, 380)
gateMul = O('*~', 200, 440)
gateLine = O('vline~', 240, 410)
write = O('tabwrite~ loop-$1-b', 20, 480)
C(play, write); C(inp, gateMul); C(gateLine, gateMul, 0, 1); C(gateMul, write)
gainMul = O('*~', 20, 540); gainLine = O('vline~', 80, 515)
C(play, gainMul); C(gainLine, gainMul, 0, 1)
fadeMul = O('*~', 20, 600); fadeLine = O('vline~', 80, 575)
C(gainMul, fadeMul); C(fadeLine, fadeMul, 0, 1)
C(fadeMul, O('s~ lp-out-$1', 20, 630))
C(O('r loopFade', 80, 550), fadeLine)

# ---------------- table selection (swap) ----------------
pA = O('symbol loop-$1', 420, 330); pB = O('symbol loop-$1-b', 520, 330)
wA = O('symbol loop-$1', 640, 330); wB = O('symbol loop-$1-b', 740, 330)
setP = M('set $1', 420, 360); setW = M('set $1', 640, 360)
for s in (pA, pB): C(s, setP)
for s in (wA, wB): C(s, setW)
C(setP, play); C(setW, write); C(setP, O('s loop-$1-active', 480, 390))

swap = O('v $0-src', 420, 240)
inv = O('expr 1-$f1', 420, 265)
swapT = O('t f f', 420, 290)
selSrc = O('sel 0 1', 420, 310)
C(swap, inv); C(inv, swapT); C(swapT, O('v $0-src', 500, 290), 1, 0); C(swapT, selSrc)
C(selSrc, pA, 0); C(selSrc, wB, 0); C(selSrc, pB, 1); C(selSrc, wA, 1)

# state setters
def setter(name, value, x, y):
    m = M(str(value), x, y); C(m, O(f'v $0-{name}', x, y + 22)); return m

# ---------------- loop boundary ----------------
rf = O('r f', 20, 40)
bt = O('t b b b', 20, 65)
vRec = O('v $0-rec', 20, 90); vClos = O('v $0-clos', 100, 90); vCont = O('v $0-cont', 180, 90)
act = O('expr if($f1, 1, if($f2, 2, if($f3, 3, 0)))', 20, 115)
selAct = O('sel 1 2 3', 20, 140)
C(rf, bt); C(bt, vCont, 2); C(bt, vClos, 1); C(bt, vRec, 0)
C(vRec, act, 0, 0); C(vClos, act, 0, 1); C(vCont, act, 0, 2); C(act, selAct)

playFromStart = M('0', 20, 390); C(playFromStart, play)
startW = M('start 0', 100, 390); C(startW, write)
stopW = M('stop', 170, 390); C(stopW, write)
stopP = M('stop', 220, 390); C(stopP, play)
contOn = setter('cont', 1, 300, 160)

# 1: recording -> swap, keep overdubbing into the other table
a1 = O('t b b b b', 20, 170)
C(selAct, a1, 0)
C(a1, swap, 3); C(a1, contOn, 2); C(a1, playFromStart, 1); C(a1, startW, 0)

# 2: closing -> swap to the table just written, stop writing, announce
a2 = O('t b b b b b b', 20, 220)
C(selAct, a2, 1)
closOff = setter('clos', 0, 360, 200)
notify = O('t b b b', 120, 260)
C(a2, swap, 5); C(a2, playFromStart, 4); C(a2, stopW, 3); C(a2, closOff, 2); C(a2, contOn, 1); C(a2, notify, 0)

# 3: has content, not recording -> restart playback
C(selAct, playFromStart, 2)

# announce "this layer has content" (lp-done-N for save/GUI, layerHasContent for the looper)
guard = O('spigot 1', 900, 120)
gClose = M('0', 860, 290); gOpen = M('1', 960, 290)
C(gClose, guard, 0, 1); C(gOpen, guard, 0, 1)
done10 = M('10', 900, 290); C(done10, O('s lp-done-$1', 900, 315))
fN = O('f $1', 1000, 290); C(fN, O('s layerHasContent', 1000, 315))
C(notify, gClose, 2); C(notify, done10, 1); C(notify, fN, 1); C(notify, gOpen, 0)

# lp-done-N from elsewhere (song load put a stem in loop-N)
C(O('r lp-done-$1', 900, 90), guard)
loaded = O('t b b b', 900, 150)
C(guard, loaded)
srcA = setter('src', 0, 960, 180)
C(loaded, srcA, 2); C(loaded, contOn, 1); C(loaded, pA, 1); C(loaded, wB, 1); C(loaded, fN, 0)

# ---------------- rec / close commands ----------------
rt = O('route rec close preview', 560, 40)
C(O('r layer-$1', 560, 15), rt)
recT = O('t f b b b b', 560, 70)
C(rt, recT, 0)
const0 = M('const 0', 760, 100)
C(const0, O('s loop-$1', 760, 125)); C(const0, O('s loop-$1-b', 830, 125))
C(recT, const0, 4)
for name, val, x in (('rec', 1, 640), ('clos', 0, 680), ('cont', 0, 720), ('src', 0, 760)):
    C(recT, setter(name, val, x, 160), 3)
C(recT, pA, 2); C(recT, wB, 2)
gateOn = M('1 5', 600, 100); C(recT, gateOn, 1); C(gateOn, gateLine)
onsetT = O('t f f', 560, 100)
C(recT, onsetT, 0)
C(onsetT, play, 1, 0)
startAt = M('start $1', 560, 125); C(onsetT, startAt, 0); C(startAt, write)

closeCheck = O('v $0-rec', 660, 40); closeSel = O('sel 1', 660, 65)
C(rt, closeCheck, 1); C(closeCheck, closeSel)
closeT = O('t b b b', 660, 90)
C(closeSel, closeT)
gateOff = M('0 5', 760, 200); C(gateOff, gateLine)
C(closeT, gateOff, 2); C(closeT, setter('rec', 0, 840, 200), 1); C(closeT, setter('clos', 1, 880, 200), 0)

# ---------------- stop / clear ----------------
stopD = O('delay 15', 20, 680)
C(O('r stop', 20, 655), stopD)
stopT = O('t b b b b', 20, 705)
C(stopD, stopT)
gateZero = M('0', 180, 730); C(gateZero, gateLine)
C(stopT, stopP, 3); C(stopT, stopW, 2); C(stopT, setter('rec', 0, 120, 730), 1)
C(stopT, setter('clos', 0, 160, 730), 1); C(stopT, gateZero, 0)

clearT = O('t b b b b b', 300, 680)
C(O('r clear-$1', 300, 655), clearT); C(O('r clearAll', 380, 655), clearT)
C(clearT, stopP, 4); C(clearT, stopW, 4); C(clearT, const0, 3)
for name, x in (('rec', 480), ('clos', 520), ('cont', 560), ('src', 600)):
    C(clearT, setter(name, 0, x, 700), 2)
C(clearT, pA, 1); C(clearT, wB, 1); C(clearT, gateZero, 1)

# ---------------- volume, manual mute, keep-first-N mute ----------------
volF = O('f 1', 700, 460)
C(O('r lp-vol-$1', 700, 435), volF)
g = O('expr $f1*(1-(($f2!=0)||(($f3!=0)&&( $1 > $f4 ))))', 700, 490)
C(volF, g, 0, 0)
gm = M('$1 15', 700, 515); C(g, gm); C(gm, gainLine)
for rname, inlet, x, vname in (('keepActive', 2, 880, 'ka'), ('keepN', 3, 980, 'kn')):
    t = O('t b f', x, 435); C(O(f'r {rname}', x, 410), t); C(t, g, 1, inlet); C(t, volF, 0, 0)
    C(t, O(f'v $0-{vname}', x + 40, 460), 1)
tog = O('f', 780, 380); togInv = O('== 0', 780, 405); manT = O('t b f', 780, 435)
C(O('r lp-trig-$1', 780, 355), tog); C(tog, togInv); C(togInv, tog, 0, 1); C(togInv, manT)
C(manT, g, 1, 1); C(manT, volF, 0, 0); C(manT, O('v $0-man', 830, 460), 1)
unmute = M('0', 840, 355); C(unmute, tog, 0, 1); C(unmute, manT)
C(clearT, unmute, 0)
C(O('r unmuteAll', 840, 330), unmute)

# save: current volume and whether this layer has content
volSave = O('f 1', 1000, 460)
C(O('r lp-vol-$1', 1000, 435), volSave, 0, 1)
saveT = O('t b b', 1000, 510)
C(O('r save', 1000, 485), saveT)
C(saveT, volSave, 1); C(volSave, O('s vol-$1', 1000, 540))
sc = O('v $0-cont', 1080, 540); C(saveT, sc, 0)
x10 = O('* 10', 1080, 565); C(sc, x10); C(x10, O('s lpd-$1', 1080, 590))

# ---------------- init ----------------
lb = O('loadbang', 300, 15)
lbT = O('t b b b', 300, 40)
C(lb, lbT)
fade1 = M('1', 300, 65); C(fade1, fadeLine)
C(lbT, fade1, 2); C(lbT, pA, 1); C(lbT, wB, 1); C(lbT, volF, 0)

# ---------------- front-panel cell: empty / playing / REC / muted, ">" = selected ----------------
sel = O('r selected-loop-r', 20, 860)
selP = O('+ 1', 20, 885); C(sel, selP)
selEq = O('== $1', 20, 910); C(selP, selEq); C(selEq, O('v $0-sel', 20, 935))
poll = O('metro 120', 200, 860); C(lb, poll)
pt = O('t b b b b b b b', 200, 885); C(poll, pt)
code = O('expr if($f1||$f2, 2, if($f3 && ($f4 || ($f5 && ( $1 > $f6 ))), 3, if($f3, 1, 0))) + 10*$f7', 200, 960)
for k, name in enumerate(['rec', 'clos', 'cont', 'man', 'ka', 'kn', 'sel']):
    v = O(f'v $0-{name}', 200 + k * 70, 910); C(pt, v, k); C(v, code, 0, k)
ch = O('change -1', 200, 985); C(code, ch)
cs = O('sel 0 1 2 3 10 11 12 13', 200, 1010); C(ch, cs)
look = {0: ('#3c3c3c', '#8c8c8c', 'empty'), 1: ('#2e7d32', '#ffffff', 'playing'),
        2: ('#c62828', '#ffffff', 'REC'), 3: ('#455a64', '#b0bec5', 'muted')}
out = O('s lyr-$1-cnv', 200, 1080)
for i, c in enumerate([0, 1, 2, 3, 10, 11, 12, 13]):
    bg, fg, word = look[c % 10]
    label = ('>\\ ' if c >= 10 else '') + word
    m = M(f'color {bg} {fg}, label {label}', 200 + i * 110, 1040); C(cs, m, i); C(m, out)

# preview <onset>: play the take being written (the first layer, pressed late with a tempo)
pv = O('t f b', 1000, 700); C(rt, pv, 2)
pvs = O('v $0-src', 1000, 725); C(pv, pvs, 1)
pvsel = O('sel 0 1', 1000, 750); C(pvs, pvsel)
C(pvsel, pB, 0); C(pvsel, pA, 1)          # src 0 writes table b, src 1 writes table a
C(pv, play, 0, 0)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'Loop.pd'))
