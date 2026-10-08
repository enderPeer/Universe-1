"""exp06b/exp06c driver, run ON a GPU node: for each candidate ISA, sweep all programs under layout L2 (von Neumann, gpu/u1_l2 or
gpu/u1_l2_vk), collect the distinct unary functions (fast/merge_np.py; skipped with --copy-only) and the self-modification /
self-copy statistics (.copy files), and write results/exp06b/<name>.json + summary.md.
ISAs come from cluster/isas_exp06b.conf (name | [W] a p I | ISA; W defaults to 4), or --only NAME[,NAME...].
usage: python3 cluster/exp06b_node.py --gpus 0,1 [--engine gpu/u1_l2_vk] [--only NAME] [--chunk-log2 26] [--cap-log2 22] [--copy-only]"""
import argparse, json, os, queue, re, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'fast')); import merge_np
ap = argparse.ArgumentParser(); ap.add_argument('--gpus', default='0'); ap.add_argument('--only', help='comma-separated ISA names'); ap.add_argument('--chunk-log2', type=int, default=26); ap.add_argument('--cap-log2', type=int, default=22)
ap.add_argument('--engine', default='gpu/u1_l2', help='gpu/u1_l2 (CUDA) or gpu/u1_l2_vk (Vulkan)'); ap.add_argument('--copy-only', action='store_true', help='self-copy statistics only, no function map (needed beyond W=4)')
ap.add_argument('--chunk-range', help='a-b: only chunks a..b (inclusive); the result is written as <name>.part_a-b.json for cluster/exp06b_combine.py')
args = ap.parse_args(); gpus = [int(g) for g in args.gpus.split(',')]
OUT = ROOT / 'results/exp06b'; RAW = ROOT / 'results/shards/exp06b'; OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
log = open(OUT / 'run.log', 'a')
def say(msg):
    line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {msg}'; print(line, flush=True); log.write(line + '\n'); log.flush()
ISAS = []
for l in (ROOT / 'cluster/isas_exp06b.conf').read_text().splitlines():
    if not l.strip() or l.lstrip().startswith('#'): continue
    name, geom, isa = (x.strip() for x in l.split('|')); g = [int(x) for x in geom.split()]
    W, a, p, I = (4, *g) if len(g) == 3 else g
    if args.only and name not in args.only.split(','): continue
    ISAS.append((name, W, a, p, I, isa))
for name, W, a, p, I, isa in ISAS:
    SPAN = 1 << ((1 << p) * I); CH = 1 << args.chunk_log2; NCH = SPAN // CH; nins = 1 << p
    k0, k1 = (int(x) for x in args.chunk_range.split('-')) if args.chunk_range else (0, NCH - 1); chunks = list(range(k0, k1 + 1)); tag = f'{name}.part_{k0}-{k1}' if args.chunk_range else name
    if (OUT / f'{tag}.json').exists(): say(f'{tag}: done already, skipped'); continue
    todo = queue.Queue(); [todo.put(k) for k in chunks]; done = {}; lock = threading.Lock(); t0 = time.time()
    def worker(gpu):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = RAW / f'{name}_{k:04d}.bin'
            cmd = [str(ROOT / args.engine), '--gpu', str(gpu), '--W', str(W), '--a', str(a), '--p', str(p), '--I', str(I), '--isa', isa, '--cap-log2', str(args.cap_log2), '--lo', str(k * CH), '--hi', str((k + 1) * CH), '--out', str(out)] + (['--copy-only'] if args.copy_only else [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            with lock:
                if r.returncode: say(f'!! {name} gpu {gpu} chunk {k} failed: {r.stderr.strip()[-300:]}'); todo.put(k); return
                done[k] = r.stderr.strip()
                if len(done) % 16 == 0 or len(done) == len(chunks): say(f'{tag}: {len(done)}/{len(chunks)} chunks ({time.time() - t0:.0f}s) last: {r.stderr.strip()[-110:]}')
    th = [threading.Thread(target=worker, args=(g,)) for g in gpus]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != len(chunks): say(f'!! {tag}: incomplete ({len(done)}/{len(chunks)}); stopping'); sys.exit(1)
    secs = time.time() - t0
    copies = sorted(str(RAW / f'{name}_{k:04d}.bin.copy') for k in chunks); assert all(Path(f).exists() for f in copies)
    functions = None
    if not args.copy_only:
        files = sorted(str(RAW / f'{name}_{k:04d}.bin') for k in chunks); assert all(Path(f).exists() for f in files)
        say(f'{tag}: swept in {secs:.0f}s, merging {len(files)} shards')
        hdr, isa_ids, covered, gaps, merged = merge_np.merge(files); assert not gaps and covered[0][0] == k0 * CH and covered[-1][1] == (k1 + 1) * CH
        np.save(OUT / f'{tag}.T256.npy', merged); functions = int(len(merged))
        for f in files: os.remove(f)
    final = {}; best = {}; fmin = {}; bmin = {}; tot = dict(ever_mod=0, final_mod=0, walkers=0, copiers_ever=0, copiers_final=0, copiers_intact=0); imin = None; first = {}; copiers = []; offsets = {}
    for f in copies:
        txt = Path(f).read_text()
        assert sum(int(c) for _, c, _ in re.findall(r'final (\d+) count (\d+) min_program (0x[0-9a-f]+)', txt)) == CH, f'{f}: programs unaccounted for (dropped GPU work?)'
        for tag, hist, mins in (('final', final, fmin), ('best', best, bmin)):
            for sc, cnt, mp in re.findall(tag + r' (\d+) count (\d+) min_program (0x[0-9a-f]+)', txt):
                sc, cnt, mp = int(sc), int(cnt), int(mp, 16); hist[sc] = hist.get(sc, 0) + cnt
                if cnt: mins[sc] = min(mins.get(sc, mp), mp)
        g = re.search(r'ever_mod (\d+) final_mod (\d+) walkers (\d+) copiers_ever (\d+) copiers_final (\d+) copiers_intact (\d+) min_intact_copier (0x[0-9a-f]+)', txt)
        for key, val in zip(tot, g.groups()[:6]): tot[key] += int(val)
        if int(g[6]): imin = int(g[7], 16) if imin is None else min(imin, int(g[7], 16))
        for t, c in re.findall(r' (\d+):(\d+)', txt.split('first_full_hist')[1].split('\n')[0]): first[int(t)] = first.get(int(t), 0) + int(c)
        for pg, fs, it, ps, of in re.findall(r'copier (0x[0-9a-f]+) first (\d+) intact (\d+) persists (\d+) offset (\d+)', txt):
            copiers.append((int(pg, 16), int(fs), int(it), int(ps), int(of))); offsets[int(of)] = offsets.get(int(of), 0) + 1
        os.remove(f)
    copiers.sort(); intact_list = [c for c in copiers if c[2]]; width = ((1 << p) * I + 3) // 4
    res = {'name': name, 'layout': 'L2', 'W': W, 'a': a, 'p': p, 'I': I, 'isa': isa.split(','), 'programs': len(chunks) * CH, 'program_range': [k0 * CH, (k1 + 1) * CH], 'copy_only': args.copy_only, 'distinct_unary_functions': functions,
           'final_score_counts': {str(s): final.get(s, 0) for s in range(nins + 1)}, 'best_score_counts': {str(s): best.get(s, 0) for s in range(nins + 1)},
           'final_score_min_program': {str(s): f'0x{fmin[s]:0{width}x}' for s in sorted(fmin)}, 'best_score_min_program': {str(s): f'0x{bmin[s]:0{width}x}' for s in sorted(bmin)},
           **tot, 'min_intact_copier': f'0x{imin:0{width}x}' if imin is not None else None, 'first_full_copy_step_histogram': dict(sorted(first.items())), 'copy_offset_histogram': dict(sorted(offsets.items())),
           'copiers_listed': len(copiers), 'copiers_sample': [dict(program=f'0x{pg:0{width}x}', first_step=fs, intact=it, persists=ps, offset=of) for pg, fs, it, ps, of in copiers[:500]],
           'intact_copiers_sample': [dict(program=f'0x{pg:0{width}x}', first_step=fs, persists=ps, offset=of) for pg, fs, it, ps, of in intact_list[:500]],
           'wall_seconds': secs, 'programs_per_second': SPAN / secs, 'gpus': gpus, 'engine': args.engine}
    (OUT / f'{tag}.json').write_text(json.dumps(res, indent=1))
    say(f'{tag}: {functions if functions is not None else "-"} functions; ever_mod {tot["ever_mod"]:,} final_mod {tot["final_mod"]:,} walkers {tot["walkers"]:,}; copiers ever {tot["copiers_ever"]:,} final {tot["copiers_final"]:,} intact {tot["copiers_intact"]:,}; best-score hist {res["best_score_counts"]}; {secs:.0f}s')
rows = [json.loads(p.read_text()) for p in sorted(OUT.glob('*.json')) if '.part_' not in p.name]
L = ['# exp06b/c: layout L2 (von Neumann, self-modifying code) sweeps', '',
     '| ISA | W | a | o | programs | distinct unary functions (step 256) | ever modified code | code differs at end | walkers (>= 4 operand-only edits) | full copy ever | persists | with original intact | 7/8 ever | first intact copier |',
     '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
for r in rows:
    bc = r['best_score_counts']; fn_ = '-' if r['distinct_unary_functions'] is None else format(r['distinct_unary_functions'], ','); L.append(f"| {','.join(r['isa'])} | {r['W']} | {r['a']} | {max(1, (len(r['isa']) - 1).bit_length())} | 2^{(1 << r['p']) * r['I']} | {fn_} | {r['ever_mod']:,} | {r['final_mod']:,} | {r['walkers']:,} | {r['copiers_ever']:,} | {r['copiers_final']:,} | {r['copiers_intact']:,} | {int(bc.get('7', 0)):,} | {r['min_intact_copier'] or '-'} |")
(OUT / 'summary.md').write_text('\n'.join(L) + '\n'); say('summary written')
