"""Rebuilds the visible front panel of piLooper/LiveLoopSynth.pd.

The top level of the main patch has no wires: every control talks through
send/receive names, and all processing lives in [pd internals]. This script
keeps [pd internals] exactly as it is (moved off-screen, with its subpatch
windows closed at startup) and regenerates every GUI object around it.
Run it after changing the layout; it is safe to run repeatedly.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'piLooper', 'LiveLoopSynth.pd')
W, H = 1010, 660


def sp(text):          # Pd label/text: escape spaces inside one symbol
    return text.replace(' ', '\\ ')


def extract_internals(src):
    start = src.index('#N canvas', src.index('\n'))   # first subpatch after the main header
    m = re.search(r'#X restore -?\d+ -?\d+ pd internals;\n', src)
    body = src[start:m.start()]
    assert body.startswith('#N canvas') and ' internals ' in body.split('\n', 1)[0], body[:80]
    # subpatch windows stay closed when the patch opens
    body = re.sub(r'^(#N canvas -?\d+ -?\d+ \d+ \d+ [^;\n]*?) 1;$', r'\1 0;', body, flags=re.M)
    return body + f'#X restore {W + 40} 20 pd internals;\n'


src = open(PATCH).read()
internals = extract_internals(src)
L = [f'#N canvas 40 40 {W} {H} 10;', '#X declare -lib zexy;']
A = L.append

def text(x, y, t, width=None):
    A(f'#X text {x} {y} {t}' + (f', f {width}' if width else '') + ';')

def cnv(x, y, w, h, recv, label, lx, ly, fs, bg, fg):
    A(f'#X obj {x} {y} cnv 15 {w} {h} empty {recv} {sp(label)} {lx} {ly} 0 {fs} {bg} {fg} 0;')

# ---------------- header: looper state, loop position, instrument ----------------
cnv(10, 10, 250, 74, 'looper-cnv', 'READY', 14, 37, 26, '#505050', '#ffffff')
A('#X obj 275 18 hsl 470 24 0 1 0 0 empty loop-pos loop\\ position 0 -9 0 10 #dcdcdc #2e7d32 #000000 0 1;')
cnv(275, 46, 470, 20, 'looper-hint', 'play or press REC to record', 8, 10, 11, '#2a2a2a', '#dddddd')
A('#X floatatom 275 70 5 0 0 1 loop\\ length\\ (s) loop-len-s -;')
A('#X floatatom 420 70 2 0 0 1 layers\\ used looper-layers -;')
# tempo: TAP (or the tap pad), light, bpm (type a value, 0 = free), click, count-in
A('#X obj 516 66 bng 22 250 50 0 looper-tap empty TAP 2 11 0 8 #fff59d #000000 #000000;')
cnv(541, 71, 12, 12, 'tap-led', '', 0, 0, 8, '#555555', '#000000')
A('#X floatatom 558 70 5 0 0 1 bpm tempo-bpm-gui tempo-set;')
A('#X obj 632 70 tgl 15 1 tempo-click empty click 17 7 0 10 #fcfcfc #000000 #000000 1 1;')
A('#X obj 682 70 tgl 15 0 tempo-countin empty count-in 17 7 0 10 #fcfcfc #000000 #000000 0 1;')
cnv(760, 10, 240, 50, 'instr-cnv', 'GMRock kit', 10, 25, 18, '#1f3a5f', '#ffffff')
text(760, 64, 'instrument (LX25+ patch - / +)')

# ---------------- layers ----------------
text(10, 92, 'LAYERS  |  big button = mute / unmute  |  red = clear  |  slider = volume  |  > = the layer the LX25+ Loop button mutes', 125)
palette = ['#b3e5fc', '#c8e6c9', '#fff9c4', '#ffcdd2']
for i in range(8):
    n, x = i + 1, 10 + i * 92
    col = palette[i % 4]
    text(x, 108, f'layer {n}')
    cnv(x, 124, 84, 24, f'lyr-{n}-cnv', 'empty', 6, 12, 12, '#3c3c3c', '#8c8c8c')
    A(f'#X obj {x} 154 bng 45 250 50 0 lp-trig-{n} lp-trig-{n}-r mute 7 22 0 11 {col} #000000 #000000;')
    A(f'#X obj {x} 205 bng 16 250 50 0 clear-{n} clear-{n}-r clear 20 8 0 10 #e53935 #000000 #000000;')
    A(f'#X obj {x + 58} 154 vsl 22 67 0 1 0 1 lp-vol-{n} lp-vol-{n}-r vol 0 76 0 10 {col} #000000 #000000 6600 1;')

# ---------------- looper transport ----------------
A('#X obj 10 262 bng 44 250 50 0 looper-rec empty REC 9 22 0 13 #c62828 #ffffff #ffffff;')
A('#X obj 62 262 bng 44 250 50 0 looper-play empty PLAY 5 22 0 13 #2e7d32 #ffffff #ffffff;')
A('#X obj 114 262 bng 44 250 50 0 looper-stop empty STOP 5 22 0 13 #424242 #ffffff #ffffff;')
A('#X obj 180 262 tgl 20 0 keepActive keepActive-gui keep\\ first\\ N\\ (FF) 24 10 0 10 #fcfcfc #000000 #000000 0 1;')
A('#X obj 180 288 nbx 2 18 1 7 0 0 keepN keepN-gui N\\ (REW) 32 9 0 10 #fcfcfc #000000 #000000 1 256;')
A('#X obj 330 262 tgl 20 1 looper-auto empty auto-record 24 10 0 10 #fcfcfc #000000 #000000 1 1;')
A('#X obj 330 288 nbx 3 18 -80 0 0 1 looper-thr empty threshold\\ dB 40 9 0 10 #fcfcfc #000000 #000000 -40 256;')
A('#X obj 470 262 bng 20 250 50 0 knob-learn empty learn\\ knobs 24 10 0 10 #fcfcfc #000000 #000000;')
A('#X obj 555 262 bng 20 250 50 0 tap-learn empty learn\\ tap\\ pad 24 10 0 10 #fcfcfc #000000 #000000;')
cnv(470, 288, 170, 18, 'knob-learn-cnv', 'not learned - click learn', 5, 9, 10, '#2a2a2a', '#dddddd')
A('#X obj 660 266 hsl 70 14 0 127 0 0 fx-cutoff fx-cutoff-r master\\ cutoff 0 -8 0 10 #dcdcdc #1f3a5f #000000 0 1;')
A('#X obj 660 298 hsl 70 14 0 127 0 0 fx-retrig fx-retrig-r retrigger 0 -8 0 10 #dcdcdc #1f3a5f #000000 0 1;')
text(10, 518, 'LX25+ BUTTONS  |  Record = start recording / start the next layer  |  Play = play-through (stop recording)', 125)
text(10, 534, 'Stop = fade out over one loop  |  Stop again = stop now  |  Stop when stopped = clear everything', 125)
text(10, 550, 'Fast-fwd = keep first N on / off (off unmutes all)  |  Rewind = change N  |  Loop = mute > layer  |  Track < > = move >', 125)

# ---------------- knobs: synth page (Inst mode) and input FX page (Preset mode) ----------------
cnv(10, 322, 740, 16, 'knobtitle-synth', 'SYNTH KNOBS (LX25+ Inst mode) - no knob controls for this instrument',
    6, 8, 11, '#dcdcdc', '#000000')
for i in range(8):
    x = 10 + i * 92 + 20
    A(f'#X obj {x} 344 vsl 26 50 0 127 0 0 knob-{i + 1} knob-{i + 1}-r - -8 60 0 10 {palette[i % 4]} #000000 #000000 0 1;')
cnv(10, 416, 570, 16, 'knobtitle-fx', 'INPUT FX KNOBS (LX25+ Preset mode) - reverb and delay per source',
    6, 8, 11, '#dcdcdc', '#000000')
A('#X obj 590 416 nbx 3 16 0 250 0 1 reverb-predelay empty reverb\\ pre-delay\\ ms 36 8 0 10 #fcfcfc #000000 #000000 20 256;')
fxin = [('mic verb', 0), ('mic delay', 0), ('in 2 verb', 0), ('in 2 delay', 0), ('synth verb', 0),
        ('synth delay', 0), ('delay time', 50), ('feedback', 50)]
for i, (label, default) in enumerate(fxin):
    x = 10 + i * 92 + 20
    pos = round(default / 127 * 49 * 100)
    A(f'#X obj {x} 438 vsl 26 50 0 127 0 1 fxin-{i + 1} fxin-{i + 1}-r {sp(label)} -8 60 0 10 {palette[i % 4]} #000000 #000000 {pos} 1;')


# ---------------- drum pads (flash when hit, color = drum kit) ----------------
text(10, 578, 'DRUM PADS  |  flash when hit  |  color = drum kit  |  grey = a synth is selected', 80)
A('#X obj 520 577 tgl 15 0 pad-led-echo empty light\\ the\\ LX25+\\ pads\\ (experimental) 19 7 0 10 #fcfcfc #000000 #000000 0 1;')
for i, name in enumerate(['kick', 'snare', 'hat closed', 'hat open', 'rimshot', 'tom high', 'tom low', 'ride']):
    cnv(10 + i * 92, 598, 84, 34, f'pad-{i + 1}-cnv', name, 6, 17, 11, '#6d3a0f', '#ffe0b2')

# ---------------- right column: instruments, meters, levels ----------------
text(770, 92, 'INSTRUMENT BANK')
A('#X obj 770 108 vradio 12 1 0 25 empty bankSelect empty 0 -8 0 10 #fcfcfc #000000 #000000 0;')
for cell, label in ((0, '0-1 drum kits \\, 2-3 own samples'), (4, '4 lead'), (5, '5-7 FM'), (8, '8 lead 2'),
                    (9, '9-11 FM'), (12, '12 synth 3'), (13, '13-15 FM'), (16, '16-18 bass'),
                    (19, '19-21 organ'), (22, '22-24 lead / pad / pluck')):
    text(787, 106 + cell * 12, label)
text(770, 418, 'IN1 IN2 OUT')
A('#X obj 772 436 vu 15 100 l-in-sig empty -1 -8 0 10 #404040 #000000 0 0;')
A('#X obj 797 436 vu 15 100 r-in-sig empty -1 -8 0 10 #404040 #000000 0 0;')
A('#X obj 822 436 vu 15 100 l-out-db empty -1 -8 0 10 #404040 #000000 1 0;')
A('#X obj 770 546 tgl 15 1 inputTogL empty 1 3 22 0 10 #fcfcfc #000000 #000000 1 1;')
A('#X obj 795 546 tgl 15 1 inputTogR empty 2 3 22 0 10 #fcfcfc #000000 #000000 1 1;')
text(840, 546, 'inputs on')
text(900, 418, 'LEVELS')
for k, (recv, label) in enumerate((('mainVol', 'main'), ('l-in-vol', 'in 1'), ('r-in-vol', 'in 2'),
                                   ('post-bits', 'bits'))):
    A(f'#X obj 900 {438 + k * 20} hsl 60 12 0 127 0 0 empty {recv} {sp(label)} 64 6 0 10 #dcdcdc #1f3a5f #000000 0 1;')

# ---------------- hidden helpers (off-screen) ----------------
A(f'#X obj {W + 40} 60 declare -lib zexy;')
A(f'#X obj {W + 40} 90 instrumentName;')
A(f'#X obj {W + 40} 120 looper;')
A(f'#X obj {W + 40} 150 knobs;')
A(f'#X obj {W + 40} 180 padDisplay;')
A(f'#X obj {W + 40} 210 wheels;')
A(f'#X obj {W + 40} 240 tempo;')

open(PATCH, 'w').write('\n'.join(L) + '\n' + internals)
