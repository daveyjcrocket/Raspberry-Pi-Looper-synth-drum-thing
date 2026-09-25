"""Generates piLooper/inputFX.pd: reverb and delay sends per source.

Inlets~: 0 = input 1 (mic), 1 = input 2 (instrument), 2 = synths/drums. Outlet~: wet only.
Controls (0-127, from the front-panel sliders / LX25+ Preset-mode knobs):
fxin-1/2 mic reverb/delay, fxin-3/4 input-2 reverb/delay, fxin-5/6 synth reverb/delay,
fxin-7 delay time (60-1500 ms, or 1/16 - 1/2 note when tempo-bpm is set), fxin-8 delay feedback (0-85 %).
reverb-predelay: ms before the reverb starts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(900, 560)
O, M, C = p.obj, p.msg, p.conn
p.text('Per-source reverb/delay sends. See tools/gen_inputfx.py (this file is generated).', 20, 5)

ins = [O('inlet~', 20 + i * 160, 30) for i in range(3)]
revBus = O('*~ 1', 20, 200)      # summing points
dlyBus = O('*~ 1', 300, 200)
for i, src in enumerate(ins):
    for j, bus in enumerate((revBus, dlyBus)):
        k = i * 2 + j + 1                               # fxin-1 .. fxin-6
        mul = O('*~', 20 + i * 160 + j * 70, 110)
        ln = O('line~', 50 + i * 160 + j * 70, 85)
        sq = O('expr pow($f1/127, 2)', 50 + i * 160 + j * 70, 60)
        mm = M('$1 20', 50 + i * 160 + j * 70, 72)
        C(O(f'r fxin-{k}', 50 + i * 160 + j * 70, 40), sq); C(sq, mm); C(mm, ln)
        C(src, mul); C(ln, mul, 0, 1); C(mul, bus)

# delay: time and feedback, damped repeats
dw = O('delwrite~ $0-inputfx-dly 2000', 300, 330)
dr = O('delread4~ $0-inputfx-dly', 300, 290)
dtime = O('line~', 380, 265)
# delay time: milliseconds, or a note value when a tempo is set
f7, fb7 = O('f', 380, 200), O('f', 470, 200)
C(O('r fxin-7', 380, 150), O('t b f', 380, 175)); t7 = len(p.lines) - 1; C(t7, f7, 1, 1)
C(O('r tempo-bpm', 470, 150), O('t b f', 470, 175)); tb = len(p.lines) - 1; C(tb, fb7, 1, 1)
rc = O('t b b', 380, 225); C(t7, rc, 0); C(tb, rc, 0)
IDX = 'int($f1/127*5.99)'
dx = O('expr if($f2>0, min(1900, 60000/$f2*if(%s==0, 0.25, if(%s==1, 0.5, if(%s==2, 0.75, if(%s==3, 1, if(%s==4, 1.5, 2)))))), 60+pow($f1/127, 2)*1440); if($f2>0, %s, 6)'
       % ((IDX,) * 6), 380, 250)
C(rc, fb7, 1); C(fb7, dx, 0, 1); C(rc, f7, 0); C(f7, dx, 0, 0)
C(dx, M('$1 50', 380, 262), 0); C(len(p.lines) - 1, dtime)
lab = O('change -1', 600, 262); C(dx, lab, 1)
ls = O('sel 0 1 2 3 4 5 6', 600, 287); C(lab, ls)
lsend = O('s fxin-7-r', 600, 340)
for i, name in enumerate(['delay 1/16', 'delay 1/8', 'delay 1/8 dotted', 'delay 1/4', 'delay 1/4 dotted', 'delay 1/2', 'delay time']):
    C(ls, M('label ' + name.replace(' ', '\\ '), 600 + i * 40, 312), i); C(len(p.lines) - 1, lsend)
C(dtime, dr)
fb = O('*~', 300, 310); fbl = O('line~', 360, 300)
C(O('r fxin-8', 450, 215), O('expr $f1/127*0.85', 450, 240)); C(p.lines.__len__() - 1, M('$1 20', 450, 265)); C(p.lines.__len__() - 1, fbl)
lop = O('lop~ 4000', 300, 305)
C(dr, lop); C(lop, fb); C(fbl, fb, 0, 1); C(fb, dw); C(dlyBus, dw)

# reverb (also gets a little of the delay, so echoes sit in the same space)
rv = O('rev3~ 100 88 3000 25', 20, 400)
# reverb pre-delay (reverb-predelay, ms): the reverb starts a moment after the dry sound
pdw = O('delwrite~ $0-inputfx-pre 300', 20, 350)
pdr = O('delread4~ $0-inputfx-pre', 20, 375)
C(O('r reverb-predelay', 200, 300), M('$1 20', 200, 325)); C(len(p.lines) - 1, O('line~', 200, 350)); C(len(p.lines) - 1, pdr)
C(revBus, pdw); C(O('*~ 0.3', 120, 320), pdw); C(dr, len(p.lines) - 1)
C(pdr, rv)
out = O('outlet~', 20, 480)
C(rv, out, 0); C(rv, out, 1); C(dr, out)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'inputFX.pd'))
