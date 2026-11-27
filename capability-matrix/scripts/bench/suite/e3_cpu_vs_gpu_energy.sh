#!/bin/bash
# Idea 3 REV 2. Rev 1's GPU arms were void: the backgrounded rail sampler was a subshell that
# INHERITED the EXIT trap, so when it finished it ran cleanup(), restarted the managed service
# mid-test, and the service then held the GPU memory the next arm needed -> "failed to create
# context". Fixes: every backgrounded subshell clears the trap with `trap - EXIT`, the sampler runs
# in the FOREGROUND (it overlaps the requests anyway), cleanup is guarded to the main shell by PID,
# and the slot geometry is reduced to fit an 8 GB unified-memory part.
#
# Instrumentation limit, unchanged and stated: rail 2 is CPU_GPU_CV (CPU+GPU+CV share one channel),
# so there is no clean iGPU-only reading. tok/J uses total-module VDD_IN (rail 1) only.
set -u
MAIN=$$
NEW=~/llama.cpp-new/build/bin
MODEL=~/models/qwen3-4b-q4km.gguf
PORT=8102
H=/sys/bus/i2c/devices/1-0040/hwmon/hwmon3
CTX=2048; PAR=4
SRV=0
cleanup () {
  [ "$$" != "$MAIN" ] && return 0          # only the main shell may restore the service
  [ "$SRV" != 0 ] && { kill -9 "$SRV" 2>/dev/null; }
  sudo systemctl start llama-server
  for i in $(seq 1 90); do [ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8101/health)" = 200 ] && break; sleep 2; done
  echo "RESTORED service=$(systemctl is-active llama-server) health=$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8101/health) gpu_load=$(cat /sys/devices/platform/gpu.0/load)"
}
trap cleanup EXIT
w () { awk -v v=$(cat $H/in1_input) -v c=$(cat $H/curr1_input) 'BEGIN{printf "%.3f", v*c/1e6}'; }

sudo systemctl stop llama-server; sleep 4
IDLE=$(for i in $(seq 1 10); do w; echo; sleep 1; done | awk '{s+=$1;n++} END{printf "%.3f", s/n}')
echo "idle VDD_IN=$IDLE W  gpu_load=$(cat /sys/devices/platform/gpu.0/load)  free=$(free -m | awk '/Mem:/{print $7}')MB"
echo "arms: -c $CTX --parallel $PAR, same binary 074f1f3, same model"

arm () {                        # label flags k
  local lab="$1" flags="$2" k="$3"
  LD_LIBRARY_PATH=$NEW $NEW/llama-server -m "$MODEL" --host 127.0.0.1 --port $PORT \
      -c $CTX --parallel $PAR $flags > /tmp/e_$lab.log 2>&1 &
  SRV=$!
  local ok=0
  for i in $(seq 1 120); do [ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:$PORT/health)" = 200 ] && { ok=1; break; }; sleep 2; done
  if [ $ok = 0 ]; then
    echo "  $lab: FAILED TO START"; grep -iE "error|cuda|memory|failed" /tmp/e_$lab.log | tail -4 | sed 's/^/      /'
    kill -9 $SRV 2>/dev/null; SRV=0; return 0
  fi
  grep -iE "load_tensors:.*buffer size|using device" /tmp/e_$lab.log | head -3 | sed 's/^/      /'
  local pids=()
  for s in $(seq 1 $k); do
    ( trap - EXIT; curl -s -H 'Content-Type: application/json' \
        -d "{\"prompt\":\"Explain why memory bandwidth limits token generation. Variant $s.\",\"n_predict\":160,\"cache_prompt\":false}" \
        http://127.0.0.1:$PORT/completion > /tmp/e_${lab}_$s.json 2>/dev/null ) &
    pids+=($!)
  done
  sleep 2
  local PW=$(for i in $(seq 1 14); do w; echo; sleep 1; done | awk '{s+=$1;n++} END{printf "%.3f", s/n}')
  local GL=$(cat /sys/devices/platform/gpu.0/load)
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  python3 -c "
import json,glob
n=0;r=0.0;c=0
for f in glob.glob('/tmp/e_${lab}_*.json'):
    try:
        t=json.load(open(f))['timings']; n+=t['predicted_n']; r+=t['predicted_per_second']; c+=1
    except Exception: pass
w=$PW; idle=$IDLE
print('  %-8s k=%s  agg %7.2f tok/s  VDD_IN %6.2f W  %6.3f tok/J  net-of-idle %6.3f  gpu_load=%s  (%d/%s ok)'
      % ('$lab', $k, r, w, r/w if w else 0, r/(w-idle) if w>idle else -1, '$GL', c, $k))"
  rm -f /tmp/e_${lab}_*.json
  kill -TERM $SRV 2>/dev/null; sleep 2; kill -9 $SRV 2>/dev/null; SRV=0
  sleep 3
}
arm cpu_k1 "-ngl 0 -dev none" 1
arm gpu_k1 "-ngl 99"          1
arm cpu_k4 "-ngl 0 -dev none" 4
arm gpu_k4 "-ngl 99"          4
