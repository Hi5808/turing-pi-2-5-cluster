# 001 — Heterogeneous pipeline-parallel LLM inference (proposal)

**Platform:** Turing Pi 2.5; node1 Turing RK1 (RK3588), node2 Jetson Orin NX 16GB,
node3 Jetson Orin Nano 8GB.
**Software stack:** as 000. llama.cpp with RPC backend; CUDA 13.2; TensorRT available on both Jetsons.
**Date:** 2026-11-17. **Status:** proposed, not yet run.

## Abstract

Proposes splitting a single language model across three structurally different accelerators in
one chassis — an Arm CPU/NPU node, an Orin NX with two DLA engines, and a DLA-less Orin Nano —
and assigning layers by *engine type* rather than by FLOPs alone. Pipeline parallelism is the
only distributed-inference strategy the measured interconnect permits, because layer-boundary
activations are on the order of 10 KB per token, making the design latency-bound rather than
bandwidth-bound.

## Rationale

From the baseline in 000: tensor parallelism needs roughly 10 GB/s of all-reduce bandwidth and
0.119 GB/s is available. Pipeline parallelism moves one activation tensor per layer boundary per
token — for a 14B-class model with hidden size 5120 at 2 bytes, about 10 KB. At 119 MB/s that is
far below the point where bandwidth matters; per-hop latency and stage balance dominate.

This also means combined memory, not per-node memory, sets the model ceiling: ~55 GB of RAM
exists across the chassis, and no single node holds more than 31 GB.

## Design constraints

1. **node1 cannot be a pipeline stage.** Pipeline throughput equals the slowest stage, and the
   A76 cores are far slower at inference than either Orin GPU. Putting node1 in the pipeline
   drags the whole pipeline to CPU speed. node1 orchestrates, holds the tokenizer and the
   request queue, and keeps nothing hot.
2. **The compute pipeline is therefore node2 -> node3**, which is also the one path that does not
   consume node1's uplink. Roughly 24 GB of GPU-addressable memory across the two — enough for a
   32B-class model at Q4.
3. **Stages must be balanced by measured throughput, not layer count.** node2 is roughly 2.3x
   node3 in INT8 TOPS, so an even layer split would idle node2 waiting on node3.
4. **The DLA asymmetry is the novel variable.** node2 has two DLA engines that are essentially
   unused for transformer work; node3 has none. If some layers can be offloaded to DLA on node2,
   its effective capacity rises without touching its GPU, changing the optimal split.

## Open questions

- Can any transformer layer run usefully on DLA? Known limits: fixed shapes, 4D tensors,
  fp16/int8, and no attention support. Feed-forward projections may be expressible as
  convolutions; attention almost certainly is not. A prior result on this hardware showed DLA
  works only via a side-by-side TensorRT 11.3 install, with ResNet-18 at 139 qps / 7.2 ms.
  **Being answered in project 003** — see [research/jetson-orin/003](../jetson-orin/003-dla-transformer-offload.md).
- Does llama.cpp's RPC backend tolerate heterogeneous backends per stage (CUDA on one, CUDA+DLA
  or CPU on another), or does it assume uniform backends?
- What is the per-hop latency floor over the backplane, and how many tokens of pipelining are
  needed to hide it?
- Does the RK3588 NPU have any role once a userland exists? Currently the driver is present with
  no userland, so this is unexplored.

## Method

1. Baseline single-node decode throughput for a model that fits on node2 alone, then on node3
   alone, establishing the per-node tok/s used for stage weighting.
2. Measure per-hop RPC latency and activation sizes directly, confirming the ~10 KB estimate.
3. Run a two-stage split (node2 -> node3) with layer assignment proportional to measured
   throughput; compare against single-node baselines on a model that fits in one node, to
   isolate pipeline overhead from capacity gain.
4. Scale to a model that does **not** fit on any single node — the actual point of the exercise.
5. Attempt DLA offload of a feed-forward block on node2 and re-derive the optimal split.

## Success criteria

Running a model no single node can hold, at a decode rate better than node1's CPU inference
(~2 tok/s for 14B Q4, previously measured), with the stage split derived from measurement rather
than guessed. A negative result on DLA offload is still a result and will be recorded as such.
