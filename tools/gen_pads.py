"""Generates piLooper/padDisplay.pd: front-panel drum pads that flash when hit.

Pads 1-8 = notes 56-63 (pad map 1) and 48-55 (pad map 2), as used by the drum kits.
Each drum kit has its own color; the pads go grey when a non-drum instrument is selected.
Optional (toggle pad-led-echo, off by default): echo pad notes back to the keyboard, with a
different velocity per kit, for controllers that light their pads from incoming MIDI.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(1300, 760)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
p.text('Drum pad display. See tools/gen_pads.py (this file is generated).', 20, 5)

# look per kit: resting color, flash color, label color, echo velocity. Index 4 = not a drum kit.
LOOK = [('#6d3a0f', '#ff9800', '#ffe0b2', 127), ('#0b4a45', '#1de9b6', '#b2dfdb', 90),
        ('#3b1f55', '#d05ce3', '#e1bee7', 60), ('#12305a', '#42a5f5', '#bbdefb', 30),
        ('#3c3c3c', '#9e9e9e', '#8c8c8c', 0)]
DRUMS = ['kick', 'snare', 'hat closed', 'hat open', 'rimshot', 'tom high', 'tom low', 'ride']
NAMES = [DRUMS, DRUMS, [f'pad {i}' for i in range(1, 9)], [f'pad {i}' for i in range(1, 9)], ['-'] * 8]
esc = lambda t: t.replace(' ', '\\ ')

# ---- current kit (0-3, 4 = none) -> resting look + labels for all pads ----
kx = O('expr if($f1>=0 && $f1<=3, $f1, 4)', 20, 55)
C(O('r bankSelect', 20, 30), kx)
kt = O('t f f f', 20, 80); C(kx, kt)
C(kt, O('v $0-kit', 140, 105), 2)
C(kt, O('s $0-kitvel', 220, 105), 1)
ks = O('sel 0 1 2 3 4', 20, 105); C(kt, ks, 0)
for k, (rest, flash, fg, vel) in enumerate(LOOK):
    msg = '; ' + '; '.join(f'pad-{i + 1}-cnv color {rest} {fg}; pad-{i + 1}-cnv label {esc(n)}'
                           for i, n in enumerate(NAMES[k]))
    C(ks, M(msg, 20 + k * 200, 140), k)
kv = O('expr if($f1==0, 127, if($f1==1, 90, if($f1==2, 60, if($f1==3, 30, 0))))', 220, 130)
C(O('r $0-kitvel', 220, 110), kv)

# ---- incoming notes: flash pad 1-8 for notes 48-63 ----
ni = O('notein', 20, 230)
pk = O('pack f f f', 20, 260)
tfl = O('tapFilter', 20, 245); C(ni, tfl, 0, 0); C(ni, tfl, 1, 1); C(ni, tfl, 2, 2)
C(ni, pk, 2, 2); C(tfl, pk, 1, 1); C(tfl, pk, 0, 0)
pn = O('expr if($f1>=48 && $f1<=63 && $f2>0, ($f1-48)%8+1, 0)', 20, 290); C(pk, pn)
test = O('r pads-test-note', 120, 260); C(test, pn)
psel = O('sel 1 2 3 4 5 6 7 8', 20, 315); C(pn, psel)
for i in range(8):
    x = 20 + i * 150
    t = O('t b b', x, 345); C(psel, t, i)
    out = O(f's pad-{i + 1}-cnv', x, 560)
    for phase, (outlet, y) in enumerate(((1, 375), (0, 440))):      # flash now, rest after 150 ms
        src = t
        if phase == 1:
            src = O('delay 150', x, 400); C(t, src, 0)
        vk = O('v $0-kit', x, y); C(src, vk, outlet if phase == 0 else 0)
        sk = O('sel 0 1 2 3 4', x, y + 25); C(vk, sk)
        for k, (rest, flash, fg, vel) in enumerate(LOOK):
            m = M(f'color {flash} #ffffff' if phase == 0 else f'color {rest} {fg}', x + (k % 2) * 70, y + 50 + (k // 2) * 18)
            C(sk, m, k); C(m, out)

# ---- optional: echo pad notes to the keyboard (note, kit velocity, channel) ----
sp = O('spigot', 20, 620)
C(O('r pad-led-echo', 90, 595), sp, 0, 1)
C(pk, sp); C(test, sp)
et = O('t l l', 20, 645); C(sp, et)
gate = O('spigot', 20, 700)
C(et, O('expr $f1>=48 && $f1<=63', 120, 670), 1); C(last(), gate, 0, 1)
C(et, gate, 0, 0)
ev = O('expr $f1; if($f2>0, $f4, 0); $f3', 20, 725); C(gate, ev)
C(kv, ev, 0, 3)
no = O('noteout', 20, 750)
C(ev, no, 0, 0); C(ev, no, 1, 1); C(ev, no, 2, 2)

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'padDisplay.pd'))
