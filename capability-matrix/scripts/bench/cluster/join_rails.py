#!/usr/bin/env python3
"""Slice each Orin's 1 Hz rail log by the ramp arms' start/end timestamps and emit ramp_joined.json."""
import csv, json, statistics as st, sys

def load(p):
    out = []
    for r in csv.DictReader(open(p)):
        try:
            out.append((float(r["ts"]), float(r["vdd_in"])))
        except Exception:
            pass
    return out

def win(rows, a, b):
    v = [w for t, w in rows if a <= t <= b]
    return (round(st.mean(v), 2), len(v)) if v else (None, 0)

nx, nano = load(sys.argv[1]), load(sys.argv[2])
arms = json.load(open(sys.argv[3]))
out = []
for a in arms:
    wnx, n1 = win(nx, a["t_start"], a["t_end"])
    wna, n2 = win(nano, a["t_start"], a["t_end"])
    tot = (wnx + wna) if (wnx and wna) else None
    out.append(dict(a, nx_w=wnx, nano_w=wna,
                    two_module_w=round(tot, 2) if tot else None,
                    tok_per_j=round(a["agg_tok_s"] / tot, 3) if tot else None,
                    pw_samples=min(n1, n2)))
json.dump(out, open("ramp_joined.json", "w"), indent=1)
print("wrote ramp_joined.json")
