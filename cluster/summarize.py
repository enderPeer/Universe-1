"""Build results/exp03_summary.md from results/exp03_*.json."""
import json, glob
from pathlib import Path
rows = []
for fn in sorted(glob.glob("results/exp03_*.json")):
    r = json.loads(Path(fn).read_text())
    rows.append((r["W"], Path(fn).stem, r["a"], r["p"], r["I"], r["opcode_bits"], ",".join(r["isa"]),
                 "binary" if r["binary"] else "unary", r["distinct_operators"], r["operator_universe"], r["gaps"]))
rows.sort(key=lambda x: (x[0], -x[8]))
out = ["# Experiment 03: 4-byte (2^32 program) exhaustive sweeps", "",
       "| W | run | a | p | I | opcode bits | ISA | mode | distinct operators | universe | gaps |", "|---|---|---|---|---|---|---|---|---:|---:|---|"]
for r in rows: out.append("| " + " | ".join(str(x) for x in r) + " |")
Path("results/exp03_summary.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
