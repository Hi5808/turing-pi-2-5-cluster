#!/bin/bash
# e7: can the A55 cluster's capability be recovered as a separate PROCESS?
#
# e2 established that putting an A55 core in a llama.cpp thread set costs ~26-32% of decode, and
# that four little cores cost no more than one -- a barrier effect, since work is split evenly per
# thread and the slowest thread gates every token. But the A55 cluster is not weak: four of them
# alone decode 12.39 tok/s.
#
# So the capability exists and threads cannot reach it. Process-level concurrency has no shared
# barrier, so it should. This tests that directly:
#
#   A  one process, 4x A76                    e2 measured 46.81
#   B  one process, 4x A55                    e2 measured 12.39
#   C  BOTH concurrently, disjointly pinned   <-- the question
#   D  one process, all 8 threads             e2 measured 34.41
#
# If C ~= A+B (~59.2) the little cluster is fully recoverable and the right policy on this chip is
# one process per cluster, never one process spanning both. If C ~= A the clusters contend for
# something outside the thread barrier -- memory bandwidth is the obvious candidate, and D already
# shows 8 threads lose to 4, so a bandwidth wall would show up here as C failing to beat A.
#
# CPU-ONLY needs BOTH -ngl 0 AND -dev none on this build (PITFALLS.md #2).
set -u
cd /mnt/nvme/llama-rpc-build/bin || exit 1
M=/mnt/nvme/share/models/Qwen3-0.6B-Q4_K_M.gguf
CPUONLY="-ngl 0 -dev none"
D=/tmp/e7; mkdir -p $D; rm -f $D/*
REPS=5
NPRED=96

# A function CANNOT hand back a background PID: `p=$(run ...)` runs the body in a command-
# substitution SUBSHELL, so the job becomes a grandchild, the parent's `wait "$p"` fails with "not
# a child", and the script races ahead. The first version of this script did exactly that and
# orphaned ~20 concurrent llama-completion processes on an 8-core box (loadavg 22.69) while
# reporting FAIL for every arm. Launch in the CURRENT shell and capture $! directly.
go () {         # label, taskset, threads, rep  -- sets LASTPID in the caller's shell
  local lab="$1" cl="$2" th="$3" rep="$4"
  taskset -c "$cl" env LD_LIBRARY_PATH=. ./llama-completion -m "$M" $CPUONLY \
    -p "Explain in detail why memory bandwidth limits token generation. $lab" \
    -n $NPRED --ignore-eos --no-warmup -st --no-display-prompt -t "$th" \
    > /dev/null 2> "$D/${lab}_r${rep}.err" &
  LASTPID=$!
}

for rep in $(seq 1 $REPS); do
  go A_a76only 4,5,6,7 4 $rep;            wait "$LASTPID" 2>/dev/null
  go B_a55only 0,1,2,3 4 $rep;            wait "$LASTPID" 2>/dev/null
  go C_a76     4,5,6,7 4 $rep; c1=$LASTPID
  go C_a55     0,1,2,3 4 $rep; c2=$LASTPID
  wait "$c1" 2>/dev/null; wait "$c2" 2>/dev/null   # explicit pids only (PITFALLS.md #5)
  go D_all8    0,1,2,3,4,5,6,7 8 $rep;    wait "$LASTPID" 2>/dev/null
done

python3 - "$D" "$REPS" <<'PY'
import glob, re, sys, statistics as st
D, REPS = sys.argv[1], int(sys.argv[2])
DEC = re.compile(r"eval time =\s+[\d.]+ ms /\s+\d+ runs.*?([\d.]+) tokens per second", re.S)
def rate(lab, rep):
    f = "%s/%s_r%d.err" % (D, lab, rep)
    try: m = DEC.search(open(f, errors="replace").read())
    except FileNotFoundError: return None
    return float(m.group(1)) if m else None
def agg(labs):
    out = []
    for r in range(1, REPS+1):
        v = [rate(l, r) for l in labs]
        if all(x is not None for x in v): out.append(sum(v))
    return (st.mean(out), st.stdev(out) if len(out) > 1 else 0.0, len(out), out) if out else None
rows = [("A  1 proc, 4x A76",       ["A_a76only"]),
        ("B  1 proc, 4x A55",       ["B_a55only"]),
        ("C  2 procs, A76 + A55",   ["C_a76", "C_a55"]),
        ("D  1 proc, all 8 threads",["D_all8"])]
res = {}
print("%-26s %10s %8s  %s" % ("arm", "decode", "sd", "per-rep"))
for name, labs in rows:
    a = agg(labs)
    if not a: print("%-26s %10s" % (name, "FAIL")); continue
    res[name[0]] = a[0]
    print("%-26s %10.2f %8.2f  %s" % (name, a[0], a[1], [round(x,1) for x in a[3]]))
# per-process split inside arm C, to see which cluster gave up throughput
cs = [(rate("C_a76", r), rate("C_a55", r)) for r in range(1, REPS+1)]
cs = [(a, b) for a, b in cs if a and b]
if cs:
    print("\n  inside C:  A76 proc %.2f tok/s   A55 proc %.2f tok/s"
          % (st.mean(a for a, _ in cs), st.mean(b for _, b in cs)))
if {"A","B","C","D"} <= set(res):
    ideal = res["A"] + res["B"]
    print("\n  A+B (if fully separable) = %.2f" % ideal)
    print("  C measured               = %.2f   -> %.1f%% of separable, %.3fx over A alone"
          % (res["C"], 100*res["C"]/ideal, res["C"]/res["A"]))
    print("  D (threads span both)    = %.2f   -> %.3fx of A: the e2 penalty, reproduced"
          % (res["D"], res["D"]/res["A"]))
    if res["C"] > res["A"]:
        print("\n  VERDICT: the A55 cluster IS recoverable as a separate process "
              "(+%.2f tok/s, +%.1f%% over the big cluster alone)."
              % (res["C"]-res["A"], 100*(res["C"]-res["A"])/res["A"]))
    else:
        print("\n  VERDICT: process separation does NOT recover it -- the clusters contend "
              "outside the thread barrier (bandwidth is the candidate).")
PY
