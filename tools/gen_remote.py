"""Generates the Pd side of the web remote: piLooper/remote.pd, piLooper/remoteOut.pd
and the allow-list remote/names.json that the bridge (remote/server.py) reads.

remote.pd listens on 127.0.0.1:9311 (TCP, FUDI) for the bridge only. Incoming
"<name> <value>" messages are passed on to [s <name>] only for the names in IN;
anything else is dropped. Every name in OUT is watched by a [remoteOut <name>],
which forwards what it hears to the bridge and remembers the last label, color
and value, so the bridge can ask for everything again ("remote-dump bang")
when it (re)connects.
"""
import json, os
from pdgen import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
PORT = 9311
N = range(1, 9)

# names the web page may send to: bang for buttons, a number for everything else.
# Controls with a front-panel receive name are driven through it, so the Pd window
# (when open) follows the phone and the control passes the value on to its send name.
IN = (['looper-rec', 'looper-play', 'looper-stop', 'looper-tap', 'knob-learn', 'tap-learn']
      + [f'lp-trig-{n}-r' for n in N] + [f'clear-{n}-r' for n in N] + [f'lp-vol-{n}-r' for n in N]
      + ['keepActive-gui', 'keepN-gui', 'looper-auto-r', 'looper-thr-r',
         'tempo-bpm-gui', 'tempo-click-r', 'tempo-countin-r',
         'fx-cutoff-r', 'fx-retrig-r', 'reverb-predelay-r']
      + [f'knob-{n}-r' for n in N] + [f'fxin-{n}-r' for n in N]
      + ['bankSelect', 'mainVol', 'l-in-vol', 'r-in-vol',
         'inputTogL-r', 'inputTogR-r', 'pad-led-echo-r'])

# names the web page listens to (displays, and the send names of the controls above)
OUT = (['looper-state', 'looper-cnv', 'looper-hint', 'loop-pos', 'loop-len-s', 'looper-layers',
        'tap-led', 'tempo-bpm-gui', 'tempo-set', 'tempo-click', 'tempo-countin', 'instr-cnv',
        'keepActive', 'keepN', 'looper-auto', 'looper-thr', 'knob-learn-cnv',
        'fx-cutoff', 'fx-cutoff-r', 'fx-retrig', 'fx-retrig-r', 'reverb-predelay',
        'knobtitle-synth', 'knobtitle-fx', 'knob-page', 'selected-loop-r',
        'bankSelect', 'mainVol', 'l-in-vol', 'r-in-vol',
        'l-in-sig', 'r-in-sig', 'l-out-db', 'inputTogL', 'inputTogR', 'pad-led-echo']
       + [f'lyr-{n}-cnv' for n in N] + [f'lp-vol-{n}' for n in N] + [f'lp-vol-{n}-r' for n in N]
       + [f'knob-{n}' for n in N] + [f'knob-{n}-r' for n in N]
       + [f'fxin-{n}' for n in N] + [f'fxin-{n}-r' for n in N]
       + [f'pad-{n}-cnv' for n in N])

# ---------------- remoteOut.pd: watch one name ----------------
p = Patch(620, 260)
O, M, C = p.obj, p.msg, p.conn
p.text('Web remote: forwards [r $1] to the bridge and keeps the last label / color / value. See tools/gen_remote.py (this file is generated).', 20, 5)
rt = O('route label color', 20, 60); C(O('r $1', 20, 35), rt)
dump = O('r remote-dump', 400, 60)
out = O('s remote-out', 20, 210)
for k, kind in enumerate(['label', 'color', None]):
    x = 20 + k * 130
    src = rt
    if kind:
        src = O(f'list prepend {kind}', x, 90); C(rt, src, k)
    pre = O('list prepend $1', x, 115); C(src, pre, k if not kind else 0)
    t = O('t a a', x, 140); C(pre, t)
    keep = O('list append', x, 175); C(t, keep, 1, 1); C(dump, keep)
    C(t, out, 0); C(keep, out)
p.save(os.path.join(ROOT, 'piLooper', 'remoteOut.pd'))

# ---------------- remote.pd: the connection to the bridge ----------------
p = Patch(900, 420)
O, M, C = p.obj, p.msg, p.conn
p.text(f'Web remote: the bridge (remote/server.py) connects to TCP 127.0.0.1:{PORT}. See tools/gen_remote.py (this file is generated).', 20, 5)
net = O('netreceive', 20, 90)
C(O('loadbang', 20, 40), M(f'listen {PORT} 127.0.0.1', 20, 65)); C(p.lines.__len__() - 1, net)
C(O('r remote-out', 300, 40), O('route bang', 300, 65))
C(p.lines.__len__() - 1, O('list prepend send', 300, 90), 1)
C(p.lines.__len__() - 1, O('list trim', 300, 115)); C(p.lines.__len__() - 1, net)
route = O('route ' + ' '.join(IN + ['remote-dump']), 20, 150); C(net, route)
for i, name in enumerate(IN + ['remote-dump']):
    C(route, O(f's {name}', 20 + (i % 8) * 110, 180 + (i // 8) * 22), i)
for i, name in enumerate(OUT):
    O(f'remoteOut {name}', 20 + (i % 6) * 145, 180 + (len(IN) // 8 + 2 + i // 6) * 22)
p.save(os.path.join(ROOT, 'piLooper', 'remote.pd'))

with open(os.path.join(ROOT, 'remote', 'names.json'), 'w') as f:
    json.dump({'pd_port': PORT, 'in': IN, 'out': OUT}, f, indent=1)
    f.write('\n')
