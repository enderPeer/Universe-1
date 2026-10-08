"""Validate a gpu/u1_l2 shard (+ .copy file) against the Python L2 reference (sim/machine_l2.py) on its full program range.
Intended for small ranges (a few thousand programs): recomputes every program's unary table and exp06b statistics in Python and
compares the distinct-key set, the minimum program per key, the final/best copy-score histograms with their minimum programs,
the ever-modified / final-modified / walker counts, the copier counts (ever, persisting, intact) and the first-copy step histogram.
usage: python fast/check_l2.py <shard.bin>"""
import re, struct, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.machine_l2 import ConfigL2, MachineL2
from merge import PNAME
fn = sys.argv[1]; b = Path(fn).read_bytes(); hdr = struct.unpack_from('<8I', b, 0); lo, hi, n = struct.unpack_from('<3Q', b, 32)
nisa = hdr[7]; isa = tuple(PNAME[i] for i in b[56:56 + nisa]); off = 56 + nisa
cfg = ConfigL2(W=hdr[1], a=hdr[2], p=hdr[3], I=hdr[4]); m = MachineL2(cfg, isa); nins = 1 << cfg.p
gpu = {}
for i in range(n):
    klo, khi, prog = struct.unpack_from('<QQI', b, off + i * 20); gpu[(klo, khi)] = prog
ref = {}; final = Counter(); best = Counter(); fmin = {}; bmin = {}; ever = fmod = walkers = cop_ever = cop_final = cop_intact = 0; first = Counter(); imin = None
for prog in range(lo, hi):
    t = m.table_unary(prog); k = 0
    for i, v in enumerate(t): k |= v << (4 * i)
    key = (k, 0)
    if key not in ref or prog < ref[key]: ref[key] = prog
    S = m.stats(prog)
    final[S['final']] += 1; best[S['best']] += 1; fmin[S['final']] = min(fmin.get(S['final'], prog), prog); bmin[S['best']] = min(bmin.get(S['best'], prog), prog)
    ever += S['ever_mod']; fmod += S['final_mod']; walkers += S['walker']
    if S['best'] == nins:
        cop_ever += 1; first[S['first_full']] += 1; cop_final += S['final'] == nins
        if S['intact']: cop_intact += 1; imin = prog if imin is None else min(imin, prog)
assert set(gpu) == set(ref), f'key sets differ: {len(gpu)} vs {len(ref)}'
assert all(gpu[k] == ref[k] for k in ref), 'minimum programs differ'
copy = Path(fn + '.copy').read_text()
for tag, hist, mins in (('final', final, fmin), ('best', best, bmin)):
    got = {int(a): (int(c), int(p, 16)) for a, c, p in re.findall(tag + r' (\d+) count (\d+) min_program (0x[0-9a-f]+)', copy)}
    for sc in range(nins + 1):
        cnt, mp = got[sc]; assert cnt == hist.get(sc, 0), (tag, sc, cnt, hist.get(sc, 0)); assert cnt == 0 or mp == mins[sc], (tag, sc, mp, mins.get(sc))
g = re.search(r'ever_mod (\d+) final_mod (\d+) walkers (\d+) copiers_ever (\d+) copiers_final (\d+) copiers_intact (\d+) min_intact_copier (0x[0-9a-f]+)', copy)
assert [int(x) for x in g.groups()[:6]] == [ever, fmod, walkers, cop_ever, cop_final, cop_intact], (g.groups(), ever, fmod, walkers, cop_ever, cop_final, cop_intact)
assert cop_intact == 0 or int(g[7], 16) == imin
gh = {int(a): int(c) for a, c in re.findall(r' (\d+):(\d+)', copy.split('first_full_hist')[1].split('\n')[0])}
assert gh == dict(first), (gh, dict(first))
print(f'{fn}: {hi - lo} programs, {len(ref)} functions; final {dict(sorted(final.items()))}; best {dict(sorted(best.items()))}; ever_mod {ever} final_mod {fmod} walkers {walkers} copiers ever/final/intact {cop_ever}/{cop_final}/{cop_intact}: all agree with Python')
