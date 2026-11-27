#!/usr/bin/env python3
"""Research idea 1: is the per-submit serial cost present on the RK3588 NPU too?

007 3b isolated it on the Orin DLA by varying DLA-resident DEPTH at a fixed submit count. That
needs a depth knob, and this box cannot build one: only yolov5s_relu_rk3588.rknn exists and the
installed rknn-toolkit-LITE2 is runtime-only (the converter is x86-only).

So use the method from research/010 instead -- WIDTH. The NPU exposes core masks, so one inference
can be given 1, 2 or 3 cores. Fit t(n) = S + W/n on that width sweep, then PREDICT the concurrency
curve the fit never saw (k independent contexts, one core each, same 3-core budget):

    t(n) = S + W/n                 one inference, n cores
    T(k) = k / (S + W/(3/k))       k contexts at 3/k cores each

If S <= 0 the model predicts no concurrency gain, which 005's 82.2 vs 58.4 fps contradicts -- so
the fit is falsifiable.
"""
import sys, time, json, statistics as st
sys.path.insert(0, "/mnt/nvme/npu-bench")
import numpy as np
from rknnlite.api import RKNNLite
import threading

M = "/mnt/nvme/npu-bench/vision/vision/yolo/yolov5s_relu_rk3588.rknn"
X = np.random.randint(0, 255, (1, 640, 640, 3), dtype=np.uint8)  # NHWC: the model is static 4-dim
WARM, ITERS, REPS = 20, 200, 5
MASKS = {1: RKNNLite.NPU_CORE_0, 2: RKNNLite.NPU_CORE_0_1, 3: RKNNLite.NPU_CORE_0_1_2}
PER_CORE = [RKNNLite.NPU_CORE_0, RKNNLite.NPU_CORE_1, RKNNLite.NPU_CORE_2]

def one(mask, iters=ITERS):
    r = RKNNLite()
    assert r.load_rknn(M) == 0
    assert r.init_runtime(core_mask=mask) == 0
    probe = r.inference(inputs=[X])
    if probe is None:
        r.release()
        raise RuntimeError("inference returned None -- bad input shape or mask; refusing to time it")
    for _ in range(WARM): r.inference(inputs=[X])
    t0 = time.perf_counter()
    for _ in range(iters):
        if r.inference(inputs=[X]) is None:
            r.release(); raise RuntimeError("inference failed mid-run")
    el = time.perf_counter() - t0
    r.release()
    return iters / el                      # fps for this context

def width(n):
    return one(MASKS[n])

def concurrent(k):
    """k contexts, each pinned to its own core, started together; aggregate fps."""
    out = [0.0] * k
    def wk(i):
        out[i] = one(PER_CORE[i], iters=ITERS)
    ths = [threading.Thread(target=wk, args=(i,)) for i in range(k)]
    t0 = time.perf_counter()
    for t in ths: t.start()
    for t in ths: t.join()
    return sum(out), time.perf_counter() - t0

W, C = {}, {}
print("=== width sweep: 1 inference, n cores ===", flush=True)
for n in (1, 2, 3):
    v = [width(n) for _ in range(REPS)]
    W[n] = st.mean(v)
    print("  n=%d  %7.2f fps  sd %.2f (%.1f%%)  %s" % (n, W[n], st.stdev(v), 100*st.stdev(v)/W[n],
          [round(x,1) for x in v]), flush=True)
print("=== concurrency: k contexts, 1 core each (3-core budget) ===", flush=True)
for k in (1, 3):
    v = [concurrent(k)[0] for _ in range(REPS)]
    C[k] = st.mean(v)
    print("  k=%d  agg %7.2f fps  sd %.2f (%.1f%%)  %s" % (k, C[k], st.stdev(v), 100*st.stdev(v)/C[k],
          [round(x,1) for x in v]), flush=True)

xs = [1.0/n for n in (1,2,3)]; ys = [1.0/W[n] for n in (1,2,3)]
n = 3; sx=sum(xs); sy=sum(ys); sxx=sum(x*x for x in xs); sxy=sum(a*b for a,b in zip(xs,ys))
w = (n*sxy - sx*sy)/(n*sxx - sx*sx); S = (sy - w*sx)/n
ym = sy/n; ss = sum((y-ym)**2 for y in ys); rs = sum((y-(S+w*x))**2 for x,y in zip(xs,ys))
print("\n=== fit t(n) = S + W/n on WIDTH ONLY ===")
print("  S = %.6f s (%.3f ms serial)   W = %.6f s (%.3f ms parallel)   R2 = %.4f"
      % (S, S*1000, w, w*1000, 1-rs/ss if ss else 0))
print("  serial share at 3 cores: %.1f%%   width 1->3 scaling: %.3fx (of ideal 3x)"
      % (100*S/(S + w/3), W[3]/W[1]))
print("\n=== OUT-OF-SAMPLE prediction of concurrency ===")
for k in (1, 3):
    if k in C:
        pred = k / (S + w/(3.0/k))
        print("  k=%d  predicted %7.2f  measured %7.2f  err %+6.1f%%" % (k, pred, C[k], 100*(pred-C[k])/C[k]))
print("\n  concurrency gain 1->3 at a constant 3-core budget: %.3fx" % (C[3]/C[1]))
json.dump({"width": W, "conc": C, "S_s": S, "W_s": w}, open("/tmp/npu_submit.json","w"), indent=1)
