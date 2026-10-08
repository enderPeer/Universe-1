"""Validate a gpu/u1_l2 run (<out>.copy and, unless copy-only, the <out> shard) against the Python L2 reference (sim/machine_l2.py)
on its full program range. Intended for small ranges (a few thousand programs): recomputes every program's unary table (when a
shard exists) and the exp06b statistics in Python and compares the distinct-key set, the minimum program per key, the final/best
copy-score histograms with their minimum programs, the ever-modified / final-modified / walker counts, the copier counts (ever,
persisting, intact), the first-copy step histogram and the listed copiers (program, first step, intact, persists, offset).
usage: python fast/check_l2.py <out>   (reads <out>.copy; <out> itself if present)"""
import re, struct, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.machine_l2 import ConfigL2, MachineL2
from merge import PNAME
fn = sys.argv[1]; copy = Path(fn + '.copy').read_text()
h = re.match(r'layout L2 W (\d+) a (\d+) p (\d+) I (\d+) isa (\S+) programs \[(\d+),(\d+)\)', copy)
W, a, p, I = (int(x) for x in h.groups()[:4]); isa = tuple(h[5].split(',')); lo, hi = int(h[6]), int(h[7]); copy_only = 'copy-only' in copy.splitlines()[0]
cfg = ConfigL2(W=W, a=a, p=p, I=I); m = MachineL2(cfg, isa); nins = 1 << p
if not copy_only and Path(fn).exists():
    b = Path(fn).read_bytes(); hdr = struct.unpack_from('<8I', b, 0); n = struct.unpack_from('<Q', b, 48)[0]; off = 56 + hdr[7]
    gpu = {}
    for i in range(n):
        klo, khi, prog = struct.unpack_from('<QQI', b, off + i * 20); gpu[(klo, khi)] = prog
    ref = {}
    for prog in range(lo, hi):
        t = m.table_unary(prog); k = 0
        for i, v in enumerate(t): k |= v << (W * i)
        key = (k & ((1 << 64) - 1), k >> 64)
        if key not in ref or prog < ref[key]: ref[key] = prog
    assert set(gpu) == set(ref), f'key sets differ: {len(gpu)} vs {len(ref)}'
    assert all(gpu[k] == ref[k] for k in ref), 'minimum programs differ'
    functions = len(ref)
else: functions = None
final = Counter(); best = Counter(); fmin = {}; bmin = {}; ever = fmod = walkers = cop_ever = cop_final = cop_intact = 0; first = Counter(); imin = None; listed = {}
for prog in range(lo, hi):
    S = m.stats(prog)
    final[S['final']] += 1; best[S['best']] += 1; fmin[S['final']] = min(fmin.get(S['final'], prog), prog); bmin[S['best']] = min(bmin.get(S['best'], prog), prog)
    ever += S['ever_mod']; fmod += S['final_mod']; walkers += S['walker']
    if S['copier']:
        cop_ever += 1; first[S['first_full']] += 1; cop_final += S['final'] == nins; listed[prog] = (S['first_full'], S['intact'], int(S['final'] == nins), S['offset'])
        if S['intact']: cop_intact += 1; imin = prog if imin is None else min(imin, prog)
for tag, hist, mins in (('final', final, fmin), ('best', best, bmin)):
    got = {int(x): (int(c), int(q, 16)) for x, c, q in re.findall(tag + r' (\d+) count (\d+) min_program (0x[0-9a-f]+)', copy)}
    for sc in range(nins + 1):
        cnt, mp = got[sc]; assert cnt == hist.get(sc, 0), (tag, sc, cnt, hist.get(sc, 0)); assert cnt == 0 or mp == mins[sc], (tag, sc, mp, mins.get(sc))
g = re.search(r'ever_mod (\d+) final_mod (\d+) walkers (\d+) copiers_ever (\d+) copiers_final (\d+) copiers_intact (\d+) min_intact_copier (0x[0-9a-f]+)', copy)
assert [int(x) for x in g.groups()[:6]] == [ever, fmod, walkers, cop_ever, cop_final, cop_intact], (g.groups(), ever, fmod, walkers, cop_ever, cop_final, cop_intact)
assert cop_intact == 0 or int(g[7], 16) == imin
gh = {int(x): int(c) for x, c in re.findall(r' (\d+):(\d+)', copy.split('first_full_hist')[1].split('\n')[0])}
assert gh == dict(first), (gh, dict(first))
got_list = {int(pg, 16): (int(fs), int(it), int(ps), int(of)) for pg, fs, it, ps, of in re.findall(r'copier (0x[0-9a-f]+) first (\d+) intact (\d+) persists (\d+) offset (\d+)', copy)}
assert got_list == listed, (len(got_list), len(listed), sorted(got_list.items())[:3], sorted(listed.items())[:3])
print(f'{fn}: W={W} a={a} {hi - lo} programs' + (f', {functions} functions' if functions is not None else ' (copy-only)') + f'; final {dict(sorted(final.items()))}; best {dict(sorted(best.items()))}; ever_mod {ever} final_mod {fmod} walkers {walkers} copiers ever/final/intact {cop_ever}/{cop_final}/{cop_intact}: all agree with Python')
