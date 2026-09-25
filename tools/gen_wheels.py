"""Generates piLooper/wheels.pd: pitch bend and mod wheel for the synths.

Pitch bend: +/- 12 semitones (one octave). Mod wheel (CC 1): vibrato, 5.5 Hz, up to +/- 0.5 semitone.
s~ pitchmod    - frequency ratio (signal) used by the analog synth and organ voices
s pitchbend-ratio - bend-only ratio (control) used by the FM voices
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pdgen import Patch

BEND_RANGE, VIB_RATE, VIB_DEPTH = 12, 5.5, 0.5
p = Patch(700, 400)
O, M, C = p.obj, p.msg, p.conn
last = lambda: len(p.lines) - 1
p.text('Pitch bend + mod wheel. See tools/gen_wheels.py (this file is generated).', 20, 5)

bs = O(f'expr ($f1-8192)/8192*{BEND_RANGE}', 20, 55)          # semitones
C(O('bendin', 20, 30), bs); C(O('r wheels-test-bend', 100, 30), bs)
bt = O('t f f', 20, 80); C(bs, bt)
C(bt, M('$1 10', 20, 105), 0); C(last(), O('line~', 20, 130)); bl = last()
C(bt, O('expr pow(2, $f1/12)', 150, 105), 1); C(last(), O('s pitchbend-ratio', 150, 130))

mw = O('expr $f1/127', 250, 55); C(O('ctlin 1', 250, 30), mw); C(O('r wheels-test-mod', 330, 30), mw); C(mw, M('$1 30', 250, 80)); 
C(last(), O('line~', 250, 105)); ml = last()
vib = O(f'osc~ {VIB_RATE}', 400, 105)
pm = O(f'expr~ pow(2, ($v1 + $v2*{VIB_DEPTH}*$v3)/12)', 20, 180)
C(bl, pm, 0, 0); C(ml, pm, 0, 1); C(vib, pm, 0, 2)
C(pm, O('s~ pitchmod', 20, 210))

p.save(os.path.join(os.path.dirname(__file__), '..', 'piLooper', 'wheels.pd'))
