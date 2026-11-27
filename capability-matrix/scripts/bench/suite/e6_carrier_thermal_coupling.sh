#!/bin/bash
# e6: does the carrier impose a THERMAL cost by packing modules into one enclosure?
#
# Runs from a workstation; orchestrates all three nodes over ssh.
#
# 009 concluded the carrier's value is packaging, having measured its switch (full line rate, no
# capability a cheap switch lacks) and its shared store (8.3x SLOWER than local NVMe for model
# load). It never tested whether the packaging itself costs anything.
#
# Two measurements today frame the question:
#   - e5: orinnx under sustained load ALONE plateaus at tj 86 C, zero throttle alerts, GPU clock
#     never leaving 1173 MHz, fan at 2/3.
#   - the 2026-11-25 accident: orinnx reached tj 98 C -- past its 95 C trip, 6 C under the 104 C
#     shutdown -- while the dashboard was driving BOTH Orins and node1's NPU at once.
# Same module, same enclosure, 12 C apart. If that gap is cross-module heating it is a measured
# cost of the carrier, not a feature, and it belongs in 009.
#
# Phases: each node loaded ALONE (its own baseline), then ALL THREE together. The delta per module
# is the coupling. Nothing is reconfigured; load goes through the existing managed services.
#
# BOUNDED: any Orin reaching ABORT_C ends the phase immediately. Strictly milder than the accident,
# and monitored rather than left running.
set -u
ABORT_C=97
PHASE_S="${PHASE_S:-240}"
SETTLE_S="${SETTLE_S:-180}"
OUT="${OUT:-$HOME/e6-$(date +%Y%m%d-%H%M%S)}"; mkdir -p "$OUT"
NODES=(node1 orinnx orin1)

# --- per-node load generators. Each clears its EXIT trap (PITFALLS.md #5) and is killed by PID.
load_start () {                 # $1 = node ; writes the remote pidfile
  case "$1" in
    orinnx|orin1)
      # 2 streams, NOT 8: paper 006 shows 8 streams draws ~4.5 W LESS, so 8 is the COLD config and
      # would hide the effect (PITFALLS.md #8).
      ssh "$1" 'rm -f /tmp/e6.pids; for s in 1 2; do ( trap - EXIT; while true; do
           curl -s -H "Content-Type: application/json" \
             -d "{\"prompt\":\"Describe in exhaustive detail how a scheduler places work across dissimilar machines. Variant '"'"'$s'"'"'.\",\"n_predict\":256,\"cache_prompt\":false}" \
             http://127.0.0.1:8101/completion >/dev/null 2>&1; done ) & echo $! >> /tmp/e6.pids; done; echo started' ;;
    node1)
      # node1 has no llama-server unit; load its CPU and NPU the way the dashboard did
      ssh node1 'rm -f /tmp/e6.pids
        ( trap - EXIT; cd /mnt/nvme/npu-bench && exec .venv/bin/python npu_live.py 3 >/dev/null 2>&1 ) & echo $! >> /tmp/e6.pids
        ( trap - EXIT; cd /mnt/nvme/llama-rpc-build/bin && while true; do LD_LIBRARY_PATH=. ./llama-completion \
            -m /mnt/nvme/share/models/Qwen3-0.6B-Q4_K_M.gguf -ngl 0 -dev none -t 4 \
            -p "why does memory bandwidth limit token generation" -n 128 --ignore-eos --no-warmup \
            -st --no-display-prompt >/dev/null 2>&1; done ) & echo $! >> /tmp/e6.pids
        echo started' ;;
  esac
}
load_stop () { ssh "$1" 'for p in $(cat /tmp/e6.pids 2>/dev/null); do kill -9 $p 2>/dev/null; done; rm -f /tmp/e6.pids; pkill -9 -x npu_live.py 2>/dev/null; echo stopped' ; }

probe () {                      # $1 = node ; one line of telemetry
  ssh "$1" 'tj=n/a; for z in 8 0; do f=/sys/class/thermal/thermal_zone$z/temp; [ -r $f ] && { tj=$(( $(cat $f)/1000 )); break; }; done
    R=/sys/bus/i2c/devices/1-0040/hwmon/hwmon3
    if [ -r $R/in1_input ]; then w=$(awk -v v=$(cat $R/in1_input) -v c=$(cat $R/curr1_input) "BEGIN{printf \"%.2f\", v*c/1e6}"); else w=n/a; fi
    g=$(cat /sys/devices/platform/gpu.0/load 2>/dev/null || echo n/a)
    al=0; for c in /sys/class/thermal/cooling_device*; do t=$(cat $c/type 2>/dev/null); case $t in *throttle-alert) [ "$(cat $c/cur_state)" != 0 ] && al=1;; esac; done
    echo "$tj $w $g $al"' 2>/dev/null
}

settle () { echo "  settling ${SETTLE_S}s..."; sleep "$SETTLE_S"; }

phase () {                      # $1 = phase label ; $2.. = nodes to load
  local label="$1"; shift
  local loaded=("$@")
  echo "=== phase $label : loading ${loaded[*]} ==="
  for n in "${loaded[@]}"; do load_start "$n" >/dev/null; done
  local t0=$(date +%s)
  while :; do
    local el=$(( $(date +%s) - t0 )) abort=0 line=""
    for n in "${NODES[@]}"; do
      read -r tj w g al <<<"$(probe "$n")"
      line+=$(printf "%s tj=%sC w=%s g=%s " "$n" "${tj:-?}" "${w:-?}" "${g:-?}")
      echo "$label $el $n ${tj:-} ${w:-} ${g:-} ${al:-}" >> "$OUT/samples.txt"
      [ "${al:-0}" = 1 ] && { echo "  >>> THROTTLE ALERT on $n"; abort=1; }
      [ "${tj:-0}" != "n/a" ] && [ "${tj:-0}" -ge "$ABORT_C" ] 2>/dev/null && { echo "  >>> ABORT: $n tj ${tj}C >= $ABORT_C"; abort=1; }
    done
    printf "  %4ss  %s\n" "$el" "$line"
    [ "$abort" = 1 ] && break
    [ "$el" -ge "$PHASE_S" ] && break
    sleep 15
  done
  for n in "${loaded[@]}"; do load_stop "$n" >/dev/null; done
  settle
}

echo "e6 carrier thermal coupling -> $OUT"
echo "baseline (all idle):"
for n in "${NODES[@]}"; do read -r tj w g al <<<"$(probe "$n")"; printf "  %-7s tj=%sC VDD_IN=%s gpu_load=%s\n" "$n" "$tj" "$w" "$g"; echo "idle 0 $n $tj $w $g $al" >> "$OUT/samples.txt"; done
settle
phase alone_node1  node1
phase alone_orinnx orinnx
phase alone_orin1  orin1
phase all_three    node1 orinnx orin1

python3 - "$OUT/samples.txt" <<'PY'
import sys, collections, statistics as st
rows = collections.defaultdict(list)
for L in open(sys.argv[1]):
    p = L.split()
    if len(p) < 7: continue
    ph, el, node, tj = p[0], int(p[1]), p[2], p[3]
    if tj == "n/a": continue
    rows[(ph, node)].append((el, float(tj), p[4]))
def plateau(k):                      # mean of the last third of the phase, so ramp is excluded
    v = sorted(rows.get(k, []))
    if not v: return None
    tail = v[max(0, int(len(v)*2/3)):]
    return st.mean(t for _, t, _ in tail), tail[-1][0]
print("\n=== plateau tj by phase (mean of final third) ===")
print("%-14s %8s %8s %8s" % ("phase", "node1", "orinnx", "orin1"))
for ph in ("idle", "alone_node1", "alone_orinnx", "alone_orin1", "all_three"):
    cells = []
    for n in ("node1", "orinnx", "orin1"):
        r = plateau((ph, n))
        cells.append("%.1f" % r[0] if r else "-")
    print("%-14s %8s %8s %8s" % (ph, *cells))
print("\n=== coupling: each module's tj when ALL loaded vs loaded ALONE ===")
for n, own in (("node1","alone_node1"), ("orinnx","alone_orinnx"), ("orin1","alone_orin1")):
    a, b = plateau((own, n)), plateau(("all_three", n))
    if a and b:
        print("  %-7s alone %.1fC -> all-three %.1fC   delta %+.1fC" % (n, a[0], b[0], b[0]-a[0]))
    else:
        print("  %-7s insufficient samples" % n)
print("\nA positive delta is heat this module receives from its neighbours through the shared")
print("enclosure -- a cost of the carrier's packaging, which 009 did not measure.")
PY
echo
echo "e6 done. Samples: $OUT/samples.txt"
