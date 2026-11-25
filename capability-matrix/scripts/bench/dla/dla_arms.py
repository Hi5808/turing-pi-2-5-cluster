#!/usr/bin/env python3
"""Two arms the first DLA sweep could not answer.

A. INT8 on DLA -- fp16 is DLA's weak mode; INT8 is what it is built for.
   No calibration data, so dynamic ranges are dummies: THROUGHPUT is valid,
   ACCURACY IS NOT MEASURED and must not be claimed.

B. Contention -- DLA's real argument is running while the GPU is busy.
   Measures LLM alone, then LLM + both DLA cores, so we can see whether DLA
   throughput is actually free or whether it taxes the LLM through shared
   memory bandwidth / SOC.
"""
import json, os, re, subprocess, threading, time, urllib.request
from pathlib import Path

D = Path("/home/orinnx/dla-trt11")
TRT = D / "TensorRT-11.3.0.99"
TE = str(TRT / "bin" / "trtexec")
ONNX = str(D / "resnet18_fp16.onnx")
ENV = dict(os.environ, LD_LIBRARY_PATH=f"{TRT}/lib:/usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu")
HW = "/sys/bus/i2c/devices/1-0040/hwmon/hwmon3"
URL = "http://127.0.0.1:8101/completion"
DUR, NPRED, STREAMS = 60, 64, 4
RAILS = {"vdd_in": 1, "cpu_gpu": 2, "soc": 3}


def rails():
    o = {}
    for k, i in RAILS.items():
        try:
            o[k] = int(open(f"{HW}/in{i}_input").read()) * int(open(f"{HW}/curr{i}_input").read()) / 1e6
        except Exception:
            o[k] = None
    return o


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.stop = threading.Event(); self.rows = []
    def run(self):
        while not self.stop.wait(1.0):
            self.rows.append(rails())
    def stats(self):
        o = {"n": len(self.rows)}
        for k in RAILS:
            v = [r[k] for r in self.rows if r.get(k) is not None]
            if v:
                m = sum(v) / len(v)
                o[k] = round(m, 3); o[k + "_sd"] = round((sum((x-m)**2 for x in v)/len(v))**0.5, 3)
        return o


class LLM(threading.Thread):
    """Keeps STREAMS requests in flight; counts only completed tokens."""
    def __init__(self):
        super().__init__(daemon=True); self.stop = threading.Event()
        self.tok = 0; self.req = 0; self.lock = threading.Lock()
    def worker(self):
        body = json.dumps({"prompt": "Explain why memory bandwidth limits token generation.",
                           "n_predict": NPRED, "temperature": 0, "cache_prompt": False}).encode()
        while not self.stop.is_set():
            try:
                r = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(r, timeout=180) as f:
                    j = json.loads(f.read())
                n = (j.get("timings") or {}).get("predicted_n") or NPRED
                with self.lock:
                    self.tok += n; self.req += 1
            except Exception:
                time.sleep(0.5)
    def run(self):
        ts = [threading.Thread(target=self.worker, daemon=True) for _ in range(STREAMS)]
        [t.start() for t in ts]
        self.stop.wait()


def build(plan, extra):
    p = str(D / plan)
    if os.path.exists(p) and os.path.getsize(p) > 1024:      # size, not mere existence
        return p
    if os.path.exists(p):
        os.remove(p)
    r = subprocess.run([TE, f"--onnx={ONNX}", f"--saveEngine={p}", "--skipInference"] + extra,
                       env=ENV, capture_output=True, text=True)
    if not os.path.exists(p) or os.path.getsize(p) < 1024:
        print(f"BUILD FAILED {plan}: " + " | ".join(re.findall(r"\[E\].*", r.stdout)[:2])[:300], flush=True)
        return None
    return p


def dla_procs(specs):
    out = []
    for plan, core in specs:
        lf = open(f"/tmp/arm_{Path(plan).stem}_{core}.log", "w")
        out.append((subprocess.Popen(
            [TE, f"--loadEngine={plan}", f"--duration={DUR}", "--avgRuns=50",
             "--warmUp=2000", f"--useDLACore={core}"], env=ENV, stdout=lf, stderr=subprocess.STDOUT),
            lf.name, core))
    return out


def qps_of(path):
    t = open(path).read()
    m = re.search(r"Throughput: ([\d.]+) qps", t)
    l = re.search(r"Latency: min = [\d.]+ ms, max = [\d.]+ ms, mean = ([\d.]+) ms", t)
    if m and "PASSED" in t:
        return float(m.group(1)), (float(l.group(1)) if l else None), None
    e = re.findall(r"\[E\].*", t)[:1]
    return 0.0, None, (e[0][:160] if e else "no throughput")


def arm(label, dla_specs=(), llm=False):
    procs = dla_procs(dla_specs) if dla_specs else []
    gen = None
    if llm:
        gen = LLM(); gen.start(); time.sleep(8)          # let the LLM reach steady state
    else:
        time.sleep(5)
    s = Sampler(); s.start()
    t0 = time.time()
    if procs:
        for p, _, _ in procs:
            p.wait()
    else:
        time.sleep(DUR)
    wall = time.time() - t0
    s.stop.set(); s.join(timeout=3)
    rec = {"arm": label, "wall_s": round(wall, 1), "power": s.stats()}
    if procs:
        per = []
        for _, name, core in procs:
            q, ms, err = qps_of(name)
            d = {"dev": f"dla{core}", "qps": q, "mean_ms": ms}
            if err:
                d["error"] = err
            per.append(d)
        rec["dla"] = per
        rec["dla_agg_qps"] = round(sum(p["qps"] for p in per), 2)
    if gen:
        gen.stop.set()
        with gen.lock:
            rec["llm"] = {"tokens": gen.tok, "requests": gen.req,
                          "tok_s": round(gen.tok / wall, 2), "streams": STREAMS}
        time.sleep(5)
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    print(json.dumps({"idle": rails()}), flush=True)
    res = []

    # --- A: INT8 on DLA ---
    p8 = build("r18_dla0_int8.plan", ["--useDLACore=0", "--allowGPUFallback", "--int8", "--fp16"])
    p16_0 = build("r18_dla0.plan", ["--useDLACore=0", "--allowGPUFallback"])
    p16_1 = build("r18_dla1.plan", ["--useDLACore=1", "--allowGPUFallback"])
    if p8:
        res.append(arm("int8_dla0", [(p8, 0)]))
        res.append(arm("int8_dla0+dla1", [(p8, 0), (p8, 1)]))

    # --- B: contention ---
    res.append(arm("llm_only", llm=True))
    if p16_0 and p16_1:
        res.append(arm("llm+dla0+dla1_fp16", [(p16_0, 0), (p16_1, 1)], llm=True))
    if p8:
        res.append(arm("llm+dla0+dla1_int8", [(p8, 0), (p8, 1)], llm=True))

    Path(D / "dla_arms.json").write_text(json.dumps(res, indent=1))
    print("WROTE dla_arms.json", flush=True)
