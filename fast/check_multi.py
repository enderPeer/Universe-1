"""Check every-step shards (gpu/u1_multi) against the Python reference machine for steps beyond 256 (exp10) or any T.

For each shard <prefix>.T<nnn>.bin given: (1) a seeded sample of its records is re-executed for exactly T steps on all 16
inputs and must reproduce the key; (2) a seeded sample of programs from the shard's range is executed for T steps and its
key must be present in the shard. usage: python3 fast/check_multi.py <shard.T257.bin> [...] [--records 64] [--programs 64]
"""
import argparse, random, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.machine import Config, Machine
from merge import PNAME

ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--records', type=int, default=64); ap.add_argument('--programs', type=int, default=64)
args = ap.parse_args(); rng = random.Random(10); total = 0

def key_of(machine, cfg, program, T):
    code = [(program >> (k * cfg.I)) & ((1 << cfg.I) - 1) for k in range(1 << cfg.p)]
    klo = 0
    for x in range(1 << cfg.W):
        st, steps, reason = machine.run(code, init_A=x, max_steps=T)
        klo |= (st.A & cfg.mask) << (x * cfg.W)
    return klo

for fn in args.files:
    b = Path(fn).read_bytes(); hdr = struct.unpack_from('<8I', b, 0); lo, hi, n = struct.unpack_from('<3Q', b, 32)
    nisa = hdr[7]; isa = tuple(PNAME[i] for i in b[56:56 + nisa]); off = 56 + nisa
    assert hdr[0] == 0x55314231 and not hdr[6], 'unary v1 shard expected'
    T = int(Path(fn).name.rsplit('.T', 1)[1][:3])
    cfg = Config(W=hdr[1], a=hdr[2], p=hdr[3], I=hdr[4]); machine = Machine(cfg, isa)
    keys = {}
    for i in range(n):
        klo, khi, prog = struct.unpack_from('<QQI', b, off + i * 20); keys[klo] = prog
    for i in rng.sample(range(n), min(args.records, n)):
        klo, khi, prog = struct.unpack_from('<QQI', b, off + i * 20)
        assert lo <= prog < hi, (fn, prog)
        k = key_of(machine, cfg, prog, T); assert k == klo, (fn, T, prog, hex(k), hex(klo)); total += 1
    for prog in rng.sample(range(lo, hi), min(args.programs, hi - lo)):
        k = key_of(machine, cfg, prog, T); assert k in keys and keys[k] <= prog, (fn, T, prog, hex(k)); total += 1
    print(f'{Path(fn).name}: T={T}, {n} records, {min(args.records, n)} witnesses and {min(args.programs, hi - lo)} programs agree with Python', flush=True)
print(f'TOTAL: {total} checks passed')
