"""Fast (numpy) merge of u1 shard files: same checks and JSON as fast/merge.py, plus an optional binary map of the
distinct (key_lo, key_hi, min program) records sorted by key (--map out.npy), for the exp09 per-step maps.
usage: python3 fast/merge_np.py <shards...> --out result.json [--map map.npy] [--quiet]"""
import argparse, json, math, struct
from pathlib import Path
import numpy as np
PNAME = ["NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR",
  "ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP",
  "JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND"]
REC = np.dtype([('klo', '<u8'), ('khi', '<u8'), ('prog', '<u4')])

def read_shard(fn):
    b = Path(fn).read_bytes()
    hdr = struct.unpack_from('<8I', b, 0); lo, hi, n = struct.unpack_from('<3Q', b, 32)
    assert hdr[0] == 0x55314231, fn
    nisa = hdr[7]; isa = list(b[56:56 + nisa]); off = 56 + nisa
    assert len(b) == off + n * 20, f'{fn}: size mismatch'
    return hdr, isa, (lo, hi), np.frombuffer(b, dtype=REC, count=n, offset=off)

def merge(files):
    hdr0 = isa0 = None; covered = []; parts = []
    for fn in files:
        hdr, isa, rng, rec = read_shard(fn)
        if hdr0 is None: hdr0, isa0 = hdr, isa
        assert hdr[1:] == hdr0[1:] and isa == isa0, f'shard {fn} has a different config'
        covered.append(rng); parts.append(rec)
    allrec = np.concatenate(parts) if parts else np.zeros(0, REC)
    order = np.lexsort((allrec['prog'], allrec['khi'], allrec['klo']))   # key ascending, then program ascending
    s = allrec[order]
    first = np.ones(len(s), bool); first[1:] = (s['klo'][1:] != s['klo'][:-1]) | (s['khi'][1:] != s['khi'][:-1])
    merged = s[first]                                                    # first of each key = minimum program
    covered.sort(); gaps = []; cur = covered[0][0] if covered else 0
    for lo, hi in covered:
        if lo > cur: gaps.append((cur, lo))
        cur = max(cur, hi)
    return hdr0, isa0, covered, gaps, merged

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--out', required=True); ap.add_argument('--map'); ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    hdr, isa, covered, gaps, merged = merge(args.files)
    W, a, p, I, o, binary = hdr[1:7]; nin = 1 << W; ntab = nin * nin if binary else nin; universe = nin ** ntab
    res = {'W': W, 'a': a, 'p': p, 'I': I, 'opcode_bits': o, 'binary': bool(binary), 'isa': [PNAME[i] for i in isa], 'program_bits': (1 << p) * I,
           'programs_covered': [[lo, hi] for lo, hi in covered], 'gaps': gaps, 'distinct_operators': int(len(merged)), 'operator_universe': universe,
           'fraction': len(merged) / universe, 'fraction_log10': math.log10(len(merged)) - math.log10(universe) if len(merged) else None, 'merged_with': 'fast/merge_np.py'}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True); Path(args.out).write_text(json.dumps(res, indent=1))
    if args.map: np.save(args.map, merged)
    if not args.quiet: print(f'{len(merged)} distinct operators / {universe} universe; gaps={gaps} -> {args.out}')

if __name__ == '__main__':
    main()
