#!/bin/bash
# Run the whole experiment suite from a workstation over ssh, then prove every node is idle.
#
#   bash run_all.sh                 # preflight, all experiments, idle verify
#   bash run_all.sh --preflight     # just validate instrumentation and flags, run nothing
#   bash run_all.sh --idle          # just check/report idle state
#   bash run_all.sh e1 e3           # only the named experiments
#
# Experiments and where they run:
#   e1  node1   NPU per-submit serial cost (width sweep by core mask -> predicts concurrency)
#   e2  node1   big.LITTLE thread placement: what an A55 core costs a decode
#   e3  orin1   CPU vs GPU decode energy on one module (total-module VDD_IN only; see note)
#   e4  orinnx  cold-start phase decomposition (cold/warm cache x CPU/GPU)
#   e5  orinnx  thermal headroom under sustained load (bounded: aborts at 99 C or first throttle)
#
# Deliberate serialisation: e1 and e2 share node1, e4 and e5 share orinnx. Running two arms on one
# node at once contaminates both -- an NPU run was once launched twice over and had to be discarded.
# Nodes that do NOT share hardware are run in parallel.
#
# Read PITFALLS.md before changing any of these scripts. Each guard in them answers a specific
# wrong number this cluster has already produced.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="${OUT:-$HOME/suite-$STAMP}"
mkdir -p "$OUT"
echo "suite run $STAMP -> $OUT"

declare -A NODE_OF=( [e1]=node1 [e2]=node1 [e3]=orin1 [e4]=orinnx [e5]=orinnx )
declare -A FILE_OF=( [e1]=e1_npu_per_submit.py [e2]=e2_big_little.sh \
                     [e3]=e3_cpu_vs_gpu_energy.sh [e4]=e4_cold_start_phases.sh \
                     [e5]=e5_thermal_headroom.sh )
ALL=(e1 e2 e3 e4 e5)
NODES=(node1 orinnx orin1)

preflight () {
  local f=0
  for n in "${NODES[@]}"; do
    scp -q "$HERE/preflight.sh" "$n:/tmp/preflight.sh" || { echo "  cannot reach $n"; f=1; continue; }
    ssh "$n" "bash /tmp/preflight.sh $n" 2>&1 | tee "$OUT/preflight-$n.txt"
    grep -q "^PREFLIGHT PASS" "$OUT/preflight-$n.txt" || f=1
  done
  return $f
}

idle () {
  local f=0
  for n in "${NODES[@]}"; do
    scp -q "$HERE/idle_verify.sh" "$n:/tmp/idle_verify.sh" 2>/dev/null || { echo "  cannot reach $n"; f=1; continue; }
    ssh "$n" "bash /tmp/idle_verify.sh $n 180" 2>&1 | tee "$OUT/idle-$n.txt"
    grep -q "^IDLE:" "$OUT/idle-$n.txt" || f=1
  done
  return $f
}

run_one () {                      # $1 = experiment id
  local e="$1" n="${NODE_OF[$e]}" f="${FILE_OF[$e]}"
  echo "--- $e on $n ($f) ---"
  scp -q "$HERE/$f" "$n:/tmp/$f" || { echo "  scp failed"; return 1; }
  if [[ "$f" == *.py ]]; then
    # the NPU venv owns rknnlite; the system python cannot import it
    ssh "$n" "cd /mnt/nvme/npu-bench && .venv/bin/python /tmp/$f" > "$OUT/$e.txt" 2>&1
  else
    ssh "$n" "bash /tmp/$f" > "$OUT/$e.txt" 2>&1
  fi
  local rc=$?
  # strip the RKNN banner spam that otherwise buries e1's actual table
  grep -vE "^(I|W) RKNN:|^W Query dynamic range" "$OUT/$e.txt" | tail -24
  echo "  [$e exit $rc, full log $OUT/$e.txt]"
  return $rc
}

case "${1:-}" in
  --preflight) preflight; exit $? ;;
  --idle)      idle; exit $? ;;
esac

WANT=("${ALL[@]}")
[ $# -gt 0 ] && WANT=("$@")

echo "=== preflight ==="
if ! preflight; then
  echo
  echo "PREFLIGHT FAILED. Not running the suite: the numbers would not be trustworthy."
  echo "Pass --preflight to re-check after fixing, or run a single experiment explicitly if you"
  echo "know the failing check does not affect it."
  exit 1
fi

echo
echo "=== experiments ==="
# group by node so same-node work serialises and different nodes overlap
declare -A PIDS=()
for n in "${NODES[@]}"; do
  ( trap - EXIT          # pitfall 5: a subshell must never inherit an EXIT trap
    for e in "${WANT[@]}"; do
      [ "${NODE_OF[$e]}" = "$n" ] && run_one "$e"
    done ) > "$OUT/node-$n.txt" 2>&1 &
  PIDS[$n]=$!
done
for n in "${NODES[@]}"; do
  wait "${PIDS[$n]}" 2>/dev/null        # pitfall 5: explicit PIDs, never bare wait
  echo "--- $n finished ---"; cat "$OUT/node-$n.txt"
done

echo
echo "=== idle verification ==="
if idle; then
  echo
  echo "SUITE COMPLETE, all nodes idle. Logs in $OUT"
else
  echo
  echo "SUITE COMPLETE but a node is NOT IDLE. See the stragglers listed above and in $OUT/idle-*.txt."
  echo "Nothing was killed automatically: decide, then kill by PID (never by pattern -- pitfall 6)."
  exit 1
fi
