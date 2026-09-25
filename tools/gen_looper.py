"""Generates piLooper/looper.pd: the looper controller (one [looper] in the main patch).

States: 0 READY (empty, auto-record armed)  1 RECORDING (first layer, sets loop length)
        2 OVERDUB (a layer is recording)     3 PLAYING (play-through, nothing recorded)
        4 FADING (fade-out over one cycle)   5 STOPPED

Buttons (receive names): looper-rec, looper-play, looper-stop, looper-keep, looper-keepn-step.
LX25+: Record 107, Play 106, Stop 105 (via [pd loop-control]); Rewind 103 = step N; Fast-forward 104 = keep/unmute.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1300, 900)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
p.text('Looper controller. See tools/gen_looper.py (this file is generated).', 20, 5)

MAX_LAYERS = 8
MAX_FIRST_MS = 20000      # loop tables hold 1e6 samples (20.8 s at 48 kHz)

def send(name, x, y):
    return O(f's {name}', x, y)

# ---------------- state + status ----------------
setstate = O('r $0-setstate', 20, 30)
stT = O('t f f', 20, 55)
C(setstate, stT); C(stT, O('v $0-state', 100, 80), 1); C(stT, O('s looper-state', 180, 80), 1)
stSel = O('sel 0 1 2 3 4 5', 20, 80)
C(stT, stSel)
status = send('looper-status', 20, 130)
for i, name in enumerate(['READY', 'RECORDING', 'OVERDUB', 'PLAYING', 'FADING', 'STOPPED']):
    m = M(f'symbol {name}', 20 + i * 80, 105); C(stSel, m, i); C(m, status)
# entering READY: auto-record is allowed again after 1 s (lets reverb tails die away)
armOff = M('0', 520, 130); armD = O('delay 1000', 560, 130); armOn = M('1', 560, 155)
C(stSel, armOff, 0); C(stSel, armD, 0); C(armD, armOn)
C(armOff, O('v $0-armed', 520, 180)); C(armOn, O('v $0-armed', 600, 180))

def setst(n, x, y):
    m = M(str(n), x, y); C(m, send('$0-setstate', x, y + 20)); return m

layers = send('looper-layers', 700, 130)
def setL(x, y):
    """Returns an object: float in -> stores layer count and shows it."""
    t = O('t f f', x, y); C(t, O('v $0-L', x + 60, y + 25), 1); C(t, layers, 0); return t

# ---------------- position in the loop (for starting layers mid-cycle) ----------------
tm = O('timer', 900, 60)
C(O('r f', 900, 35), tm)
onsetIn = O('r $0-onset', 1000, 10)
onT = O('t b b b', 1000, 35)
C(onsetIn, onT)
sr = O('samplerate~', 1100, 60)
onExpr = O('expr max(0, min(int($f1*$f2/1000), int($f3*$f2/1000)-64))', 900, 90)
C(onT, sr, 2); C(sr, onExpr, 0, 1)
C(onT, O('v $0-len', 1000, 60), 1); C(p.lines.__len__() - 1, onExpr, 0, 2)
C(onT, tm, 0, 1); C(tm, onExpr)
C(onExpr, send('$0-startLayer', 900, 115))

# ---------------- start the next layer at <onset> ----------------
slT = O('t b f', 20, 200)
C(O('r $0-startLayer', 20, 175), slT)
pk = O('pack 0 0', 20, 275)
C(slT, pk, 1, 1)
vL = O('v $0-L', 20, 225); C(slT, vL, 0)
mo = O('moses %d' % MAX_LAYERS, 20, 250); C(vL, mo)
plus = O('+ 1', 20, 275 - 0); C(mo, plus, 0)
plT = O('t f f', 20, 300); C(plus, plT)
C(plT, setL(120, 300), 1); C(plT, pk, 0)
plT2 = O('t b l', 20, 330); C(pk, plT2)
C(plT2, M('; layer-$1 rec $2', 60, 355), 1); C(plT2, setst(2, 20, 380), 0)
full = O('t b', 200, 250); C(mo, full, 1)
C(full, O('print looper:_all_8_layers_used', 200, 275)); C(full, setst(3, 360, 250))

# ---------------- close the recording layer ----------------
closeT = O('v $0-L', 20, 450)
C(O('r $0-close', 20, 425), closeT)
cm = O('moses 1', 20, 475); C(closeT, cm)
C(cm, M('; layer-$1 close', 60, 500), 1)

# ---------------- first layer ----------------
tLen = O('timer', 400, 450)
maxD = O('delay %d' % MAX_FIRST_MS, 520, 450)
C(maxD, send('looper-rec', 520, 475))
r1 = O('t b b b b', 400, 400)
C(O('r $0-rec1', 400, 375), r1)
C(r1, M('; layer-1 rec 0', 520, 400), 3)
one = M('1', 600, 425); C(r1, one, 2); C(one, setL(600, 450))
C(r1, tLen, 1); C(r1, maxD, 1)
C(r1, setst(1, 480, 425), 0)

# end of first layer: <mode> 1 = start overdubbing layer 2, 0 = play-through
e1 = O('t b f', 400, 540)
C(O('r $0-end1', 400, 515), e1)
modeF = O('f', 500, 640); C(e1, modeF, 1, 1)
eb = O('t b b', 400, 565); C(e1, eb, 0)
C(eb, M('stop', 520, 565), 1); C(p.lines.__len__() - 1, maxD)
C(eb, tLen, 0, 1)
lm = O('moses 250', 400, 590); C(tLen, lm)       # ignore double-taps shorter than 250 ms
def ending(value, x, y):
    m = M(str(value), x, y); C(m, O('v $0-ending', x, y + 22)); return m

# finish the first layer with loop length <len>
lt = O('t b b f f', 400, 615)
C(lt, O('v $0-len', 520, 640), 3)
C(lt, M('; layer-1 close; ms $1; play bang', 400, 640), 2)
C(lt, ending(0, 470, 665), 1)
C(lt, modeF, 0); ms = O('sel 1 0', 500, 665); C(modeF, ms)
z = M('0', 500, 690); C(ms, z, 0); C(z, send('$0-startLayer', 500, 715))
C(ms, setst(3, 560, 690), 1)

# With a tempo, the length snaps to the nearest whole number of 4/4 bars (max 20 s).
# Pressed early: keep recording until the bar line. Pressed late: close now, play the
# loop from where the performance has got to, and start the loop clock at the next bar line.
sn = O('t f f', 200, 590); C(lm, sn, 1)
diff = O('-', 200, 690); C(sn, diff, 1, 1)                  # len -> right inlet (cold)
snx = O('expr if($f2>0, max(1, min(rint($f1*$f2/240000), floor(%d*$f2/240000)))*240000/$f2, $f1)' % MAX_FIRST_MS, 200, 640)
snt = O('t f b', 200, 615); C(sn, snt, 0)
C(snt, O('v $0-bpm', 260, 630), 1); C(last(), snx, 0, 1); C(snt, snx, 0, 0)
sS = O('f', 60, 740); sL = O('f', 30, 870)   # snapped length: early path / late path
plus = O('+', 300, 760)
st2 = O('t f f f', 200, 665); C(snx, st2)
C(st2, sS, 2, 1); C(st2, sL, 2, 1); C(st2, plus, 1, 1); C(st2, diff, 0, 0)    # snapped: store, then diff = snapped - len
dm = O('moses 0', 200, 715); C(diff, dm)
# early (diff >= 0): wait diff ms, then finish with the snapped length
pp = O('pipe', 60, 790)
et = O('t b b f', 260, 740); C(dm, et, 1)
C(et, pp, 2, 1); C(et, ending(1, 330, 765), 1); C(et, sS, 0); C(sS, pp, 0, 0); C(pp, lt)
# late (diff < 0): d = -diff, wait = snapped - d
dS, wS = O('f', 120, 820), O('f', 300, 820)
lat = O('t b b b f', 120, 740); C(dm, lat, 0)
lf = O('t f f', 200, 790); C(lat, lf, 3)
C(lf, O('* -1', 160, 815), 1); C(last(), dS, 0, 1)
C(lf, plus, 0, 0); C(plus, wS, 0, 1)
C(lat, ending(1, 400, 765), 2)
lpk = O('pack f f', 120, 900)
lg = O('t b b b', 120, 845); C(lat, lg, 1)
C(lg, dS, 2); C(dS, lpk, 0, 1)
C(lg, sL, 1); lsf = O('t f f', 60, 895); C(sL, lsf)
C(lsf, O('v $0-len', 30, 920), 1); C(lsf, lpk, 0, 0)
C(lpk, M('; layer-1 close; layer-1 preview $2; ms $1', 120, 925))
C(lg, setst(3, 240, 870), 0)
lateD = O('delay', 300, 845); C(lat, wS, 0); C(wS, lateD)
ld = O('t b b', 300, 870); C(lateD, ld)
C(ld, M('; play bang', 360, 895), 1)
C(ld, ending(0, 300, 895), 0); C(ld, modeF, 0)

# ---------------- fade / stop / clear ----------------
fadeD = O('delay', 800, 450)
fT = O('t f f', 800, 425)
C(O('r $0-fade', 800, 375), O('v $0-len', 800, 400)); C(p.lines.__len__() - 1, fT)
C(fT, M('; loopFade 0 $1', 870, 450), 1); C(fT, fadeD, 0)
C(O('r $0-fade', 960, 375), setst(4, 960, 400))
C(fadeD, send('$0-hardstop', 800, 475))

cf = O('t b b', 800, 520)
C(O('r $0-cancelfade', 800, 500), cf)
C(cf, M('stop', 860, 545), 1); C(p.lines.__len__() - 1, fadeD)
C(cf, M('; loopFade 1 30', 800, 545), 0)

hs = O('t b b b b', 1000, 520)
C(O('r $0-hardstop', 1000, 500), hs)
C(hs, M('stop', 1100, 545), 3); C(p.lines.__len__() - 1, fadeD)
C(hs, M('; stop bang', 1060, 570), 2)
rd = O('delay 40', 1020, 595); C(hs, rd, 1); C(rd, M('; loopFade 1 0', 1020, 620))
C(hs, setst(5, 1000, 645), 0)

clr = O('t b b b', 800, 700)
C(O('r $0-clear', 800, 680), clr)
C(clr, M('stop', 880, 725), 2); C(p.lines.__len__() - 1, fadeD)
C(clr, M('stop', 920, 725), 1); C(p.lines.__len__() - 1, maxD)
C(clr, M('; clearAll bang; loopFade 1 0', 800, 750), 0)
C(O('r clearAll', 900, 780), O('t b b b', 900, 800)); cz = last()
C(cz, M('clear', 900, 825), 2); C(last(), pp)
C(cz, M('stop', 950, 825), 1); C(last(), lateD)
C(cz, ending(0, 1000, 825), 0)
C(cz, M('0', 1050, 825), 0); C(last(), O('v $0-counting', 1050, 850))

# clearAll from anywhere (also sent at load): back to READY with no layers
ca = O('t b b', 1000, 700)
C(O('r clearAll', 1000, 680), ca)
z0 = M('0', 1080, 725); C(ca, z0, 1); C(z0, setL(1080, 750))
C(ca, setst(0, 1000, 725), 0)

# ---------------- buttons ----------------
def dispatch(recv, x, y):
    g = O('v $0-ending', x, y + 12); C(O(f'r {recv}', x, y), g)   # ignored while a bar-snapped finish is pending
    gs = O('sel 0', x + 90, y + 12); C(g, gs)
    t = O('v $0-state', x, y + 25); C(gs, t)
    s = O('sel 0 1 2 3 4 5', x, y + 50); C(t, s); return s

def go(name):
    return send(f'$0-{name}', 0, 0)

def chain(src, outlet, *names, x=0, y=0):
    """src outlet -> [t b b ...] firing $0-<names> in the listed order."""
    t = O('t' + ' b' * len(names), x, y); C(src, t, outlet)
    for i, n in enumerate(names):
        C(t, n if isinstance(n, int) else go(n), len(names) - 1 - i)
    return t

def bangmsg(text):
    return M(text, 0, 0)

# Record
rs = dispatch('looper-rec', 20, 800)
# READY: with a tempo and count-in on, count in first
rc = O('t b b b', 20, 875); C(rs, rc, 0)
cx = O('expr if($f1, 2, if($f2>0 && $f3, 1, 0))', 20, 925)
C(rc, O('v $0-bpm', 120, 900), 2); C(last(), cx, 0, 1)
C(rc, O('v $0-countin', 180, 900), 1); C(last(), cx, 0, 2)
C(rc, O('v $0-counting', 60, 900), 0); C(last(), cx, 0, 0)
cxs = O('sel 0 1', 20, 950); C(cx, cxs)
C(cxs, go('rec1'), 0)
cit = O('t b b b', 100, 975); C(cxs, cit, 1)
C(cit, M('1', 100, 1000), 2); C(last(), O('v $0-counting', 100, 1020))
C(cit, M('0', 140, 1000), 1); C(last(), O('v $0-armed', 140, 1020))
C(cit, M('; tempo-countin-start bang', 180, 1000), 0)
cd = O('t b b', 300, 975); C(O('r looper-countin-done', 300, 950), cd)
C(cd, M('0', 300, 1000), 1); C(last(), O('v $0-counting', 300, 1020))
C(cd, O('v $0-state', 360, 1000), 0); C(last(), O('sel 0', 360, 1020)); C(last(), go('rec1'))
C(O('r tempo-bpm', 450, 950), O('v $0-bpm', 450, 975))
C(O('r tempo-countin', 550, 950), O('v $0-countin', 550, 975))
m1 = M('1', 90, 875); C(rs, m1, 1); C(m1, go('end1'))
chain(rs, 2, 'close', 'onset', x=160, y=875)
chain(rs, 3, 'onset', x=240, y=875)
chain(rs, 4, 'cancelfade', 'onset', x=300, y=875)
pz = M('; play bang', 380, 900); zz = M('0', 460, 900); C(zz, go('startLayer'))
chain(rs, 5, pz, zz, x=380, y=875)

# Play
ps = dispatch('looper-play', 520, 800)
m0 = M('0', 590, 875); C(ps, m0, 1); C(m0, go('end1'))
chain(ps, 2, 'close', setst(3, 660, 900), x=660, y=875)
chain(ps, 4, 'cancelfade', setst(3, 760, 900), x=760, y=875)
chain(ps, 5, M('; play bang', 860, 900), setst(3, 940, 900), x=860, y=875)

# Stop
ss = dispatch('looper-stop', 1000, 800)
# READY: Stop cancels a count-in
sc0 = O('v $0-counting', 1000, 875); C(ss, sc0, 0)
C(sc0, O('sel 1', 1000, 900)); sct = O('t b b b', 1000, 925); C(last() - 1, sct)
C(sct, M('0', 1000, 950), 2); C(last(), O('v $0-counting', 1000, 970))
C(sct, M('; tempo-countin-cancel bang', 1040, 950), 1)
C(sct, setst(0, 1100, 950), 0)
chain(ss, 1, 'clear', x=1070, y=875)
chain(ss, 2, 'close', 'fade', x=1120, y=875)
chain(ss, 3, 'fade', x=1180, y=875)
chain(ss, 4, 'hardstop', x=1220, y=875)
chain(ss, 5, 'clear', x=1260, y=875)

# LX25+ Rewind (103) / Fast-forward (104)
bs = O('sel 103 104', 1100, 180)
C(O('r midi-btn-ctl-in', 1100, 155), bs)
C(bs, send('looper-keepn-step', 1100, 205), 0); C(bs, send('looper-keep', 1180, 205), 1)

# keep-first-N mute: toggle, and turning it off also unmutes every layer
kv = O('v $0-keep', 1100, 260); C(O('r looper-keep', 1100, 235), kv)
kinv = O('== 0', 1100, 285); C(kv, kinv)
C(kinv, M('; keepActive $1; keepActive-gui set $1', 1100, 310))
kr = O('t f f', 1100, 360); C(O('r keepActive', 1100, 335), kr)
C(kr, O('v $0-keep', 1180, 385), 1)
ks = O('sel 0', 1100, 385); C(kr, ks); C(ks, M('; unmuteAll bang', 1100, 410))

nv = O('v $0-keepN', 1100, 460); C(O('r looper-keepn-step', 1100, 435), nv)
nm = O('% 7', 1100, 485); C(nv, nm); n1 = O('+ 1', 1100, 510); C(nm, n1)
C(n1, M('; keepN $1; keepN-gui set $1', 1100, 535))
C(O('r keepN', 1200, 435), O('v $0-keepN', 1200, 460))

# ---------------- auto-record on first sound ----------------
ni = O('notein', 20, 540)
tfl = O('tapFilter', 20, 560); C(ni, tfl, 0, 0); C(ni, tfl, 1, 1); C(ni, tfl, 2, 2)
vp = O('> 0', 20, 585); C(tfl, vp, 1)
nsel = O('sel 1', 20, 610); C(vp, nsel)
envIn = O('r~ input', 120, 560)
env = O('env~ 256 128', 120, 585); C(envIn, env)
db = O('- 100', 120, 610); C(env, db)
thr = O('> -40', 120, 635); C(db, thr)
C(O('r looper-thr', 200, 610), thr, 0, 1)
ch = O('change', 120, 660); C(thr, ch)
asel = O('sel 1', 120, 685); C(ch, asel)
at = O('t b b b', 20, 710)
C(nsel, at); C(asel, at)
cond = O('expr $f1==0 && $f2 && $f3', 20, 760)
C(at, O('v $0-armed', 140, 735), 2); C(p.lines.__len__() - 1, cond, 0, 2)
C(at, O('v $0-auto', 80, 735), 1); C(p.lines.__len__() - 1, cond, 0, 1)
C(at, O('v $0-state', 20, 735), 0); C(p.lines.__len__() - 1, cond, 0, 0)
csel = O('sel 1', 20, 785); C(cond, csel); C(csel, go('rec1'))
C(O('r looper-auto', 200, 710), O('v $0-auto', 200, 735))


# a layer got content (recorded here, or loaded from a saved song)
hc = O('t b b f', 700, 200)
C(O('r layerHasContent', 700, 175), hc)
mx = O('max', 760, 250); C(hc, mx, 2, 1)
C(hc, O('v $0-L', 760, 225), 1); C(p.lines.__len__() - 1, mx); C(mx, setL(760, 275))
hs0 = O('v $0-state', 700, 225); C(hc, hs0, 0)
h0 = O('sel 0', 700, 250); C(hs0, h0); C(h0, setst(5, 700, 300))


# ---------------- front panel: state box, hint line, loop position, loop length ----------------
looks = [('#505050', 'READY', 'play or press REC to record'),
         ('#c62828', 'RECORDING', 'REC = set loop length + next layer'),
         ('#ef6c00', 'OVERDUB', 'REC = next layer   PLAY = stop recording'),
         ('#2e7d32', 'PLAYING', 'REC = add a layer   STOP = fade out'),
         ('#1565c0', 'FADING', 'STOP = stop now   PLAY = keep playing'),
         ('#303030', 'STOPPED', 'PLAY = restart   STOP = clear all')]
cnvS = O('s looper-cnv', 20, 1060); hintS = O('s looper-hint', 400, 1060)
for i, (bg, word, hint) in enumerate(looks):
    m = M(f'color {bg} #ffffff, label {word}', 20 + i * 130, 1000); C(stSel, m, i); C(m, cnvS)
    h = M('label ' + hint.replace(' ', '\\ '), 20 + i * 130, 1030); C(stSel, h, i); C(h, hintS)

# loop position bar: fraction of the cycle (while recording the first layer: fraction of the 20 s maximum)
tPos = O('timer', 1000, 1000); C(O('r f', 1000, 975), tPos)
tRec = O('timer', 1080, 1000); C(r1, tRec, 1)
pm = O('metro 50', 900, 975); C(O('loadbang', 900, 950), pm)
pt = O('t b b b b', 900, 1025); C(pm, pt)
pos = O('expr if($f4>=2 && $f4<=4 && $f3>0, min($f1/$f3, 1), if($f4==1, min($f2/%d, 1), 0))' % MAX_FIRST_MS, 900, 1075)
C(pt, O('v $0-state', 1160, 1050), 3); C(p.lines.__len__() - 1, pos, 0, 3)
C(pt, O('v $0-len', 1100, 1050), 2); C(p.lines.__len__() - 1, pos, 0, 2)
C(pt, tRec, 1, 1); C(tRec, pos, 0, 1)
C(pt, tPos, 0, 1); C(tPos, pos, 0, 0)
C(pos, O('s loop-pos', 900, 1100))

# loop length in seconds (also when a saved song sets it)
lenIn = O('r ms', 1100, 1125)
C(lenIn, O('v $0-len', 1100, 1150))
C(lenIn, O('/ 1000', 1180, 1150)); C(p.lines.__len__() - 1, O('s loop-len-s', 1180, 1175))
z1 = M('0', 1260, 1150); C(O('r clearAll', 1260, 1125), z1); C(z1, O('s loop-len-s', 1260, 1175))

# ---------------- init ----------------
lb = O('loadbang', 700, 30)
C(lb, M('; looper-auto 1; keepN 1; keepN-gui set 1', 700, 55))

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'looper.pd'))
