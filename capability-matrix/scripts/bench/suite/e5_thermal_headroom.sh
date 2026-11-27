#!/bin/bash
# Research idea 5: does the thermal governor actually protect a sustained run?
# Incidental finding earlier today: orinnx sat at tj 98 C -- PAST its 95 C trip, 6 C under the
# 104 C shutdown trip -- with every *-throttle-alert cooling device reading cur=0 and both CPU
# clusters at full 1984 MHz. That suggests the governor does NOT clamp clocks at 98 C, which is
# not something vendors publish. This measures it deliberately, with hard limits.
#
# BOUNDED: aborts at tj >= ABORT_C, or after MAX_S seconds, or as soon as any throttle alert
# fires (which is the positive result -- no need to keep cooking it). Strictly milder than the
# 9-hour accident. Load is driven through the EXISTING managed service; nothing is reconfigured.
set -u
MAIN=$$
URL=http://127.0.0.1:8101
ABORT_C=99
MAX_S=600
PIDS=()
cleanup () {
  [ "$$" != "$MAIN" ] && return 0
  for p in "${PIDS[@]:-}"; do kill -9 "$p" 2>/dev/null; done
  sleep 3
  echo "LOAD STOPPED. settling 20s..."
  sleep 60
  echo "after: tj=$(( $(cat /sys/class/thermal/thermal_zone8/temp)/1000 ))C gpu_load=$(cat /sys/devices/platform/gpu.0/load) VDD_IN=$(awk -v v=$(cat /sys/bus/i2c/devices/1-0040/hwmon/hwmon3/in1_input) -v c=$(cat /sys/bus/i2c/devices/1-0040/hwmon/hwmon3/curr1_input) 'BEGIN{printf "%.2f", v*c/1e6}')W service=$(systemctl is-active llama-server)"
}
trap cleanup EXIT
H=/sys/bus/i2c/devices/1-0040/hwmon/hwmon3
alerts () { for c in /sys/class/thermal/cooling_device*; do t=$(cat $c/type); case $t in *throttle-alert) printf "%s=%s " "${t%%-throttle-alert}" "$(cat $c/cur_state)";; esac; done; }
fan ()    { for c in /sys/class/thermal/cooling_device*; do [ "$(cat $c/type)" = pwm-fan ] && { echo "$(cat $c/cur_state)/$(cat $c/max_state)"; return; }; done; echo "?"; }

[ "$(curl -s -o /dev/null -w %{http_code} $URL/health)" != 200 ] && { echo "service not healthy, aborting"; exit 1; }
echo "baseline: tj=$(( $(cat /sys/class/thermal/thermal_zone8/temp)/1000 ))C fan=$(fan) alerts: $(alerts)"
echo "starting 2 concurrent streams (the high-power config per 006); abort at ${ABORT_C}C or ${MAX_S}s or first throttle"

for s in $(seq 1 2); do   # 2 streams, NOT 8: 006 shows 8 streams draws 4.51W LESS, so 8 is the COLD config
  ( trap - EXIT
    while true; do
      curl -s -H 'Content-Type: application/json' \
        -d "{\"prompt\":\"Describe in exhaustive detail how a scheduler places work. Variant $s.\",\"n_predict\":256,\"cache_prompt\":false}" \
        $URL/completion >/dev/null 2>&1
    done ) &
  PIDS+=($!)
done

t0=$(date +%s); maxtj=0; fired=""; gmin=999999; cmin=999999
printf "%6s %6s %6s %9s %9s %7s %6s  %s\n" "t(s)" "tj" "gpu" "gpuMHz" "cpuMHz" "VDD_IN" "fan" "alerts"
while :; do
  now=$(( $(date +%s) - t0 ))
  tj=$(( $(cat /sys/class/thermal/thermal_zone8/temp)/1000 ))
  gt=$(( $(cat /sys/class/thermal/thermal_zone1/temp)/1000 ))
  gf=$(( $(cat /sys/class/devfreq/17000000.gpu/cur_freq 2>/dev/null || echo 0)/1000000 ))
  cf=$(( $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)/1000 ))
  pw=$(awk -v v=$(cat $H/in1_input) -v c=$(cat $H/curr1_input) 'BEGIN{printf "%.2f", v*c/1e6}')
  al=$(alerts)
  [ "$tj" -gt "$maxtj" ] && maxtj=$tj
  [ "$gf" -lt "$gmin" ] && gmin=$gf
  [ "$cf" -lt "$cmin" ] && cmin=$cf
  printf "%6s %5sC %5sC %8sM %8sM %6sW %6s  %s\n" "$now" "$tj" "$gt" "$gf" "$cf" "$pw" "$(fan)" "$al"
  echo "$al" | grep -qvE "^(cpu=0 |gpu=0 |cv0=0 |cv1=0 |cv2=0 |soc0=0 |soc1=0 |soc2=0 )+$" && { fired="$al"; echo ">>> THROTTLE ALERT FIRED: $al"; break; }
  [ "$tj" -ge "$ABORT_C" ] && { echo ">>> ABORT: tj reached ${tj}C (limit ${ABORT_C})"; break; }
  [ "$now" -ge "$MAX_S" ] && { echo ">>> reached ${MAX_S}s without a throttle alert"; break; }
  sleep 5
done
echo
echo "VERDICT: max tj ${maxtj}C | min GPU clock ${gmin} MHz | min CPU clock ${cmin} MHz | alert fired: ${fired:-NONE}"
