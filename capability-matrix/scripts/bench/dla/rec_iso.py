import sys; sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm
c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "isolate.py", "Isolates the 1.806x two-engine DLA deficit by varying DLA-resident "
  "work per submit at a constant submit count (strict DLA, 1 ForeignNode). Rules out DVFS, CPU/IRQ and bandwidth.")
def r(m, v, u, meth, **kw): sm.record(c, rid, "orinnx", "dla", m, v, u, meth,
    sw_commit="TensorRT 11.3.0.99 b99 / JetPack 7.2 L4T R39.2", **kw)
for d, q1, q2, sc, f, ms1, add in [(2,2242.90,3120.11,1.391,0.4377,0.4445,0.195),
                                   (8,627.55,1143.16,1.822,0.0979,1.5921,0.156),
                                   (32,163.28,313.04,1.917,0.0432,6.1231,0.264)]:
    r(f"conv_d{d}_qps_1engine", q1, "qps", f"strict DLA, {d}x(Conv+ReLU), zero GPU layers, 45s",
      model=f"conv_d{d}", params={"mean_ms": ms1})
    r(f"conv_d{d}_qps_2engines", q2, "qps", "aggregate, one trtexec per core",
      model=f"conv_d{d}", params={"scaling_x": sc, "serialized_fraction": f, "latency_adder_ms": add})
r("dla_2engine_fixed_serialized_cost", 0.205, "ms",
  "Mean per-inference latency added by activating the 2nd engine: 0.195/0.156/0.264 ms at "
  "single-engine latencies of 0.44/1.59/6.12 ms. Constant to +-0.05 ms (22%) across a 13.8x range "
  "of inference time => FIXED per-submit cost, not proportional contention",
  params={"sd_ms": 0.045, "n_depths": 3})
r("dla_dvfs_ruled_out", 1228.8, "MHz",
  "Both dla0_core and dla1_core held 1228.8 MHz (= max_rate) in every arm, mean == min; EMC 3199 MHz "
  "throughout. Power mode MAXN_SUPER. DVFS cannot explain the deficit")
r("dla_cpu_irq_ruled_out", 20.7, "percent",
  "Worst-case CPU0 busy across all arms; CPU0 irq <=2.27%, softirq <=0.14%, and the host1x_syncpt "
  "counter showed ZERO delta during every arm, so DLA completion does not use that IRQ. The CPU0 "
  "IRQ-affinity hypothesis is REFUTED")
sm.finish_run(c, rid); print("run", rid)
