#!/usr/bin/env python3
"""Whole-machine saturation: where is the knee for concurrent LLM streams on this cluster?

Streams are round-robined across BOTH Orin endpoints, the way a real service would route them.
Each endpoint has 8 slots, so 16 is the last fully-concurrent arm and anything above it is
queueing, not concurrency -- the arms are labelled accordingly rather than silently conflated.

Per stream we record time-to-first-token and every inter-token gap, because aggregate tok/s
alone cannot tell a fast service from a saturated one.
"""
import json, statistics, sys, threading, time, urllib.request
from collections import defaultdict

EPS = [("nx-14b", "http://10.43.0.12:8101/completion"),
       ("nano-4b", "http://10.43.0.13:8101/completion")]
SLOTS_PER_EP = 8
ARMS = [1, 2, 4, 8, 12, 16, 24, 32]
DUR = 45
NPRED = 96
PROMPT = "Explain in two sentences why memory bandwidth limits token generation."

# SLO: a stream a human would accept reading.
SLO_ITL_MS = 200.0     # p95 inter-token latency
SLO_TOK_S = 5.0        # per-stream decode rate


class Stream(threading.Thread):
    def __init__(self, name, url):
        super().__init__(daemon=True)
        self.name, self.url = name, url
        self.stop = threading.Event()
        self.tok = 0
        self.ttft = []
        self.itl = []
        self.reqs = 0
        self.errs = 0

    def run(self):
        body = json.dumps({"prompt": PROMPT, "n_predict": NPRED, "temperature": 0,
                           "cache_prompt": False, "stream": True}).encode()
        while not self.stop.is_set():
            t0 = time.time()
            last = None
            got = 0
            try:
                rq = urllib.request.Request(self.url, data=body,
                                            headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(rq, timeout=240) as f:
                    for raw in f:
                        if self.stop.is_set():
                            break
                        if not raw.startswith(b"data:"):
                            continue
                        try:
                            j = json.loads(raw[5:].strip() or b"{}")
                        except Exception:
                            continue
                        if not j.get("content"):
                            continue
                        now = time.time()
                        if last is None:
                            self.ttft.append((now - t0) * 1000.0)
                        else:
                            self.itl.append((now - last) * 1000.0)
                        last = now
                        got += 1
                self.tok += got
                self.reqs += 1
            except Exception:
                self.errs += 1
                time.sleep(0.5)


def pct(v, p):
    if not v:
        return None
    v = sorted(v)
    return round(v[min(int(len(v) * p / 100.0), len(v) - 1)], 1)


def arm(n):
    streams = [Stream(*EPS[i % len(EPS)]) for i in range(n)]
    t0 = time.time()
    for s in streams:
        s.start()
    time.sleep(DUR)
    for s in streams:
        s.stop.set()
    time.sleep(2)
    wall = time.time() - t0

    by_ep = defaultdict(lambda: {"tok": 0, "streams": 0})
    allitl, allttft, per_stream = [], [], []
    tot = errs = reqs = 0
    for s in streams:
        by_ep[s.name]["tok"] += s.tok
        by_ep[s.name]["streams"] += 1
        allitl += s.itl
        allttft += s.ttft
        per_stream.append(s.tok / wall)
        tot += s.tok
        errs += s.errs
        reqs += s.reqs

    itl95 = pct(allitl, 95)
    slowest = round(min(per_stream), 2) if per_stream else 0
    ok = (itl95 is not None and itl95 <= SLO_ITL_MS and slowest >= SLO_TOK_S)
    rec = {"streams": n, "concurrent": n <= SLOTS_PER_EP * len(EPS),
           "wall_s": round(wall, 1), "t_start": round(t0, 1), "t_end": round(t0 + wall, 1),
           "agg_tok_s": round(tot / wall, 2),
           "per_stream_tok_s_mean": round(statistics.mean(per_stream), 2) if per_stream else 0,
           "per_stream_tok_s_min": slowest,
           "ttft_p50_ms": pct(allttft, 50), "ttft_p95_ms": pct(allttft, 95),
           "itl_p50_ms": pct(allitl, 50), "itl_p95_ms": itl95,
           "requests": reqs, "errors": errs,
           "by_endpoint": {k: {"tok_s": round(v["tok"] / wall, 2), "streams": v["streams"]}
                           for k, v in by_ep.items()},
           "meets_slo": ok}
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    res = []
    for n in ARMS:
        res.append(arm(n))
        time.sleep(8)      # let slots drain between arms
    knee = max([r["streams"] for r in res if r["meets_slo"]], default=0)
    best = max(res, key=lambda r: r["agg_tok_s"])
    print(json.dumps({"knee_streams_meeting_slo": knee,
                      "slo": {"itl_p95_ms": SLO_ITL_MS, "per_stream_tok_s": SLO_TOK_S},
                      "peak_agg_tok_s": best["agg_tok_s"], "peak_at_streams": best["streams"]}),
          flush=True)
    open("/mnt/nvme/share/studio/research/ramp.json", "w").write(json.dumps(res, indent=1))
    print("WROTE ramp.json", flush=True)
