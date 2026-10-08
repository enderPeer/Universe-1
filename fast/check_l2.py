"""Validate a gpu/u1_l2 shard (+ .copy file) against the Python L2 reference (sim/machine_l2.py) on its full program range.
Intended for small ranges (a few thousand programs): recomputes every program's unary table and copy score in Python and
compares the distinct-key set, the minimum program per key, the copy-score histogram and the per-score minimum program.
usage: python fast/check_l2.py <shard.bin>"""
import re, struct, sys
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
ref = {}; scores = {}; score_min = {}
for prog in range(lo, hi):
    t = m.table_unary(prog); k = 0
    for i, v in enumerate(t): k |= v << (4 * i)
    key = (k, 0)
    if key not in ref or prog < ref[key]: ref[key] = prog
    sc, _ = m.copy_score(prog); scores[sc] = scores.get(sc, 0) + 1; score_min[sc] = min(score_min.get(sc, prog), prog)
assert set(gpu) == set(ref), f'key sets differ: {len(gpu)} vs {len(ref)}'
assert all(gpu[k] == ref[k] for k in ref), 'minimum programs differ'
copy = Path(fn + '.copy').read_text(); got = {int(a): (int(c), int(p, 16)) for a, c, p in re.findall(r'score (\d+) count (\d+) min_program (0x[0-9a-f]+)', copy)}
for sc in range(nins + 1):
    cnt, mp = got[sc]; assert cnt == scores.get(sc, 0), (sc, cnt, scores.get(sc, 0)); assert cnt == 0 or mp == score_min[sc], (sc, mp, score_min.get(sc))
print(f'{fn}: {hi - lo} programs, {len(ref)} distinct functions and the copy histogram {dict(sorted(scores.items()))} agree with Python')
