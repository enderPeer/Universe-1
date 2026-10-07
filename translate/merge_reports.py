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
json.dump({f"{t}/{n}": r for (t, n), r in rows.items()}, open(ROOT / "translate/report_merged.json", "w"), indent=1)
def cell(tag, name):
    r = rows.get((tag, name))
    if r is None: return "-"
    if not r["ok"]: return "✗"
    s = f"{r['stages']}st/{r['max_steps']}" + ("" if r["halts"] else "*")
    return s + (" ✓" if r.get("test_ok") else (" ✗test" if "test_ok" in r else ""))
out = ["# Translation report: test corpus -> Universe-1 programs", "",
       f"Corpus: `translate/corpus.py` ({len(un)} unary, {len(bi)} binary functions, W=4).",
       "Cell = stages/total max steps (`*` = some stage never halts; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not synthesizable.", ""]
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
out += ["## Not translatable by any map", "", ", ".join(f"`{n}`" for n in never) or "none", ""]
(ROOT / "translate/REPORT.md").write_text("\n".join(out) + "\n"); print(f"{len(rows)} rows, {len(never)} functions untranslatable: {never}")
