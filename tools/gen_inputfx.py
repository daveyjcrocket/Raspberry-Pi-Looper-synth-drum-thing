"""Generates piLooper/inputFX.pd: reverb and delay sends per source.

Inlets~: 0 = input 1 (mic), 1 = input 2 (instrument), 2 = synths/drums. Outlet~: wet only.
Controls (0-127, from the front-panel sliders / LX25+ Preset-mode knobs):
fxin-1/2 mic reverb/delay, fxin-3/4 input-2 reverb/delay, fxin-5/6 synth reverb/delay,
fxin-7 delay time (60-1500 ms), fxin-8 delay feedback (0-85 %).
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
C(O('r fxin-7', 380, 215), O('expr 60+pow($f1/127, 2)*1440', 380, 240))
C(p.lines.__len__() - 1, M('$1 50', 380, 252)); C(p.lines.__len__() - 1, dtime)
C(dtime, dr)
fb = O('*~', 300, 310); fbl = O('line~', 360, 300)
C(O('r fxin-8', 450, 215), O('expr $f1/127*0.85', 450, 240)); C(p.lines.__len__() - 1, M('$1 20', 450, 265)); C(p.lines.__len__() - 1, fbl)
lop = O('lop~ 4000', 300, 305)
C(dr, lop); C(lop, fb); C(fbl, fb, 0, 1); C(fb, dw); C(dlyBus, dw)

# reverb (also gets a little of the delay, so echoes sit in the same space)
rv = O('rev3~ 100 88 3000 25', 20, 380)
C(revBus, rv); C(O('*~ 0.3', 120, 350), rv); C(dr, p.lines.__len__() - 1)
out = O('outlet~', 20, 480)
C(rv, out, 0); C(rv, out, 1); C(dr, out)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'inputFX.pd'))
