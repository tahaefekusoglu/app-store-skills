#!/bin/sh
# apptest-store-assets: simulator screenshot receiver (file handshake).
#
# The tour inside the app writes the image name to <DIR>/req.txt; this script
# takes the image with `xcrun simctl io <SIM> screenshot` (status bar included)
# and writes the name to <DIR>/ack.txt; the tour continues once the ack arrives.
#
#   sh shot_host.sh <SIMULATOR_UDID> <DIR> &      # start (PID → <DIR>/host.pid)
#   kill "$(cat <DIR>/host.pid)"                   # stop: NOT by pattern (pkill -f)
#
# Do NOT use pkill -f: the pattern also matches the command line of the shell
# that started this script and cuts the job short (CONVENTIONS §5.3).
SIM=$1; DIR=$2
[ -n "$SIM" ] && [ -n "$DIR" ] || { echo "usage: shot_host.sh <UDID> <DIR>" >&2; exit 2; }
mkdir -p "$DIR"
echo $$ > "$DIR/host.pid"
rm -f "$DIR/req.txt" "$DIR/ack.txt"
trap 'rm -f "$DIR/host.pid"; exit 0' INT TERM
last=""
while true; do
  if [ -f "$DIR/req.txt" ]; then
    name=$(cat "$DIR/req.txt")
    if [ -n "$name" ] && [ "$name" != "$last" ]; then
      mkdir -p "$DIR/$(dirname "$name")"
      if xcrun simctl io "$SIM" screenshot --type=png "$DIR/$name.png" >/dev/null 2>&1; then
        echo "captured $name"
      else
        echo "ERROR $name" >&2
      fi
      printf '%s' "$name" > "$DIR/ack.txt"
      last=$name
    fi
  fi
  sleep 0.2
done
