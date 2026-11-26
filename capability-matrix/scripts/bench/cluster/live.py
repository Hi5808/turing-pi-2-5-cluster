"""One board, three accelerators, live.

Every result from this cluster so far has been a table in a markdown file. This serves the same
facts as something you can watch: the RK3588's NPU running YOLOv5s while both Orin GPUs decode
tokens, with real INA3221 rail power next to each engine.

The point of the concurrency control is to make research/006 visible instead of readable. Push the
Orins from 1 stream to 8 and the throughput climbs while the watts *fall* -- because the dominant
cost at low concurrency is a fixed per-decode-step overhead, not compute. That is the one finding
here that contradicts how edge inference power is normally budgeted, and it is much more convincing
watched than read.

node1 has no power rails (its BMC has no sensing hardware at all -- see the 2026-11-24 BMC log), so
its card shows throughput only. That absence is displayed rather than hidden.

    python3 live.py [port]      # default 8096

Two things to know before running it.

**It generates real load, and only while watched.** The Orin workers and the NPU subprocess are
gated on a page poll within IDLE_GRACE seconds; with no browser attached the whole thing idles at
roughly 8 W per Orin. That gate exists because it was missing: on 2026-11-25 a forgotten
`nohup python3 live.py 8096` was found still holding both Orins at full GPU load after 9 h 06 m,
with orinnx at tj 98 C -- past its 95 C trip, 6 C under the 104 C shutdown trip -- while `uptime`
read 0.21, because the work was all in CUDA and never touched a CPU runqueue. It also silently
contaminated the "idle" power baseline of every measurement taken in that window. See
docs/MEASUREMENTS.md.

**It binds 0.0.0.0 and has no authentication.** `GET /set?n=8` will start eight decode streams per
module for anyone who can reach the port. That is fine on a trusted lab LAN and is not safe to
expose; bind it to a specific interface or put it behind something if your network is shared.
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.sys.argv[1]) if len(os.sys.argv) > 1 else 8096
MAXW = 8                      # worker threads spawned per Orin; STREAMS of them are active
NPRED = 48
HIST = 90                     # seconds of history kept for the sparklines
RAIL = "/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon3"
PROMPT = ("Describe, without repeating yourself, how a scheduler should place work across "
          "machines that are not identical.")

NODES = {
    "node1":  {"label": "node1 — Turing RK1", "engine": "RK3588 NPU, 3 cores",
               "model": "YOLOv5s-relu int8 @640", "unit": "fps", "ssh": None, "url": None},
    "orinnx": {"label": "node2 — Jetson Orin NX 16GB", "engine": "Ampere GPU, 1024 CUDA",
               "model": "Qwen3-14B Q4_K_M", "unit": "tok/s",
               "ssh": "orinnx@10.43.0.12", "url": "http://10.43.0.12:8101"},
    "orin1":  {"label": "node3 — Jetson Orin Nano 8GB", "engine": "Ampere GPU, 1024 CUDA",
               "model": "Qwen3-4B Q4_K_M", "unit": "tok/s",
               "ssh": "orin1@10.43.0.13", "url": "http://10.43.0.13:8101"},
}

STREAMS = 2          # the measured interactive knee; 006 says batch work should use 8
toks = {k: 0 for k in NODES}
state = {k: {"rate": 0.0, "watts": None, "hist": deque([0.0] * HIST, maxlen=HIST),
             "whist": deque([0.0] * HIST, maxlen=HIST), "err": None} for k in NODES}
lock = threading.Lock()


# ---- idle gate ----------------------------------------------------------------------------
# The load generators below used to run whether or not a browser was attached. On 2026-11-25 a
# forgotten `nohup python3 live.py 8096` was found still holding both Orins at full GPU load
# after 9 h: orinnx sat at tj 98 C -- past its 95 C trip, 6 C under the 104 C shutdown -- at
# 30.2 W with gpu_load 999, while `uptime` read 0.21 because the work was all in CUDA and never
# touched a CPU runqueue. The same invisible load silently contaminated the "idle" baseline of
# every power measurement taken in that window. This is a demo; it must cost nothing when nobody
# is watching it.
IDLE_GRACE = 30.0        # seconds without a page poll before every generator parks
LAST_VIEW = 0.0          # stamped by do_GET on "/" and "/state"


def viewed():
    return (time.time() - LAST_VIEW) < IDLE_GRACE


# ---- load generation on the two Orins -----------------------------------------------------
def orin_worker(node, idx):
    url = NODES[node]["url"] + "/completion"
    body = json.dumps({"prompt": PROMPT, "n_predict": NPRED, "temperature": 0,
                       "cache_prompt": False}).encode()
    while True:
        if idx >= STREAMS or not viewed():   # parked: over the concurrency setting, or unwatched
            time.sleep(0.3)
            continue
        try:
            req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read())
            n = (d.get("timings") or {}).get("predicted_n") or 0
            with lock:
                toks[node] += n
                state[node]["err"] = None
        except Exception as e:
            with lock:
                state[node]["err"] = type(e).__name__
            time.sleep(2)


# ---- power, read straight off the INA3221 over one persistent ssh --------------------------
def power_reader(node):
    target = NODES[node]["ssh"]
    remote = ('while true; do paste -d" " %s/in1_input %s/curr1_input; sleep 0.5; done'
              % (RAIL, RAIL))
    while True:
        try:
            p = subprocess.Popen(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
                 "-o", "ServerAliveInterval=10", target, remote],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            for line in p.stdout:
                mv, ma = line.split()
                with lock:
                    state[node]["watts"] = int(mv) * int(ma) / 1e6
        except Exception:
            pass
        with lock:
            state[node]["watts"] = None
        time.sleep(3)


# ---- the NPU worker is a subprocess, because rknnlite lives in its own venv ----------------
def npu_reader():
    while True:
        if not viewed():
            time.sleep(1.0)
            continue
        try:
            p = subprocess.Popen(
                ["/mnt/nvme/npu-bench/.venv/bin/python",
                 "/mnt/nvme/npu-bench/npu_live.py", "3"],
                cwd="/mnt/nvme/npu-bench", stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1)
            for line in p.stdout:
                if not viewed():     # the child runs forever on its own; it must be reaped here
                    p.terminate()
                    break
                line = line.strip()
                if not line.startswith("{"):
                    continue
                d = json.loads(line)
                with lock:
                    state["node1"]["rate"] = d.get("fps", 0.0)
                    state["node1"]["hist"].append(d.get("fps", 0.0))
                    state["node1"]["whist"].append(0.0)
                    state["node1"]["err"] = d.get("error")
        except Exception as e:
            with lock:
                state["node1"]["err"] = type(e).__name__
        time.sleep(3)


# ---- tick: turn token counters into rates -------------------------------------------------
WINDOW = 10.0   # seconds; see note below


def ticker():
    """Rolling-window rate, not a per-second difference.

    Tokens are only credited when a request finishes, and a 48-token request on the 14B model
    takes ~13 s. A 1-second difference therefore reads zero on most ticks and spikes on the few
    where a request lands -- which is exactly how this first read 0.0 tok/s on a node whose rail
    power proved it was working hard. A trailing window over the cumulative counter is immune to
    how long individual requests take.
    """
    samples = deque()        # (timestamp, {node: cumulative tokens})
    while True:
        time.sleep(1.0)
        now = time.time()
        with lock:
            samples.append((now, dict(toks)))
            while len(samples) > 1 and now - samples[0][0] > WINDOW:
                samples.popleft()
            t0, base = samples[0]
            dt = now - t0
            for k in ("orinnx", "orin1"):
                r = (toks[k] - base[k]) / dt if dt >= 1.0 else 0.0
                state[k]["rate"] = r
                state[k]["hist"].append(r)
                state[k]["whist"].append(state[k]["watts"] or 0.0)


slots = {"orinnx": None, "orin1": None}


def slot_probe():
    """Read each server's actual --parallel value.

    A dashboard that lets you ask for 8 streams while the server has 2 slots does not measure
    concurrency, it measures queueing -- and it produced a result that briefly looked like it
    contradicted research/006. The page now shows the real slot count so the two cannot be
    confused again.
    """
    while True:
        for k, meta in NODES.items():
            if not meta["url"]:
                continue
            try:
                req = urllib.request.Request(meta["url"] + "/props")
                with urllib.request.urlopen(req, timeout=6) as r:
                    d = json.loads(r.read())
                n = d.get("total_slots") or (d.get("default_generation_settings") or {}).get("n_parallel")
                with lock:
                    slots[k] = n
            except Exception:
                pass
        time.sleep(20)


def snapshot():
    with lock:
        out = {"streams": STREAMS, "nodes": {}}
        board = 0.0
        for k, meta in NODES.items():
            s = state[k]
            w = s["watts"]
            if w:
                board += w
            out["nodes"][k] = {
                "label": meta["label"], "engine": meta["engine"], "model": meta["model"],
                "unit": meta["unit"], "rate": round(s["rate"], 1),
                "watts": round(w, 2) if w else None,
                "per_joule": round(s["rate"] / w, 3) if (w and s["rate"]) else None,
                "hist": [round(x, 1) for x in s["hist"]],
                "whist": [round(x, 2) for x in s["whist"]],
                "err": s["err"],
            }
        out["board_measured_w"] = round(board, 2)
        out["slots"] = dict(slots)
        # a request for more streams than the server has slots is queueing, not batching
        out["capped"] = [k for k, v in slots.items() if v and STREAMS > v]
        return out


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Three Accelerators</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#14161a;--dim:#5d6470;--line:#e3e6ea;
      --a:#2f6fdc;--b:#1f9d78;--c:#c76a1f;--warn:#c0392b}
:root:not([data-theme=light]){@media (prefers-color-scheme:dark){
  --bg:#0f1115;--card:#171a20;--ink:#e8eaed;--dim:#9aa2b1;--line:#262b34;
  --a:#6ea8fe;--b:#4fd1a5;--c:#e8a158;--warn:#ff6b6b}}
:root[data-theme=dark]{--bg:#0f1115;--card:#171a20;--ink:#e8eaed;--dim:#9aa2b1;--line:#262b34;
  --a:#6ea8fe;--b:#4fd1a5;--c:#e8a158;--warn:#ff6b6b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:23px;margin:0 0 4px;letter-spacing:-.2px}
.sub{color:var(--dim);margin:0 0 22px;font-size:14px}
.ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 20px;
  padding:14px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.ctl b{font-weight:600;margin-right:6px}
button{font:inherit;padding:7px 15px;border-radius:8px;border:1px solid var(--line);
  background:transparent;color:var(--ink);cursor:pointer}
button.on{background:var(--a);border-color:var(--a);color:#fff;font-weight:600}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.lab{font-weight:650;font-size:15px}
.eng{color:var(--dim);font-size:12.5px;margin:2px 0 14px}
.big{font-variant-numeric:tabular-nums;font-size:40px;font-weight:620;letter-spacing:-1px;
  line-height:1.05}
.unit{font-size:14px;color:var(--dim);font-weight:400;margin-left:5px}
.row{display:flex;gap:18px;margin-top:12px;font-variant-numeric:tabular-nums;font-size:13px}
.row div span{color:var(--dim);display:block;font-size:11.5px;text-transform:uppercase;
  letter-spacing:.4px}
svg{display:block;width:100%;height:46px;margin-top:14px;overflow:visible}
.err{color:var(--warn);font-size:12.5px;margin-top:8px}
.note{color:var(--dim);font-size:12.5px;margin-top:10px;font-style:italic}
.tot{margin-top:18px;padding:14px 16px;background:var(--card);border:1px solid var(--line);
  border-radius:12px;display:flex;gap:26px;flex-wrap:wrap;font-variant-numeric:tabular-nums}
.tot div span{color:var(--dim);display:block;font-size:11.5px;text-transform:uppercase;
  letter-spacing:.4px}
.tot b{font-size:21px;font-weight:620}
footer{color:var(--dim);font-size:12.5px;margin-top:26px;line-height:1.7}
</style></head><body><div class="wrap">
<h1>One board, three accelerators</h1>
<p class="sub">Live. Two Jetson GPUs decoding tokens and an RK3588 NPU running object detection,
on one Turing Pi 2.5, with power read off the INA3221 rails.</p>

<div class="ctl"><b>Concurrent streams per Orin</b>
  <button data-n="1">1</button><button data-n="2">2</button>
  <button data-n="4">4</button><button data-n="8">8</button>
  <span class="note" style="margin:0 0 0 8px">Watch the watts as you raise this — throughput goes
  up and power goes <em>down</em>.</span>
</div>

<p id="warn" style="font-size:12.5px;margin:-8px 0 16px"></p>
<div class="grid" id="grid"></div>
<div class="tot" id="tot"></div>
<footer id="foot"></footer>
</div><script>
const spark = (h, max, color) => {
  if (!h.length) return "";
  const m = Math.max(max, ...h) || 1, n = h.length;
  const pts = h.map((v, i) => `${(i / (n - 1) * 100).toFixed(2)},${(44 - v / m * 42).toFixed(2)}`);
  return `<svg viewBox="0 0 100 46" preserveAspectRatio="none">
    <polyline fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"
      points="${pts.join(" ")}"/></svg>`;
};
const COL = {node1: "var(--c)", orinnx: "var(--a)", orin1: "var(--b)"};
async function tick() {
  let d;
  try { d = await (await fetch("state")).json(); } catch (e) { return; }
  document.querySelectorAll(".ctl button").forEach(b =>
    b.classList.toggle("on", +b.dataset.n === d.streams));
  const g = [];
  for (const [k, n] of Object.entries(d.nodes)) {
    g.push(`<div class="card"><div class="lab">${n.label}</div>
      <div class="eng">${n.engine} &middot; ${n.model}</div>
      <div class="big">${n.rate.toFixed(1)}<span class="unit">${n.unit}</span></div>
      <div class="row">
        <div><span>power</span>${n.watts === null ? "no rails" : n.watts.toFixed(2) + " W"}</div>
        <div><span>per joule</span>${n.per_joule === null ? "—" :
            n.per_joule.toFixed(2) + " " + n.unit.replace("/s", "") + "/J"}</div>
      </div>
      ${spark(n.hist, 1, COL[k])}
      ${n.err ? `<div class="err">${n.err}</div>` : ""}
      ${n.watts === null ? `<div class="note">The RK1 module exposes no power rails, and the
        board's BMC has no power-sensing hardware at all — so this is unmeasured, not zero.</div>`
        : ""}
    </div>`);
  }
  document.getElementById("grid").innerHTML = g.join("");
  const nx = d.nodes.orinnx, n1 = d.nodes.orin1;
  const tok = nx.rate + n1.rate;
  document.getElementById("tot").innerHTML = `
    <div><span>measured board power</span><b>${d.board_measured_w.toFixed(2)} W</b></div>
    <div><span>tokens / s</span><b>${tok.toFixed(1)}</b></div>
    <div><span>detections / s</span><b>${d.nodes.node1.rate.toFixed(0)}</b></div>
    <div><span>tokens / joule</span><b>${d.board_measured_w ?
        (tok / d.board_measured_w).toFixed(2) : "—"}</b></div>`;
  const cap = (d.capped || []);
  const sl = Object.entries(d.slots || {}).filter(([k, v]) => v)
                   .map(([k, v]) => `${k}: ${v} slots`).join(" &middot; ");
  document.getElementById("warn").innerHTML = cap.length
    ? `<b>Queueing, not batching.</b> You asked for ${d.streams} streams but
       ${cap.join(" and ")} has fewer slots, so the extra requests are waiting in line and real
       concurrency is capped. Restart the server with more <code>--parallel</code> slots.`
    : (sl ? `Server slots &mdash; ${sl}` : "");
  document.getElementById("warn").style.color = cap.length ? "var(--warn)" : "var(--dim)";
  document.getElementById("foot").innerHTML = `Power is the two Jetson modules' VDD_IN rails only.
    It excludes node1 and the carrier itself — fan, BMC and Ethernet switch — which nothing on this
    board can measure. Every figure here is a live reading, not a stored benchmark.`;
}
document.querySelectorAll(".ctl button").forEach(b => b.onclick = async () => {
  await fetch("set?n=" + b.dataset.n); tick();
});
tick(); setInterval(tick, 1000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        global STREAMS, LAST_VIEW
        p = self.path.split("?")[0].rstrip("/") or "/"
        if p in ("/", "/state"):
            LAST_VIEW = time.time()
        if p == "/":
            self._send(PAGE, "text/html; charset=utf-8")
        elif p == "/state":
            self._send(json.dumps(snapshot()), "application/json")
        elif p == "/set":
            q = self.path.split("?", 1)[1] if "?" in self.path else ""
            n = dict(kv.split("=") for kv in q.split("&") if "=" in kv).get("n", "2")
            STREAMS = max(1, min(MAXW, int(n)))
            self._send(json.dumps({"streams": STREAMS}), "application/json")
        else:
            self.send_error(404)


for n in ("orinnx", "orin1"):
    threading.Thread(target=power_reader, args=(n,), daemon=True).start()
    for i in range(MAXW):
        threading.Thread(target=orin_worker, args=(n, i), daemon=True).start()
threading.Thread(target=npu_reader, daemon=True).start()
threading.Thread(target=slot_probe, daemon=True).start()
threading.Thread(target=ticker, daemon=True).start()

print("live on :%d" % PORT, flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
