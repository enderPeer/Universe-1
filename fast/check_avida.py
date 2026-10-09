"""Validate a gpu/u1_avida (CUDA, emulation or Vulkan) list-mode run against the Python reference (sim/avida.py).
usage: python fast/check_avida.py --make N SEED OUT.txt [--len L]    write N random genomes of length L (plus the 914 published
                                                                   length-8 replicators when L = 8) to OUT.txt, one per line
       python fast/check_avida.py ENGINE_OUT                        ENGINE_OUT = output of u1_avida --genomes OUT.txt --out ENGINE_OUT;
                                                                   every listed genome is re-run on the reference and viable, depth,
                                                                   first-divide cycle, intact, copy-true, fecundity and copy-true
                                                                   fecundity are compared; the first mismatch is printed with a trace."""
import random, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim import avida
ROOT = Path(__file__).resolve().parents[1]
if sys.argv[1] == '--make':
    n, seed, out = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; L = int(sys.argv[sys.argv.index('--len') + 1]) if '--len' in sys.argv else 8
    rng = random.Random(seed); lines = []
    if L == 8: lines += [l.strip() for l in (ROOT / 'results/exp11/figshare/len8').read_text().splitlines() if l.strip()]
    lines += [''.join(rng.choice(avida.ALPHABET) for _ in range(L)) for _ in range(n)]
    Path(out).write_text('\n'.join(lines) + '\n'); print(f'{out}: {len(lines)} genomes of length {L}'); sys.exit(0)
txt = Path(sys.argv[1]).read_text(); head = txt.splitlines()[0]
h = re.match(r'avida len (\d+) genomes \[(\d+),(\d+)\) budget (\d+) gens (\d+)( list-mode)?', head); L = int(h[1]); assert h[6], 'engine must be run with --genomes (list mode)'
rows = re.findall(r'genome ([a-z]+) index (\d+) viable (\d) depth (-?\d+) first (\d+) intact (\d) copy_true (\d) fecundity (\d+) fecundity_true (\d+)', txt)
assert len(rows) == int(h[3]) - int(h[2]), (len(rows), head)
bad = 0; viable = 0
for g, idx, v, d, first, intact, ct, fec, fect in rows:
    assert avida.index_of(avida.parse(g)) == int(idx), (g, idx)
    r = avida.run_test(g); got = (int(v), int(d), int(first), int(intact), int(ct), min(int(fec), 511), min(int(fect), 511))
    exp = (int(r['viable']), r['depth_found'], r['first_divide_step'], int(r['intact']), int(r['copy_true']), min(r['fecundity'], 511), min(r['fecundity_true'], 511))
    viable += exp[0]
    if got != exp:
        bad += 1
        if bad <= 5:
            print(f'MISMATCH {g}: engine (viable, depth, first, intact, copy_true, fecundity, fecundity_true) = {got}, reference = {exp}')
            tr = []; avida.gestation(avida.parse(g), tr)
            for s in tr[:40]: print('   ', s)
if bad: print(f'{sys.argv[1]}: {bad} of {len(rows)} genomes DIFFER from the reference'); sys.exit(1)
print(f'{sys.argv[1]}: {len(rows)} genomes of length {L}, {viable} viable: engine and reference agree on every field')
