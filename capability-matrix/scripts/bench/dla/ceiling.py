#!/usr/bin/env python3
"""Is the DLA concurrency ceiling bandwidth, or per-inference GPU-fallback sync?

conv_pure (strict DLA, 0 GPU layers) vs conv_fallback (identical + 1 GPU elementwise).
Same weights, same arithmetic, same 0.59 MB of weights -- so neither is bandwidth-bound
and the ONLY difference is one DLA->GPU->DLA round trip per inference.

Prediction if the ceiling is fallback sync: pure scales ~2x across the two engines,
fallback does not. If both stall, the ceiling is neither bandwidth nor fallback.
"""
import json, os, re, subprocess, threading, time
from pathlib import Path

D = Path("/home/orinnx/dla-trt11")
TRT = D / "TensorRT-11.3.0.99"
TE = str(TRT / "bin" / "trtexec")
ENV = dict(os.environ, LD_LIBRARY_PATH=f"{TRT}/lib:/usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu")
HW = "/sys/bus/i2c/devices/1-0040/hwmon/hwmon3"
FMT = ["--inputIOFormats=chw16", "--outputIOFormats=chw16"]
DUR = 60
WEIGHTS_MB, ACT_MB = 0.590, 0.401


def rails():
    o = {}
    for k, i in {"vdd_in": 1, "cpu_gpu": 2, "soc": 3}.items():
        try:
            o[k] = int(open(f"{HW}/in{i}_input").read()) * int(open(f"{HW}/curr{i}_input").read()) / 1e6
        except Exception:
            o[k] = None
    return o


class S(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.stop = threading.Event(); self.rows = []
    def run(self):
        while not self.stop.wait(1.0):
            self.rows.append(rails())
    def stats(self):
        o = {"n": len(self.rows)}
        for k in ("vdd_in", "cpu_gpu", "soc"):
            v = [r[k] for r in self.rows if r.get(k) is not None]
            if v:
                m = sum(v)/len(v); o[k] = round(m, 3)
                o[k+"_sd"] = round((sum((x-m)**2 for x in v)/len(v))**0.5, 3)
        return o


def build(onnx, plan, core, fallback):
    p = str(D / plan)
    if os.path.exists(p) and os.path.getsize(p) > 1024:
        return p
    if os.path.exists(p):
        os.remove(p)
    cmd = [TE, f"--onnx={D/onnx}", f"--saveEngine={p}", "--skipInference",
           f"--useDLACore={core}"] + FMT + (["--allowGPUFallback"] if fallback else [])
    r = subprocess.run(cmd, env=ENV, capture_output=True, text=True)
    if not os.path.exists(p) or os.path.getsize(p) < 1024:
        print(f"BUILD FAILED {plan}: " + " | ".join(re.findall(r"\[E\].*", r.stdout)[:2])[:250], flush=True)
        return None
    return p


def arm(label, specs):
    procs = []
    for plan, core in specs:
        lf = open(f"/tmp/ceil_{label}_{core}.log", "w")
        procs.append((subprocess.Popen([TE, f"--loadEngine={plan}", f"--duration={DUR}",
                                        "--avgRuns=100", "--warmUp=2000", f"--useDLACore={core}"],
                                       env=ENV, stdout=lf, stderr=subprocess.STDOUT), lf.name, core))
    time.sleep(5)
    s = S(); s.start()
    for p, _, _ in procs:
        p.wait()
    s.stop.set(); s.join(timeout=3)
    per = []
    for _, name, core in procs:
        t = open(name).read()
        m = re.search(r"Throughput: ([\d.]+) qps", t)
        l = re.search(r"Latency: min = [\d.]+ ms, max = [\d.]+ ms, mean = ([\d.]+) ms", t)
        d = {"core": core, "qps": float(m.group(1)) if m and "PASSED" in t else 0.0,
             "mean_ms": float(l.group(1)) if l else None}
        if d["qps"] == 0.0:
            e = re.findall(r"\[E\].*", t)[:1]
            d["error"] = e[0][:160] if e else "no throughput"
        per.append(d)
    agg = sum(p["qps"] for p in per)
    rec = {"arm": label, "n": len(specs), "agg_qps": round(agg, 2), "per": per,
           "weights_gb_s": round(agg * WEIGHTS_MB / 1000.0, 3),
           "weights_plus_act_gb_s": round(agg * (WEIGHTS_MB + ACT_MB * 9) / 1000.0, 3),
           "power": s.stats()}
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    print(json.dumps({"idle": rails(), "note": "peak DRAM 102.4 GB/s"}), flush=True)
    pp0 = build("conv_pure.onnx", "cp_dla0.plan", 0, False)
    pp1 = build("conv_pure.onnx", "cp_dla1.plan", 1, False)
    pf0 = build("conv_fallback.onnx", "cf_dla0.plan", 0, True)
    pf1 = build("conv_fallback.onnx", "cf_dla1.plan", 1, True)
    res = []
    if pp0: res.append(arm("pure_1", [(pp0, 0)]))
    if pp0 and pp1: res.append(arm("pure_2", [(pp0, 0), (pp1, 1)]))
    if pf0: res.append(arm("fallback_1", [(pf0, 0)]))
    if pf0 and pf1: res.append(arm("fallback_2", [(pf0, 0), (pf1, 1)]))
    for r in res:
        base = next((x for x in res if x["arm"] == r["arm"].split("_")[0] + "_1"), None)
        if base and r["n"] == 2:
            print(f"SCALING {r['arm']}: {r['agg_qps']/base['agg_qps']:.3f}x", flush=True)
    Path(D / "ceiling.json").write_text(json.dumps(res, indent=1))
    print("WROTE ceiling.json", flush=True)
