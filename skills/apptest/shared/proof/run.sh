#!/bin/sh
# All templates on a temporary simulator; deletes the simulator when done. Mac + Xcode only. Usage: run.sh <empty folder> [devicetype] [runtime]
set -u
HERE=$(cd "$(dirname "$0")" && pwd); W=$(mkdir -p "$1" && cd "$1" && pwd)
DT=${2:-"iPhone 17 Pro"}; RT=${3:-$(xcrun simctl list runtimes | grep -o 'com.apple.CoreSimulator.SimRuntime.iOS-[0-9-]*' | tail -1)}
python3 -I "$HERE/generate.py" "$W/p" || exit 2
UD=$(xcrun simctl create apptest-proof "$DT" "$RT") || exit 2
trap 'kill $PIDS 2>/dev/null; xcrun simctl delete "$UD"' EXIT
mkdir -p "$W/www"; echo '{"ok":true}' > "$W/www/ping"; PIDS=""
start() { "$@" >/dev/null 2>&1 & PIDS="$PIDS $!"; }
(cd "$W/www" && exec python3 -I -m http.server 8890 --bind 127.0.0.1) >/dev/null 2>&1 & PIDS="$!"
NC="$HERE/../../../apptest-network-chaos/scripts/nc_proxy.py"; U=http://localhost:8890
start python3 -I "$NC" --upstream $U --port 8897
start python3 -I "$NC" --upstream $U --port 8891 --rule '^GET /ping' status:503
start python3 -I "$NC" --upstream $U --port 8892 --rule '^GET /ping' garbage
start python3 -I "$NC" --upstream $U --port 8893 --rule '^GET /ping' reset
start python3 -I "$NC" --upstream $U --port 8894 --rule '^GET /ping' hang:30
sleep 1; cd "$W/p"
xcodebuild test -project Proof.xcodeproj -scheme ProofUITests -destination "platform=iOS Simulator,id=$UD" \
  -derivedDataPath "$W/dd" -parallel-testing-enabled NO > "$W/test.log" 2>&1
grep -E "Test Case .*(passed|failed)" "$W/test.log" | sed 's/ProofUITests\.//' | sort > "$W/got.txt"
BAD=0
while read -r t; do grep -q "\[$t\]' failed" "$W/got.txt" || { echo "SHOULD HAVE FAILED: $t"; BAD=1; }; done <<EOF2
CrawlBugCrashTests testCrawl
CrawlBugA11yTests testCrawl
RIBug testDoubleTapSaveCreatesOneRecord
StateSimBugTests testSimulation
EOF2
N=$(grep -c "' passed" "$W/got.txt"); F=$(grep -c "' failed" "$W/got.txt")
grep "' failed" "$W/got.txt" | grep -vE "Bug" && BAD=1
echo "passed $N · failed $F (4 expected to fail)"; [ "$N" -ge 15 ] && [ "$F" = 4 ] && [ "$BAD" = 0 ] && echo PROOF-OK || { echo PROOF-BROKEN; exit 1; }
