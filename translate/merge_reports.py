"""Merge per-map translation reports (from several nodes) into translate/report_merged.json
and rebuild translate/REPORT.md from them without re-synthesizing.
Usage: python3 translate/merge_reports.py"""
import json, glob, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus
ROOT = Path(__file__).resolve().parents[1]
un, bi = corpus.tables(); rows = {}; cols = []
for f in sorted(glob.glob(str(ROOT / "translate/out/*.report.jsonl"))):
    tag = Path(f).name.replace(".report.jsonl", "")
    stats = json.loads((ROOT / "results/maps" / f"{tag}.stats.json").read_text()); cols.append((tag, stats))
    for l in Path(f).read_text().splitlines():
        r = json.loads(l); rows[(tag, r["name"])] = r
    expected=set(bi if stats['binary'] else un)
    actual={name for (t,name) in rows if t==tag}
    if actual!=expected: raise ValueError(f'{tag}: incomplete or unexpected target set')
    for name in expected:
        row=rows[(tag,name)]
        if row['ok'] and not row.get('test_ok'):
            raise ValueError(f'{tag}/{name}: emitted Rust lacks a passing test')
json.dump({f"{t}/{n}": r for (t, n), r in rows.items()}, open(ROOT / "translate/report_merged.json", "w"), indent=1)
def cell(tag, name):
    r = rows.get((tag, name))
    if r is None: return "-"
    if not r["ok"]: return "✗"
    s = f"{r['stages']}st/{r['max_steps']}" + ("" if r["halts"] else "*")
    return s + (" ✓" if r.get("test_ok") else (" ✗test" if "test_ok" in r else ""))
out = ["# Translation report: test corpus -> Universe-1 programs", "",
       f"Corpus: `translate/corpus.py` ({len(un)} unary, {len(bi)} binary functions, W=4).",
       "Cell = stages/sum of per-stage worst-case steps (`*` = not every input halts within the budget in every stage; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not found in the configured search. This is a bounded basis search, not a proof of impossibility.", "",
       "## Run settings and timings", "", "| Map | Node | Actual depth | Extra basis | Wall seconds (including tests) |", "|---|---|---:|---:|---:|"]
for tag,_ in cols:
    r=next(v for (t,n),v in rows.items() if t==tag)
    depth='binary forms <=3' if r.get('binary_composition') else r.get('search_depth','unknown')
    out.append(f"| {tag} | {r.get('node','unknown')} | {depth} | {r.get('basis_extra','unknown')} | {r.get('map_wall_seconds',0):.2f} |")
out.append('')
never = []
for kind, names in (("unary", un), ("binary", bi)):
    cs = [(t, s) for t, s in cols if ("binary" if s["binary"] else "unary") == kind]
    if not cs: continue
    out += [f"## {kind} functions", "", "| function | " + " | ".join(f"{t}<br>`{s['isa']}`" for t, s in cs) + " |", "|---|" + "---|" * len(cs)]
    for n in names:
        out.append(f"| `{n}` | " + " | ".join(cell(t, n) for t, _ in cs) + " |")
        if not any(rows.get((t, n), {}).get("ok") for t, _ in cs): never.append(n)
    tot = {t: sum(1 for n in names if rows.get((t, n), {}).get("ok")) for t, _ in cs}
    out.append("| **translated** | " + " | ".join(f"**{tot[t]}/{len(names)}**" for t, _ in cs) + " |"); out.append("")
out += ["## Not translated within this search", "", ", ".join(f"`{n}`" for n in never) or "none", "",
        "Binary maps marked 'binary forms <=3' use the matching unary map and the composition forms introduced in 87185a8; other binary rows are direct lookup. Unary depth and any memory fallback are listed above; all searches use bounded bases. Source revision and mode are stored per row in report_merged.json.", "",
        "[Cluster timings, validation and next-ISA proposal](CLUSTER_RUN.md) | [All emitted sources and test logs](emitted_sources.zip)"]
(ROOT / "translate/REPORT.md").write_text("\n".join(out) + "\n", encoding='utf-8'); print(f"{len(rows)} rows, {len(never)} functions not translated within search: {never}")
