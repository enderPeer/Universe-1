"""Merge shard files from fast/u1 into one result.
Usage: python3 fast/merge.py results/shards/exp03_W4_*.bin --out results/exp03_W4.json"""
import argparse, json, math, struct, sys
from pathlib import Path
PNAME = ["NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR",
  "ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP",
  "JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--out", required=True)
    ap.add_argument("--dump-tables", action="store_true", help="include decoded tables (W<=4 unary only)")
    args = ap.parse_args()
    merged = {}; covered = []; hdr0 = None; isa = None
    for fn in args.files:
        b = Path(fn).read_bytes()
        hdr = struct.unpack_from("<8I", b, 0); lo, hi, n = struct.unpack_from("<3Q", b, 32)
        assert hdr[0] == 0x55314231, fn
        nisa = hdr[7]; isa_ids = list(b[56:56 + nisa]); off = 56 + nisa
        if hdr0 is None: hdr0, isa = hdr, isa_ids
        assert hdr[1:] == hdr0[1:] and isa_ids == isa, f"shard {fn} has a different config"
        covered.append((lo, hi))
        for i in range(n):
            klo, khi, prog = struct.unpack_from("<QQI", b, off + i * 20)
            k = (klo, khi)
            if k not in merged or prog < merged[k]: merged[k] = prog
    covered.sort(); gaps = []; cur = covered[0][0]
    for lo, hi in covered:
        if lo > cur: gaps.append((cur, lo))
        cur = max(cur, hi)
    W, a, p, I, o, binary = hdr0[1:7]
    nin = 1 << W; ntab = nin * nin if binary else nin
    universe = nin ** ntab
    res = {"W": W, "a": a, "p": p, "I": I, "opcode_bits": o, "binary": bool(binary),
           "isa": [PNAME[i] for i in isa], "program_bits": (1 << p) * I,
           "programs_covered": [[lo, hi] for lo, hi in covered], "gaps": gaps,
           "distinct_operators": len(merged), "operator_universe": universe,
           "fraction": len(merged) / universe,
           "fraction_log10": math.log10(len(merged)) - math.log10(universe) if merged else None}
    if args.dump_tables and not binary and ntab * W <= 128:
        tabs = []
        for (klo, khi), prog in sorted(merged.items(), key=lambda kv: kv[1]):
            v = klo | (khi << 64); tabs.append({"table": [(v >> (i * W)) & (nin - 1) for i in range(ntab)], "program": prog})
        res["tables"] = tabs
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=1))
    print(f"{len(merged)} distinct operators / {universe} universe; gaps={gaps} -> {args.out}")

if __name__ == "__main__":
    main()
