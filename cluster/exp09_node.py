"""exp09/exp10 driver, run ON a GPU node: sweep all 2^32 programs of one ISA at every step T (docs/08_exp09_every_step.md).

Passes of --per-pass checkpoints (64 unary, 16 binary) go through the chunk queue on the node's GPUs with gpu/u1_multi; after each
pass every T is merged (in a background thread, while the next pass sweeps) with fast/merge_np.py into
results/exp09/<name>/T<nnn>.npy (distinct keys with minimum program, sorted) and T<nnn>.json (coverage, count), and the raw shards
are deleted. Unless --no-union, the union over T = 1..T-max is built at the end (unary W<=4 only: exact 64-bit keys): per function
its minimal T, the program at that T, and the number of distinct T at which it occurs -> union.npy, summary.json, summary.md.
usage: python3 cluster/exp09_node.py --name w4_o2_add --isa SWAP,ADD,NAND,SKZ --gpus 0,1,2 [--chunk-log2 26] [--per-pass 64] [--cap-log2 21]
       binary: --binary --per-pass 16 --cap-log2 22 --no-union [--T-min a --T-max b] (per-step maps only; collect them with cluster/exp09_collect.py)
exp10 (steps 257..512 on top of a finished exp09 run): add --T-min 257 --T-max 512; the union is rebuilt over 1..512 as union_1-512.npy.
"""
import argparse, json, os, queue, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'fast')); import merge_np
ap = argparse.ArgumentParser()
ap.add_argument('--name', required=True); ap.add_argument('--isa', required=True); ap.add_argument('--gpus', default='0')
ap.add_argument('--W', type=int, default=4); ap.add_argument('--a', type=int, default=2); ap.add_argument('--p', type=int, default=3); ap.add_argument('--I', type=int, default=4)
ap.add_argument('--chunk-log2', type=int, default=26); ap.add_argument('--per-pass', type=int, default=64); ap.add_argument('--cap-log2', type=int, default=21)
ap.add_argument('--T-max', type=int, default=256); ap.add_argument('--T-min', type=int, default=1, help='first step to sweep (earlier per-T maps must already exist for the union)')
ap.add_argument('--binary', action='store_true'); ap.add_argument('--no-union', action='store_true')
args = ap.parse_args()
RAW = ROOT / 'results/shards/exp09' / args.name; OUT = ROOT / 'results/exp09' / args.name; RAW.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
log = open(OUT / 'run.log', 'a'); say_lock = threading.Lock()
def say(msg):
    line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {msg}'
    with say_lock: print(line, flush=True); log.write(line + '\n'); log.flush()
SPAN = 1 << ((1 << args.p) * args.I); CH = 1 << args.chunk_log2; NCH = SPAN // CH; gpus = [int(g) for g in args.gpus.split(',')]
passes = [(lo, min(lo + args.per_pass - 1, args.T_max)) for lo in range(args.T_min, args.T_max + 1, args.per_pass)]
SUFFIX = '' if args.T_max == 256 and args.T_min == 1 else f'_{args.T_min}-{args.T_max}' if args.T_min != 1 else f'_1-{args.T_max}'
say(f'exp09/10 {args.name} isa={args.isa} {"binary" if args.binary else "unary"} chunks={NCH} x 2^{args.chunk_log2}, passes={passes}, gpus={gpus}')
timings = {}; merge_threads = []; merge_errors = []

def merge_pass(Tlo, Thi, sweep_s):
    t1 = time.time()
    try:
        for T in range(Tlo, Thi + 1):
            files = sorted(str(p) for p in RAW.glob(f'{args.name}_c[0-9][0-9][0-9][0-9].T{T:03d}.bin'))
            assert len(files) == NCH, (T, len(files))
            hdr, isa, covered, gaps, merged = merge_np.merge(files)
            assert not gaps and covered[0][0] == 0 and covered[-1][1] == SPAN, (T, gaps, covered[:2], covered[-1])
            np.save(OUT / f'T{T:03d}.npy', merged)
            (OUT / f'T{T:03d}.json').write_text(json.dumps({'T': T, 'isa': args.isa, 'binary': args.binary, 'distinct_functions': int(len(merged)), 'programs_covered': [[0, SPAN]], 'gaps': [], 'chunks': NCH}))
            for f in files: os.remove(f)
        timings[f'{Tlo}-{Thi}'] = {'sweep_seconds': sweep_s, 'merge_seconds': time.time() - t1}
        say(f'pass T=[{Tlo},{Thi}] merged: sweep {sweep_s:.0f}s, merge {time.time() - t1:.0f}s, {sum(json.loads((OUT / f"T{T:03d}.json").read_text())["distinct_functions"] for T in range(Tlo, Thi + 1)):,} records')
    except Exception as e:
        merge_errors.append((Tlo, Thi, repr(e))); say(f'!! merge of pass T=[{Tlo},{Thi}] failed: {e!r}')

for Tlo, Thi in passes:
    if all((OUT / f'T{T:03d}.json').exists() for T in range(Tlo, Thi + 1)): say(f'pass T=[{Tlo},{Thi}] already merged, skipped'); continue
    todo = queue.Queue(); [todo.put(k) for k in range(NCH)]; done = {}; lock = threading.Lock(); t0 = time.time()
    def worker(gpu):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = RAW / f'{args.name}_c{k:04d}.bin'
            cmd = [str(ROOT / 'gpu/u1_multi'), '--gpu', str(gpu), '--W', str(args.W), '--a', str(args.a), '--p', str(args.p), '--I', str(args.I), '--isa', args.isa,
                   '--cap-log2', str(args.cap_log2), '--lo', str(k * CH), '--hi', str((k + 1) * CH), '--T-lo', str(Tlo), '--T-hi', str(Thi), '--out', str(out)] + (['--binary'] if args.binary else [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            with lock:
                if r.returncode: say(f'!! gpu {gpu} chunk {k} failed: {r.stderr.strip()[:300]}'); todo.put(k); return
                done[k] = r.stderr.strip()
                if len(done) % 8 == 0 or len(done) == NCH: say(f'pass T=[{Tlo},{Thi}]: {len(done)}/{NCH} chunks ({time.time() - t0:.0f}s) last: {r.stderr.strip()[-90:]}')
    th = [threading.Thread(target=worker, args=(g,)) for g in gpus]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != NCH: say(f'!! pass T=[{Tlo},{Thi}] incomplete ({len(done)}/{NCH}); stopping'); sys.exit(1)
    mt = threading.Thread(target=merge_pass, args=(Tlo, Thi, time.time() - t0)); mt.start(); merge_threads.append(mt)
    say(f'pass T=[{Tlo},{Thi}] swept in {time.time() - t0:.0f}s; merging in the background')
for mt in merge_threads: mt.join()
(OUT / f'timings{SUFFIX}.json').write_text(json.dumps(timings, indent=1))
if merge_errors: say(f'!! {len(merge_errors)} merge failures: {merge_errors}'); sys.exit(1)
if args.no_union or args.binary: say('done: per-step maps written (no union requested)'); sys.exit(0)

# ---- union over T = 1..T_max: minimal T, program at minimal T, number of T at which each function occurs (batched by 16 steps) ----
say('building the union over all T')
counts = {}; union = np.zeros(0, '<u8'); minT = np.zeros(0, '<u2'); prog = np.zeros(0, '<u4'); occ = np.zeros(0, '<u2'); BATCH = 16
for b0 in range(1, args.T_max + 1, BATCH):
    Ts = list(range(b0, min(b0 + BATCH, args.T_max + 1))); ks, ps, ts = [], [], []
    for T in Ts:
        m = np.load(OUT / f'T{T:03d}.npy'); assert not m['khi'].any(), 'union builder assumes exact 64-bit keys (unary W<=4)'
        counts[T] = int(len(m)); ks.append(m['klo']); ps.append(m['prog']); ts.append(np.full(len(m), T, '<u2'))
    k = np.concatenate(ks); pg = np.concatenate(ps); tt = np.concatenate(ts)
    order = np.lexsort((tt, k)); k, pg, tt = k[order], pg[order], tt[order]          # key, then T ascending
    first = np.ones(len(k), bool); first[1:] = k[1:] != k[:-1]
    bk, bminT, bprog = k[first], tt[first], pg[first]; bocc = np.diff(np.append(np.flatnonzero(first), len(k))).astype('<u2')
    if len(union):
        pos = np.searchsorted(union, bk); present = (pos < len(union)) & (union[np.minimum(pos, len(union) - 1)] == bk)
        occ[pos[present]] += bocc[present]; new = ~present
    else: new = np.ones(len(bk), bool)
    if new.any():
        union = np.concatenate([union, bk[new]]); minT = np.concatenate([minT, bminT[new]]); prog = np.concatenate([prog, bprog[new]]); occ = np.concatenate([occ, bocc[new]])
        order = np.argsort(union, kind='stable'); union, minT, prog, occ = union[order], minT[order], prog[order], occ[order]
    say(f'union after T={Ts[-1]}: {len(union):,} functions')
rec = np.zeros(len(union), dtype=[('key', '<u8'), ('minT', '<u2'), ('prog', '<u4'), ('nT', '<u2')]); rec['key'] = union; rec['minT'] = minT; rec['prog'] = prog; rec['nT'] = occ
np.save(OUT / f'union{SUFFIX}.npy', rec)
minT_hist = np.bincount(minT, minlength=args.T_max + 1).tolist(); occ_hist = np.bincount(occ, minlength=args.T_max + 1).tolist()
summary = {'name': args.name, 'isa': args.isa, 'programs': SPAN, 'T_max': args.T_max, 'per_T_distinct': counts, 'union': int(len(union)),
           'ratio_union_to_T256': len(union) / counts[256] if 256 in counts else None, 'ratio_union_to_Tmax': len(union) / counts[args.T_max],
           'minT_histogram': minT_hist, 'occurrence_histogram': occ_hist,
           'functions_at_every_T': int((occ == args.T_max).sum()), 'functions_at_one_T_only': int((occ == 1).sum()), 'timings': timings}
(OUT / f'summary{SUFFIX}.json').write_text(json.dumps(summary, indent=1))
L = [f'# exp09/10 {args.name} ({args.isa}): every step of every program, T = 1..{args.T_max}', '', f'Programs: {SPAN:,}; union {len(union):,} functions = {len(union) / counts[args.T_max]:.2f}x the T={args.T_max} set ({counts[args.T_max]:,}).', '',
     f'Functions occurring at every T: {int((occ == args.T_max).sum()):,}; at exactly one T: {int((occ == 1).sum()):,}.', '', '| T | distinct functions | first appearing at T |', '|---:|---:|---:|']
for T in range(1, args.T_max + 1): L.append(f'| {T} | {counts[T]:,} | {minT_hist[T]:,} |')
(OUT / f'summary{SUFFIX}.md').write_text('\n'.join(L) + '\n'); say(f'done: union {len(union):,} functions; summary in {OUT}')
