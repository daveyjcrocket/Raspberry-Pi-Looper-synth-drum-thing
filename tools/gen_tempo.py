"""Generates piLooper/tempo.pd: tap tempo, click and count-in.

Tap: the tap pad (tap-note / tap-ch, default note 55 on channel 10 = pad 8 on LX25+ pad map 2,
learnable with "learn tap pad", saved in tappad.txt) or the on-screen TAP button (looper-tap).
Averages up to 4 intervals, restarts after a 2 s pause, ignores a tap more than 40 % off.
Tempo is locked unless the looper is READY. While the first layer records, the tap pad
completes the loop (same as Record) - for natural, free-length loops. Typing a bpm on screen sets it; 0 = free.

Publishes tempo-bpm (0 = no tempo). The click (tempo-click) sounds while the first layer records;
count-in (looper sends tempo-countin-start) plays 4 clicks, then sends looper-countin-done.
The click goes straight to [dac~], so it is never recorded.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1400, 1000)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
esc = lambda t: t.replace(' ', '\\ ')
p.text('Tap tempo, click, count-in. See tools/gen_tempo.py (this file is generated).', 20, 5)
O('table tap-iv 4', 1200, 950)
status = O('s knob-learn-cnv', 900, 560)
hint = O('s looper-hint', 400, 960)

def setter(name, value, x, y):
    m = M(str(value), x, y); C(m, O(f'v $0-{name}', x, y + 22)); return m

# ---------------- tap pad identity: defaults, saved file ----------------
lb = O('loadbang', 900, 30)
lbt = O('t b b', 900, 55); C(lb, lbt)
C(lbt, M('55', 1000, 80), 1); C(last(), O('v tap-note', 1000, 105))
C(lbt, M('10', 1050, 80), 1); C(last(), O('v tap-ch', 1050, 105))
tf = O('textfile', 900, 260)
fw = O('file which', 900, 105); C(lbt, M('symbol tappad.txt', 900, 80), 0); C(last(), fw)
fws = O('list split 1', 900, 130); C(fw, fws)
rd = O('t b b a', 900, 155); C(fws, rd)
C(rd, M('read $1', 900, 180), 2); C(last(), tf)
C(rd, M('rewind', 960, 180), 1); C(last(), tf)
C(rd, tf, 0, 0)
up = O('unpack f f', 900, 285); C(tf, up)
C(up, O('v tap-note', 900, 310), 0); C(up, O('v tap-ch', 980, 310), 1)

# ---------------- incoming notes: learn / tap ----------------
ni = O('notein', 20, 30)
pk = O('pack f f f', 20, 55); C(ni, pk, 2, 2); C(ni, pk, 1, 1); C(ni, pk, 0, 0)
br = O('t l l', 20, 80); C(pk, br)

# learn: the next note-on becomes the tap pad
la = O('t l l b', 600, 105); C(br, la, 1)
lx = O('expr $f4 && $f2>0', 600, 160)
C(la, O('v $0-learn', 700, 130), 2); C(last(), lx, 0, 3)
lu = O('unpack f f f', 660, 160); C(la, lu, 1)
nS, cS = O('f', 660, 250), O('f', 720, 250)
C(lu, nS, 0, 1); C(lu, cS, 2, 1)
C(la, lx, 0, 0)
lsel = O('sel 1', 600, 185); C(lx, lsel)
lt = O('t b b b', 600, 210); C(lsel, lt)
C(lt, setter('learn', 0, 780, 235), 2)
C(lt, nS, 1); C(nS, O('v tap-note', 660, 275))
C(lt, cS, 1); C(cS, O('v tap-ch', 720, 275))
lp = O('pack f f', 600, 330); C(lt, O('t b b', 600, 305), 0); tb2 = last()
C(tb2, cS, 1); C(cS, lp, 0, 1); C(tb2, nS, 0); C(nS, lp, 0, 0)
C(lp, M('label tap\\ pad\\ =\\ note\\ $1\\ ch\\ $2', 600, 355)); C(last(), status)
C(lp, O('t l b', 700, 355)); sv = last()
C(sv, M('clear', 760, 380), 1); C(last(), tf)
C(sv, O('list prepend add', 700, 380), 0); C(last(), O('list trim', 700, 405)); C(last(), tf)
C(sv, M('write tappad.txt', 820, 405), 0); C(last(), tf)
lr = O('t b b', 600, 430); C(O('r tap-learn', 600, 405), lr)
C(lr, setter('learn', 1, 600, 455), 1); C(lr, M('label hit\\ the\\ tap\\ pad', 660, 455), 0); C(last(), status)

# tap: note == tap-note on tap-ch (0 = any), note-on only
ta = O('t l b b', 20, 105); C(br, ta, 0)
tx = O('expr $f1==$f4 && ($f5==0 || $f3==$f5) && $f2>0', 20, 160)
C(ta, O('v tap-ch', 160, 130), 2); C(last(), tx, 0, 4)
C(ta, O('v tap-note', 90, 130), 1); C(last(), tx, 0, 3)
C(ta, tx, 0, 0)
tapIn = O('t b b', 20, 210)
C(tx, O('sel 1', 20, 185)); C(last(), tapIn)
C(O('r looper-tap', 120, 185), tapIn)

# tap light (on-screen)
led = O('s tap-led', 300, 290)
C(tapIn, M('color #ffeb3b #000000', 300, 240), 1); C(last(), led)
C(tapIn, O('delay 100', 420, 240), 1); C(last(), M('color #555555 #000000', 420, 265)); C(last(), led)

# locked unless READY
ls = O('v $0-ls', 20, 240); C(tapIn, ls, 0)
lsel2 = O('sel 0', 20, 265); C(ls, lsel2)
lk = O('sel 1', 120, 290); C(lsel2, lk, 1)
C(lk, M('; looper-rec bang', 120, 315), 0)                     # RECORDING: close the loop
C(lk, M('label tempo\\ is\\ locked\\ -\\ clear\\ the\\ loop\\ to\\ change\\ it', 200, 315), 1); C(last(), hint)
tmr = O('timer', 20, 320)
tt = O('t b b', 20, 290); C(lsel2, tt, 0)
C(tt, tmr, 1, 1); C(tt, tmr, 0, 0)

# interval -> keep up to 4, average, bpm
gS = O('f', 300, 420)
gt = O('t f f', 20, 345); C(tmr, gt); C(gt, gS, 1, 1)
gd = O('t f b b b', 20, 370); C(gt, gd, 0)
dec = O('expr if($f1>2000 || !$f4, 0, if($f2>=2 && abs($f1-$f3)/$f3>0.4, 1, 2))', 20, 420)
C(gd, O('v $0-started', 220, 395), 3); C(last(), dec, 0, 3)     # first tap after startup only starts the count
C(gd, O('v $0-avg', 160, 395), 2); C(last(), dec, 0, 2)
C(gd, O('v $0-n', 100, 395), 1); C(last(), dec, 0, 1)
C(gd, dec, 0, 0)
ds = O('sel 0 1 2', 20, 445); C(dec, ds)
C(ds, setter('n', 0, 20, 470), 0); C(ds, setter('started', 1, 80, 470), 0)
st = O('t b b b', 200, 470); C(ds, st, 2)
tw = O('tabwrite tap-iv', 300, 560)
wt = O('t b b', 300, 495); C(st, wt, 2)
C(wt, O('v $0-n', 360, 520), 1); C(last(), O('% 4', 360, 540)); C(last(), tw, 0, 1)
C(wt, gS, 0); C(gS, tw, 0, 0)
C(st, O('v $0-n', 250, 520), 1); C(last(), O('+ 1', 250, 540)); C(last(), O('v $0-n', 250, 560))
C(st, O('v $0-n', 200, 600), 0); C(last(), O('min 4', 200, 625))
mt = O('t b f f', 200, 650); C(last() - 1, mt)
asum = O('array sum tap-iv', 200, 700); dv = O('/', 200, 725)
C(mt, asum, 2, 1); C(mt, dv, 1, 1); C(mt, M('0', 200, 675), 0); C(last(), asum); C(asum, dv)
av = O('t f f', 200, 750); C(dv, av); C(av, O('v $0-avg', 260, 775), 1)
bpm = O('expr min(300, max(30, rint(600000/$f1)/10))', 200, 800); C(av, bpm, 0)
pub = O('s $0-pub', 200, 825); C(bpm, pub)

# typed on screen (0 = free); only while READY
ts = O('t b f', 600, 620); C(O('r tempo-set', 600, 595), ts)
tv = O('f', 700, 645); C(ts, tv, 1, 1)
C(ts, O('v $0-ls', 600, 645), 0); tsl = O('sel 0', 600, 670); C(last() - 1, tsl)
C(tsl, tv, 0); C(tv, O('expr if($f1<=0, 0, min(300, max(30, $f1)))', 700, 695)); C(last(), O('s $0-pub', 700, 720))
C(tsl, O('v $0-bpm', 620, 720), 1); C(last(), M('; tempo-bpm-gui set $1', 620, 745))

# publish
pb = O('t f f', 400, 850); C(O('r $0-pub', 400, 825), pb)
C(pb, O('v $0-bpm', 500, 875), 1)
C(pb, O('s tempo-bpm', 400, 900), 0)
C(pb, M('; tempo-bpm-gui set $1', 520, 900), 0)

# ---------------- click / count-in ----------------
met = O('metro 500', 1000, 600)
C(O('r tempo-bpm', 1100, 550), O('expr 60000/max($f1, 1)', 1100, 575)); C(last(), met, 0, 1)
bc = O('f', 1000, 625); inc = O('+ 1', 1040, 625); C(met, bc); C(bc, inc); C(inc, bc, 0, 1)
tk = O('t f f f', 1000, 650); C(bc, tk)
# count-in bookkeeping (fires first)
cx = O('expr if($f2, if($f1<4, 1, 2), 0)', 1150, 700)
b2 = O('t f f', 1150, 660); C(tk, b2, 2)                  # store beat+1 for the label first
C(b2, O('t f b', 1150, 675), 0); cb = last()
C(cb, O('v $0-counting', 1220, 690), 1); C(last(), cx, 0, 1); C(cb, cx, 0, 0)
cs = O('sel 1 2', 1150, 725); C(cx, cs)
C(b2, O('+ 1', 1300, 700), 1)       # beat number shown during count-in
cnum = last(); cf = O('f', 1300, 750); C(cnum, cf, 0, 1)
C(cs, cf, 0); C(cf, M('label count-in\\ $1', 1300, 775)); C(last(), hint)
cd = O('t b b b', 1150, 750); C(cs, cd, 1)
C(cd, setter('counting', 0, 1150, 775), 2)
C(cd, M('; looper-countin-done bang', 1150, 820), 1)
C(cd, O('v $0-clickon', 1230, 800), 0); C(last(), O('sel 0', 1230, 825)); C(last(), M('0', 1230, 850)); C(last(), met)
# click sound
ce = O('expr if($f2 || $f3, if($f1%4==0, 2, 1), 0)', 1000, 725)
C(tk, O('t f b b', 1000, 700), 1); ct = last()
C(ct, O('v $0-counting', 1060, 715), 2); C(last(), ce, 0, 2)
C(ct, O('v $0-clickon', 1100, 715), 1); C(last(), ce, 0, 1)
C(ct, ce, 0, 0)
csel = O('sel 1 2', 1000, 750); C(ce, csel)
osc = O('osc~ 1000', 1000, 850); env = O('vline~', 1080, 850); mul = O('*~', 1000, 875)
C(osc, mul); C(env, mul, 0, 1)
C(mul, O('*~ 0.25', 1000, 900)); C(last(), O('dac~ 1 2', 1000, 925)); dac = last(); C(last() - 1, dac, 0, 1)
for i, f in enumerate((1000, 1600)):
    t = O('t b b', 1000 + i * 90, 775); C(csel, t, i)
    C(t, M(str(f), 1000 + i * 90, 800), 1); C(last(), osc)
    C(t, M('1, 0 40', 1000 + i * 90, 825), 0); C(last(), env)
C(O('r tempo-click', 1200, 880), O('v $0-clickon', 1200, 905))

def start(x, y):
    t = O('t b b b', x, y)
    C(t, M('0', x, y + 25), 2); C(last(), bc, 0, 1)
    C(t, setter('running', 1, x + 40, y + 25), 1)
    C(t, M('1', x + 80, y + 25), 0); C(last(), met)
    return t

def stop(x, y):
    t = O('t b b', x, y)
    C(t, setter('running', 0, x, y + 25), 1); C(t, M('0', x + 40, y + 25), 0); C(last(), met)
    return t

# looper state: start the click when the first layer starts recording; stop it otherwise
sr = O('t f f', 600, 780); C(O('r looper-state', 600, 755), sr)
C(sr, O('v $0-ls', 700, 805), 1)
sx = O('t f b b b b', 600, 805); C(sr, sx, 0)
sc = O('expr if($f1==1, if($f2>0 && $f3 && !$f4, 1, 0), if($f5, 0, 2))', 600, 880)
for outlet, name, x in ((4, 'counting', 880), (3, 'running', 820), (2, 'clickon', 760), (1, 'bpm', 700)):
    C(sx, O(f'v $0-{name}', x, 830), outlet); C(last(), sc, 0, outlet)
C(sx, sc, 0, 0)
ssel = O('sel 1 2', 600, 905); C(sc, ssel)
C(ssel, start(600, 930), 0); C(ssel, stop(720, 930), 1)

# count-in start / cancel
ci = O('t b b', 900, 640); C(O('r tempo-countin-start', 900, 615), ci)
C(ci, setter('counting', 1, 900, 665), 1); C(ci, start(900, 700), 0)
cc = O('t b b b', 800, 640); C(O('r tempo-countin-cancel', 800, 590), cc); C(O('r clearAll', 800, 615), cc)
C(cc, setter('counting', 0, 800, 665), 2); C(cc, stop(800, 700), 1)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'tempo.pd'))
