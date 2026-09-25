"""Generates piLooper/tapFilter.pd: drops the tap-tempo pad from a [notein] stream.

Inlets: note, velocity, channel (connect a [notein] 1:1). Outlets: note, velocity.
The tap pad is the global values tap-note / tap-ch (channel 0 = any channel),
set by tempo.pd. Every instrument listens through this, so tapping makes no sound.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

p = Patch(500, 330)
O, M, C = p.obj, p.msg, p.conn
p.text('Drops the tap-tempo pad. See tools/gen_tapfilter.py (this file is generated).', 20, 5)
iN, iV, iC = O('inlet', 20, 30), O('inlet', 150, 30), O('inlet', 250, 30)
oN, oV = O('outlet', 20, 290), O('outlet', 150, 290)
vel = O('f', 150, 230); C(iV, vel, 0, 1)
note = O('f', 20, 230)
pe = O('expr !($f1==$f3 && ($f4==0 || $f2==$f4))', 20, 150)
C(iC, pe, 0, 1)
t = O('t f f b b', 20, 60); C(iN, t)
C(t, O('v tap-ch', 250, 100), 3); C(len(p.lines) - 1, pe, 0, 3)
C(t, O('v tap-note', 180, 100), 2); C(len(p.lines) - 1, pe, 0, 2)
C(t, note, 1, 1); C(t, pe, 0, 0)
s = O('sel 1', 20, 175); C(pe, s)
tb = O('t b b', 20, 200); C(s, tb)
C(tb, vel, 1); C(vel, oV); C(tb, note, 0); C(note, oN)
p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'tapFilter.pd'))
