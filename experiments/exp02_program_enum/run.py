"""Experiment 02: fixed ISA, enumerate (or sample) all programs, run each for
<= 256 steps over all inputs, collect distinct unary and binary operators.

Usage: python -m experiments.exp02_program_enum.run --W 2 --a 2 --p 3 \
       --isa LD,ST,NAND,JZ
"""
import argparse, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.machine import Config, Machine, state_bits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=2)
    ap.add_argument("--a", type=int, default=2)
    ap.add_argument("--p", type=int, default=3)
    ap.add_argument("--I", type=int, default=None)
    ap.add_argument("--isa", required=True, help="comma list, length power of two")
    ap.add_argument("--max-programs", type=int, default=None)
    ap.add_argument("--binary", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    cfg = Config(W=args.W, a=args.a, p=args.p, I=args.I)
    isa = tuple(args.isa.split(","))
    m = Machine(cfg, isa)
    nbits = (1 << cfg.p) * cfg.I
    total = 1 << nbits
    rng = random.Random(args.seed)
    it = range(total) if (args.max_programs is None or total <= args.max_programs) \
        else (rng.getrandbits(nbits) for _ in range(args.max_programs))
    un, bi, reasons = {}, {}, {"halt": 0, "budget": 0, "loop": 0}
    t0 = time.time(); n = 0
    for pb in it:
        n += 1
        code = [(pb >> (k * cfg.I)) & ((1 << cfg.I) - 1) for k in range(1 << cfg.p)]
        tt = m.truth_table_unary(code)
        if tt is not None and tt not in un:
            un[tt] = pb
        if args.binary:
            tb = m.truth_table_binary(code)
            if tb is not None and tb not in bi:
                bi[tb] = pb
        _, _, why = m.run(code)
        reasons[why] += 1
    W = cfg.W
    summary = {"cfg": vars(cfg), "isa": isa, "state_bits": state_bits(cfg),
               "programs_run": n, "seconds": round(time.time() - t0, 2),
               "unary_found": len(un), "unary_universe": (1 << W) ** (1 << W),
               "binary_found": len(bi) if args.binary else None,
               "binary_universe": (1 << W) ** (1 << (2 * W)) if args.binary else None,
               "run_reasons_input0": reasons,
               "unary_tables": {str(k): v for k, v in un.items()},
               "binary_tables": {str(k): v for k, v in bi.items()} if args.binary else {}}
    out = args.out or f"results/exp02_W{W}_{'_'.join(isa)}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(summary, indent=1))
    print(f"W={W} isa={isa}: {n} programs, unary {len(un)}/{summary['unary_universe']}"
          + (f", binary {len(bi)}/{summary['binary_universe']}" if args.binary else "")
          + f" -> {out}")

if __name__ == "__main__":
    main()
