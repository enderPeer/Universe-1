"""Validate life/u1soup_cuda against the Python reference sim/soup.py on one configuration: runs both with --dump-final into
<out>/gpu and <out>/ref and compares final.txt (memory, every living processor, counters: exact), stats.csv (exact except the
entropies, which may differ in the last digit from summation order), every census_*.tsv, activity.tsv and shadow_activity.tsv (exact).
usage: python3 fast/check_soup.py --engine life/u1soup_cuda --gpu 0 --out results/soup/check/chain -- --N 1024 --P 64 --ancestors 0x01b30b20c9 --spontaneous 0 --fill zero --ticks 100
(run on a node with the engine built; the reference is slow: keep P x S x ticks below ~10^7 instructions)"""
import argparse, csv, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument('--engine', default='life/u1soup_cuda'); ap.add_argument('--gpu', default='0'); ap.add_argument('--out', required=True); ap.add_argument('args', nargs=argparse.REMAINDER)
a = ap.parse_args(); args = [x for x in a.args if x != '--']; out = Path(a.out); gpu, ref = out / 'gpu', out / 'ref'
t0 = time.time(); r = subprocess.run([str(ROOT / a.engine), '--gpu', a.gpu] + args + ['--out-dir', str(gpu), '--dump-final'], capture_output=True, text=True)
if r.returncode: print(r.stderr[-2000:]); sys.exit(f'engine failed ({r.returncode})')
t1 = time.time(); r = subprocess.run([sys.executable, str(ROOT / 'sim/soup.py')] + args + ['--out-dir', str(ref), '--dump-final'], capture_output=True, text=True)
if r.returncode: print(r.stderr[-2000:]); sys.exit(f'reference failed ({r.returncode})')
t2 = time.time()
def lines(p): return Path(p).read_text().splitlines()
g, f = lines(gpu / 'final.txt'), lines(ref / 'final.txt')
assert g[0] == f[0], ('header', g[0], f[0])
if g[1] != f[1]:
    d = [i for i in range(min(len(g[1]), len(f[1])) // 2) if g[1][2 * i:2 * i + 2] != f[1][2 * i:2 * i + 2]]
    sys.exit(f'memory differs at {len(d)} words, first {d[:10]}')
assert len(g) == len(f), ('line counts', len(g), len(f))
for i, (x, y) in enumerate(zip(g[2:], f[2:])):
    if x != y: sys.exit(f'state line {i} differs:\n gpu {x}\n ref {y}')
gs, fs = list(csv.reader(open(gpu / 'stats.csv'))), list(csv.reader(open(ref / 'stats.csv')))
assert gs[0] == fs[0] and len(gs) == len(fs), ('stats shape', len(gs), len(fs))
ent = [i for i, h in enumerate(gs[0]) if 'entropy' in h]
for x, y in zip(gs[1:], fs[1:]):
    for i, (u, v) in enumerate(zip(x, y)):
        if i in ent:
            if abs(float(u or 0) - float(v or 0)) > 2e-4: sys.exit(f'entropy differs at tick {x[0]}: {u} vs {v}')
        elif u != v: sys.exit(f'stats differ at tick {x[0]} column {gs[0][i]}: gpu {u} ref {v}')
for name in sorted(p.name for p in ref.glob('census_*.tsv')) + ['activity.tsv', 'shadow_activity.tsv']:
    if not (ref / name).exists(): continue
    if lines(gpu / name) != lines(ref / name): sys.exit(f'{name} differs')
live = sum(1 for l in g[2:] if ' B ' in l)
print(f'{out}: {" ".join(args)}: identical (tick {g[0].split()[-1]}, {live} living processors, {len(gs) - 1} stats rows, {len(list(ref.glob("census_*.tsv")))} censuses); engine {t1 - t0:.1f}s, reference {t2 - t1:.1f}s')
