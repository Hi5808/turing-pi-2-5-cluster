#!/usr/bin/env python3
"""Render MATRIX.md from data/capabilities.csv and data/slot_coverage.csv.

    python3 scripts/render_matrix.py            # writes MATRIX.md
    python3 scripts/render_matrix.py --check    # exits 1 if MATRIX.md is out of date

The CSV files are the single source of truth; never edit MATRIX.md by hand.
"""
import csv, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(ROOT, "data", "capabilities.csv")
COV = os.path.join(ROOT, "data", "slot_coverage.csv")
OUT = os.path.join(ROOT, "MATRIX.md")

STATUS_ORDER = ["WORKS", "PARTIAL", "FAILS", "NEEDS-HW", "UNTESTED"]
ICON = {"WORKS": "✅", "PARTIAL": "🟡", "FAILS": "❌", "NEEDS-HW": "🔌", "UNTESTED": "⬜"}
CHIPS = ["rk3588", "orin-nx-16g", "orin-nano-8g"]
CHIP_NAME = {"rk3588": "Turing RK1 (RK3588)", "orin-nx-16g": "Jetson Orin NX 16GB", "orin-nano-8g": "Jetson Orin Nano 8GB"}


def cell(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def render():
    rows = list(csv.DictReader(open(CAP, newline="")))
    cov = list(csv.DictReader(open(COV, newline="")))
    out = []
    a = out.append
    a("# Capability matrix\n")
    a("> Generated from [`data/capabilities.csv`](data/capabilities.csv) by `scripts/render_matrix.py`. Do not edit by hand.\n")
    a("**Legend.** ✅ works · 🟡 partial · ❌ fails · 🔌 needs hardware/ports not present · ⬜ untested. "
      "**Evidence:** MEASURED (this unit, with a log) · INVENTORY (seen on the system, not exercised) · "
      "DOCUMENTED (vendor docs, not verified here) · PLANNED · UNKNOWN.\n")

    counts = collections.Counter(r["status"] for r in rows)
    total = len(rows)
    a("## Progress\n")
    a("| Status | Rows | Share |")
    a("|---|---:|---:|")
    for s in STATUS_ORDER:
        a(f"| {ICON[s]} {s} | {counts.get(s,0)} | {100*counts.get(s,0)/total:.0f}% |")
    a(f"| **Total** | **{total}** | |\n")

    by_track = collections.OrderedDict()
    for r in rows:
        by_track.setdefault(r["track"], []).append(r)
    for track, items in by_track.items():
        a(f"## {track}\n")
        a("| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |")
        a("|---|---|---|:-:|---|---|---|---|")
        for r in items:
            log = f"[{r['log']}](logs/{r['log']}.md)" if r["log"] else ""
            a(f"| {r['id']} | {cell(r['feature'])} | {cell(r['chip'])} | {cell(r['slot'])} | "
              f"{ICON.get(r['status'],'')} {r['status']} | {r['evidence']} | {cell(r['measurement'])} | {log} |")
        a("")

    a("## Slot coverage\n")
    a("Each chip can only reach the ports of the slot it sits in ([port map](docs/PORT-MAP.md)), so a feature "
      "is only fully explored once every chip has been tested in every slot that offers it. "
      "Cells show the session in which a chip was tested in a slot.\n")
    grid = {(c["chip"], c["slot"]): c["session"] for c in cov}
    a("| Chip | Slot 1 | Slot 2 | Slot 3 | Slot 4 |")
    a("|---|:-:|:-:|:-:|:-:|")
    for chip in CHIPS:
        cells = [grid.get((chip, str(s)), "·") for s in (1, 2, 3, 4)]
        a(f"| {CHIP_NAME[chip]} | " + " | ".join(cells) + " |")
    done = len(grid)
    a(f"\n**{done} of 12** chip-in-slot combinations tested. Protocol for the rest: "
      "[rotation protocol](docs/PORT-MAP.md#rotation-protocol).\n")
    return "\n".join(out)


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        cur = open(OUT).read() if os.path.exists(OUT) else ""
        sys.exit(0 if cur == text else 1)
    open(OUT, "w").write(text)
    print("wrote", OUT)
