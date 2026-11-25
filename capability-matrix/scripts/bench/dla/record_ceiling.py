#!/usr/bin/env python3
import sys
sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm

SW = "TensorRT 11.3.0.99 b99 / JetPack 7.2 L4T R39.2"
N = "orinnx"
c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "ceiling.py",
    "Isolates what limits DLA concurrency. conv_pure (strict DLA, 0 GPU layers) vs conv_fallback "
    "(identical + 1 GPU elementwise). Refutes both the bandwidth explanation (003 6b) and the "
    "~253 qps shared-ceiling claim (003 6c, same day).")

def r(metric, val, unit, method, **kw):
    sm.record(c, rid, N, "dla", metric, val, unit, method, sw_commit=SW, **kw)

r("conv_pure_qps_1engine", 627.734, "qps", "strict DLA, zero GPU layers, chw16 IO, 60s",
  model="conv_pure (8x Conv3x3 64->64 + ReLU, fp16)", params={"mean_ms": 1.592, "vdd_in_w": 15.209})
r("conv_pure_qps_2engines", 1133.80, "qps", "aggregate, one trtexec per DLA core",
  model="conv_pure", params={"per_engine": 566.902, "mean_ms": 1.763, "vdd_in_w": 20.274, "scaling_x": 1.806})
r("conv_fallback_qps_1engine", 535.52, "qps", "identical model + ONE GPU elementwise add",
  model="conv_fallback", params={"mean_ms": 1.866, "vdd_in_w": 15.496})
r("conv_fallback_qps_2engines", 871.73, "qps", "aggregate",
  model="conv_fallback", params={"per_engine": 435.865, "mean_ms": 2.293, "vdd_in_w": 19.640, "scaling_x": 1.628})

r("dla_scaling_pure", 1.806, "x", "2 engines / 1 engine, zero GPU layers")
r("dla_scaling_one_gpu_op", 1.628, "x", "2 engines / 1 engine, exactly one GPU op")
r("cost_of_one_gpu_fallback_op", -14.7, "percent",
  "627.73 -> 535.52 qps single engine from adding one elementwise add; +0.274 ms latency")
r("peak_dram_utilisation_fastest_arm", 4.6, "percent",
  "4.76 GB/s of 102.4 GB/s peak at 1133.8 qps, counting weights + all 9 activations. "
  "Refutes bandwidth as the limit at these rates")
r("conv_pure_inf_per_j_1engine", 41.27, "inf/J", "qps / mean VDD_IN, whole module")
r("conv_pure_inf_per_j_2engines", 55.93, "inf/J", "+35% vs 1 engine -- P7 holds where concurrency buys throughput")
r("conv_fallback_inf_per_j_1engine", 34.56, "inf/J", "qps / mean VDD_IN")
r("conv_fallback_inf_per_j_2engines", 44.38, "inf/J", "+28% vs 1 engine")

# Retraction, recorded as data so it cannot be lost.
sm.record(c, rid, N, "dla", "shared_qps_ceiling_RETRACTED", 252.88, "qps",
    "RETRACTED -- do not use. Claimed in research/jetson-orin/003 6c (commit 2672bf1, same day) as a "
    "shared ~253 qps hardware ceiling for the two DLA engines. conv_pure reaches 1133.80 qps on the "
    "same two engines, 4.5x higher, at 4.6% of DRAM peak. 252.88 was a property of that ResNet-18 "
    "INT8 engine's fragmentation (16 DLA nodes, 70 Q / 110 DQ), not of the hardware. The engine's own "
    "1.034x scaling stands; only the named cause was wrong.",
    sw_commit=SW, model="resnet18 INT8 QDQ")

sm.finish_run(c, rid)
print("run", rid)
