"""exp06b driver, run ON a GPU node: for each candidate ISA, sweep all 2^32 programs under layout L2 (von Neumann, gpu/u1_l2),
collect the distinct unary functions (fast/merge_np.py) and the self-copy statistics (.copy files), and write
results/exp06b/<name>.json + a summary table. ISAs come from cluster/isas_exp06b.conf (name | a p I | ISA), or --only NAME.
usage: python3 cluster/exp06b_node.py --gpus 0,1 [--only NAME] [--chunk-log2 26] [--cap-log2 22]"""
import argparse, json, os, queue, re, subprocess, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'fast')); import merge_np
ap = argparse.ArgumentParser(); ap.add_argument('--gpus', default='0'); ap.add_argument('--only'); ap.add_argument('--chunk-log2', type=int, default=26); ap.add_argument('--cap-log2', type=int, default=22)
args = ap.parse_args(); gpus = [int(g) for g in args.gpus.split(',')]
OUT = ROOT / 'results/exp06b'; RAW = ROOT / 'results/shards/exp06b'; OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
log = open(OUT / 'run.log', 'a')
def say(msg):
    line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {msg}'; print(line, flush=True); log.write(line + '\n'); log.flush()
ISAS = []
for l in (ROOT / 'cluster/isas_exp06b.conf').read_text().splitlines():
    if not l.strip() or l.lstrip().startswith('#'): continue
    name, geom, isa = (x.strip() for x in l.split('|')); a, p, I = (int(x) for x in geom.split())
    if args.only and args.only != name: continue
    ISAS.append((name, a, p, I, isa))
for name, a, p, I, isa in ISAS:
    if (OUT / f'{name}.json').exists(): say(f'{name}: done already, skipped'); continue
    SPAN = 1 << ((1 << p) * I); CH = 1 << args.chunk_log2; NCH = SPAN // CH
    todo = queue.Queue(); [todo.put(k) for k in range(NCH)]; done = {}; lock = threading.Lock(); t0 = time.time()
    def worker(gpu):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = RAW / f'{name}_{k:04d}.bin'
            cmd = [str(ROOT / 'gpu/u1_l2'), '--gpu', str(gpu), '--W', '4', '--a', str(a), '--p', str(p), '--I', str(I), '--isa', isa, '--cap-log2', str(args.cap_log2), '--lo', str(k * CH), '--hi', str((k + 1) * CH), '--out', str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            with lock:
                if r.returncode: say(f'!! {name} gpu {gpu} chunk {k} failed: {r.stderr.strip()[:300]}'); todo.put(k); return
                done[k] = r.stderr.strip()
                if len(done) % 16 == 0 or len(done) == NCH: say(f'{name}: {len(done)}/{NCH} chunks ({time.time() - t0:.0f}s) last: {r.stderr.strip()[-100:]}')
    th = [threading.Thread(target=worker, args=(g,)) for g in gpus]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != NCH: say(f'!! {name}: incomplete ({len(done)}/{NCH}); stopping'); sys.exit(1)
    secs = time.time() - t0
    files = sorted(str(f) for f in RAW.glob(f'{name}_[0-9][0-9][0-9][0-9].bin'))
    hdr, isa_ids, covered, gaps, merged = merge_np.merge(files); assert not gaps and covered[0][0] == 0 and covered[-1][1] == SPAN
    import numpy as np; np.save(OUT / f'{name}.T256.npy', merged)
    counts = {}; mins = {}; copiers = []; total_copiers = 0
    for f in files:
        txt = Path(f + '.copy').read_text()
        for sc, cnt, mp in re.findall(r'score (\d+) count (\d+) min_program (0x[0-9a-f]+)', txt):
            sc, cnt, mp = int(sc), int(cnt), int(mp, 16); counts[sc] = counts.get(sc, 0) + cnt
            if cnt: mins[sc] = min(mins.get(sc, mp), mp)
        total_copiers += int(re.search(r'full_copiers (\d+)', txt)[1]); copiers += [int(x, 16) for x in re.findall(r'copier (0x[0-9a-f]+)', txt)]
    for f in files: os.remove(f); os.remove(f + '.copy')
    nins = 1 << p
    res = {'name': name, 'layout': 'L2', 'W': 4, 'a': a, 'p': p, 'I': I, 'isa': isa.split(','), 'programs': SPAN, 'distinct_unary_functions': int(len(merged)),
           'copy_score_counts': {str(s): counts.get(s, 0) for s in range(nins + 1)}, 'copy_score_min_program': {str(s): f'0x{mins[s]:08x}' for s in sorted(mins)},
           'full_copiers': total_copiers, 'copiers_listed': sorted(copiers)[:1000], 'copiers_listed_hex': [f'0x{x:08x}' for x in sorted(copiers)[:200]],
           'wall_seconds': secs, 'programs_per_second': SPAN / secs, 'gpus': gpus}
    (OUT / f'{name}.json').write_text(json.dumps(res, indent=1))
    say(f'{name}: {len(merged):,} distinct functions, copy scores {res["copy_score_counts"]}, full copiers {total_copiers}, {secs:.0f}s')
rows = [json.loads(p.read_text()) for p in sorted(OUT.glob('*.json'))]
L = ['# exp06b: layout L2 (von Neumann, self-modifying code) sweeps, 2^32 programs per ISA', '',
     '| ISA | geometry | distinct unary functions at step 256 | programs copying 8/8 words to M[8..15] | 7/8 | 6/8 | first full copier |', '|---|---|---:|---:|---:|---:|---|']
for r in rows:
    c = r['copy_score_counts']; L.append(f"| {','.join(r['isa'])} | a={r['a']} p={r['p']} I={r['I']} o={max(1, (len(r['isa']) - 1).bit_length())} | {r['distinct_unary_functions']:,} | {int(c.get('8', 0)):,} | {int(c.get('7', 0)):,} | {int(c.get('6', 0)):,} | {r['copy_score_min_program'].get('8', '-')} |")
(OUT / 'summary.md').write_text('\n'.join(L) + '\n'); say('summary written')
