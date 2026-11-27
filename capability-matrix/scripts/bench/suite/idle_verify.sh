#!/bin/bash
# Assert a node is actually idle, and print the numbers rather than claiming it.
# Usage:  bash idle_verify.sh <node1|orinnx|orin1> [timeout_s]
#
# Why this is a separate, polling script (pitfall 7): after an 8-stream run, gpu_load still read
# 999 and the rail 26.52 W twenty seconds after the load generators were killed, because the server
# was still draining queued requests. A fixed `sleep` reports a false positive; this waits for the
# condition with a deadline.
#
# Also checks for stragglers -- hand-started servers and load loops that outlived their script.
# It does NOT kill anything: it reports, so a human decides. Killing by pattern is how an earlier
# cleanup killed its own ssh session (pitfall 6).
set -u
NODE="${1:?usage: idle_verify.sh <node1|orinnx|orin1> [timeout_s]}"
TMO="${2:-120}"
RAIL=/sys/bus/i2c/devices/1-0040/hwmon/hwmon3
IDLE_W=12.0          # VDD_IN above this on an Orin means work is still running
rail_w () { [ -r "$RAIL/in1_input" ] || { echo "n/a"; return; }
  awk -v v=$(cat $RAIL/in1_input) -v c=$(cat $RAIL/curr1_input) 'BEGIN{printf "%.2f", v*c/1e6}'; }
gload  () { cat /sys/devices/platform/gpu.0/load 2>/dev/null || echo "n/a"; }
tj     () { for z in 8 0; do f=/sys/class/thermal/thermal_zone$z/temp; [ -r $f ] && { echo $(( $(cat $f)/1000 )); return; }; done; echo "n/a"; }

t0=$(date +%s); ok=0
while :; do
  el=$(( $(date +%s) - t0 ))
  g=$(gload); w=$(rail_w)
  quiet=1
  [ "$g" != "n/a" ] && [ "$g" -gt 50 ] 2>/dev/null && quiet=0
  if [ "$w" != "n/a" ]; then
    over=$(python3 -c "print(1 if $w > $IDLE_W else 0)" 2>/dev/null || echo 0)
    [ "$over" = 1 ] && quiet=0
  fi
  [ "$quiet" = 1 ] && { ok=1; break; }
  [ "$el" -ge "$TMO" ] && break
  sleep 5
done

echo "=== $NODE after ${el}s ==="
echo "  gpu_load = $(gload)   (0 = idle; 999 = saturated)"
echo "  VDD_IN   = $(rail_w) W   (threshold $IDLE_W)"
echo "  tj       = $(tj) C"
echo "  loadavg  = $(cut -d' ' -f1-3 /proc/loadavg)"
echo "  --- stragglers (reported, NOT killed) ---"
ps -eo pid,etime,args --no-headers 2>/dev/null |
  awk '$0 ~ /llama-server|llama-completion|npu_live|live\.py/ && $0 !~ /awk/ {printf "    %s %s %.90s\n", $1, $2, $3" "$4" "$5" "$6}' |
  head -8
S=$(ps -eo args --no-headers 2>/dev/null | grep -cE "llama-completion|npu_live\.py")
echo "    load generators still alive: $S"
echo "  --- managed service ---"
if systemctl list-unit-files llama-server.service >/dev/null 2>&1; then
  echo "    llama-server: $(systemctl is-active llama-server)  (expected: active)"
  echo "    TimeoutStopSec: $(systemctl show llama-server -p TimeoutStopUSec --value)  (expected: 15s)"
  d=$(ls /etc/systemd/system/llama-server.service.d/ 2>/dev/null | wc -l)
  [ "$d" -gt 0 ] && echo "    WARNING: $d leftover drop-in(s) in llama-server.service.d -- a test did not clean up"
else
  echo "    no llama-server unit on this node"
fi
echo
[ "$ok" = 1 ] && echo "IDLE: $NODE" || echo "NOT IDLE after ${TMO}s: $NODE -- investigate the stragglers above"
exit $(( 1 - ok ))
