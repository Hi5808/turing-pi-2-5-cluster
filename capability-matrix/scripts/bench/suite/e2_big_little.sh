#!/bin/bash
# Research idea 2: quantify the big.LITTLE penalty on RK3588 for llama.cpp decode.
# Today's incidental finding was that ADDING the 4x A55 cores makes a single wide inference SLOWER
# (35.07 tok/s on 8 mixed threads vs 43.70 on 4x A76 alone). No published llama.cpp result
# quantifies this; the closest is a turingpi.com write-up that attributes a 4-thread win to
# cluster locality without measuring the breakdown, and a TVM result on different silicon where
# the little cores HELPED -- so it is worth measuring per placement rather than asserting a rule.
# cpu0-3 = Cortex-A55 @1800 (part 0xd05), cpu4-7 = Cortex-A76 @2256 (part 0xd0b).
# CPU-ONLY requires BOTH -ngl 0 and -dev none on this build, or every layer goes to Mali.
cd /mnt/nvme/llama-rpc-build/bin || exit 1
M=/mnt/nvme/share/models/Qwen3-0.6B-Q4_K_M.gguf
D=/tmp/biglittle; mkdir -p $D; rm -f $D/*
REPS=3
arm () {            # label, taskset list, nthreads
  local lab="$1" cl="$2" th="$3" rep="$4"
  taskset -c "$cl" env LD_LIBRARY_PATH=. ./llama-completion -m "$M" -ngl 0 -dev none \
    -p "Explain in detail why memory bandwidth limits token generation." \
    -n 96 --ignore-eos --no-warmup -st --no-display-prompt -t "$th" \
    > /dev/null 2> "$D/${lab}_r${rep}.err"
}
# label            cores        threads   what it isolates
ARMS=(
  "1xA76|4|1"            "2xA76|4,5|2"          "3xA76|4,5,6|3"        "4xA76|4,5,6,7|4"
  "1xA55|0|1"            "2xA55|0,1|2"          "4xA55|0,1,2,3|4"
  "4xA76+1xA55|0,4,5,6,7|5"   "4xA76+2xA55|0,1,4,5,6,7|6"
  "4xA76+4xA55|0,1,2,3,4,5,6,7|8"
  "2xA76+2xA55|0,1,4,5|4"
)
for rep in $(seq 1 $REPS); do
  for a in "${ARMS[@]}"; do
    IFS='|' read -r lab cl th <<< "$a"
    arm "$lab" "$cl" "$th" "$rep"
  done
done
python3 - "$D" "$REPS" <<'PY'
import glob, re, sys, statistics as st
D, REPS = sys.argv[1], int(sys.argv[2])
DEC = re.compile(r"eval time =\s+[\d.]+ ms /\s+\d+ runs.*?([\d.]+) tokens per second", re.S)
labels = ["1xA76","2xA76","3xA76","4xA76","1xA55","2xA55","4xA55",
          "4xA76+1xA55","4xA76+2xA55","4xA76+4xA55","2xA76+2xA55"]
res = {}
print("%-14s %10s %8s  %s" % ("placement", "decode", "sd", "reps"))
for lab in labels:
    v = []
    for r in range(1, REPS+1):
        f = "%s/%s_r%d.err" % (D, lab, r)
        try: m = DEC.search(open(f, errors="replace").read())
        except FileNotFoundError: continue
        if m: v.append(float(m.group(1)))
    if not v: print("%-14s %10s" % (lab, "FAIL")); continue
    res[lab] = st.mean(v)
    print("%-14s %10.2f %8.2f  %s" % (lab, res[lab], st.stdev(v) if len(v)>1 else 0.0,
          [round(x,1) for x in v]))
print()
if "4xA76" in res and "4xA76+4xA55" in res:
    a, b = res["4xA76"], res["4xA76+4xA55"]
    print("THE PENALTY: 4xA76 alone %.2f -> all 8 cores %.2f  = %+.1f%% (%.3fx)"
          % (a, b, 100*(b-a)/a, b/a))
for k in ("4xA76+1xA55","4xA76+2xA55","4xA76+4xA55"):
    if k in res and "4xA76" in res:
        print("  adding %-9s %+6.1f%%" % (k.split("+")[1], 100*(res[k]-res["4xA76"])/res["4xA76"]))
if "4xA55" in res and "4xA76" in res:
    print("\ncluster ratio at equal core count: A76/A55 = %.2fx" % (res["4xA76"]/res["4xA55"]))
PY
