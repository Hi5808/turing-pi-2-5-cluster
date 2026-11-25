import json, sys; sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm
A = json.load(open("/mnt/nvme/share/studio/research/ramp_joined.json"))
c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "ramp.py", "Whole-machine serving capacity: streams round-robined across both Orin "
  "endpoints, 1->32, with TTFT and inter-token latency per stream. First cluster-level (not single-node) "
  "measurement since 002. SLO: p95 ITL<=200ms and every stream >=5 tok/s.")
SW = "llama.cpp b10362-5-g704485942 / JetPack 7.2 L4T R39.2"
for a in A:
    n = a["streams"]; tag = "conc" if a["concurrent"] else "queued"
    for node, key in (("orinnx", "nx_w"), ("orin1", "nano_w")):
        if a.get(key):
            sm.record(c, rid, node, "node", f"ramp_{n}streams_mean_power", a[key], "W",
                      f"mean VDD_IN over the {n}-stream arm ({tag}), 1 Hz samples", sw_commit=SW,
                      reps=a.get("pw_samples"), params={"streams": n})
    sm.record(c, rid, "cluster", "llm", f"ramp_{n}streams_agg_tok_s", a["agg_tok_s"], "tok/s",
              f"aggregate across both endpoints, {tag}; slowest stream {a['per_stream_tok_s_min']} tok/s, "
              f"TTFT p95 {a['ttft_p95_ms']} ms, ITL p95 {a['itl_p95_ms']} ms, SLO={a['meets_slo']}",
              sw_commit=SW, params={"streams": n, "ttft_p95_ms": a["ttft_p95_ms"],
                                    "itl_p95_ms": a["itl_p95_ms"], "two_module_w": a["two_module_w"],
                                    "tok_per_j": a["tok_per_j"], "meets_slo": a["meets_slo"]})
def r(m, v, u, meth, **kw):
    sm.record(c, rid, "cluster", "llm", m, v, u, meth, sw_commit=SW, **kw)
r("serving_knee_streams", 4, "streams",
  "Largest concurrent load where p95 ITL<=200ms AND every stream >=5 tok/s. At 8 streams the slowest "
  "stream is 4.06 tok/s and ITL p95 231 ms, both outside SLO")
r("peak_agg_tok_s", 61.29, "tok/s", "at 32 streams, but TTFT p95 = 41526 ms -- unusable. Peak throughput "
  "overstates serviceable capacity by 8x in stream count and 38% in tok/s")
r("queueing_ttft_blowup", 41525.8, "ms", "TTFT p95 at 32 streams vs 220 ms at 1 stream (189x), while ITL "
  "p95 stays FLAT 417->418 ms past the 16-slot limit. Queueing moves the pain from streaming to starting, "
  "and aggregate tok/s is blind to it")
r("tok_per_joule_range", 1.536, "tok/J", "two-module; rises monotonically 0.229 -> 1.536 (6.7x) from 1 to "
  "32 streams as power FALLS 47.38 -> 39.87 W. P7 reproduced at cluster scale across two modules and two models")
r("slo_efficiency_penalty", 1.64, "x", "energy per token at the SLO-respecting knee (0.936 tok/J) vs at the "
  "efficiency optimum (1.536 tok/J). The efficiency optimum has 41 s TTFT, so every tok/J figure in this "
  "repo is measured at a load no product would ship")
r("heterogeneous_routing_unfairness", 2.42, "x", "Nano/4B plateaus at 43.4 tok/s vs NX/14B at 17.9 tok/s, so "
  "round-robin gives one user 7.1 tok/s and the next 17.0 from the same service. Confounded: different "
  "nodes AND different models")
sm.record(c, rid, "rk1-node1", "npu", "ramp_background_fps_ARTIFACT", 56.0, "fps",
  "ARTIFACT -- do not use as interference evidence. 3-stream NPU load averaged 56 fps (min 22) during the "
  "ramp vs 89-103 fps alone, because the load generator ran on node1 and its up-to-32 SSE threads competed "
  "for the same 8 RK3588 cores. Harness placement, not cluster contention.", sw_commit=SW)
sm.finish_run(c, rid); print("run", rid)
