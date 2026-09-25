"""Generates piLooper/knobs.pd: routes the LX25+ knobs.

Inst mode (CC 56-63, channel 16)  -> synth parameters of the selected instrument (knob-1..8)
Preset mode (learned, knobmap.txt) -> per-source reverb/delay (fxin-1..8)
Mixer mode is handled elsewhere (layer volumes).

Knob values go to the front-panel sliders (knob-N-r / fxin-N-r), which pass them on
(knob-N / fxin-N), so mouse and knobs do the same thing. For tests, "value cc channel"
lists can be sent to knobs-inject.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1400, 1000)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
p.text('LX25+ knob routing. See tools/gen_knobs.py (this file is generated).', 20, 5)

INST_CH, INST_CC0 = 16, 56
KEY0 = INST_CH * 128 + INST_CC0          # keys of the Inst-mode knobs (never learned for Preset mode)

O('table knob-keymap 2200', 1000, 900)    # key = channel*128+cc -> preset knob 1..8 (0 = none)
O('table knob-learnkeys 8', 1150, 900)

# ---------------- incoming CCs: "value cc channel" ----------------
ci = O('ctlin', 20, 30)
pk = O('pack f f f', 20, 60)
C(ci, pk, 2, 2); C(ci, pk, 1, 1); C(ci, pk, 0, 0)
H = O('t l l l', 20, 100)
C(pk, H); C(O('r knobs-inject', 120, 60), H)

def page(n, x, y):
    m = M(str(n), x, y); C(m, O('s knob-page', x, y + 25)); return m

# (a) Inst mode -> synth knob sliders
ta = O('t l l', 20, 120); C(H, ta, 0)
pa = O('pack f f', 20, 240)
va = O('list split 1', 120, 150); C(ta, va, 1); C(va, pa, 0, 1)     # value -> cold inlet first
kx = O(f'expr if($f3=={INST_CH} && $f2>={INST_CC0} && $f2<={INST_CC0 + 7}, $f2-{INST_CC0 - 1}, 0)', 20, 190)
C(ta, kx, 0)
ma = O('moses 1', 20, 215); C(kx, ma); C(ma, pa, 1, 0); C(ma, page(1, 100, 240), 1)
C(pa, M('; knob-$1-r $2', 20, 265))

# (b) Preset mode (learned) -> input FX sliders
tb = O('t l l', 300, 120); C(H, tb, 1)
pb = O('pack f f', 300, 240)
vb = O('list split 1', 400, 150); C(tb, vb, 1); C(vb, pb, 0, 1)
kb = O('expr $f3*128+$f2', 300, 165); C(tb, kb, 0)
lk = O('tabread knob-keymap', 300, 190); C(kb, lk)
mb = O('moses 1', 300, 215); C(lk, mb); C(mb, pb, 1, 0); C(mb, page(2, 380, 240), 1)
C(pb, M('; fxin-$1-r $2', 300, 265))

# (c) learning the Preset-mode knobs: turn knob 1, then 2 ... 8
status = O('s knob-learn-cnv', 600, 700)
def say(text, x, y):
    m = M('label ' + text.replace(' ', '\\ '), x, y); C(m, status); return m

key = O('expr $f3*128+$f2', 600, 120); C(H, key, 2)
kt = O('t f f', 600, 145); C(key, kt)
C(kt, O('v $0-last', 700, 145), 0)                  # remember this key after the check below
kc = O('t f b b f', 600, 170); C(kt, kc, 1)
cond = O(f'expr $f2 && $f1!=$f3 && $f4==0 && ($f1<{KEY0} || $f1>{KEY0 + 7})', 600, 250)
ks1 = O('f', 900, 300); ks2 = O('f', 960, 300)
C(kc, O('tabread knob-keymap', 780, 200), 3); C(last(), cond, 0, 3)
C(kc, ks1, 3, 1); C(kc, ks2, 3, 1)
C(kc, O('v $0-learn', 720, 200), 2); C(last(), cond, 0, 1)
C(kc, O('v $0-last', 660, 200), 1); C(last(), cond, 0, 2)
C(kc, cond, 0, 0)
cs = O('sel 1', 600, 275); C(cond, cs)
nx = O('v $0-lidx', 600, 300); C(cs, nx)
n1 = O('+ 1', 600, 325); C(nx, n1)
nt = O('t f f f f', 600, 350); C(n1, nt)
C(nt, O('v $0-lidx', 760, 380), 3)
wk = O('tabwrite knob-keymap', 700, 440)                # keymap[key] = n
tk = O('t f b', 700, 400); C(nt, tk, 2); C(tk, ks1, 1); C(ks1, wk, 0, 1); C(tk, wk, 0, 0)
wl = O('tabwrite knob-learnkeys', 850, 440)             # learnkeys[n-1] = key
tl = O('t b f', 850, 400); C(nt, tl, 1)
n0 = O('- 1', 900, 420); C(tl, n0, 1); C(n0, wl, 0, 1); C(tl, ks2, 0); C(ks2, wl, 0, 0)
nm = O('moses 8', 600, 460); C(nt, nm, 0)
C(nm, O('+ 1', 600, 485), 0); C(last(), M('label turn\\ Preset\\ knob\\ $1', 600, 510)); C(last(), status)
done = O('t b b b', 700, 485); C(nm, done, 1)
C(done, O('s $0-save', 860, 510), 2)
C(done, M('0', 780, 510), 1); C(last(), O('v $0-learn', 780, 535))
C(done, say('Preset knobs learned', 700, 560), 0)

start = O('t b b b b b', 600, 600)
C(O('r knob-learn', 600, 575), start)
C(start, M('1', 600, 630), 4); C(last(), O('v $0-learn', 600, 655))
C(start, M('0', 640, 630), 3); C(last(), O('v $0-lidx', 640, 655))
C(start, M('-1', 680, 630), 2); C(last(), O('v $0-last', 680, 655))
C(start, M('; knob-keymap const 0; knob-learnkeys const 0', 740, 630), 1)
C(start, say('turn Preset knob 1', 740, 660), 0)

# save / load knobmap.txt (next to the patch)
tf = O('textfile', 1000, 700)
sv = O('t b b b', 1000, 560); C(O('r $0-save', 1000, 535), sv)
C(sv, M('clear', 1000, 590), 2); C(last(), tf)
C(sv, O('array get knob-learnkeys', 1060, 590), 1); C(last(), O('list prepend add', 1060, 615))
C(last(), O('list trim', 1060, 640)); C(last(), tf)
C(sv, M('write knobmap.txt', 1150, 590), 0); C(last(), tf)

lb = O('loadbang', 1000, 30)
lbt = O('t b b', 1000, 55); C(lb, lbt)
C(lbt, say('not learned - click learn', 1100, 80), 1)
fw = O('file which', 1000, 110); C(lbt, M('symbol knobmap.txt', 1000, 80), 0); C(last(), fw)
fwl = O('list split 1', 1000, 135); C(fw, fwl)
rd = O('t b b a', 1000, 160); C(fwl, rd)
C(rd, M('read $1', 1000, 190), 2); C(last(), tf)
C(rd, M('rewind', 1060, 190), 1); C(last(), tf)
lt2 = O('t b b b', 1120, 190); C(rd, lt2, 0)
C(lt2, tf, 2, 0)                                        # output the saved line
C(tf, O('array set knob-learnkeys', 1000, 740))
C(lt2, say('Preset knobs learned', 1200, 215), 1)
rb = O('t b b', 1200, 250); C(lt2, rb, 0)               # rebuild keymap from learnkeys
un = O('until', 1200, 300); C(rb, M('8', 1200, 275), 0); C(last(), un)
C(rb, M('; knob-keymap const 0', 1260, 275), 1)
cnt = O('f', 1200, 325); inc = O('+ 1', 1240, 325); C(un, cnt); C(cnt, inc); C(inc, cnt, 0, 1)
C(rb, M('0', 1330, 275), 1); C(last(), cnt, 0, 1)
ct = O('t f f', 1200, 350); C(cnt, ct)
kw = O('tabwrite knob-keymap', 1200, 450)
kn = O('+ 1', 1300, 380); kv = O('f', 1300, 405); C(ct, kn, 1); C(kn, kv, 0, 1)
rk = O('tabread knob-learnkeys', 1200, 380); C(ct, rk, 0)
rkt = O('t b f', 1200, 405); C(rk, rkt); C(rkt, kw, 1, 1); C(rkt, kv, 0, 0); C(kv, kw, 0, 0)

# ---------------- synth parameters for the selected instrument ----------------
eng = O('expr if(($f1>=16&&$f1<=18)||($f1>=22&&$f1<=24), 1, if($f1>=19&&$f1<=21, 2, if(($f1>=5&&$f1<=7)||($f1>=9&&$f1<=11)||($f1>=13&&$f1<=15), 3, 0)))', 20, 330)
C(O('r bankSelect', 20, 305), eng)
et = O('t f f', 20, 355); C(eng, et)
C(et, O('v $0-eng', 120, 380), 1)
ec = O('change -1', 20, 380); C(et, ec)
es = O('sel 0 1 2 3', 20, 405); C(ec, es)
names = {0: ('no knob controls for this instrument', ['-'] * 8),
         1: ('filter / envelope / LFO', ['cutoff', 'resonance', 'filter env', 'attack', 'release', 'detune', 'LFO rate', 'LFO depth']),
         2: ('organ drawbars', ["16'", "5 1/3'", "8'", "4'", "2 2/3'", "2'", "1 3/5'", "1 1/3'"]),
         3: ('FM synth', ['mod 1 amt', 'mod 2 amt', 'cross mod', 'attack', 'decay', 'release', 'LFO rate', 'LFO depth'])}
title = O('s knobtitle-synth', 20, 480)
for e, (what, labels) in names.items():
    t = f'SYNTH KNOBS (LX25+ Inst mode) - {what}'
    m = M('label ' + t.replace(' ', '\\ '), 20 + e * 150, 430); C(es, m, e); C(m, title)
    msg = '; ' + '; '.join(f'knob-{i + 1}-r label ' + l.replace(' ', '\\ ') for i, l in enumerate(labels))
    m2 = M(msg, 20 + e * 150, 455); C(es, m2, e)

kt2 = O('t l b', 20, 545)
pe = O('list prepend', 20, 595)
C(kt2, O('v $0-eng', 100, 570), 1); C(last(), pe, 0, 1)
C(kt2, pe, 0, 0)
re = O('route 1 2 3', 20, 620); C(pe, re)
for i in range(8):
    C(O(f'r knob-{i + 1}', 20 + i * 70, 500), O(f'list prepend {i + 1}', 20 + i * 70, 520)); C(last(), kt2)

def knobs_for(outlet, x, specs):
    r = O('route 1 2 3 4 5 6 7 8', x, 650); C(re, r, outlet)
    for i, (formula, *messages) in enumerate(specs):
        e = O(f'expr {formula}', x + i * 45, 680); C(r, e, i)
        for j, message in enumerate(messages):
            C(e, M(message, x + i * 45, 710 + j * 25), j)

knobs_for(0, 20, [('50*pow(2, $f1/127*8)', '; as-params 6 $1; as-live 6 $1'),
                  ('0.5+pow($f1/127, 2)*19.5', '; as-params 8 $1; as-live 8 $1'),
                  ('pow($f1/127, 2)*8000', '; as-params 7 $1; as-live 7 $1'),
                  ('5+pow($f1/127, 2)*2000', '; as-params 12 $1'),
                  ('20+pow($f1/127, 2)*4000', '; as-params 15 $1; as-params 16 $1'),
                  ('3+$f1/127*37; min(1, $f1/40)', '; as-params 2 $1; as-live 2 $1', '; as-params 1 $1; as-live 1 $1'),
                  ('0.05*pow(240, $f1/127)', '; as-lfo-rate $1'),
                  ('$f1/127', '; as-lfo-depth $1')])
knobs_for(1, 420, [('int($f1/127*8+0.5)', f'; organ-params {i} $1; organ-live {i} $1') for i in range(8)])
knobs_for(2, 820, [('1+pow($f1/127, 2)*1999', '; fmOpOneAmt $1'), ('1+pow($f1/127, 2)*1999', '; fmOpTwoAmt $1'),
                   ('$f1/127*10', '; crossMod $1'), ('1+pow($f1/127, 2)*2999', '; envAttack $1'),
                   ('1+pow($f1/127, 2)*2999', '; envDecay $1'), ('1+pow($f1/127, 2)*2999', '; envRelease $1'),
                   ('$f1/127*10', '; lfoOneFreq $1'), ('$f1/127*0.05', '; lfoOneAmt $1')])

# ---------------- which page the knobs were last on (front-panel title colors) ----------------
pc = O('change', 300, 800); C(O('r knob-page', 300, 775), pc)
psel = O('sel 1 2', 300, 825); C(pc, psel)
on, off = 'color #1f3a5f #ffffff', 'color #dcdcdc #000000'
C(psel, M(f'; knobtitle-synth {on}; knobtitle-fx {off}', 300, 850), 0)
C(psel, M(f'; knobtitle-synth {off}; knobtitle-fx {on}', 300, 875), 1)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'knobs.pd'))
