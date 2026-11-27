#!/usr/bin/env python3
"""Parse a suite experiment's output and record it into selfmodel.db.

Run on node1, which owns the database:

    python3 record.py <e1|e2|e3|e4|e5|e7> <output-file> [--dry-run]

Why this exists: the five experiments of 2026-11-26 were run, reported in conversation, and then
very nearly lost -- their only copies were /tmp logs on the nodes, which get cleared. Matrix rows
were written by hand afterwards from memory of the numbers. That is exactly the failure the
database is supposed to prevent, so recording is now part of the suite rather than an afterthought
somebody has to remember.

`run_all.sh` calls this automatically for every experiment it runs. Nothing here invents values:
each parser reads the experiment's own printed table, and an experiment whose output cannot be
parsed records NOTHING and exits non-zero rather than filing a plausible-looking guess.
"""
import re
import sys
import os

sys.path.insert(0, "/mnt/nvme/share/studio/research")

EXP = sys.argv[1] if len(sys.argv) > 1 else ""
PATH = sys.argv[2] if len(sys.argv) > 2 else ""
DRY = "--dry-run" in sys.argv

if not EXP or not PATH:
    sys.exit(__doc__)
if not os.path.exists(PATH):
    sys.exit("no such output file: %s" % PATH)
TXT = open(PATH, errors="replace").read()

META = {
    "e1": ("node1",  "npu",     "NPU per-submit serial cost: width sweep by core mask, then an "
                                "out-of-sample prediction of the concurrency curve"),
    "e2": ("node1",  "cpu-a76", "big.LITTLE thread placement: what an A55 core costs a decode"),
    "e3": ("orin1",  "gpu",     "CPU vs GPU decode energy on one Orin module, same binary and model"),
    "e4": ("orinnx", "gpu",     "cold-start phase decomposition, cold/warm page cache x CPU/GPU"),
    "e5": ("orinnx", "gpu",     "thermal headroom under sustained load (bounded)"),
    "e7": ("node1",  "cpu-a76", "is the A55 cluster recoverable as a separate process?"),
}
if EXP not in META:
    sys.exit("unknown experiment %r (have %s)" % (EXP, ", ".join(sorted(META))))
NODE, ENGINE, NOTE = META[EXP]

F = r"([-\d.]+)"
out = []          # (metric, value, unit, method, kwargs)


def e1():
    for n, v, sd in re.findall(r"n=(\d)\s+" + F + r" fps\s+sd " + F, TXT):
        out.append(("npu_decode_width_%score" % n, float(v), "fps",
                    "1 RKNNLite context on %s core(s) via core_mask, 200 iters after 20 warmup" % n,
                    {"stddev": float(sd), "reps": 5, "params": {"cores": int(n), "contexts": 1}}))
    for k, v, sd in re.findall(r"k=(\d)\s+agg\s+" + F + r" fps\s+sd " + F, TXT):
        out.append(("npu_concurrency_%sctx" % k, float(v), "fps",
                    "%s RKNNLite contexts, one core each, started together" % k,
                    {"stddev": float(sd), "reps": 5, "params": {"contexts": int(k)}}))
    m = re.search(r"S = " + F + r" s \(" + F + r" ms serial\)\s+W = " + F + r" s \(" + F
                  + r" ms parallel\)\s+R2 = " + F, TXT)
    if m:
        out.append(("npu_per_submit_serial_cost", float(m.group(1)), "s",
                    "least squares t(n)=S+W/n on the WIDTH sweep only",
                    {"reps": 5, "params": {"W_s": float(m.group(3)), "r2": float(m.group(5))}}))
    for k, pred, meas, err in re.findall(r"k=(\d)\s+predicted\s+" + F + r"\s+measured\s+" + F
                                         + r"\s+err\s+" + F, TXT):
        out.append(("npu_oos_pred_err_k%s" % k, float(err), "%",
                    "out-of-sample: fit from width predicts %s vs %s measured" % (pred, meas),
                    {"reps": 5}))


def e2():
    for lab, v, sd in re.findall(r"^(\S+)\s+" + F + r"\s+" + F + r"\s+\[", TXT, re.M):
        if not re.match(r"\d*x?A(76|55)", lab):
            continue
        out.append(("decode_placement_%s" % lab, float(v), "tok/s",
                    "Qwen3-0.6B Q4_K_M CPU-only (-ngl 0 -dev none), taskset %s" % lab,
                    {"stddev": float(sd), "reps": 3, "model": "Qwen3-0.6B-Q4_K_M",
                     "params": {"placement": lab}}))
    m = re.search(r"THE PENALTY: 4xA76 alone " + F + r" -> all 8 cores " + F + r"\s+= " + F, TXT)
    if m:
        out.append(("a55_thread_penalty_pct", float(m.group(3)), "%",
                    "4xA76 %s tok/s vs all 8 cores %s tok/s" % (m.group(1), m.group(2)),
                    {"reps": 3, "model": "Qwen3-0.6B-Q4_K_M"}))


def e3():
    for lab, k, agg, w, tj, net in re.findall(
            r"(\w+_k\d)\s+k=(\d)\s+agg\s+" + F + r" tok/s\s+VDD_IN\s+" + F
            + r" W\s+" + F + r" tok/J\s+net-of-idle\s+" + F, TXT):
        out.append(("decode_%s" % lab, float(agg), "tok/s",
                    "same binary 074f1f3, same model, -c 2048 --parallel 4, %s streams" % k,
                    {"params": {"streams": int(k), "vdd_in_w": float(w),
                                "tok_per_j": float(tj), "tok_per_j_net_idle": float(net)}}))
    m = re.search(r"idle VDD_IN=" + F, TXT)
    if m:
        out.append(("idle_vdd_in", float(m.group(1)), "W",
                    "10 samples at 1 Hz, managed service stopped", {}))


def e4():
    for lab, op, ld, ci, sl, tot in re.findall(
            r"^(\w+_(?:cold|warm))\s+\S*\s+" + F + r"\s+" + F + r"\s+" + F + r"\s+" + F
            + r"\s+" + F, TXT, re.M):
        out.append(("coldstart_%s" % lab, float(tot), "s",
                    "phases from llama-server's own timestamps (open/load/ctxinit/slots)",
                    {"reps": 2, "model": "Qwen3-14B-Q4_K_M",
                     "params": {"open_s": float(op), "load_block_s": float(ld),
                                "ctxinit_s": float(ci), "slots_s": float(sl)}}))


def e5():
    m = re.search(r"VERDICT: max tj " + F + r"C \| min GPU clock " + F
                  + r" MHz \| min CPU clock " + F + r" MHz \| alert fired: (\S+)", TXT)
    if m:
        out.append(("sustained_load_max_tj", float(m.group(1)), "C",
                    "2 concurrent streams, bounded run, 5 s sampling",
                    {"params": {"min_gpu_mhz": float(m.group(2)),
                                "min_cpu_mhz": float(m.group(3)),
                                "throttle_alert": m.group(4)}}))


def e7():
    for lab, v, sd in re.findall(r"^([A-D])\s+[^\n]*?\s+" + F + r"\s+" + F + r"\s+\[", TXT, re.M):
        out.append(("a55_worker_arm_%s" % lab, float(v), "tok/s",
                    "arm %s; A=4xA76, B=4xA55, C=both as separate processes, D=8 threads" % lab,
                    {"stddev": float(sd), "reps": 5, "model": "Qwen3-0.6B-Q4_K_M"}))
    m = re.search(r"C measured\s+= " + F + r"\s+-> " + F + r"% of separable, " + F + r"x over A", TXT)
    if m:
        out.append(("a55_process_recovery_pct", float(m.group(2)), "%",
                    "arm C as a fraction of A+B (fully separable); %sx over the big cluster alone"
                    % m.group(3), {"reps": 5}))


{"e1": e1, "e2": e2, "e3": e3, "e4": e4, "e5": e5, "e7": e7}[EXP]()

if not out:
    sys.exit("REFUSING TO RECORD: parsed nothing from %s. Either the experiment failed or its "
             "output format changed -- fix the parser rather than letting the run go unrecorded."
             % PATH)

print("%s: parsed %d measurements from %s" % (EXP, len(out), PATH))
for metric, value, unit, method, kw in out:
    print("   %-34s %12.4f %-6s" % (metric, value, unit))
if DRY:
    print("(dry run, nothing written)")
    sys.exit(0)

import selfmodel as sm
c = sm.connect()
sm.init(c)
rid = sm.start_run(c, "suite/%s" % EXP, NOTE)
for metric, value, unit, method, kw in out:
    sm.record(c, rid, NODE, ENGINE, metric, value, unit, method, **kw)
sm.finish_run(c, rid)
print("recorded run %s (%d measurements, node=%s engine=%s)" % (rid, len(out), NODE, ENGINE))
