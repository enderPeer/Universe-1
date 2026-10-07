"""Cross-ISA usability matrix: which named operators each ISA realizes, and at what step cost.
Usage: python3 mapper/usability.py results/maps/*.named.jsonl --out results/maps/usability.md"""
import argparse, json, re
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--out", required=True); ap.add_argument("--top", type=int, default=120)
a = ap.parse_args()
cols = []; have = {}
for fn in sorted(a.files):
    tag = Path(fn).name.replace(".named.jsonl", ""); stats = json.loads(Path(fn).with_name(tag + ".stats.json").read_text())
    rows = [json.loads(l) for l in Path(fn).read_text().splitlines() if l.strip()]
    cols.append((tag, stats)); have[tag] = {r["name"]: r for r in rows}
# elementary (depth-1) names first: no parentheses
names = sorted({n for t in have for n in have[t]}, key=lambda n: ("(" in n, len(n), n))
elem = [n for n in names if "(" not in n or re.fullmatch(r"\w+\(x(,\d+)?\)|\w+\(x,y\)|\w+\(x\+y\)|\w+\(x-y\)", n)]
out = ["# Usability matrix: named operators per ISA", "",
       "Cell = max steps over all inputs of the minimum-numeric-ID witness. 256 is the execution ceiling; consult the halting flag rather than treating that number alone as nontermination. `-` means this canonical name is absent; equivalent aliases can differ across widths/arity. Compare like-width, like-arity columns.", "",
       "| ISA | W | mode | operators | named | all-inputs-halting |", "|---|---|---|---:|---:|---:|"]
for tag, s in cols: out.append(f"| {tag} ({s['isa']}) | {s['W']} | {'binary' if s['binary'] else 'unary'} | {s['operators']} | {s['named_found']}/{s['vocabulary_size']} | {s['all_inputs_halt']} |")
for title, subset in (("Elementary operators", elem), ("Composite names (depth 2)", [n for n in names if n not in elem][:a.top])):
    out += ["", f"## {title}", "", "| operator | " + " | ".join(t for t, _ in cols) + " |", "|---|" + "---|" * len(cols)]
    for n in subset:
        cells = [(str(have[t][n]["steps"]) + ("" if have[t][n]["halts"] else "*")) if n in have[t] else "-" for t, _ in cols]
        if any(c != "-" for c in cells):
            label=n.replace('|',r'\|')
            out.append(f"| `{label}` | " + " | ".join(cells) + " |")
out += ["", "`*` = some input does not halt (value taken at step 256)."]
Path(a.out).write_text("\n".join(out) + "\n", encoding='utf-8'); print(f"{len(elem)} elementary + {len(names) - len(elem)} composite names across {len(cols)} ISAs -> {a.out}")
