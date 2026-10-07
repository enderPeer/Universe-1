"""Translate the test corpus into Universe-1 programs with every available map, compile and
self-test the emitted Rust, and write translate/REPORT.md.
Usage: python3 translate/translate.py [--depth 3] [--extra 64] [--no-compile]"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus
ROOT = Path(__file__).resolve().parents[1]; U = ROOT / "mapper/target/release/u1map"
ap = argparse.ArgumentParser(); ap.add_argument("--depth", type=int, default=3); ap.add_argument("--extra", type=int, default=64)
ap.add_argument("--no-compile", action="store_true"); ap.add_argument("--maps", nargs="*")
a = ap.parse_args()
un, bi = corpus.tables()
tdir = ROOT / "translate/targets"; tdir.mkdir(exist_ok=True)
(tdir / "unary.txt").write_text("".join(f"{k}|{','.join(map(str, t))}\n" for k, t in un.items()))
(tdir / "binary.txt").write_text("".join(f"{k}|{','.join(map(str, t))}\n" for k, t in bi.items()))
maps = [Path(m) for m in a.maps] if a.maps else sorted((ROOT / "results/maps").glob("w4_*.u1prog"))
results = {}; cols = []
for m in maps:
    stats = json.loads((m.with_suffix(".stats.json")).read_text())
    kind = "binary" if stats["binary"] else "unary"; tag = m.stem; cols.append((tag, stats))
    out = ROOT / "translate/out" / tag; out.mkdir(parents=True, exist_ok=True)
    rep = ROOT / "translate/out" / f"{tag}.report.jsonl"
    cmd = [str(U), "translate", "--map", str(m), "--targets", str(tdir / f"{kind}.txt"), "--out-dir", str(out),
           "--depth", str(a.depth), "--extra", str(a.extra), "--report", str(rep)]
    umap = m.with_name(m.name.replace("_bin.u1prog", ".u1prog"))
    if kind == "binary" and umap != m and umap.exists(): cmd += ["--unary-map", str(umap)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print(f"!! {tag}: {r.stderr.strip()[:300]}"); continue
    print(f"{tag}: {r.stderr.strip().splitlines()[-1]}")
    for line in rep.read_text().splitlines():
        row = json.loads(line); results[(tag, row["name"])] = row
        if row["ok"] and not a.no_compile:
            src = ROOT / row["file"]; exe = src.with_suffix("")
            c = subprocess.run(["rustc", "--edition", "2021", "--test", "-O", "-o", str(exe), str(src)], capture_output=True, text=True)
            t = subprocess.run([str(exe)], capture_output=True, text=True) if c.returncode == 0 else None
            row["compiled"] = c.returncode == 0; row["test_ok"] = bool(t and "test result: ok" in t.stdout)
            if exe.exists(): exe.unlink()
            if not row["test_ok"]: print(f"!! {tag}/{row['name']}: compile/test failed\n{c.stderr[:400]}{(t.stdout if t else '')[:400]}")
def cell(tag, name):
    r = results.get((tag, name))
    if r is None: return "-"
    if not r["ok"]: return "✗"
    s = f"{r['stages']}st/{r['max_steps']}" + ("" if r["halts"] else "*")
    if "test_ok" in r: s += " ✓" if r["test_ok"] else " ✗test"
    return s
out = ["# Translation report: test corpus -> Universe-1 programs", "",
       f"Corpus: `translate/corpus.py` ({len(un)} unary, {len(bi)} binary functions, W=4). Search depth {a.depth}, basis extra {a.extra}.",
       "Cell = stages/total max steps (`*` = some stage never halts; value exact at step 256), `✓` = emitted Rust compiled and its emulation test passed, `✗` = not synthesizable.", ""]
for kind, names in (("unary", un), ("binary", bi)):
    cs = [(t, s) for t, s in cols if ("binary" if s["binary"] else "unary") == kind]
    if not cs: continue
    out += [f"## {kind} functions", "", "| function | " + " | ".join(f"{t}<br>`{s['isa']}`" for t, s in cs) + " |", "|---|" + "---|" * len(cs)]
    for n in names: out.append(f"| `{n}` | " + " | ".join(cell(t, n) for t, _ in cs) + " |")
    tot = {t: sum(1 for n in names if results.get((t, n), {}).get("ok")) for t, _ in cs}
    out.append("| **translated** | " + " | ".join(f"**{tot[t]}/{len(names)}**" for t, _ in cs) + " |"); out.append("")
(ROOT / "translate/REPORT.md").write_text("\n".join(out) + "\n"); print("wrote translate/REPORT.md")
