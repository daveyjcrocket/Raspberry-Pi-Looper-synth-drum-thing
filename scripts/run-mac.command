#!/usr/bin/env bash
# Start LiveLoopSynth on macOS. Double-click this file in Finder, or run it from Terminal.
# Audio (CoreAudio) and the MIDI keyboard are whatever Pd's Audio/MIDI settings are set to.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$HERE/piLooper/LiveLoopSynth.pd"

# Use PD_APP=/path/to/Pd.app to pick a specific install; otherwise take the newest in /Applications.
PD_APP="${PD_APP:-$(ls -d /Applications/Pd*.app 2>/dev/null | sort -V | tail -n 1 || true)}"
if [ -z "$PD_APP" ] || [ ! -d "$PD_APP" ]; then
  echo "Pure Data not found in /Applications. Install Pd vanilla 0.52 or newer from https://puredata.info/downloads" >&2
  exit 1
fi

open -a "$PD_APP" "$PATCH"
