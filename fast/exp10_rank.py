"""exp10 ranking: what is new beyond step 256, and which of it is worth using.

Reads results/exp09/<name>/union_1-512.npy (key, minT, prog, nT over T = 1..512) and the per-T counts, and writes
results/exp10_<name>_summary.md + results/exp09/<name>/exp10_rank.json + ranked lists:
- growth beyond 256 (functions first appearing at T > 256, per step), persistence of new vs old functions;
- structural classes of the new functions (constants, bijections, image size, bits depended on) computed from the packed keys;
- named functions (the catalog of fast/map_functions.py) that exist ONLY beyond step 256, or whose minimal T is > 256;
- the top new functions ranked by persistence (number of steps at which they occur), with program, minimal T and disassembly.
usage: python fast/exp10_rank.py [--name w4_o2_add] [--isa SWAP,ADD,NAND,SKZ] [--top 40]
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'fast'))
from map_functions import catalog
ap = argparse.ArgumentParser(); ap.add_argument('--name', default='w4_o2_add'); ap.add_argument('--isa', default='SWAP,ADD,NAND,SKZ'); ap.add_argument('--top', type=int, default=40)
args = ap.parse_args(); D = ROOT / 'results/exp09' / args.name
u = np.load(D / 'union_1-512.npy', mmap_mode='r'); s512 = json.loads((D / 'summary_1-512.json').read_text()); s256 = json.loads((D / 'summary.json').read_text())
minT = np.asarray(u['minT']); nT = np.asarray(u['nT']); new = minT > 256
n_all, n_new = len(u), int(new.sum()); c512 = {int(k): v for k, v in s512['per_T_distinct'].items()}
print(f'union 1..512: {n_all:,}; new beyond 256: {n_new:,}', flush=True)

def nibbles(keys):  # (n, 16) uint8 table entries from packed 64-bit keys
    return ((keys[:, None] >> (4 * np.arange(16, dtype=np.uint64))) & np.uint64(15)).astype(np.uint8)
def classes(keys, chunk=4_000_000):
    out = dict(constant=0, bijective=0, involution=0, idempotent=0, depend_all_bits=0, image_hist=np.zeros(17, np.int64), depends_hist=np.zeros(16, np.int64))
    x = np.arange(16, dtype=np.uint8)
    for i in range(0, len(keys), chunk):
        t = nibbles(np.asarray(keys[i:i + chunk], dtype=np.uint64)); n = len(t)
        srt = np.sort(t, axis=1); img = 1 + (srt[:, 1:] != srt[:, :-1]).sum(1)
        out['image_hist'] += np.bincount(img, minlength=17); out['constant'] += int((img == 1).sum()); bij = img == 16; out['bijective'] += int(bij.sum())
        ft = np.take_along_axis(t, t.astype(np.intp), axis=1)           # f(f(x))
        out['involution'] += int((bij & (ft == x).all(1)).sum()); out['idempotent'] += int((ft == t).all(1).sum())
        dep = np.zeros(n, np.uint8)
        for b in range(4):
            xb = x ^ (1 << b); dep |= ((t != t[:, xb]).any(1).astype(np.uint8) << b)
        out['depends_hist'] += np.bincount(dep, minlength=16); out['depend_all_bits'] += int((dep == 15).sum())
    out['image_hist'] = out['image_hist'].tolist(); out['depends_hist'] = out['depends_hist'].tolist(); return out
keys = np.asarray(u['key']); cls_new = classes(keys[new]); cls_old = classes(keys[~new])
print('classes done', flush=True)

# named functions: catalog tables -> packed key
names = {}
for name, expr, table in catalog(4, False):
    k = 0
    for i, v in enumerate(table): k |= (int(v) & 15) << (4 * i)
    names.setdefault(k, []).append((name, expr))
cat_keys = np.array(sorted(names), dtype=np.uint64); pos = np.searchsorted(keys, cat_keys); hit = (pos < len(keys)) & (keys[np.minimum(pos, len(keys) - 1)] == cat_keys)
named_rows = []
for k, p in zip(cat_keys[hit], pos[hit]):
    named_rows.append(dict(names=[n for n, _ in names[int(k)]], expression=names[int(k)][0][1], key=f'0x{int(k):016x}', minT=int(minT[p]), nT=int(nT[p]), program=f'0x{int(u["prog"][p]):08x}'))
named_new = [r for r in named_rows if r['minT'] > 256]; named_total = len(named_rows)
print(f'named: {named_total} catalog tables present in 1..512, {len(named_new)} of them only beyond 256', flush=True)

def disasm(prog, isa):
    isa = isa.split(','); o = max(1, (len(isa) - 1).bit_length()); I = 4
    return '; '.join(f'{isa[((prog >> (4 * k)) & 15) >> (I - o)]} {((prog >> (4 * k)) & 15) & ((1 << (I - o)) - 1)}' for k in range(8))
idx_new = np.flatnonzero(new); order = idx_new[np.lexsort((minT[idx_new], -nT[idx_new].astype(np.int32)))][:args.top]
top = [dict(key=f'0x{int(u["key"][i]):016x}', table=[int((int(u['key'][i]) >> (4 * x)) & 15) for x in range(16)], minT=int(minT[i]), nT=int(nT[i]), program=f'0x{int(u["prog"][i]):08x}',
            asm=disasm(int(u['prog'][i]), args.isa), names=[n for n, _ in names.get(int(u['key'][i]), [])]) for i in order]
first_new = s512['minT_histogram']; per_step_new = {T: first_new[T] for T in range(257, 513)}
pers_new = np.bincount(nT[new], minlength=513); pers_old = np.bincount(nT[~new], minlength=513)
out = dict(name=args.name, isa=args.isa, union_512=n_all, union_256=s256['union'], new_beyond_256=n_new, T256_set=c512[256], T512_set=c512[512],
           peak=max(c512, key=c512.get), peak_count=c512[max(c512, key=c512.get)], first_new_per_step=per_step_new,
           persistence_new=dict(one_step=int(pers_new[1]), median=int(np.flatnonzero(np.cumsum(pers_new) >= n_new / 2)[0]), ge_64=int(pers_new[64:].sum()), ge_128=int(pers_new[128:].sum()), ge_256=int(pers_new[256:].sum())),
           persistence_old=dict(one_step=int(pers_old[1]), median=int(np.flatnonzero(np.cumsum(pers_old) >= (n_all - n_new) / 2)[0]), ge_64=int(pers_old[64:].sum()), ge_128=int(pers_old[128:].sum()), ge_256=int(pers_old[256:].sum()), ge_512=int(pers_old[512:].sum())),
           classes_new=cls_new, classes_old=cls_old, named_present=named_total, named_only_beyond_256=named_new, top_new_by_persistence=top)
(D / 'exp10_rank.json').write_text(json.dumps(out, indent=1))
pct = lambda a, b: f'{100 * a / b:.1f} %'
L = [f'# exp10: the clock extended to 512 steps, champion ISA {args.isa}', '',
     f"Steps 257..512 were swept for all 4,294,967,296 programs on knecht24 (kernel and driver of exp09, `MAX_STEPS` 512; validation of the new",
     f"steps against the Python reference in `exp09_validation.md`). Ranking by `fast/exp10_rank.py`; data `results/exp09/{args.name}/union_1-512.npy`.", '',
     '## Growth', '',
     f"| | functions |", '|---|---:|', f"| union over T = 1..256 (exp09) | {s256['union']:,} |", f"| union over T = 1..512 | {n_all:,} |",
     f"| new beyond step 256 | {n_new:,} ({pct(n_new, n_all)} of the union) |", f"| at step 512 alone | {c512[512]:,} (step 256: {c512[256]:,}) |",
     f"| richest single step | T = {out['peak']} with {out['peak_count']:,} |",
     f"| new per step, 257..320 / 321..384 / 385..448 / 449..512 | {sum(first_new[257:321]):,} / {sum(first_new[321:385]):,} / {sum(first_new[385:449]):,} / {sum(first_new[449:513]):,} |", '',
     '## Persistence (at how many of the 512 steps a function occurs)', '',
     '| | first seen at T <= 256 | first seen at T > 256 |', '|---|---:|---:|',
     f"| functions | {n_all - n_new:,} | {n_new:,} |", f"| at one step only | {pct(pers_old[1], n_all - n_new)} | {pct(pers_new[1], n_new)} |",
     f"| median steps | {out['persistence_old']['median']} | {out['persistence_new']['median']} |", f"| at 64 or more steps | {pers_old[64:].sum():,} | {pers_new[64:].sum():,} |",
     f"| at 256 or more steps | {pers_old[256:].sum():,} | {pers_new[256:].sum():,} |", '',
     '## What the new functions are', '',
     '| class | first seen at T <= 256 | first seen at T > 256 |', '|---|---:|---:|']
for k, lab in (('constant', 'constants'), ('bijective', 'bijections'), ('involution', 'involutions'), ('idempotent', 'idempotent'), ('depend_all_bits', 'depend on all 4 input bits')):
    L.append(f"| {lab} | {cls_old[k]:,} ({pct(cls_old[k], n_all - n_new)}) | {cls_new[k]:,} ({pct(cls_new[k], n_new)}) |")
L += ['', 'image size (distinct outputs) histogram, old vs new: ' + ', '.join(f"{i}: {cls_old['image_hist'][i]:,}/{cls_new['image_hist'][i]:,}" for i in range(1, 17)), '',
      '## Named functions', '',
      f"{named_total} of the catalog's named tables occur somewhere in T = 1..512; {len(named_new)} of them only beyond step 256:", '']
L += [f"- {', '.join(r['names'][:3])} (`{r['expression']}`): minimal T {r['minT']}, at {r['nT']} steps, program `{r['program']}`" for r in named_new] or ['- none']
L += ['', f'## Top {args.top} new functions by persistence', '', '| key (table x=0..15) | min T | steps present | program | disassembly | names |', '|---|---:|---:|---|---|---|']
for r in top: L.append(f"| `{''.join(f'{v:x}' for v in r['table'])}` | {r['minT']} | {r['nT']} | `{r['program']}` | `{r['asm']}` | {', '.join(r['names']) or '-'} |")
L += ['', '## Using them', '',
      '- A function is addressed by (program, T): run the program for exactly its minimal T steps (`sim/machine.py` `run(max_steps=T)`,',
      '  `u1map` `run_budget`, the Life engines `--max-steps`). The union file gives (key, minT, program, persistence) for every function.',
      '- The Life engines (CUDA and Rust reference) now take `--max-steps`; a world with `--max-steps 512` draws its phenotypes from the 512-step',
      '  library, at a step cost of up to 32 per tick instead of 16. The Vulkan engine does not have the option yet.',
      '- The ranking columns to pick functions for a world or a translation: persistence (robust to the clock), minimal T (cost), class, name.']
(ROOT / f'results/exp10_{args.name}_summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8'); print('wrote summary', flush=True)
