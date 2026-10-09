"""exp11 analysis of a viable-genome table (results/exp11/<name>_viable.tsv from cluster/exp11_node.py --combine, or any file with
one genome per line): counts by depth, intact and copy-true fractions, fecundity and first-divide distributions, instructions present
in every genome, monomer frequencies, rotation classes, one-substitution (Hamming-1) clusters and the largest cluster sizes.
usage: python fast/exp11_analyze.py FILE [--json OUT.json]      (a .tsv with a header is read by column; otherwise one genome per line)"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim import avida

def load(fn):
    lines = [l.rstrip('\n') for l in Path(fn).read_text().splitlines() if l.strip()]
    if lines[0].startswith('genome\t'):
        cols = lines[0].split('\t'); rows = []
        for l in lines[1:]:
            v = l.split('\t'); d = dict(zip(cols, v)); rows.append({k: (d[k] if k == 'genome' else int(d[k])) for k in cols})
        return rows
    return [dict(genome=l.strip()) for l in lines]

def clusters(genomes):
    """connected components of the Hamming-distance-1 graph over the 26-letter alphabet (union-find over single substitutions)."""
    idx = {g: i for i, g in enumerate(genomes)}; parent = list(range(len(genomes)))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for g in genomes:
        for p in range(len(g)):
            for c in avida.ALPHABET:
                if c == g[p]: continue
                h = g[:p] + c + g[p + 1:]
                if h in idx: parent[find(idx[g])] = find(idx[h])
    comp = Counter(find(i) for i in range(len(genomes)))
    return sorted(comp.values(), reverse=True)

def analyze(rows):
    genomes = [r['genome'] for r in rows]; n = len(genomes); L = len(genomes[0]) if genomes else 0
    res = dict(viable=n, length=L)
    if n == 0: return res
    rot = {min(g[i:] + g[:i] for i in range(L)) for g in genomes}; res['distinct_up_to_rotation'] = len(rot)
    present = Counter(); mono = Counter()
    for g in genomes:
        for c in set(g): present[c] += 1
        mono.update(g)
    res['in_every_genome'] = [avida.NAMES[avida.ALPHABET.index(c)] for c in avida.ALPHABET if present[c] == n]
    res['monomer_fraction'] = {avida.NAMES[avida.ALPHABET.index(c)]: round(present[c] / n, 3) for c in avida.ALPHABET}
    res['instruction_frequency'] = {avida.NAMES[avida.ALPHABET.index(c)]: mono[c] for c in avida.ALPHABET}
    sizes = clusters(genomes); res['clusters'] = len(sizes); res['largest_clusters'] = sizes[:8]; res['singletons'] = sum(s == 1 for s in sizes)
    res['multisets'] = len({''.join(sorted(g)) for g in genomes})
    if 'depth' in rows[0]:
        res['depth'] = dict(Counter(r['depth'] for r in rows)); res['intact'] = sum(r['intact'] for r in rows); res['copy_true'] = sum(r['copy_true'] for r in rows)
        res['fecundity_hist'] = dict(sorted(Counter(r['fecundity'] for r in rows).items())); res['fecundity_true_hist'] = dict(sorted(Counter(r['fecundity_true'] for r in rows).items()))
        res['first_divide_hist'] = dict(sorted(Counter(r['first_divide'] for r in rows).items()))
        fd = sorted(r['first_divide'] for r in rows); res['first_divide_min_median_max'] = [fd[0], fd[len(fd) // 2], fd[-1]]
    return res

if __name__ == '__main__':
    rows = load(sys.argv[1]); res = analyze(rows)
    if '--json' in sys.argv: Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        if k in ('monomer_fraction', 'instruction_frequency'): continue
        print(f'{k}: {v}')
    print('monomer fraction (share of genomes containing the instruction):', ', '.join(f'{k} {v}' for k, v in sorted(res.get('monomer_fraction', {}).items(), key=lambda kv: -kv[1]) if v > 0))
