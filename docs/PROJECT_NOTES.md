# Project notes: where we are, how it works, what's next

Working notes for picking the project up again. For how to *use* it, see the [user manual](USER_MANUAL.md).

## Session summary (September 2026)

The 2017 patch was stalled mid-way through a MIDI rework. Here's what was done, in order:

1. **Two platforms, one patch.**
   - `LLS.pd` became the single main patch, `piLooper/LiveLoopSynth.pd`.
   - `scripts/run-mac.command` starts it on the Mac.
   - `scripts/setup-pi.sh` and `scripts/run-pi.sh` start it on the Pi. The Pi scripts use ALSA, select the Behringer UMC22 automatically, connect the Nektar Impact LX25+ both ways, and can autostart at login.
   - The hardcoded `/Users/...` song-folder shell calls were replaced with `sessionFiles.pd`, which uses vanilla `[file]` objects.
2. **Instruments.**
   - `analogSynth`: Moog, Acid and Reese bass, Supersaw lead, Warm pad, Pluck.
   - `organSynth`: Jazz, Gospel and Church organ.
   - All 25 banks are now reachable (the counter was `mod 8`), and the instrument name is shown on screen.
3. **Drum kits.** GMRockKit (GPL) and Virtuosity Drums (CC0), eight sounds each on the LX25+ pads, converted to 48 kHz mono.
   - Late in the session we found that **MIDI notes never reached the drum samplers**. `samp.pd`'s `[stripnote]` output was never connected, even in the 2017 original. It's connected now.
4. **Looper rework.**
   - Auto-record on the first note or input sound.
   - Continuous overdub layers (Record = next layer).
   - Play-through, and a fade-out on Stop (again = stop now, when stopped = clear).
   - Keep-first-N mute, where the off press unmutes everything.
5. **Front panel redesign** with a color-coded state box, loop position, per-layer status and more. Plus the user manual with screenshots.
6. **Knob pages.**
   - Inst mode drives synth parameters.
   - Preset mode, learned on screen, drives per-source reverb/delay.
   - Mixer mode drives layer volumes.
   - Ring mod, bit crush, distortion and the old insert delay/reverb were removed.
7. **Drum pad display** with per-kit colors. There's also an experimental echo to light the LX25+ pads.
8. **Pitch bend** (±1 octave) and **mod wheel** (vibrato).
9. **Tap tempo.**
   - Tap source: pad 8 on pad map 2, filtered out of every instrument, plus an on-screen TAP button.
   - Bar snapping when the first layer is closed.
   - Click, count-in, tempo-synced delay and reverb pre-delay.
   - The tap pad also completes natural loops.
10. **Loop reverb switched off**, as requested: it was only reachable from the old Teensy XY pad.

Everything was tested headless with Pure Data 0.54: offline renders, simulated MIDI and button messages, and screenshots on a virtual display. **Nothing has been tried on the real LX25+, UMC22, Mac or Pi yet.** Things to check first:

- **Drums from the pads:** the drum kits should now play from the pads.
- **Button CCs:** the transport buttons should match the CC numbers in the manual (Record 107, Play 106, Stop 105, FF 104, Rewind 103, Loop 102, Track 109/110, Patch 111/112).
- **Tap pad:** it should be silent, and the G3 key should still play (this depends on the pads' MIDI channel).
- **Preset-mode knobs:** run *learn knobs* once.
- **Pad LED echo:** whether the LX25+ reacts to it at all.
- **Pi CPU headroom:** check it with a few layers, a synth and the input effects running.

## Architecture

### Files

| Path | What it is |
|---|---|
| `piLooper/LiveLoopSynth.pd` | Main patch. The top level is only the front panel (generated) plus the hidden helper objects; everything else lives in `[pd internals]`. |
| `piLooper/*.pd` from `tools/gen_*.py` | **Generated:** `Loop.pd` (one layer), `looper.pd` (controller), `knobs.pd`, `inputFX.pd`, `padDisplay.pd`, `wheels.pd`, `tempo.pd`, `tapFilter.pd`. Edit the generator, not the `.pd`. |
| `piLooper/analogSynth.pd`, `analogVoice.pd`, `organSynth.pd`, `organVoice.pd`, `sessionFiles.pd`, `instrumentName.pd` | Hand-written this session. |
| `piLooper/fmSynth` (inside the main patch), `fmVoice.pd`, `synthLeadVoice*.pd`, `samp.pd`, `notecheck.pd`, `oneshot.pd`, `load.pd`, `loopSave.pd`, `loopLoad.pd` | Legacy (2017) parts, lightly modified. |
| `piLooper/kits/` | Drum samples, licenses and pad map. |
| `tools/pdgen.py` | Tiny patch-writing helper used by all generators. |
| `tools/gen_gui.py` | Regenerates the front panel **around** `[pd internals]`, leaving that block untouched. |
| `scripts/` | Mac and Pi launchers and setup. |
| `docs/` | User manual, screenshots, these notes. |

### Signal flow

```
LX25+ keys/pads ──notein──► tapFilter ──► noteSelect (poly 4) ──► synth engines ─┐
                            tapFilter ──► samp ×64 (4 kits)  ───────────────────┤
UMC22 in 1/2 ──adc~──► gain ► IN1/IN2 gates ─────────────────────────────────────┤
                                                                                 ▼
             instrumentSelector (gates by bankSelect) + analogSynth/organSynth ► *~ 1
                      ► reTrigger ► robotDelay ► cutoff ► (+ inputFX returns) ► fx-post-vol
                                                                                 │
                         ┌────────── s~ input (what gets recorded) ◄─────────────┤
                         │           s~ direct-in (live monitoring) ◄────────────┘
                         ▼
   Loop 1..8 (tables loop-N / loop-N-b) ─s~ lp-out-N─► microFade ► post-loop-fx ► dac~
                                                                  (loop reverb off)
   click (tempo.pd) ────────────────────────────────────────────────────────► dac~ (not recorded)
```

### Timing

- **`looper.pd` owns the loop length.** It sends `ms` (loop length) and `play` / `stop`.
- **The loop clock comes from `[pd metros]`,** a legacy subpatch. It runs a metro at `ms/256` and sends `f` once per loop.
- **Every layer restarts playback on `f`.**
- **Overdub:** a recording layer plays one table while writing "that + input" into the other, and the two swap on `f`.
- **Starting a layer mid-cycle:** the write begins at a sample offset (`tabwrite~ start N`).
- **Bar snapping with a tempo:**
  - Pressed early: `looper.pd` delays the close until the bar line.
  - Pressed late: it closes now, plays the take from the overshoot (`layer-1 preview d`), and starts the clock at the next bar line.

### Message bus (main names)

| Name | Direction | Meaning |
|---|---|---|
| `looper-rec`, `looper-play`, `looper-stop`, `looper-keep`, `looper-keepn-step`, `looper-tap` | → controller / tempo | buttons (LX25+ via `[pd loop-control]` and `midi-btn-ctl-in`, and on-screen) |
| `looper-state` (0 READY, 1 RECORDING, 2 OVERDUB, 3 PLAYING, 4 FADING, 5 STOPPED) | controller → | state number |
| `layer-N rec <onset>` / `close` / `preview <onset>` | controller → layer | layer commands |
| `layerHasContent N`, `lp-done-N` | layer → | a layer got content (also used by save/load) |
| `keepActive`, `keepN`, `unmuteAll`, `lp-trig-N`, `clear-N`, `clearAll`, `loopFade` | → layers | mute / clear / fade |
| `ms`, `play`, `stop`, `f` | clock | loop length, start/stop, once-per-loop tick |
| `bankSelect` | → everything | current instrument bank 0–24 |
| `knob-N` / `fxin-N` (sliders `…-r`) | knobs | synth page / input FX page |
| `as-params`, `as-live`, `as-lfo-*`, `organ-params`, `organ-live`, `fm*` | → synths | synth parameters |
| `tempo-bpm`, `tempo-set`, `tempo-click`, `tempo-countin`, `tap-note`/`tap-ch` (values) | tempo | tempo state |
| `reverb-predelay`, `pitchmod` (signal), `pitchbend-ratio` | effects / wheels | |
| `looper-cnv`, `looper-hint`, `lyr-N-cnv`, `pad-N-cnv`, `instr-cnv`, `knobtitle-*`, `knob-learn-cnv`, `tap-led` | → screen | display updates |

### Conventions and Pd gotchas we hit

- **The main patch's top level has no wires.** It's all send/receive, so `gen_gui.py` can rebuild the layout safely. Run it after changing any front-panel element.
- **Object numbering:** a subpatch counts as **one** object in its parent. Count carefully when adding connections by hand; `tools/pdgen.py` avoids this.
- **`$1` inside `[expr]`** is only replaced by the abstraction argument when it's a separate word (` $1 `). Glued to other characters, expr reads it as inlet 1.
- **`[switch~]` starts off.** Adding one to a subpatch disables it; that's used to park the removed effects.
- **A list into `[expr]`'s left inlet** fills its inlets in order.
- **`[bendin]` range:** it outputs 0–16383 (centre 8192).
- **Sample rate:** samples are played at Pd's rate without resampling, so keep Pd at **48 kHz**.
- **Per-user files are git-ignored:** `piLooper/knobmap.txt` (learned Preset knobs), `piLooper/tappad.txt` (learned tap pad), user drum samples.

### Testing approach

- **Offline audio:** `pd -batch -nosound` with a small harness patch, a `[qlist]` script of timed messages and `[writesf~]` to a WAV, analysed with Python for RMS, pitch (Goertzel) and timing.
- **No MIDI in batch mode.** The controls have test inputs instead (`knobs-inject`, `pads-test-note`, `wheels-test-bend`/`-mod`), and buttons are simulated with `midi-btn-ctl-in <cc>`.
- **Screenshots:** `Xvfb` plus Pd's normal GUI, captured with `import`.

## Known issues and loose ends

- **Save, load, new song and song select** were only on the old Teensy panel; no LX25+ button triggers them yet.
- **The lead synths** (banks 4, 8, 12) ignore the knobs and wheels.
- **The FM presets** are named FM 1–9, because their sound types weren't clear from the patch.
- **Drum banks 2–3** still expect user samples (`kick_13.wav` …). Their pad map 2 pad 8 is now the tap pad.
- **Pre-existing load messages** from the 2017 patch: two "(bng->loadbang) connection failed" lines.
- **The legacy Teensy parts** (`serialControls`, `piLoopControl.ino`, `comPortMsg` traffic) are still in the patch but unused.
- **The 20-second limit:** loops can't be longer, because the tables hold 1e6 samples at 48 kHz.

## To-do and ideas

- [ ] **Hardware check-out** of the list above on the real LX25+, UMC22, Mac and Pi.
- [ ] **Song save/load on the LX25+:** e.g. hold Stop + a pad to save to a slot, and a pad to load. Show the song name on screen.
- [ ] **Sample groove collection:** a library of drum grooves (one-bar and two-bar loops at known tempos, CC0 sources) that drop straight into layer 1.
  - Browse them with the Track buttons.
  - Each groove is time-matched to the tapped tempo (resample or stretch) and shown with its name and bpm.
  - It gives an instant backing to jam over.
- [ ] **AI drummer:** a drum part generated to fit what you just played.
  - It listens to the first layer (onsets and accents from the loop audio, or the MIDI notes played) and generates a matching pattern on the drum kits: complementary kick/snare, hats that follow your subdivision, and fills every 4 or 8 bars.
  - Controls: a knob for *density*, one for *swing/humanize*, a pad to regenerate.
  - Could start rule-based (probabilities from onset analysis) and grow into a small model, e.g. a Magenta-style drum RNN running off-line on the Pi or the Mac and sending MIDI back into Pd.
- [ ] **Tempo changes after recording:** time-stretch the layers (e.g. a phase-vocoder or granular playback) so the tempo can be tapped again mid-song.
- [ ] **MIDI clock out/in:** sync external gear or a DAW to the loop.
- [ ] **Undo last layer:** keep the previous table so a bad overdub can be taken back.
- [ ] **Scenes:** save and recall sets of layer mutes/volumes and flip between them from the pads.
- [ ] **Export:** write a mixdown and the individual layers as WAV files for use in a DAW.
- [ ] **Touchscreen layout** for the Pi's official display: bigger buttons, fewer small sliders.
- [ ] **Knobs for the lead synths and FM preset names** (listen to them and name them).
- [ ] **Sidechain ducking:** the kick briefly ducks the pads and bass for a pumping feel.
