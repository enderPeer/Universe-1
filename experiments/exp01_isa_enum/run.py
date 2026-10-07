"""Experiment 01: enumerate ISAs for width W and score each by the number of
distinct unary operators (truth tables) realizable by exhaustive program
enumeration within 256 steps.

Usage: python -m experiments.exp01_isa_enum.run --W 1 --a 2 --p 2
Exhaustive for W<=2 with small p; use --max-isas / --max-programs to sample.
"""
import argparse, itertools, json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.machine import Config, Machine, PRIMS, state_bits

def score_isa(cfg, isa, max_programs, rng):
    m = Machine(cfg, isa)
    nprog_bits = (1 << cfg.p) * cfg.I
    total = 1 << nprog_bits
    tables = set()
    if max_programs is None or total <= max_programs:
        it = range(total)
    else:
        it = (rng.getrandbits(nprog_bits) for _ in range(max_programs))
    for pb in it:
        code = [(pb >> (k * cfg.I)) & ((1 << cfg.I) - 1) for k in range(1 << cfg.p)]
        tt = m.truth_table_unary(code)
        if tt is not None:
            tables.add(tt)
    return tables

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--W", type=int, default=1)
    ap.add_argument("--a", type=int, default=2)
    ap.add_argument("--p", type=int, default=2)
    ap.add_argument("--I", type=int, default=None)
    ap.add_argument("--prims", default=",".join(PRIMS))
    ap.add_argument("--max-isas", type=int, default=None)
    ap.add_argument("--max-programs", type=int, default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    cfg = Config(W=args.W, a=args.a, p=args.p, I=args.I)
    prims = args.prims.split(",")
    nops = 1 << cfg.I  # opcode count when opcode field = whole instruction
    # minimal opcode field: we let opcode take o bits, operand takes I-o. Try all o.
    rng = random.Random(args.seed)
    results = []
    t0 = time.time()
    for o in range(1, cfg.I + 1):
        n = 1 << o
        combos = itertools.combinations_with_replacement(prims, n)
        if args.max_isas:
            combos = itertools.islice(combos, args.max_isas)
        for isa in combos:
            tables = score_isa(cfg, isa, args.max_programs, rng)
            results.append({"opcode_bits": o, "isa": isa, "score": len(tables),
                            "tables": sorted(tables)})
    results.sort(key=lambda r: -r["score"])
    unary_universe = (1 << cfg.W) ** (1 << cfg.W)
    summary = {"cfg": vars(cfg), "state_bits": state_bits(cfg),
               "unary_operator_universe": unary_universe,
               "isas_evaluated": len(results), "seconds": round(time.time() - t0, 2),
               "top": results[:20]}
    out = args.out or f"results/exp01_W{cfg.W}_a{cfg.a}_p{cfg.p}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(summary, indent=1))
    print(f"W={cfg.W} a={cfg.a} p={cfg.p}: {len(results)} ISAs, best score "
          f"{results[0]['score']}/{unary_universe}: {results[0]['isa']} -> {out}")

if __name__ == "__main__":
    main()
