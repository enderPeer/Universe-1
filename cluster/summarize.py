"""Build results/exp03_summary.md from results/exp03_*.json."""
import json, glob
from pathlib import Path
rows = []
for fn in sorted(glob.glob("results/exp03_*.json")):
    r = json.loads(Path(fn).read_text())
    if "distinct_operators" not in r: continue
    cursor = 0
    for lo, hi in sorted(r["programs_covered"]):
        if lo != cursor or hi <= lo: raise ValueError(f"Invalid coverage: {fn}")
        cursor = hi
    if cursor != 1 << r["program_bits"]: raise ValueError(f"Incomplete sweep: {fn}")
    exponent = r["W"] * (1 << r["W"]) ** (2 if r["binary"] else 1)
    rows.append((r["W"], Path(fn).stem, r["a"], r["p"], r["I"], r["opcode_bits"], ",".join(r["isa"]),
                 "binary" if r["binary"] else "unary", r["distinct_operators"], f"2^{exponent}",
                 round(r.get("wall_seconds", 0), 2), round(r.get("programs_per_second", 0) / 1e6, 2), "complete"))
rows.sort(key=lambda x: (x[0], -x[8]))
out = ["# Experiment 03: 4-byte (2^32 program) exhaustive sweeps", "",
       "Wall time includes dispatch and GPU work; excludes shard download and merge.", "",
       "| W | run | a | p | I | opcode bits | ISA | mode | distinct operators | universe | seconds | M programs/s | coverage |", "|---|---|---|---|---|---|---|---|---:|---|---:|---:|---|"]
for r in rows: out.append("| " + " | ".join(str(x) for x in r) + " |")
out += ["", "## Highest counts among completed candidates", ""]
for W, mode in sorted({(r[0], r[7]) for r in rows}):
    candidates = [r for r in rows if r[0] == W and r[7] == mode]
    best = max(r[8] for r in candidates)
    out.append(f"- W={W}, {mode}: " + ", ".join(r[1] for r in candidates if r[8] == best) + f" ({best} operators).")
out += ["", "These rankings compare only the configured candidate ISAs; they do not prove global optimality.",
        "All runs use layout L3 (address 0 aliases A), so no memory-layout winner is established.",
        "Raw shards and minimum-program witnesses are in results/shards/ on the coordinator and producing worker.",
        "W<=4 unary and W<=2 binary use exact keys; larger tables are represented by hashes.",
        "GPU engines do not report halt/loop/budget distributions. W=8 binary exceeds the current GPU table limit."]
Path("results/exp03_summary.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
