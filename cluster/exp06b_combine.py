"""Combine partial exp06b/exp06c results (<name>.part_a-b.json from cluster/exp06b_node.py --chunk-range on several nodes) into
<name>.json: histograms and counts are summed, minimum programs taken, copier lists concatenated, and the program ranges must
tile [0, 2^(2^p * I)) exactly. usage: python cluster/exp06b_combine.py results/exp06b/l2c_crawl_w5_a5.part_*.json"""
import json, sys
from pathlib import Path
parts = [json.loads(Path(f).read_text()) for f in sys.argv[1:]]; assert parts
name = parts[0]['name']; p, I = parts[0]['p'], parts[0]['I']; SPAN = 1 << ((1 << p) * I); nins = 1 << p
rng = sorted(tuple(x['program_range']) for x in parts); cur = 0
for lo, hi in rng: assert lo == cur, f'gap or overlap at {cur}'; cur = hi
assert cur == SPAN, f'ranges end at {cur}, expected {SPAN}'
out = dict(parts[0]); out['programs'] = SPAN; out['program_range'] = [0, SPAN]; out['gpus'] = sorted({g for x in parts for g in x['gpus']}); out['wall_seconds'] = max(x['wall_seconds'] for x in parts)
out['programs_per_second'] = SPAN / sum(x['wall_seconds'] for x in parts); out['combined_from'] = [x['program_range'] for x in parts]
for key in ('final_score_counts', 'best_score_counts'): out[key] = {str(s): sum(x[key].get(str(s), 0) for x in parts) for s in range(nins + 1)}
for key in ('first_full_copy_step_histogram', 'copy_offset_histogram'):
    acc = {}
    for x in parts:
        for k, v in x[key].items(): acc[int(k)] = acc.get(int(k), 0) + v
    out[key] = dict(sorted(acc.items()))
for key in ('ever_mod', 'final_mod', 'walkers', 'copiers_ever', 'copiers_final', 'copiers_intact', 'copiers_listed'): out[key] = sum(x[key] for x in parts)
for key in ('final_score_min_program', 'best_score_min_program'):
    acc = {}
    for x in parts:
        for s, pg in x[key].items():
            if s not in acc or int(pg, 16) < int(acc[s], 16): acc[s] = pg
    out[key] = dict(sorted(acc.items(), key=lambda kv: int(kv[0])))
mins = [x['min_intact_copier'] for x in parts if x['min_intact_copier']]; out['min_intact_copier'] = min(mins, key=lambda h: int(h, 16)) if mins else None
out['copiers_sample'] = sorted((c for x in parts for c in x['copiers_sample']), key=lambda c: int(c['program'], 16))[:500]
out['intact_copiers_sample'] = sorted((c for x in parts for c in x['intact_copiers_sample']), key=lambda c: int(c['program'], 16))[:500]
if any(x['distinct_unary_functions'] is None for x in parts): out['distinct_unary_functions'] = None
Path(sys.argv[1]).with_name(f'{name}.json').write_text(json.dumps(out, indent=1)); print(f"{name}: combined {len(parts)} parts; copiers ever {out['copiers_ever']:,} final {out['copiers_final']:,} intact {out['copiers_intact']:,}")
