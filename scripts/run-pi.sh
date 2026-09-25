#!/usr/bin/env bash
# Start LiveLoopSynth on a Raspberry Pi with a monitor, using ALSA for audio and MIDI.
# Uses the USB audio interface (Behringer UMC22 by default) for input and output,
# and connects the MIDI keyboard (Nektar Impact LX25+ by default) to Pd.
#
# Settings (environment variables):
#   AUDIO_DEVICE regex matched against Pd's audio device names (default: UMC22 / USB Audio CODEC)
#   AUDIO_DEV    Pd ALSA audio device number, overrides AUDIO_DEVICE; list them with: scripts/run-pi.sh --list
#   MIDI_DEVICE  part of the ALSA MIDI client name to connect   (default: Impact)
#   SAMPLE_RATE  default 48000
#   AUDIO_BUF    audio buffer in ms; raise it if you hear clicks (default 20)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$HERE/piLooper/LiveLoopSynth.pd"
AUDIO_DEVICE="${AUDIO_DEVICE:-UMC22|USB Audio CODEC}"
MIDI_DEVICE="${MIDI_DEVICE:-Impact}"
SAMPLE_RATE="${SAMPLE_RATE:-48000}"
AUDIO_BUF="${AUDIO_BUF:-20}"

if [ "${1:-}" = "--list" ]; then
  pd -nogui -alsa -listdev -send "pd quit" 2>&1
  echo; aconnect -i
  exit 0
fi

# Pd's device number for the first "$1" ("input" or "output") device matching $AUDIO_DEVICE,
# preferring the direct "(hardware)" device over the "(plug-in)" one.
audio_dev_number() {
  printf '%s\n' "$devlist" | awk -v sect="audio $1 devices:" -v want="$AUDIO_DEVICE" '
    /devices:$/ { on = ($0 == sect); next }
    on && $1 ~ /^[0-9]+\.$/ && tolower($0) ~ tolower(want) {
      n = $1; sub(/\./, "", n)
      if ($0 ~ /\(hardware\)/) { hw = n; exit }
      if (fb == "") fb = n
    }
    END { if (hw != "") print hw; else if (fb != "") print fb }'
}

args=(-alsa -r "$SAMPLE_RATE" -audiobuf "$AUDIO_BUF" -inchannels 2 -outchannels 2
      -alsamidi -midiindev 1 -midioutdev 1)
if [ -n "${AUDIO_DEV:-}" ]; then
  args+=(-audiodev "$AUDIO_DEV")
else
  devlist="$(pd -nogui -alsa -listdev -send "pd quit" 2>&1 || true)"
  in_dev="$(audio_dev_number input)"
  out_dev="$(audio_dev_number output)"
  if [ -n "$in_dev" ] && [ -n "$out_dev" ]; then
    args+=(-audioindev "$in_dev" -audiooutdev "$out_dev")
    echo "Audio: using device in=$in_dev out=$out_dev matching '$AUDIO_DEVICE'"
  else
    echo "No audio device matching '$AUDIO_DEVICE' found; using Pd's default. Is the UMC22 plugged in? (see: $0 --list)" >&2
  fi
fi

pd "${args[@]}" -open "$PATCH" &
pd_pid=$!
trap 'kill "$pd_pid" 2>/dev/null || true' INT TERM

# ALSA client id whose name contains $1 (case-insensitive), from `aconnect $2` output.
client_id() {
  aconnect "$2" | awk -v want="$1" 'tolower($0) ~ /^client [0-9]+:/ && index(tolower($0), tolower(want)) {
    sub(/^client /, ""); sub(/:.*/, ""); print; exit }'
}

# Wait for Pd's MIDI port to appear.
pd_client=""
for _ in $(seq 1 30); do
  pd_client="$(client_id "Pure Data" -o)"
  [ -n "$pd_client" ] && break
  sleep 0.5
done

kb_client="$(client_id "$MIDI_DEVICE" -i)"
if [ -z "$pd_client" ]; then
  echo "Pd's ALSA MIDI port never appeared; MIDI not connected." >&2
elif [ -z "$kb_client" ]; then
  echo "No MIDI device matching '$MIDI_DEVICE' found. Plug it in, or set MIDI_DEVICE (see: aconnect -i)." >&2
else
  # Connect every output port of the keyboard (the LX25+ has a keys port and a DAW/transport port).
  for port in $(aconnect -i | awk -v c="$kb_client" '
      /^client [0-9]+:/ { cur = $2; sub(/:/, "", cur); next }
      cur == c && $1 ~ /^[0-9]+$/ { print $1 }'); do
    aconnect "$kb_client:$port" "$pd_client:0" && echo "Connected MIDI $kb_client:$port -> Pd"
  done
fi

wait "$pd_pid"
