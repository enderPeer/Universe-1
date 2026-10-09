"""exp11 driver, run ON a GPU node: sweep all 26^L genomes of length L through the Avida heads-CPU engine (gpu/u1_avida_vk on the
AMD cards, gpu/u1_avida on the NVIDIA cards) in chunks of 2^chunk_log2 genomes, one chunk per engine call, several GPUs in parallel,
resumable (a finished chunk's output in results/shards/exp11/ is reused); writes results/exp11/<name>[.part_a-b].json with the
counts, histograms and the full list of viable genomes. --combine merges the part files of several nodes into results/exp11/<name>.json
and <name>_viable.tsv and, with --expect FILE, compares the viable set with a published list (every discrepancy is printed).
usage: python3 cluster/exp11_node.py --len 8 --gpus 0,1 [--engine gpu/u1_avida_vk] [--chunk-log2 26] [--chunk-range a-b] [--name len8] [--gens 3]
       python3 cluster/exp11_node.py --combine --len 8 --name len8 [--expect results/exp11/figshare/len8]"""
import argparse, json, os, queue, re, subprocess, sys, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument('--len', type=int, required=True); ap.add_argument('--gpus', default='0'); ap.add_argument('--engine', default='gpu/u1_avida_vk')
ap.add_argument('--chunk-log2', type=int, default=26); ap.add_argument('--chunk-range', help='a-b: only chunks a..b (inclusive), written as <name>.part_a-b.json')
ap.add_argument('--name'); ap.add_argument('--gens', type=int, default=3); ap.add_argument('--combine', action='store_true'); ap.add_argument('--expect')
ap.add_argument('--max-list', type=int, default=1000000)
args = ap.parse_args(); L = args.len; name = args.name or f'len{L}'
OUT = ROOT / 'results/exp11'; RAW = ROOT / 'results/shards/exp11'; OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
SPAN = 26 ** L; CH = 1 << args.chunk_log2; NCH = (SPAN + CH - 1) // CH
log = open(OUT / 'run.log', 'a')
def say(msg):
    line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {msg}'; print(line, flush=True); log.write(line + '\n'); log.flush()
HEAD = re.compile(r'avida len (\d+) genomes \[(\d+),(\d+)\) budget (\d+) gens (\d+)')
COUNTS = re.compile(r'viable (\d+) depth0 (\d+) depth1 (\d+) depth2 (\d+) divides0 (\d+) intact (\d+) copy_true0 (\d+) processed (\d+)')
GENOME = re.compile(r'genome ([a-z]+) index (\d+) viable (\d) depth (-?\d+) first (\d+) intact (\d) copy_true (\d) fecundity (\d+) fecundity_true (\d+)')
KEYS = ('viable', 'depth0', 'depth1', 'depth2', 'divides0', 'intact', 'copy_true0', 'processed')

def parse_out(txt, lo, hi):
    h = HEAD.match(txt); assert h and int(h[1]) == L and int(h[2]) == lo and int(h[3]) == hi, (txt[:120], lo, hi)
    c = COUNTS.search(txt); assert c; counts = {k: int(v) for k, v in zip(KEYS, c.groups())}; assert counts['processed'] == hi - lo, (counts, lo, hi)
    hists = {}
    for tag in ('first_divide_hist', 'fecundity_hist', 'fecundity_true_hist'):
        line = txt.split(tag)[1].split('\n')[0]; hists[tag] = {int(a): int(b) for a, b in re.findall(r' (\d+):(\d+)', line)}
    listed = re.search(r'listed (\d+) of (\d+)', txt); assert listed and listed[1] == listed[2], f'list overflow {listed.groups()}: raise --max-list'
    genomes = [(g, int(i), int(v), int(d), int(f), int(it), int(ct), int(fe), int(ft)) for g, i, v, d, f, it, ct, fe, ft in GENOME.findall(txt)]
    assert len(genomes) == counts['viable'], (len(genomes), counts)
    return counts, hists, genomes

def merge(acc, counts, hists, genomes):
    for k in KEYS: acc['counts'][k] = acc['counts'].get(k, 0) + counts[k]
    for tag, h in hists.items():
        a = acc['hists'].setdefault(tag, {})
        for k, v in h.items(): a[k] = a.get(k, 0) + v
    acc['genomes'] += genomes

def write_json(path, acc, k0, k1, secs, extra):
    acc['genomes'].sort(key=lambda r: r[1])
    res = {'experiment': 'exp11', 'length': L, 'alphabet': 'abcdefghijklmnopqrstuvwxyz', 'genome_index': 'sum op_i * 26^i, position 0 least significant',
           'gens': args.gens, 'budget_cycles': 20 * L, 'chunk_log2': args.chunk_log2, 'chunks': [k0, k1], 'genomes': min((k1 + 1) * CH, SPAN) - k0 * CH, **acc['counts'],
           'hist': {tag: dict(sorted(h.items())) for tag, h in acc['hists'].items()}, 'wall_seconds': secs, **extra,
           'viable_genomes': [dict(genome=g, index=i, depth=d, first_divide=f, intact=it, copy_true=ct, fecundity=fe, fecundity_true=ft) for g, i, v, d, f, it, ct, fe, ft in acc['genomes']]}
    path.write_text(json.dumps(res, indent=1)); return res

if args.combine:
    parts = sorted(OUT.glob(f'{name}.part_*.json')) + ([OUT / f'{name}.json'] if (OUT / f'{name}.json').exists() and not list(OUT.glob(f'{name}.part_*.json')) else [])
    assert parts, f'no {name}.part_*.json in {OUT}'
    acc = {'counts': {}, 'hists': {}, 'genomes': []}; covered = []; secs = 0; nodes = []
    for p in parts:
        r = json.loads(p.read_text()); assert r['length'] == L and r['chunk_log2'] == args.chunk_log2, p
        covered.append(tuple(r['chunks'])); secs += r['wall_seconds']; nodes += r.get('nodes', [])
        merge(acc, {k: r[k] for k in KEYS}, {t: {int(a): b for a, b in h.items()} for t, h in r['hist'].items()},
              [(g['genome'], g['index'], 1, g['depth'], g['first_divide'], g['intact'], g['copy_true'], g['fecundity'], g['fecundity_true']) for g in r['viable_genomes']])
    covered.sort(); assert covered[0][0] == 0 and covered[-1][1] == NCH - 1 and all(covered[i][1] + 1 == covered[i + 1][0] for i in range(len(covered) - 1)), f'chunk coverage gaps: {covered}'
    assert acc['counts']['processed'] == SPAN, (acc['counts']['processed'], SPAN)
    res = write_json(OUT / f'{name}.json', acc, 0, NCH - 1, secs, {'nodes': nodes, 'parts': [p.name for p in parts]})
    with open(OUT / f'{name}_viable.tsv', 'w') as f:
        f.write('genome\tindex\tdepth\tfirst_divide\tintact\tcopy_true\tfecundity\tfecundity_true\n')
        for g in res['viable_genomes']: f.write('\t'.join(str(g[k]) for k in ('genome', 'index', 'depth', 'first_divide', 'intact', 'copy_true', 'fecundity', 'fecundity_true')) + '\n')
    say(f'{name}: {SPAN:,} genomes, viable {res["viable"]:,} (depth 0/1/2 {res["depth0"]}/{res["depth1"]}/{res["depth2"]}), dividing {res["divides0"]:,}, intact {res["intact"]:,}; {secs:.0f} GPU-seconds')
    if args.expect:
        exp = {l.strip() for l in Path(args.expect).read_text().splitlines() if l.strip()}; got = {g['genome'] for g in res['viable_genomes']}
        missing = sorted(exp - got); extra = sorted(got - exp)
        say(f'{name} vs {args.expect}: expected {len(exp)}, found {len(got)}, common {len(exp & got)}, missing {len(missing)}, extra {len(extra)}')
        for g in missing: say(f'  MISSING (published, not found): {g}')
        for g in extra: say(f'  EXTRA (found, not published): {g}')
        if missing or extra: sys.exit(1)
        say(f'{name}: the viable set is EXACTLY the published set')
    sys.exit(0)

gpus = [int(g) for g in args.gpus.split(',')]
k0, k1 = (int(x) for x in args.chunk_range.split('-')) if args.chunk_range else (0, NCH - 1); chunks = list(range(k0, k1 + 1)); tag = f'{name}.part_{k0}-{k1}' if args.chunk_range else name
if (OUT / f'{tag}.json').exists(): say(f'{tag}: done already'); sys.exit(0)
todo = queue.Queue(); [todo.put(k) for k in chunks]; done = {}; lock = threading.Lock(); t0 = time.time(); fail = []
def worker(gpu):
    while True:
        try: k = todo.get_nowait()
        except queue.Empty: return
        out = RAW / f'{name}_{k:05d}.txt'; lo, hi = k * CH, min((k + 1) * CH, SPAN)
        if out.exists() and out.read_text().endswith('\n') and HEAD.match(out.read_text()):
            with lock: done[k] = 'reused'; continue
        cmd = [str(ROOT / args.engine), '--gpu', str(gpu), '--len', str(L), '--gens', str(args.gens), '--max-list', str(args.max_list), '--lo', str(lo), '--hi', str(hi), '--out', str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        with lock:
            if r.returncode: say(f'!! gpu {gpu} chunk {k} failed: {r.stderr.strip()[-300:]}'); fail.append(k); return
            done[k] = r.stderr.strip().splitlines()[-1]
            if len(done) % 50 == 0 or len(done) == len(chunks): say(f'{tag}: {len(done)}/{len(chunks)} chunks ({time.time() - t0:.0f}s) last: {done[k][-120:]}')
th = [threading.Thread(target=worker, args=(g,)) for g in gpus]; [t.start() for t in th]; [t.join() for t in th]
if len(done) != len(chunks): say(f'!! {tag}: incomplete ({len(done)}/{len(chunks)}, failed {fail}); rerun to resume'); sys.exit(1)
secs = time.time() - t0; acc = {'counts': {}, 'hists': {}, 'genomes': []}
for k in chunks:
    counts, hists, genomes = parse_out((RAW / f'{name}_{k:05d}.txt').read_text(), k * CH, min((k + 1) * CH, SPAN)); merge(acc, counts, hists, genomes)
res = write_json(OUT / f'{tag}.json', acc, k0, k1, secs, {'nodes': [dict(host=os.uname().nodename, gpus=gpus, engine=args.engine, chunks=[k0, k1], wall_seconds=secs)]})
for k in chunks: os.remove(RAW / f'{name}_{k:05d}.txt')
say(f'{tag}: {res["genomes"]:,} genomes, viable {res["viable"]} (depth 0/1/2 {res["depth0"]}/{res["depth1"]}/{res["depth2"]}), dividing {res["divides0"]:,}, intact {res["intact"]}; {secs:.0f}s, {res["genomes"] / secs / 1e6:.1f} Mgen/s on {len(gpus)} GPUs')
