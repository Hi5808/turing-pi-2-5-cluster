#!/usr/bin/env python3
"""DLA vs GPU on Orin NX: single-engine rates, then concurrency across DLA0+DLA1+GPU.

Engines are prebuilt and loaded, so build cost never lands in a power window.
Power is sampled from the INA3221 rails here, in-process, at 1 s.
"""
import json, os, re, subprocess, sys, threading, time
from pathlib import Path

D = Path("/home/orinnx/dla-trt11")
TRT = D / "TensorRT-11.3.0.99"
TREXEC = str(TRT / "bin" / "trtexec")
ONNX = str(D / "resnet18_fp16.onnx")
ENV = dict(os.environ, LD_LIBRARY_PATH=f"{TRT}/lib:/usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu")
HW = "/sys/bus/i2c/devices/1-0040/hwmon/hwmon3"
DUR = 60          # seconds per arm
RAILS = {"vdd_in": 1, "cpu_gpu": 2, "soc": 3}


def rails():
    out = {}
    for name, i in RAILS.items():
        try:
            mv = int(open(f"{HW}/in{i}_input").read())
            ma = int(open(f"{HW}/curr{i}_input").read())
            out[name] = mv * ma / 1e6
        except Exception:
            out[name] = None
    return out


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop = threading.Event()
        self.rows = []

    def run(self):
        while not self.stop.wait(1.0):
            self.rows.append(rails())

    def stats(self):
        o = {"n": len(self.rows)}
        for k in RAILS:
            v = [r[k] for r in self.rows if r.get(k) is not None]
            if v:
                m = sum(v) / len(v)
                o[k] = round(m, 3)
                o[k + "_sd"] = round((sum((x - m) ** 2 for x in v) / len(v)) ** 0.5, 3)
        return o


def build(core):
    """Prebuild a loadable engine. core=None -> GPU only."""
    plan = str(D / (f"r18_dla{core}.plan" if core is not None else "r18_gpu.plan"))
    # Size, not mere existence: a killed run leaves a 0-byte plan behind and
    # trtexec then fails with "read 0 out of 32 bytes" on load.
    if os.path.exists(plan) and os.path.getsize(plan) > 1024:
        return plan
    if os.path.exists(plan):
        os.remove(plan)
    cmd = [TREXEC, f"--onnx={ONNX}", f"--saveEngine={plan}", "--skipInference"]
    if core is not None:
        cmd += [f"--useDLACore={core}", "--allowGPUFallback"]
    r = subprocess.run(cmd, env=ENV, capture_output=True, text=True)
    if "PASSED" not in r.stdout:
        print(f"BUILD FAILED core={core}:\n{r.stdout[-1500:]}", flush=True)
        return None
    return plan


def arm(label, specs):
    """specs: list of (plan, core_or_None). Runs them concurrently for DUR."""
    procs = []
    logs = []
    for i, (plan, core) in enumerate(specs):
        cmd = [TREXEC, f"--loadEngine={plan}", f"--duration={DUR}", "--avgRuns=50", "--warmUp=2000"]
        if core is not None:
            cmd.append(f"--useDLACore={core}")
        lf = open(f"/tmp/dla_{label}_{i}.log", "w")
        logs.append((lf.name, core))
        procs.append(subprocess.Popen(cmd, env=ENV, stdout=lf, stderr=subprocess.STDOUT))

    time.sleep(5)                     # let all arms reach steady state
    s = Sampler(); s.start()
    for p in procs:
        p.wait()
    s.stop.set(); s.join(timeout=3)

    per, ok = [], 0
    for name, core in logs:
        txt = open(name).read()
        m = re.search(r"Throughput: ([\d.]+) qps", txt)
        lat = re.search(r"Latency: min = [\d.]+ ms, max = [\d.]+ ms, mean = ([\d.]+) ms", txt)
        if m and "PASSED" in txt:
            ok += 1
            per.append({"dev": f"dla{core}" if core is not None else "gpu",
                        "qps": float(m.group(1)),
                        "mean_ms": float(lat.group(1)) if lat else None})
        else:
            e = re.findall(r"\[E\].*", txt)[:2]
            per.append({"dev": f"dla{core}" if core is not None else "gpu",
                        "qps": 0.0, "error": (e[0][:160] if e else "no throughput line")})
    rec = {"arm": label, "procs": len(specs), "ok": ok,
           "agg_qps": round(sum(p["qps"] for p in per), 2), "per": per, "power": s.stats()}
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    print(json.dumps({"idle": rails()}), flush=True)
    p_gpu, p_d0, p_d1 = build(None), build(0), build(1)
    if not (p_gpu and p_d0 and p_d1):
        sys.exit("engine build failed; aborting")

    res = []
    res.append(arm("gpu_1",       [(p_gpu, None)]))
    res.append(arm("dla0_1",      [(p_d0, 0)]))
    res.append(arm("dla1_1",      [(p_d1, 1)]))
    res.append(arm("dla0+dla1",   [(p_d0, 0), (p_d1, 1)]))
    res.append(arm("gpu+dla0+dla1", [(p_gpu, None), (p_d0, 0), (p_d1, 1)]))
    Path("/home/orinnx/dla-trt11/dla_sweep.json").write_text(json.dumps(res, indent=1))
    print("WROTE /home/orinnx/dla-trt11/dla_sweep.json", flush=True)
