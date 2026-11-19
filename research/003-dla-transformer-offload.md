# 003 — Can the DLA run transformer layers? A measured capability map and verdict

**Platform:** Turing Pi 2.5; node2 Jetson Orin NX 16GB (2 DLA engines), JetPack 7.2 / L4T R39.2 /
CUDA 13.2.
**Toolchains:** system TensorRT **10.16.2.10**; side-by-side TensorRT **11.3.0.99** (build tag
`[b99]`) in `~/dla-trt11/TensorRT-11.3.0.99`.
**Model dimensions:** Qwen3-32B, read from the GGUF header: 64 layers, hidden 5120, FFN 25600,
64 heads, 8 KV heads, head_dim 128.
**Date:** 2026-11-18. **Status:** complete. **Verdict: do not build a ggml DLA backend for decode.**

## Abstract

Project 001 deferred one question: *can any transformer layer run usefully on the Orin NX's two
otherwise-idle DLA engines?* This project answers it in two parts. **Capability:** far more of a
transformer block is DLA-resident than either the project-001 prediction or NVIDIA's published
layer table suggests — RMSNorm, Softmax and the full attention core (QK^T → softmax → PV) all
compile with GPU fallback *disabled*. The only rejections are convolutions wider than 8192
channels, a dimension limit that 4-way tiling removes. **Performance:** the DLA is nevertheless
**2.1× to 33.7× slower than the GPU** on every component at decode shapes. The capability
question has a surprisingly positive answer and the engineering question has a clearly negative
one.

## 1. Correction to project 001

Project 001 recorded that `/dev/nvhost-nvdla*` was "absent" on node2 and that DLA "may not even
open today". **That was a bad glob.** The device nodes are `/dev/nvhost-ctrl-nvdla0` and
`nvdla1` — with a `-ctrl-` infix. The driver is loaded, both engines probe at boot, and firmware
is present. Corrected in commit 9443941.

Re-verified directly: ResNet-18 on DLA core 0, **7.83 ms mean / 127.7 qps** over 30 iterations,
matching the 7.2 ms recorded in September.

## 2. Which toolchain has DLA — not the one the docs name

NVIDIA's current documentation (read 2026-11-18) states:

> "DLA is not supported in TensorRT 11.3.0 or in TensorRT 11.3.1 for DriveOS."
> "TensorRT 10.7 was the last release that supported DLA."
> "DLA was unavailable in TensorRT 11.0 through 11.3."
> "TensorRT 11.4.1 restores DLA support, on Jetson AGX Orin only, and only under NVIDIA
> JetPack 7.2.2 or later."

**Our measurements contradict this for our build.** TensorRT `11.3.0.99` build `[b99]` builds and
runs DLA engines on an **Orin NX** — a module not named in the restoration note, under a
TensorRT version documented as having no DLA at all. The `.99` patch and `b99` build tag indicate
a special build rather than the public 11.3.0 release.

The engine is also version-locked to it. Loading the September DLA engine under system
TensorRT 10.16 fails:

```
Serialization assertion stdVersionRead == kSERIALIZATION_VERSION failed.
Version tag does not match. Note: Current Version: 240, Serialized Engine Version: 244
```

**Consequence:** DLA on this node depends on a single non-public toolchain directory. That is a
sustainability risk for any product built on it, and on its own is close to disqualifying.

Also logged, from trtexec itself: *"CUDA graphs and DLA offloading are not simultaneously
supported."*

## 3. Method

Seven ONNX graphs decompose one Qwen3 block, at **decode shapes** (batch 1, sequence length 1),
with Linear expressed as 1×1 convolution because DLA requires 4D tensors. Plus four probes:
`conv_8192` / `conv_8193` to bracket the dimension cap, and `ffn_{gate,down}_tile` at 6400
channels to test tiling.

Capability was tested with **`--allowGPUFallback` omitted**, so a successful build means every
layer is genuinely DLA-resident rather than silently relocated to the GPU.

### Three methodology traps, all of which produced false verdicts first

1. **`--fp16` does not exist in TensorRT 11.** Builder flags were removed: *"The following builder
   flags were removed in TensorRT 11.0 and no longer exist: `BuilderFlag::kFP16`, `kINT8`…"*
   Networks are strongly typed; precision comes from the graph, so the **ONNX must be exported in
   fp16** (`.half()` on modules and inputs). NVIDIA's recommended route is ModelOpt AutoCast with
   `--target_dla --low_precision_type fp16`.
2. **The format spec is layout-only.** `fp16:chw16` is TensorRT 10 syntax and errors with
   `Invalid TensorFormat`. TensorRT 11 takes `chw16`, `dla_linear`, `dla_hwc4` — no type prefix.
3. **With `--useDLACore`, every failure mode returns exit=1** — argument parsing, ONNX parse
   failure, and genuine DLA rejection are indistinguishable by exit code. Three separate harness
   faults in this project (wrong binary path, missing `onnx` module, wrong format syntax) each
   produced a uniform wall of exit=1 that looked exactly like a capability result. **Never read an
   exit code as a verdict here; read the error text.**

## 4. Capability map (strict DLA, no GPU fallback)

| Component | Shape | `chw16` | `dla_linear` | DLA-resident |
|---|---|---|---|---|
| `rmsnorm` | 1×5120×1×1 | exit=0 | exit=0 | **yes** |
| `softmax` | 1×64×1×128 | exit=0 | exit=0 | **yes** |
| `attn_core` (QK^T→softmax→PV) | 64 heads, S=128 | exit=0 | — | **yes** |
| `qkv_q` | 5120→8192 | exit=0 | exit=0 | **yes** |
| `ffn_gate` | 5120→**25600** | exit=1 | — | no |
| `ffn_down` | **25600**→5120 | exit=1 | — | no |
| `swiglu` (full FFN) | 5120→25600→5120 | exit=1 | — | no |
| `conv_8192` | 5120→**8192** | exit=0 | exit=0 | **yes** |
| `conv_8193` | 5120→**8193** | exit=1 | exit=1 | no |
| `ffn_gate_tile` | 5120→6400 | exit=0 | exit=0 | **yes** |
| `ffn_down_tile` | 6400→5120 | exit=0 | exit=0 | **yes** |

Rejections are specific and consistent:

```
Layer '/c/Conv' is not supported on DLA but GPU fallback is not enabled.
checkDLASupport: [8] DLA validation failed for layer: /c/Conv
```

### Finding: the 8192 limit is exact, and it is the only blocker

`conv_8192` passes and `conv_8193` fails — a one-channel bracket, measured rather than taken on
trust from the documented *"maximum supported size for non-batch dimensions is 8192"*. Qwen3-32B's
FFN is 25600 wide, 3.1× over. **Both 6400-channel tiles are DLA-resident, so the FFN is reachable
as 4 slices.** The blocker is a dimension limit with a known workaround, not an unsupported
operation.

### Finding: attention compiles on DLA, contradicting the published layer table

The documented DLA layer table lists Reduce as supporting *"MAX operation type"* only — which
should reject RMSNorm's mean — and lists **no general MatMul**, which should reject `attn_core`.
Both compile DLA-resident on the b99 build. One logical RMSNorm produced **8** DLA entries in the
exported layer info, so TensorRT is likely rewriting these into DLA-supported primitives. Either
way, the widely repeated claim that "transformers don't run on DLA" is **false at the
compile level** on this hardware.

The project-001 prediction — projections and SwiGLU pass, norm/softmax/attention fail — was
**wrong in both directions**, and is recorded here as a falsified prediction rather than quietly
amended.

## 5. Performance: DLA vs GPU at identical decode shapes

`trtexec`, 200 iterations, median GPU-compute time. DLA runs used `chw16` I/O.

| Component | DLA (ms) | GPU (ms) | DLA penalty |
|---|---|---|---|
| `rmsnorm` | 0.1025 | 0.00781 | **13.1× slower** |
| `softmax` | 0.0981 | 0.00800 | **12.3× slower** |
| `attn_core` | 1.8451 | 0.05475 | **33.7× slower** |
| `qkv_q` | 1.8247 | 0.8428 | **2.17× slower** |
| `conv_8192` | 1.7738 | 0.8428 | **2.10× slower** |
| `ffn_gate_tile` | 1.4313 | 0.6569 | **2.18× slower** |
| `ffn_down_tile` | 1.4008 | 0.6646 | **2.11× slower** |

**The DLA loses every single component.** Two distinct regimes:

- **Large projections: ~2.1×.** Consistent across all four convolutions — this is the DLA's
  honest throughput deficit against an Ampere GPU on work it is designed for.
- **Small ops: 12–34×.** `rmsnorm`, `softmax` and `attn_core` are dominated by fixed per-engine
  overhead, not arithmetic. `attn_core` is the worst case at 33.7×, which matters because
  attention is the part that cannot be made larger at batch 1.

The convolution floor of ~1.4–1.8 ms regardless of width (6400 vs 8192 channels differ by 24% in
work but 27% in time) indicates these are near the engine's latency floor rather than its
bandwidth limit — exactly the wrong regime for decode, which is a sequence of tiny
batch-1 operations.

## 6. Verdict

**Do not build a ggml DLA backend for decode.** Four independent reasons, any one sufficient:

1. **It is slower everywhere.** 2.1× on its best case, 33.7× on attention. There is no component
   where offload wins, so there is no partial-offload strategy either.
2. **No dynamic shapes.** *"DLA does not support dynamic dimensions"* — min/max/opt must be equal.
   Decode would need a separately built engine per sequence length, or padding to a fixed maximum
   and paying for the waste every token.
3. **The FFN needs 4-way tiling** to clear the 8192 cap, adding concat/slice boundaries that the
   docs note *"require GPU fallback"* — reintroducing the GPU round-trips the offload was meant
   to avoid.
4. **The toolchain is a single non-public build.** DLA is absent from public TensorRT 11.0–11.4.0,
   and 11.4.1 restores it for AGX Orin under JetPack ≥7.2.2 — not the Orin NX. Our engines
   deserialize only under `11.3.0.99`.

### What the DLA *is* worth on this cluster

**Corrected 2026-11-18.** An earlier revision of this section claimed the DLA's value was
**concurrency, not acceleration** — a second compute stream running CNN work while the GPU serves
LLM decode. That claim was asserted, not measured. It has now been measured, and it is **wrong**:
see §6b. The GPU alone already consumes 97% of the module's memory bandwidth, so there is no
headroom for a second engine, and adding the DLA *reduces* total throughput.

This reframes project 001's fourth design constraint. The DLA does not raise node2's effective
capacity for LLM work and should **not** change the pipeline split. It is a parallel engine for a
*different* model, which is what NVIDIA's own positioning says — and what our numbers confirm for
a reason more specific than "transformers don't run on DLA": they do compile, they are simply
slower.

## 7. Reproduction

Artifacts on node2 in `/home/orinnx/dla-transformer/`: `export.py` (fp16 component graphs),
`export2.py` (tiling and cap probes), `run003.sh`–`run006.sh`, per-component logs
`s3.*`/`a5.*`/`b5.*`/`c5.*`/`d6.*`/`g6.*`, exported layer info `li.*.json`.

```bash
# strict capability test — a pass means genuinely DLA-resident
LD_LIBRARY_PATH=$T/lib $T/bin/trtexec --onnx=COMPONENT.onnx --useDLACore=0 \
  --skipInference --inputIOFormats=chw16 --outputIOFormats=chw16
# benchmark
LD_LIBRARY_PATH=$T/lib $T/bin/trtexec --onnx=COMPONENT.onnx --useDLACore=0 --iterations=200 \
  --inputIOFormats=chw16 --outputIOFormats=chw16     # drop --useDLACore for the GPU number
```

`T=/home/orinnx/dla-trt11/TensorRT-11.3.0.99`. The venv at `~/dla-trt11/venv` holds torch 2.14.0
and onnx 1.23.0; system pip is PEP 668-blocked.

## 6b. Concurrency and prefill, measured (2026-11-18)

Both of this document's original open questions are now answered, and both answers went against
the expectation written down here first.

### Concurrency is not additive — the GPU is already bandwidth-saturated

`qkv_q` (5120→8192 GEMM-as-1×1-conv), identical engine on each device, 20 s per scenario,
throughput in inferences/s. Each inference reads 5120×8192×2 = 83.89 MB of fp16 weights, which
converts qps directly to DRAM bandwidth. Orin NX 16GB peak is 102.4 GB/s.

| Scenario | Total qps | GB/s | % of peak |
|---|---|---|---|
| **GPU alone** | **1182.5** | 99.2 | **97%** |
| DLA0 alone | 592.4 | 49.7 | 49% |
| DLA0 + GPU | 1025.5 | 86.0 | 84% |
| DLA0 + DLA1 | 539.8 | 45.3 | 44% |
| DLA0 + DLA1 + GPU | 1046.1 | 87.8 | 86% |

Three findings:

1. **The GPU alone saturates memory bandwidth at 97% of peak.** This workload is bandwidth-bound,
   not compute-bound, so there is nothing left for a second engine to use.
2. **DLA + GPU is 13% *slower* than the GPU alone** (1025.5 vs 1182.5 qps). The DLA does not add
   capacity; it takes bandwidth and adds contention.
3. **The two DLA engines do not scale with each other** — 539.8 qps together vs 592.4 for one.
   Two engines are slower in aggregate than one.

No combination beats the GPU by itself. The "second compute stream" framing is therefore
unsupported *for any bandwidth-bound workload*, which includes LLM decode and, by the ResNet-18
weight-reuse argument, most CNN inference at batch 1 as well.

### At prefill shapes the DLA mostly will not compile

Components re-exported with the token count in the W spatial dim (decode used W=1), strict DLA,
`chw16`, 200 iterations:

| Component | Tokens | DLA | GPU qps | Result |
|---|---|---|---|---|
| qkv_q | 128 / 512 | **compile error 8** | 973.0 / 336.8 | DLA rejected |
| ffn_gate_tile | 128 / 512 | **compile error 8** | 1143.8 / 357.2 | DLA rejected |
| ffn_down_tile | 128 / 512 | **compile error 8** | 1210.1 / 424.4 | DLA rejected |
| rmsnorm | 128 / 512 | **compile error 8** | 2479.3 / 611.2 | DLA rejected |
| softmax | 128 | 840.9 qps | 5116.1 | GPU 6.1× |
| softmax | 512 | 54.6 qps | 431.0 | GPU 7.9× |
| attn_core | 128 | 94.0 qps | 2933.7 | GPU 31.2× |

The failure is `Error Code 2: DLA Compile exception` / `DLA Compilation failed ... error code 8`
on `ForeignNode[/c/Conv]` — the *same* convolutions that compile successfully at W=1. So this is a
shape rejection, not a layer-support one, and it is not the 8192 cap (all dims are ≤ 6400).

This reverses the guess recorded in §8: prefill was expected to be DLA's best case because of its
throughput orientation. Instead it is where the DLA stops working altogether.

`p512_attn_core` was still compiling when this was written and is not included.

### Net effect on the verdict

The verdict — **do not build a ggml DLA backend** — is unchanged and now rests on firmer ground.
But two of the reasons originally given for it were wrong: concurrency was presented as the
DLA's redeeming use and is not available, and prefill was dismissed as unable to change the
verdict when in fact it strengthens it. The conclusion was right for reasons that were not.

## 8. Open

- Does `kADJUST_FOR_DLA` (available, left `Disabled` in all runs) change any rejection?
- What exactly does DLA compile error 8 object to in a 1×1 conv at W>1? The limit is undocumented
  and is not the 8192 non-batch cap.
- Is any *compute*-bound workload (high arithmetic intensity, small weights) additive across DLA
  and GPU? Every workload measured here was bandwidth-bound, so the concurrency result should not
  be over-generalized to e.g. large-batch CNN inference with heavy weight reuse.
- `p512_attn_core`: build was still running.
