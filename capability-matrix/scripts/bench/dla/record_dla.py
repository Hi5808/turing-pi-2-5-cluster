#!/usr/bin/env python3
import json, sys
sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm

SW = "TensorRT 11.3.0.99 b99 / JetPack 7.2 L4T R39.2"
MODEL = "resnet18 b1 (fp16 onnx; INT8 = symmetric QDQ, random calibration)"
N = "orinnx"

c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "dla_sweep.py + dla_arms.py",
                   "DLA on Orin NX: GPU vs 1 vs 2 engines, fp16 vs INT8, plus LLM contention. "
                   "Module quiet (llama-server resident, GPU load 0). Answers 003 section 8 open question 3.")

def r(metric, val, unit, method, **kw):
    sm.record(c, rid, N, kw.pop("engine", "dla"), metric, val, unit, method,
              model=MODEL, sw_commit=SW, **kw)

# --- single-engine and scaling, quiet module ---
r("resnet18_qps_gpu_fp16", 1360.3, "qps", "trtexec 60s, GPU, prebuilt plan", engine="gpu", params={"mean_ms": 0.734, "vdd_in_w": 22.465})
r("resnet18_qps_dla0_fp16", 126.695, "qps", "trtexec 60s, DLA core 0, allowGPUFallback", params={"mean_ms": 7.892, "vdd_in_w": 15.052})
r("resnet18_qps_dla1_fp16", 126.502, "qps", "trtexec 60s, DLA core 1, allowGPUFallback", params={"mean_ms": 7.904, "vdd_in_w": 15.057})
r("resnet18_qps_dla_both_fp16", 202.886, "qps", "aggregate, 2 concurrent trtexec, one per DLA core", params={"per_engine": 101.443, "vdd_in_w": 19.113, "scaling_x": 1.601})
r("resnet18_qps_dla0_int8", 244.566, "qps", "trtexec 60s, DLA core 0, symmetric QDQ INT8", params={"mean_ms": 4.088, "vdd_in_w": 13.401})
r("resnet18_qps_dla_both_int8", 252.877, "qps", "aggregate, 2 concurrent, INT8", params={"per_engine": 126.44, "vdd_in_w": 15.062, "scaling_x": 1.034})

# --- efficiency ---
r("resnet18_inf_per_j_gpu_fp16", 60.55, "inf/J", "qps / mean VDD_IN, whole module", engine="gpu")
r("resnet18_inf_per_j_dla0_fp16", 8.42, "inf/J", "qps / mean VDD_IN, whole module")
r("resnet18_inf_per_j_dla_both_fp16", 10.62, "inf/J", "qps / mean VDD_IN; +26% vs 1 engine -- P7 holds")
r("resnet18_inf_per_j_dla0_int8", 18.25, "inf/J", "qps / mean VDD_IN")
r("resnet18_inf_per_j_dla_both_int8", 16.79, "inf/J", "qps / mean VDD_IN; -8% vs 1 engine -- P7 REVERSES past the ceiling")

# --- contention against the real LLM ---
r("llm_tok_s_alone", 17.07, "tok/s", "llama-server Qwen3-14B Q4_K_M, 4 streams, n_predict 64, 60s; "
  "granularity is 1 completed request ~= 1.07 tok/s (+-6%)", engine="gpu",
  params={"vdd_in_w": 25.676, "requests": 16})
r("llm_tok_s_with_dla_fp16", 9.39, "tok/s", "same, both DLA engines co-running fp16; -45%", engine="gpu",
  params={"vdd_in_w": 24.989, "dla_agg_qps": 79.64})
r("llm_tok_s_with_dla_int8", 9.35, "tok/s", "same, both DLA engines co-running INT8; -45%", engine="gpu",
  params={"vdd_in_w": 24.953, "dla_agg_qps": 47.95})
r("dla_qps_under_llm_fp16", 79.64, "qps", "both engines fp16 while GPU serves the LLM; -61% vs quiet")
r("dla_qps_under_llm_int8", 47.95, "qps", "both engines INT8 while GPU serves the LLM; -81% vs quiet. "
  "Worse than fp16 despite being 1.93x faster alone -- more QDQ work left on the GPU (inferred)")
r("heterogeneous_additivity_fp16", 0.943, "fraction", "LLM 9.39/17.07 + DLA 79.64/202.89; <1 means sub-additive")
r("heterogeneous_additivity_int8", 0.738, "fraction", "LLM 9.35/17.07 + DLA 47.95/252.88; <1 means sub-additive")

# --- the discarded contaminated run, kept so nobody rediscovers it ---
sm.record(c, rid, N, "dla", "resnet18_qps_dla0_fp16_VOID", 43.45, "qps",
          "VOID -- do not use. Measured while the live dashboard drove llama-server and the GPU sat at "
          "993/1000, so the engine's GPU-fallback layers queued behind the LLM. Reads 2.9x low against "
          "the correct 126.70. Caught by the power rail (28.56 W 'idle'), not by the throughput number.",
          model=MODEL, sw_commit=SW)

sm.finish_run(c, rid)
print("run", rid)
