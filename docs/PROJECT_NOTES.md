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

## October 2026: AI drummer, step 1

- Explored how an AI drummer could work and wrote up the design and plan: see [AI drummer](#ai-drummer-design-and-plan) below.
- Built step 1: `[drummer]` (from `tools/gen_drummer.py`) plays the selected kit in time with the loop, from a small groove library. It is heard but not recorded, and it can be paused.
- In drummer mode the drum pads are its controls (pause, fill, rebonk) instead of playing the kit.
- Tested headless with Pd 0.54: hit timing per 16th step, swing, pause/resume, fill, rebonk, fade on Stop, nothing on `s~ input`, and the pad filtering. Not yet tried on the LX25+ or the Pi.

## Architecture

### Files

| Path | What it is |
|---|---|
| `piLooper/LiveLoopSynth.pd` | Main patch. The top level is only the front panel (generated) plus the hidden helper objects; everything else lives in `[pd internals]`. |
| `piLooper/*.pd` from `tools/gen_*.py` | **Generated:** `Loop.pd` (one layer), `looper.pd` (controller), `knobs.pd`, `inputFX.pd`, `padDisplay.pd`, `wheels.pd`, `tempo.pd`, `tapFilter.pd`, `drummer.pd` (AI drummer). Edit the generator, not the `.pd`. |
| `piLooper/analogSynth.pd`, `analogVoice.pd`, `organSynth.pd`, `organVoice.pd`, `sessionFiles.pd`, `instrumentName.pd` | Hand-written this session. |
| `piLooper/fmSynth` (inside the main patch), `fmVoice.pd`, `synthLeadVoice*.pd`, `samp.pd`, `notecheck.pd`, `oneshot.pd`, `load.pd`, `loopSave.pd`, `loopLoad.pd` | Legacy (2017) parts, lightly modified. |
| `piLooper/kits/` | Drum samples, licenses and pad map. |
| `tools/pdgen.py` | Tiny patch-writing helper used by all generators. |
| `tools/gen_gui.py` | Regenerates the front panel **around** `[pd internals]`, leaving that block untouched. |
| `piLooper/remote.pd`, `remoteOut.pd`, `remote/names.json` from `tools/gen_remote.py` | **Generated:** the Pd end of the web remote, and its allow-list. |
| `remote/server.py` | Web remote bridge: serves `remote/web/` and relays WebSocket ⇄ Pd (stdlib only). |
| `remote/web/` | The web remote page (`index.html`, `style.css`, `app.js`, manifest, icon). No build step. |
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
   drummer.pd (8 kit voices) ─s~ drummer-out─► audio-IO, after microFade, into the main volume ► dac~
                                                                             (heard, not recorded)
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
| `drummer-mode` (`-r`), `drummer-pause`, `drummer-fill`, `drummer-rebonk`, `drummer-level` (`-r`), `drummer-swing` | → drummer | on/off (pads become controls), pause/resume, fill, change groove, level 0–1, swing 50–75 % |
| `drummer-cnv`, `drummer-mode-pads` | drummer → | status line; pad display relabels the pads |
| `drummer-hit` | drummer → its voices | `role*128 + velocity`, after swing (handy for tests) |
| `drmgroove` (array, 8 values per 16th: kick, snare, hat closed, hat open, rimshot, tom high, tom low, ride), `drmGlen`, `drmSw`, `drmKit` … | drummer state | `[value]`s and arrays named without hyphens so `[expr]` can read them |
| `remote-out`, `remote-dump` | web remote | `[remoteOut <name>]` reports a name to the bridge; `remote-dump` makes them all repeat their last label / color / value |

### Conventions and Pd gotchas we hit

- **The main patch's top level has no wires.** It's all send/receive, so `gen_gui.py` can rebuild the layout safely. Run it after changing any front-panel element.
- **Object numbering:** a subpatch counts as **one** object in its parent. Count carefully when adding connections by hand; `tools/pdgen.py` avoids this.
- **`$1` inside `[expr]`** is only replaced by the abstraction argument when it's a separate word (` $1 `). Glued to other characters, expr reads it as inlet 1.
- **`[switch~]` starts off.** Adding one to a subpatch disables it; that's used to park the removed effects.
- **A list into `[expr]`'s left inlet** fills its inlets in order.
- **`[bendin]` range:** it outputs 0–16383 (centre 8192).
- **Sample rate:** samples are played at Pd's rate without resampling, so keep Pd at **48 kHz**.
- **`[v name]` stores a float without sending it on.** Only a bang makes it output. Put a `[t b f]` in front when the chain has to carry on.
- **`[expr]` can read `[value]` variables and arrays by name** (`expr drmS % 16`, `drmgroove[$f1]`). The names can't contain hyphens (expr reads `-` as minus), and `$0` doesn't work there. A `; name 5` message sets a `[value]`.
- **Generator pitfall:** `x = O(...); C(last(), x)` wires `x` to itself, because `last()` is now `x`. That makes a stack overflow in Pd, which silently stops the message chain. Keep a handle on the source object instead. Scan for it with `awk '/^#X connect/{split($0,a," "); if(a[3]==a[5]) print}' piLooper/*.pd`.
- **Per-user files are git-ignored:** `piLooper/knobmap.txt` (learned Preset knobs), `piLooper/tappad.txt` (learned tap pad), user drum samples.

### Web remote

```
browser ── WebSocket /ws (JSON) ──► remote/server.py ── TCP 127.0.0.1:9311 (FUDI) ──► [remote] in the patch
```

- **Pd side (`remote.pd`):**
  - `[netreceive]` listens on localhost only.
  - Incoming `<name> <value>` messages go through a `[route]` of allowed names to `[s <name>]`.
  - `[netreceive]`'s `send` message talks back to the bridge.
  - Every watched name has a `[remoteOut <name>]`, which keeps the last label, color and value for `remote-dump`.
- **The bridge (`server.py`):**
  - It retries the Pd connection every second and asks for a dump each time it connects.
  - It caches the state for new browsers and only forwards allowed names with a bang or a number.
  - It sends loop position and meters at most every 40 ms.
- **Driving controls:** the page drives each control through its front-panel **receive** name (`lp-vol-N-r`, `knob-N-r`, `tempo-click-r` …). The Pd window follows, and the control passes the value on as usual. The toggles and number boxes that had no receive name got one (`*-r`) for this.
- **Adding a control:**
  1. Add its names to `IN` / `OUT` in `tools/gen_remote.py`.
  2. Run the generator.
  3. Add the widget in `remote/web/app.js`.
- **Bank counter:** `[pd instrument-select]` now also follows `bankSelect`, so the LX25+ patch − / + carry on from a bank picked elsewhere.
- **Level ranges:** the front-panel level sliders were 0–127 but receive 0–1 gains (the inputs start at 2). Their ranges now match.

### Testing approach

- **Offline audio:** `pd -batch -nosound` with a small harness patch, a `[qlist]` script of timed messages and `[writesf~]` to a WAV, analysed with Python for RMS, pitch (Goertzel) and timing.
- **No MIDI in batch mode.** The controls have test inputs instead (`knobs-inject`, `pads-test-note`, `wheels-test-bend`/`-mod`, `drummer-test-pad <1-8>`), and buttons are simulated with `midi-btn-ctl-in <cc>`.
- **Drummer timing:** log `[r drummer-hit]` with a `[timer]` to get every hit with its exact logical time. That's more reliable than finding onsets in the rendered audio, because the tom samples have several peaks.
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
- [ ] **AI drummer:** step 1 is done; steps 2–4 and the ideas list are in [AI drummer: design and plan](#ai-drummer-design-and-plan).
- [ ] **Web remote, next steps:**
  - A systemd service, so `--headless` runs without a desktop login.
  - A password or pairing code if it's used on shared Wi-Fi.
  - Song save/load from the page.
  - Drum pads that play from the phone.
  - Test on the real Pi: CPU with the bridge running, and latency over Wi-Fi.
- [ ] **Tempo changes after recording:** time-stretch the layers (e.g. a phase-vocoder or granular playback) so the tempo can be tapped again mid-song.
- [ ] **MIDI clock out/in:** sync external gear or a DAW to the loop.
- [ ] **Undo last layer:** keep the previous table so a bad overdub can be taken back.
- [ ] **Scenes:** save and recall sets of layer mutes/volumes and flip between them from the pads.
- [ ] **Export:** write a mixdown and the individual layers as WAV files for use in a DAW.
- [ ] **Touchscreen layout** for the Pi's official display: bigger buttons, fewer small sliders.
- [ ] **Knobs for the lead synths and FM preset names** (listen to them and name them).
- [ ] **Sidechain ducking:** the kick briefly ducks the pads and bass for a pumping feel.

## AI drummer: design and plan

A drum part that fits what you just played. The requirements:

- **Light on the Pi's CPU.** A heavy version may run on the computer only.
- **Listens to the first layer** for tempo and swing.
- **Different on every pass** through the loop, so it sounds live.
- **Its own layer:** heard but never recorded, and it can be paused.
- **Replaces the drum pads.** With the drummer on, the pads are its inputs (pause, fill, rebonk) instead of playing the kit.
- **Uses the selected kit.**

### Why it's cheap

Layer 1 already gives away most of the answer:

- **The downbeat is known.** Auto-record starts on your first note, so the start of the loop is beat 1.
- **The loop length is known exactly.** "Find the tempo" becomes "how many beats fit in this loop", which has only a few dozen possible answers.
- **A tapped tempo answers it outright.**

That avoids real beat tracking, the expensive part.

### How it fits together

```
layer 1 recording ──► [bonk~] onsets (on only while it listens)  ┐
LX25+ notes ────────► exact onsets, if layer 1 was played on keys or pads ┤ onset list (time, strength, low or high)
                                                                     ▼
              brain (Python, like remote/server.py; wakes once per loop)
                analyse ► choose a groove ► vary it ► the NEXT loop's hits
                                                                     │ FUDI, sent during the current loop
                                                                     ▼
        [drummer] in Pd: steps through the loop in 16ths from [r f] ► 8 kit voices
        ► s~ drummer-out ► audio-IO after the loopers ► dac~   (never s~ input: not recorded)
```

**The rule that keeps it safe on a Pi: Python never sits in the audio path.** The brain sends the next loop's pattern while the current loop plays. If the brain is late, slow or crashed, Pd simply plays the last pattern again.

The CPU cost is about what the pads use now:

- one onset detector while it listens
- one voice per kit sound
- a few milliseconds of Python per loop

### Listening: tempo and swing

1. **Onsets.** Use `[bonk~]` (in Pd vanilla's extra) on the input while layer 1 records, then switch it off with `[switch~]`. Merge in the MIDI note-ons from that pass, which are exact. bonk~'s spectral template also tells low hits from high ones, which helps place the kick and snare.
2. **Tempo.** Try every whole-bar beat count that gives 60–180 bpm. Score each one by how well the onsets sit on a 16th grid and on a triplet grid, with a gentle preference for tempos around 100 bpm. A tapped tempo skips this step.
3. **Swing.** Measure where the off-beat 8ths actually land in the beat: 50 % is straight, 67 % is a triplet shuffle. The average early or late offset (pushing ahead or laying back) is copied as well.
4. **Groove choice.** A 16-step accent histogram shows the subdivision you play (8ths, 16ths or triplets) and where your accents are. Pick from the groove library: the kick goes under your strong low accents, and the drums fill the gaps rather than doubling your accents.

**Prototype results.** A pure-Python sketch was tried on synthetic loops with ±8 ms timing slop and the loop closed 1.5 % early or late.

- Each analysis took 0.3–10 ms.
- Straight and swung grooves usually came out within about 1 bpm and a few % of swing.
- The misses were the classic metrical ambiguities: 65 bpm read as 130, a triplet feel read as swung 8ths, and sometimes 4/4 read as 3/4.

So:

- **Tap tempo** settles all of them.
- **Without a tap,** the screen should show the guess ("96 bpm · swing 62 %") with **½× / 2×** and **straight / swing / triplet** corrections.

### Playing: different every pass

- **Steps with chances.** Each groove step has a chance to play and a velocity, instead of being simply on or off.
  - **Backbone** hits (kick on 1, snare on 2 and 4) always play.
  - **Decoration** (ghost notes, extra kicks, open hats) is rolled again every pass. A **density** knob scales those chances.
- **Humanize** (a second knob) adds small timing and velocity changes on top of the measured swing and push/lay-back. Hats get a natural accent pattern rather than random volumes.
- **Phrasing.** The decoration changes slowly and drifts back toward the base groove, so it sounds like one drummer rather than dice. Fills come every 4 or 8 bars, with an accent on the next downbeat.
- **Intensity follows the band.** It gets busier as layers are added (hats to ride, more ghost notes) and calmer when keep-N mutes layers.

### Pi vs computer

- **Pi and computer:** everything above. The analysis and the per-step-chance engine are cheap.
- **Computer only (optional):** a trained model such as Magenta's GrooVAE for more human timing, or a model that writes new patterns. It plugs in where the brain writes `drmgroove`, so the Pd side doesn't change.

### The drummer's own layer

- **Not recorded.** It works like the click: `s~ drummer-out` is added in `audio-IO` after the loopers and `microFade`, just before the main volume. It never reaches `s~ input`.
- **Pause.** Pause stops it on the next beat. Resume brings it back on the next bar line. While paused it keeps counting, so it always comes back in time.
- **Follows the looper.** It runs only while the loop plays (OVERDUB, PLAYING, FADING), not while layer 1 records. It fades with `loopFade`, and Stop and clear stop it.
- **Mic bleed:** in the room it comes out of the speakers, so a mic can pick it up during overdubs. Use headphones, or pause it while recording from the mic.

### The pads as inputs

In drummer mode:

- **`tapFilter` drops the pads from every instrument** (notes 48–63 on the pads' channel), so they stop playing the kit or a synth. The pads' channel is taken from the tap pad (`tap-ch`). With `tap-ch` = 0 (any) the pads can't be told from the keys, so nothing is dropped and the pads don't control the drummer.
- **`[tapFilter 1]` keeps the pads.** The pad display uses it, so the pads still flash.
- **Pad roles**, by position, on both pad maps:
  - 1 = pause / resume
  - 2 = fill
  - 3 = rebonk
  - 4–7 are free (ideas below). Pad 8 on map 2 stays the tap pad.
- **Ideas for later:** use the pad velocity, e.g. a harder fill hit plays a bigger fill.

### Build steps

- [x] **Step 1: player** (`tools/gen_drummer.py` → `piLooper/drummer.pd`). Done:
  - **Kit:** the selected kit (banks 0–3, kept while a synth is selected), all 32 samples preloaded. Missing user samples are silent.
  - **Timing:** 16th steps timed from `[r f]`. Bars come from the tapped tempo, otherwise from about 100 bpm in 4/4, and over 16 bars it plays half-time.
  - **Grooves:** a library of five (rock, half-time, four on the floor, funk, ride), and **rebonk** steps through them for now.
  - **Controls:** a fill on the last beat of the bar plus a downbeat accent, a hi-hat lift on the last off-beat of the loop, and swing (`drummer-swing`, 50–75 %).
  - **Pause and output:** pause and resume on the beat and bar grid, a level control, and output that is heard but not recorded.
  - **Front panel and web remote:** status line, on switch, pause / fill / rebonk, level. The pad display relabels the pads in drummer mode.
- [ ] **Step 2: variation every pass.**
  - The brain (Python, a separate process on its own FUDI port, e.g. 9312) writes a whole-loop pattern into `drmgroove` (up to 256 steps × 8 sounds) and sets `drmGlen`.
  - Double-buffer it (write `drmnext`, copy on `[r f]`) so a pattern never changes mid-loop.
  - Knobs for **density** and **humanize**.
  - Pd keeps playing the last pattern if the brain stops.
- [ ] **Step 3: listening.** `[bonk~]` and MIDI onsets from layer 1 → the brain → tempo and swing guess (`drummer-swing`), with the ½× / 2× and feel corrections on screen and on the remote.
- [ ] **Step 4: groove choice from your accents,** automatic fills every 4 or 8 bars, and intensity that follows the layers.

### Development possibilities

- **Rebonk from time to time.** Don't only listen once. Let `[bonk~]` wake up every so often, e.g. for one pass every 8 or 16 loops, or when a new layer is closed. It listens to the whole band (the loop mix plus what's being played live), and the brain changes up the groove to match how the song has grown: busier when it got denser, half-time when it thinned out, ride instead of hats when the chords got bigger.
  - bonk~ is on only for that one pass, so the CPU cost stays near zero the rest of the time.
  - A **rebonk** setting could pick *never / every N loops / on every new layer*.
  - Pad 3 (**rebonk**) triggers it by hand.
- **Live listening:** bonk~ always on, following your playing as it happens (pushes, accents, stops). It costs more but is still fine on a Pi 4.
- **Saved grooves:** keep the last few grooves and flip between them with pads 4–7, or keep one per scene.
- **Pad velocity:** fill size, or how far rebonk changes things.
- **Count-in drums:** with a tapped tempo, the drummer could play during the count-in and while layer 1 records, instead of the click.
- **Record it on purpose:** a "print drums" button that records one pass of the drummer into a layer, for when you want to keep it.
- **A trained model** on the Mac (GrooVAE-style humanizing, or generated patterns), as above.
