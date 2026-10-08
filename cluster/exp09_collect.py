"""Collector, run on the workstation: pull finished per-step maps (T<nnn>.npy + .json) of an exp09/exp10 run from the nodes as they
appear, verify the size, delete them on the node, and keep the node's disk small. Stops when every T in --T-range is local.
usage: python cluster/exp09_collect.py --name w4_o2_add_bin --nodes adler40,knecht24 --T-range 1-256 [--keep-on-node] [--interval 60]
Local destination: results/exp09/<name>/ (gitignored per-step arrays)."""
import argparse, json, subprocess, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--nodes', required=True); ap.add_argument('--T-range', default='1-256')
ap.add_argument('--interval', type=int, default=60); ap.add_argument('--keep-on-node', action='store_true'); args = ap.parse_args()
lo, hi = (int(x) for x in args.T_range.split('-')); want = set(range(lo, hi + 1)); nodes = args.nodes.split(',')
D = ROOT / 'results/exp09' / args.name; D.mkdir(parents=True, exist_ok=True); REMOTE = f'universe-1/results/exp09/{args.name}'
def ssh(node, cmd): return subprocess.run(['ssh', '-o', 'BatchMode=yes', node, cmd], capture_output=True, text=True)
def have_local(): return {int(p.stem[1:]) for p in D.glob('T[0-9][0-9][0-9].json') if (D / f'{p.stem}.npy').exists()}
while True:
    missing = want - have_local()
    if not missing: print('all', len(want), 'steps collected'); break
    pulled = 0
    for node in nodes:
        r = ssh(node, f'cd {REMOTE} 2>/dev/null && ls -l T[0-9][0-9][0-9].json T[0-9][0-9][0-9].npy 2>/dev/null')
        sizes = {}
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 9: sizes[parts[-1]] = int(parts[4])
        for T in sorted(missing):
            fj, fn = f'T{T:03d}.json', f'T{T:03d}.npy'
            if fj not in sizes or fn not in sizes: continue
            r = subprocess.run(['scp', '-q', f'{node}:{REMOTE}/{fj}', f'{node}:{REMOTE}/{fn}', str(D)], capture_output=True, text=True)
            if r.returncode or (D / fn).stat().st_size != sizes[fn]: print(f'!! {node} T={T} transfer failed or size mismatch', r.stderr.strip()[:200]); (D / fn).unlink(missing_ok=True); continue
            if not args.keep_on_node: ssh(node, f'rm -f {REMOTE}/{fn}')
            pulled += 1; print(f'{time.strftime("%H:%M:%S")} T={T} from {node}: {sizes[fn] / 1e6:.0f} MB, {json.loads((D / fj).read_text())["distinct_functions"]:,} functions', flush=True)
    if not pulled: time.sleep(args.interval)
