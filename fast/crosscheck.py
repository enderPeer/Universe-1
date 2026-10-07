"""Verify fast/u1 against the Python reference on random programs.
Usage: python3 fast/crosscheck.py [--W 4 --a 2 --p 3 --isa ...] [--n 300]"""
import argparse, random, struct, subprocess, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.machine import Config, Machine

def read_shard(path):
    b = Path(path).read_bytes()
    hdr = struct.unpack_from("<8I", b, 0); lo, hi, n = struct.unpack_from("<3Q", b, 32)
    nisa = hdr[7]; off = 56 + nisa
    recs = {}
    for i in range(n):
        klo, khi, prog = struct.unpack_from("<QQI", b, off + i * 20)
        recs[(klo, khi)] = prog
    return hdr, lo, hi, recs

M64 = (1 << 64) - 1
def mix(x):
    x ^= x >> 33; x = (x * 0xff51afd7ed558ccd) & M64; x ^= x >> 33; x = (x * 0xc4ceb9fe1a85ec53) & M64; x ^= x >> 33; return x
def key(tbl, W):
    if len(tbl) * W <= 128:
        v = 0
        for i, t in enumerate(tbl): v |= t << (i * W)
        return (v & M64, v >> 64)
    a, b = 0x9E3779B97F4A7C15, 0xD1B54A32D192ED03
    for t in tbl: a = mix(a ^ t); b = mix((b + t * 0x100000001b3) & M64)
    return (a, b)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=4); ap.add_argument("--a", type=int, default=2)
    ap.add_argument("--p", type=int, default=3); ap.add_argument("--I", type=int, default=None)
    ap.add_argument("--isa", default="LD,ST,LDI,NAND,ADD,SHL,JZ,HALT")
    ap.add_argument("--n", type=int, default=300); ap.add_argument("--binary", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    cfg = Config(W=args.W, a=args.a, p=args.p, I=args.I)
    isa = tuple(args.isa.split(","))
    m = Machine(cfg, isa)
    nbits = (1 << cfg.p) * cfg.I
    rng = random.Random(args.seed)
    bad = 0
    u1 = Path(__file__).resolve().parent / "u1"
    for _ in range(args.n):
        pb = rng.getrandbits(nbits)
        code = [(pb >> (k * cfg.I)) & ((1 << cfg.I) - 1) for k in range(1 << cfg.p)]
        tt = m.truth_table_binary(code) if args.binary else m.truth_table_unary(code)
        with tempfile.NamedTemporaryFile(delete=False) as f: out = f.name
        cmd = [str(u1), "--W", str(cfg.W), "--a", str(cfg.a), "--p", str(cfg.p), "--I", str(cfg.I),
               "--isa", args.isa, "--lo", str(pb), "--hi", str(pb + 1), "--out", out, "--threads", "1"]
        if args.binary: cmd.append("--binary")
        subprocess.run(cmd, check=True, capture_output=True)
        _, _, _, recs = read_shard(out); os.unlink(out)
        ck = list(recs)[0]
        if ck != key(tt, cfg.W):
            bad += 1; print("MISMATCH prog", pb, "py", tt, "c", ck)
    print(f"{args.n - bad}/{args.n} programs agree")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
