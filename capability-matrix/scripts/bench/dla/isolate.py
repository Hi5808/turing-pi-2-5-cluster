#!/usr/bin/env python3
"""Isolate why two DLA engines give 1.806x and not 2.0x.

Two competing mechanisms, distinguished by varying DLA-resident work per submit while
holding the submit count at exactly one (strict DLA, one fused ForeignNode):

  H1 FIXED PER-SUBMIT COST (completion IRQ / driver / sync, all of it serialized on one
     host1x syncpoint IRQ pinned to CPU0). Then the serialized share shrinks as the model
     gets deeper, and scaling must RISE toward 2.0x with depth.
  H2 PROPORTIONAL CONTENTION in a shared datapath. Then the serialized share is constant
     and scaling stays FLAT at ~1.806x regardless of depth.

Also samples what H1 would have to show: both DLA core clocks (to rule out DVFS), EMC,
the host1x syncpt IRQ rate, and CPU0's interrupt/softirq time.
"""
import json, os, re, subprocess, threading, time
from pathlib import Path

D = Path("/home/orinnx/dla-trt11")
TRT = D / "TensorRT-11.3.0.99"
TE = str(TRT / "bin" / "trtexec")
ENV = dict(os.environ, LD_LIBRARY_PATH=f"{TRT}/lib:/usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu")
HW = "/sys/bus/i2c/devices/1-0040/hwmon/hwmon3"
CLK = "/sys/kernel/debug/bpmp/debug/clk"
FMT = ["--inputIOFormats=chw16", "--outputIOFormats=chw16"]
DUR = 45
DEPTHS = [2, 8, 32]


def rail(i):
    try:
        return int(open(f"{HW}/in{i}_input").read()) * int(open(f"{HW}/curr{i}_input").read()) / 1e6
    except Exception:
        return None


def clk(name):
    try:
        return int(open(f"{CLK}/{name}/rate").read()) / 1e6
    except Exception:
        return None


def syncpt_irq():
    """Total host1x_syncpt interrupts, and how many landed on CPU0."""
    tot = cpu0 = 0
    for ln in open("/proc/interrupts"):
        if "host1x_syncpt" in ln:
            cols = ln.split()[1:9]
            v = [int(x) for x in cols if x.isdigit()]
            if v:
                tot += sum(v); cpu0 += v[0]
    return tot, cpu0


def cpu0_times():
    for ln in open("/proc/stat"):
        if ln.startswith("cpu0 "):
            f = [int(x) for x in ln.split()[1:]]
            # user nice system idle iowait irq softirq
            return {"busy": sum(f[:3]) + sum(f[5:7]), "irq": f[5], "softirq": f[6], "total": sum(f)}
    return None


class S(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.stop = threading.Event(); self.rows = []
    def run(self):
        while not self.stop.wait(1.0):
            self.rows.append({"vdd_in": rail(1), "dla0": clk("dla0_core"),
                              "dla1": clk("dla1_core"), "emc": clk("emc")})
    def stats(self):
        o = {"n": len(self.rows)}
        for k in ("vdd_in", "dla0", "dla1", "emc"):
            v = [r[k] for r in self.rows if r.get(k) is not None]
            if v:
                o[k] = round(sum(v)/len(v), 2); o[k+"_min"] = round(min(v), 2)
        return o


def build(depth, core):
    onnx = D / f"conv_d{depth}.onnx"
    plan = D / f"cd{depth}_dla{core}.plan"
    if plan.exists() and plan.stat().st_size > 1024:
        return str(plan)
    if plan.exists():
        plan.unlink()
    r = subprocess.run([TE, f"--onnx={onnx}", f"--saveEngine={plan}", "--skipInference",
                        f"--useDLACore={core}"] + FMT, env=ENV, capture_output=True, text=True)
    if not plan.exists() or plan.stat().st_size < 1024:
        print(f"BUILD FAILED d{depth} core{core}: " +
              " | ".join(re.findall(r"\[E\].*", r.stdout)[:2])[:220], flush=True)
        return None
    return str(plan)


def arm(label, specs):
    procs = []
    for plan, core in specs:
        lf = open(f"/tmp/iso_{label}_{core}.log", "w")
        procs.append((subprocess.Popen(
            [TE, f"--loadEngine={plan}", f"--duration={DUR}", "--avgRuns=100",
             "--warmUp=2000", f"--useDLACore={core}"], env=ENV, stdout=lf,
            stderr=subprocess.STDOUT), lf.name, core))
    time.sleep(5)
    i0, c0 = syncpt_irq(); t0 = cpu0_times(); w0 = time.time()
    s = S(); s.start()
    for p, _, _ in procs:
        p.wait()
    s.stop.set(); s.join(timeout=3)
    i1, c1 = syncpt_irq(); t1 = cpu0_times(); wall = time.time() - w0

    per = []
    for _, name, core in procs:
        t = open(name).read()
        m = re.search(r"Throughput: ([\d.]+) qps", t)
        l = re.search(r"Latency: min = [\d.]+ ms, max = [\d.]+ ms, mean = ([\d.]+) ms", t)
        per.append({"core": core, "qps": float(m.group(1)) if m and "PASSED" in t else 0.0,
                    "mean_ms": float(l.group(1)) if l else None})
    agg = sum(p["qps"] for p in per)
    dt = max(t1["total"] - t0["total"], 1)
    rec = {"arm": label, "n": len(specs), "agg_qps": round(agg, 2), "per": per,
           "syncpt_irq_per_s": round((i1 - i0) / wall, 1),
           "syncpt_irq_cpu0_share": round((c1 - c0) / max(i1 - i0, 1), 4),
           "irq_per_inference": round((i1 - i0) / max(agg * wall, 1), 3),
           "cpu0_busy_pct": round(100.0 * (t1["busy"] - t0["busy"]) / dt, 1),
           "cpu0_irq_pct": round(100.0 * (t1["irq"] - t0["irq"]) / dt, 2),
           "cpu0_softirq_pct": round(100.0 * (t1["softirq"] - t0["softirq"]) / dt, 2),
           "clocks_power": s.stats()}
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    print(json.dumps({"idle_w": rail(1), "dla0_mhz": clk("dla0_core"),
                      "dla1_mhz": clk("dla1_core"), "emc_mhz": clk("emc")}), flush=True)
    res = []
    for d in DEPTHS:
        p0, p1 = build(d, 0), build(d, 1)
        if not (p0 and p1):
            continue
        a1 = arm(f"d{d}_1", [(p0, 0)])
        a2 = arm(f"d{d}_2", [(p0, 0), (p1, 1)])
        sc = a2["agg_qps"] / a1["agg_qps"] if a1["agg_qps"] else 0
        # Amdahl: S = 2/(1+f) for 2 engines with serialized fraction f
        f = (2.0 / sc - 1.0) if sc else None
        print(json.dumps({"depth": d, "scaling_x": round(sc, 3),
                          "implied_serialized_fraction": round(f, 4) if f else None,
                          "ms_per_inference_1engine": a1["per"][0]["mean_ms"]}), flush=True)
        res += [a1, a2]
    Path(D / "isolate.json").write_text(json.dumps(res, indent=1))
    print("WROTE isolate.json", flush=True)
