# Drum kits

Two kits, eight sounds each, mapped to the Nektar Impact LX25+ pads. The same layout is on both pad maps (notes 48–55 and 56–63):

| Pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Note (map 1 / map 2) | 56 / 48 | 57 / 49 | 58 / 50 | 59 / 51 | 60 / 52 | 61 / 53 | 62 / 54 | 63 / 55 |
| Sound | kick | snare | closed hi-hat | open hi-hat | rimshot | high tom | low tom | ride |

All files are 48 kHz mono 16-bit WAV. Pd plays samples at its own sample rate without resampling, so run Pd at 48 kHz or the drums will be off-pitch. Drums, toms and rimshot are normalized to −1/−2 dBFS, and hi-hats and ride to −7 dBFS, for a natural kit balance.

## gmrock/ (instrument bank 0)

From **GMRockKit** by Glen MacArthur and Sebastian Moors, distributed with the [Hydrogen drum machine](https://github.com/hydrogen-music/hydrogen/tree/master/data/drumkits/GMRockKit). License: GPL, full text in `gmrock/COPYING`.

Changes: the "Hard" velocity layer of Kick, Snare, SnareRimshot, HatClosed, HatOpen, Ride, Tom1 and TomFloor, resampled from 44.1 to 48 kHz, silent tails trimmed, and normalized. The unmodified originals are at the link above.

## virtuosity/ (instrument bank 1)

From **Virtuosity Drums** by Versilian Studios ([sfzinstruments/virtuosity_drums](https://github.com/sfzinstruments/virtuosity_drums)). License: CC0 1.0 (public domain), text in `virtuosity/LICENSE`.

Changes: each sound is a mono mix of the kick mic, snare mic and overhead mics (the library's "basic kit" setup), with tails trimmed to at most 3 s and normalized. Layers used: kick snare-off vl3, snare center vl28, snare rimshot vl9, hi-hat closed vl3, hi-hat open vl3, ride vl3, high tom center vl12, low tom center vl12.
