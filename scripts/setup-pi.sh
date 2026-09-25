#!/usr/bin/env bash
# One-time setup for Raspberry Pi OS (Bookworm or newer, desktop version).
#   scripts/setup-pi.sh              install Pd + externals
#   scripts/setup-pi.sh --autostart  also start LiveLoopSynth when the desktop logs in
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt-get update
sudo apt-get install -y puredata pd-zexy alsa-utils

# [file] (used for song folders) needs Pd 0.52+.
ver="$(pd -version 2>&1 | sed -n 's/^Pd-\([0-9]*\.[0-9]*\).*/\1/p' | head -n 1)"
if [ -n "$ver" ] && [ "$(printf '%s\n0.52\n' "$ver" | sort -V | head -n 1)" != "0.52" ]; then
  echo "Warning: Pd $ver is older than 0.52; saving/loading songs won't work. Use Raspberry Pi OS Bookworm or newer." >&2
fi

# Lets Pd run its audio thread at real-time priority (takes effect after logging out and back in).
sudo usermod -aG audio "$USER"

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cat > "$HOME/.config/autostart/liveloopsynth.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=LiveLoopSynth
Exec=$HERE/scripts/run-pi.sh
Terminal=false
DESKTOP
  echo "Autostart installed: $HOME/.config/autostart/liveloopsynth.desktop"
fi

echo "Done. Start it with: $HERE/scripts/run-pi.sh"
