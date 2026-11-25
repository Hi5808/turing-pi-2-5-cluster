# 005 — The RK3588 NPU on its design target: concurrency is the lever, not core count

**Platform:** node1, Turing RK1 (RK3588), 3-core 6 TOPS NPU, librknnrt 2.3.2, driver 0.9.7.
Kernel 6.1.0-1025-rockchip.
**Date:** 2026-11-19. **Status:** measured; cross-node comparison blocked (see Open).

## Abstract

[004](004-rk3588-npu-llm.md) ruled the NPU out as an LLM stage and left its actual design target
unmeasured: CNN inference. Measured here with the `yolov5s_relu_rk3588.rknn` model that had been
staged on node1 since September and never run.

Peak throughput is **98.6 fps** at 640x640, reached with **six concurrent single-core contexts**,
not by handing one context all three cores. The documented "use all 3 cores" path
(`NPU_CORE_0_1_2`) tops out at 58.4 fps — **1.7x** the single-core 36.5 fps, nowhere near 3x.
Three concurrent contexts beat it at 82.2 fps while *also* costing less per-stream latency growth
than expected. Pinning one context per core is worth nothing over letting the scheduler place
them (82.1 vs 82.2 fps).

This is the third engine on this cluster to show the same signature as the Orin NX's DLA in
[003](003-dla-transformer-offload.md): a fixed-function accelerator that does not scale linearly
with engine count, where aggregate throughput comes from concurrency rather than from widening a
single inference. It is also the same conclusion project [001](001-heterogeneous-llm-pipeline.md)
reached for LLM decode — batching is the throughput lever — arrived at on unrelated hardware and
a different workload.

## Measurements

YOLOv5s-relu, 640x640x3 uint8 input, int8 weights, static shape. `rknn-toolkit-lite2` 2.3.2,
300 iterations after 20 warm-up for the single-stream figures, 200 per stream for the
concurrency sweep.

### Core mask, single stream

| Core mask | mean | p50 | p99 | fps |
|---|---|---|---|---|
| `NPU_CORE_0` | 27.41 ms | 24.81 | 44.66 | 36.5 |
| `NPU_CORE_0_1_2` | 17.12 ms | 16.32 | 25.15 | 58.4 |

Three cores on one inference buy **1.60x**, not 3x. Core load during the 3-core run: Core0
52–58%, Core1 42–47%, Core2 42–47% — evenly spread and **not saturated**, so a single stream is
dispatch-bound, not compute-bound. That is what predicted the concurrency result below.

### Concurrency sweep

Each stream an independent `RKNNLite` context in its own thread.

| Config | streams | agg fps | mean lat | p99 lat |
|---|---|---|---|---|
| 1x `AUTO` | 1 | 33.6 | 27.35 ms | 37.91 |
| 2x `AUTO` | 2 | 57.5 | 30.58 ms | 41.56 |
| 3x `AUTO` | 3 | 82.2 | 32.81 ms | 62.11 |
| 3x pinned (core 0/1/2) | 3 | 82.1 | 31.45 ms | 49.70 |
| 3x `CORE_0_1_2` each | 3 | 73.8 | 35.16 ms | 49.00 |
| 4x `AUTO` | 4 | 89.1 | 39.42 ms | 68.64 |
| 6x `AUTO` | 6 | 98.6 / 94.0 | 54.74 / 56.11 ms | 89.79 |
| 8x `AUTO` | 8 | 97.1 | 72.57 ms | 126.12 |

Four things fall out:

1. **`AUTO` is one core per context.** 1x `AUTO` at 33.6 fps matches `CORE_0` at 36.5, not
   `CORE_0_1_2` at 58.4. The scheduler does not widen a lone inference across cores.
2. **Concurrency beats width.** 3 single-core contexts (82.2 fps) beat 1 three-core context
   (58.4 fps) by 1.41x, at 32.8 ms mean latency against 17.1 — throughput bought with latency,
   but not linearly.
3. **Pinning is pointless.** Explicit one-context-per-core placement lands within noise of
   `AUTO` (82.1 vs 82.2). Letting three contexts each request all three cores is actively
   *worse* (73.8 fps) — they contend.
4. **Ceiling is ~6 streams, ~95–98 fps.** 8 streams gains nothing (97.1) and costs 33% more
   mean latency and 40% more p99. The 6-stream figure varied 94.0–98.6 across two runs, so
   call the plateau 95 fps ±5%.

### What limits the plateau

Neither of the obvious candidates. At 8 streams, NPU core load reads Core0 77–79%, Core1 71–73%,
Core2 60–64% — headroom on every core. Host CPU at 6 streams is **79% idle** (14.4% us, 5.6% sy),
so node1's A76/A55 complex is not feeding the accelerator at its limit either. The ceiling is
internal to the NPU or its driver — most likely DRAM bandwidth or a per-submit cost the load
counter does not account for. Same unexplained-headroom pattern the DLA showed in 003, where the
reported utilisation also never reached 100% at saturation.

## What this says about node1

node1 has a real, idle, measurable vision accelerator: ~95 fps of YOLOv5s-class detection at
640x640, or ~36 fps per stream across 6 concurrent streams at ~55 ms latency. Unlike the LLM
case in 004, nothing here is an order of magnitude behind the Orins by construction — it was
simply never measured.

That is a capability, not yet a verdict. Whether it is *better* than giving the same job to an
Orin GPU is unanswered, and until it is answered this changes no placement decision. 004's
conclusion stands untouched: it concerned LLM inference, and nothing here bears on it.

## Open

- **The cross-node comparison is blocked, not negative.** No `yolov5s*.onnx` exists on either
  Orin, neither has `ultralytics` or `onnx` installed, and neither has internet (cluster net
  reaches node1 only). node1 has internet but both candidate ONNX sources —
  `ultralytics/yolov5` v7.0 release assets and `airockchip/rknn_model_zoo` — were unreachable
  from it on 2026-11-19. The `.rknn` cannot be converted back to ONNX. Unblocking it means
  exporting YOLOv5s to ONNX on an x86 box (pikoi has torch and internet), copying it to an Orin
  over the backplane, and building an FP16 TensorRT engine with `trtexec` (present at
  `/usr/bin/trtexec` on orinnx). Note the comparison would be int8-on-NPU against FP16-on-GPU
  unless the TRT engine is calibrated — a real caveat, since int8 is roughly a 2x advantage.
- The Mali-G610 remains unmeasured — a third idle engine on node1.
- Only one model was measured. YOLOv5s is one architecture at one resolution; nothing here
  generalises to larger backbones or to segmentation heads.
- Preprocessing was excluded. Inputs were pre-made uint8 arrays; a real pipeline pays for
  decode, resize and layout conversion, which on RK3588 would route through the RGA block —
  also unmeasured.

## Reproduction

```bash
# single stream, per core mask
cd /mnt/nvme/npu-bench && ./.venv/bin/python yolo_rk1.py

# concurrency sweep (N independent contexts, one thread each)
#   model: /mnt/nvme/npu-bench/vision/vision/yolo/yolov5s_relu_rk3588.rknn
#   core_mask=RKNNLite.NPU_CORE_AUTO per context, 200 iters after 10 warm-up
./.venv/bin/python /tmp/yolo_conc.py

# core load while a sweep runs
sudo cat /sys/kernel/debug/rknpu/load
```

The `W Query dynamic range failed ... RKNN_ERR_MODEL_INVALID` warning on every `load_rknn` is
expected for a static-shape model and is not an error.
