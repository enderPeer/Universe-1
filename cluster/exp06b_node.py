"""exp06b driver, run ON a GPU node: for each candidate ISA, sweep all 2^32 programs under layout L2 (von Neumann, gpu/u1_l2),
collect the distinct unary functions (fast/merge_np.py) and the self-modification / self-copy statistics (.copy files), and write
results/exp06b/<name>.json + summary.md. ISAs come from cluster/isas_exp06b.conf (name | a p I | ISA), or --only NAME.
usage: python3 cluster/exp06b_node.py --gpus 0,1 [--only NAME] [--chunk-log2 26] [--cap-log2 22]"""
import argparse, json, os, queue, re, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'fast')); import merge_np
ap = argparse.ArgumentParser(); ap.add_argument('--gpus', default='0'); ap.add_argument('--only', help='comma-separated ISA names'); ap.add_argument('--chunk-log2', type=int, default=26); ap.add_argument('--cap-log2', type=int, default=22)
ap.add_argument('--engine', default='gpu/u1_l2', help='gpu/u1_l2 (CUDA) or gpu/u1_l2_vk (Vulkan)')
args = ap.parse_args(); gpus = [int(g) for g in args.gpus.split(',')]
OUT = ROOT / 'results/exp06b'; RAW = ROOT / 'results/shards/exp06b'; OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
log = open(OUT / 'run.log', 'a')
def say(msg):
    line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {msg}'; print(line, flush=True); log.write(line + '\n'); log.flush()
ISAS = []
for l in (ROOT / 'cluster/isas_exp06b.conf').read_text().splitlines():
    if not l.strip() or l.lstrip().startswith('#'): continue
    name, geom, isa = (x.strip() for x in l.split('|')); a, p, I = (int(x) for x in geom.split())
    if args.only and name not in args.only.split(','): continue
    ISAS.append((name, a, p, I, isa))
for name, a, p, I, isa in ISAS:
    if (OUT / f'{name}.json').exists(): say(f'{name}: done already, skipped'); continue
    SPAN = 1 << ((1 << p) * I); CH = 1 << args.chunk_log2; NCH = SPAN // CH; nins = 1 << p
    todo = queue.Queue(); [todo.put(k) for k in range(NCH)]; done = {}; lock = threading.Lock(); t0 = time.time()
    def worker(gpu):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = RAW / f'{name}_{k:04d}.bin'
            cmd = [str(ROOT / args.engine), '--gpu', str(gpu), '--W', '4', '--a', str(a), '--p', str(p), '--I', str(I), '--isa', isa, '--cap-log2', str(args.cap_log2), '--lo', str(k * CH), '--hi', str((k + 1) * CH), '--out', str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            with lock:
                if r.returncode: say(f'!! {name} gpu {gpu} chunk {k} failed: {r.stderr.strip()[:300]}'); todo.put(k); return
                done[k] = r.stderr.strip()
                if len(done) % 16 == 0 or len(done) == NCH: say(f'{name}: {len(done)}/{NCH} chunks ({time.time() - t0:.0f}s) last: {r.stderr.strip()[-110:]}')
    th = [threading.Thread(target=worker, args=(g,)) for g in gpus]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != NCH: say(f'!! {name}: incomplete ({len(done)}/{NCH}); stopping'); sys.exit(1)
    secs = time.time() - t0
    files = sorted(str(f) for f in RAW.glob(f'{name}_[0-9][0-9][0-9][0-9].bin'))
    hdr, isa_ids, covered, gaps, merged = merge_np.merge(files); assert not gaps and covered[0][0] == 0 and covered[-1][1] == SPAN
    say(f'{name}: swept in {secs:.0f}s, merging {len(files)} shards')
    np.save(OUT / f'{name}.T256.npy', merged)
    final = {}; best = {}; fmin = {}; bmin = {}; tot = dict(ever_mod=0, final_mod=0, walkers=0, copiers_ever=0, copiers_final=0, copiers_intact=0); imin = None; first = {}; copiers = []
    for f in files:
        txt = Path(f + '.copy').read_text()
        assert sum(int(c) for _, c, _ in re.findall(r'final (\d+) count (\d+) min_program (0x[0-9a-f]+)', txt)) == CH, f'{f}: programs unaccounted for (dropped GPU work?)'
        for tag, hist, mins in (('final', final, fmin), ('best', best, bmin)):
            for sc, cnt, mp in re.findall(tag + r' (\d+) count (\d+) min_program (0x[0-9a-f]+)', txt):
                sc, cnt, mp = int(sc), int(cnt), int(mp, 16); hist[sc] = hist.get(sc, 0) + cnt
                if cnt: mins[sc] = min(mins.get(sc, mp), mp)
        g = re.search(r'ever_mod (\d+) final_mod (\d+) walkers (\d+) copiers_ever (\d+) copiers_final (\d+) copiers_intact (\d+) min_intact_copier (0x[0-9a-f]+)', txt)
        for key, val in zip(tot, g.groups()[:6]): tot[key] += int(val)
        if int(g[6]): imin = int(g[7], 16) if imin is None else min(imin, int(g[7], 16))
        for t, c in re.findall(r' (\d+):(\d+)', txt.split('first_full_hist')[1].split('\n')[0]): first[int(t)] = first.get(int(t), 0) + int(c)
        copiers += [(int(pg, 16), int(fs), int(it), int(ps)) for pg, fs, it, ps in re.findall(r'copier (0x[0-9a-f]+) first (\d+) intact (\d+) persists (\d+)', txt)]
    for f in files: os.remove(f); os.remove(f + '.copy')
    copiers.sort(); intact_list = [c for c in copiers if c[2]]
    res = {'name': name, 'layout': 'L2', 'W': 4, 'a': a, 'p': p, 'I': I, 'isa': isa.split(','), 'programs': SPAN, 'distinct_unary_functions': int(len(merged)),
           'final_score_counts': {str(s): final.get(s, 0) for s in range(nins + 1)}, 'best_score_counts': {str(s): best.get(s, 0) for s in range(nins + 1)},
           'final_score_min_program': {str(s): f'0x{fmin[s]:08x}' for s in sorted(fmin)}, 'best_score_min_program': {str(s): f'0x{bmin[s]:08x}' for s in sorted(bmin)},
           **tot, 'min_intact_copier': f'0x{imin:08x}' if imin is not None else None, 'first_full_copy_step_histogram': dict(sorted(first.items())),
           'copiers_listed': len(copiers), 'copiers_sample': [dict(program=f'0x{pg:08x}', first_step=fs, intact=it, persists=ps) for pg, fs, it, ps in copiers[:200]],
           'intact_copiers_sample': [dict(program=f'0x{pg:08x}', first_step=fs, persists=ps) for pg, fs, it, ps in intact_list[:200]],
           'wall_seconds': secs, 'programs_per_second': SPAN / secs, 'gpus': gpus}
    (OUT / f'{name}.json').write_text(json.dumps(res, indent=1))
    say(f'{name}: {len(merged):,} functions; ever_mod {tot["ever_mod"]:,} final_mod {tot["final_mod"]:,} walkers {tot["walkers"]:,}; copiers ever {tot["copiers_ever"]:,} final {tot["copiers_final"]:,} intact {tot["copiers_intact"]:,}; best-score hist {res["best_score_counts"]}; {secs:.0f}s')
rows = [json.loads(p.read_text()) for p in sorted(OUT.glob('*.json'))]
L = ['# exp06b: layout L2 (von Neumann, self-modifying code) sweeps, 2^32 programs per ISA', '',
     '| ISA | o | distinct unary functions (step 256) | ever modified code | code differs at end | walkers (>= 4 operand-only edits) | full copy ever | persists | with original intact | 7/8 ever | first intact copier |',
     '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
for r in rows:
    bc = r['best_score_counts']; L.append(f"| {','.join(r['isa'])} | {max(1, (len(r['isa']) - 1).bit_length())} | {r['distinct_unary_functions']:,} | {r['ever_mod']:,} | {r['final_mod']:,} | {r['walkers']:,} | {r['copiers_ever']:,} | {r['copiers_final']:,} | {r['copiers_intact']:,} | {int(bc.get('7', 0)):,} | {r['min_intact_copier'] or '-'} |")
(OUT / 'summary.md').write_text('\n'.join(L) + '\n'); say('summary written')
