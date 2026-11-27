#!/bin/bash
# Idea 4 REV 2. Rev 1's phase regexes matched nothing and its fallback print had no argument, so it
# emitted a literal "%-16s". Real log format is M.SS.mmm.uuu and the real markers are below.
# NOTE this build logs NO "load_tensors: buffer size" line, so model load is ONE opaque block --
# splitting mmap from tensor setup from H2D copy would need strace/perf, not log lines. Stated.
set -u
MAIN=$$; NEW=~/llama.cpp-new/build/bin; MODEL=~/models/Qwen3-14B-Q4_K_M.gguf; PORT=8102; SRV=0
cleanup(){ [ "$$" != "$MAIN" ] && return 0; [ "$SRV" != 0 ] && kill -9 "$SRV" 2>/dev/null
  sudo systemctl start llama-server
  for i in $(seq 1 90); do [ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8101/health)" = 200 ] && break; sleep 2; done
  echo "RESTORED service=$(systemctl is-active llama-server) health=$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8101/health)"; }
trap cleanup EXIT
sudo systemctl stop llama-server; sleep 3
arm () {
  local lab="$1" flags="$2" cold="$3" rep="$4"
  [ "$cold" = 1 ] && { sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null; sleep 2; }
  LD_LIBRARY_PATH=$NEW $NEW/llama-server -m "$MODEL" --host 127.0.0.1 --port $PORT \
      -c 2048 --parallel 2 $flags > /tmp/p_${lab}_$rep.log 2>&1 &
  SRV=$!
  for i in $(seq 1 240); do [ "$(curl -s -o /dev/null -w %{http_code} http://127.0.0.1:$PORT/health)" = 200 ] && break; sleep 1; done
  kill -9 $SRV 2>/dev/null; SRV=0; sleep 2
}
for rep in 1 2; do
  arm gpu_cold "-ngl 99" 1 $rep; arm gpu_warm "-ngl 99" 0 $rep
  arm cpu_cold "-ngl 0 -dev none" 1 $rep; arm cpu_warm "-ngl 0 -dev none" 0 $rep
done
python3 - <<'PY'
import re, glob, statistics as st
def ts(line):                       # M.SS.mmm.uuu  -> seconds
    m = re.match(r"\s*(\d+)\.(\d+)\.(\d+)\.(\d+)\s", line)
    if not m: return None
    mi, s, ms, us = (int(x) for x in m.groups())
    return mi*60 + s + ms/1000.0 + us/1e6
MARKS = [("start",      r"llama_server: initializing"),
         ("open model", r"load_model: loading model"),
         ("threadpool", r"llama threadpool init"),
         ("slots/kv",   r"load_model: initializing, n_slots"),
         ("loaded",     r"server_run_i: model loaded"),
         ("listening",  r"server_on_li: listening")]
print("%-9s %-11s %8s %8s %8s %8s %8s" % ("arm","", "open","load","ctxinit","slots","total"))
for lab in ("gpu_cold","gpu_warm","cpu_cold","cpu_warm"):
    rows=[]
    for f in sorted(glob.glob("/tmp/p_%s_*.log" % lab)):
        L = open(f, errors="replace").read().splitlines()
        t = {}
        for name, pat in MARKS:
            for line in L:
                if re.search(pat, line):
                    v = ts(line)
                    if v is not None: t[name]=v; break
        if len(t) < 5: continue
        rows.append(( t["open model"]-t["start"],
                      t["threadpool"]-t["open model"],      # the opaque model-load block
                      t["slots/kv"]-t["threadpool"],
                      t["listening"]-t["slots/kv"],
                      t["listening"]-t["start"] ))
    if not rows: print("%-9s  no parsable reps" % lab); continue
    m = [st.mean(c) for c in zip(*rows)]
    print("%-9s %-11s %7.3f %8.3f %8.3f %8.3f %8.3f   (%d reps)"
          % (lab, "", m[0], m[1], m[2], m[3], m[4], len(rows)))
print("\n'load' is the opaque block between opening the file and threadpool init.")
PY
