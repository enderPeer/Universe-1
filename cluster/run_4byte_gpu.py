"""Sweep every ISA in cluster/isas_4byte.conf over all 2^32 programs on the 9 cluster GPUs.
Pattern from enderPeer/Dimension42 explorer/search3_run.py: one worker thread per GPU pulls
program-range chunks from a shared queue, so fast GPUs take more chunks. Each chunk is one
u1_cuda / u1_vk invocation over ssh that writes a shard file on the node; shards are copied
back and merged with fast/merge.py.

usage: python3 cluster/run_4byte_gpu.py [--binary] [--only NAME] [--chunk-log2 28] [--no-sync]
Prereq on nodes: repo at ~/universe-1, built with `make -C gpu u1_cuda` (NVIDIA) or `make -C gpu u1_vk` (AMD).
"""
import argparse, pathlib, queue, subprocess, sys, threading, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
REMOTE = "universe-1"
ap = argparse.ArgumentParser()
ap.add_argument("--binary", action="store_true"); ap.add_argument("--only"); ap.add_argument("--chunk-log2", type=int, default=28)
ap.add_argument("--no-sync", action="store_true"); ap.add_argument("--dry", action="store_true")
args = ap.parse_args()
GPUS = [tuple(x.strip() for x in l.split("|")) for l in (ROOT / "cluster/gpus.conf").read_text().splitlines() if l.strip() and not l.startswith("#")]
ISAS = []
for l in (ROOT / "cluster/isas_4byte.conf").read_text().splitlines():
    if not l.strip() or l.lstrip().startswith("#"): continue
    name, geom, isa = (x.strip() for x in l.split("|")); W, a, p, I = (int(x) for x in geom.split())
    if (1 << p) * I != 32: print(f"skip {name}: program bits != 32"); continue
    if args.only and args.only != name: continue
    ISAS.append((name, W, a, p, I, isa))
def sh(node, cmd):
    if args.dry: print(f"[{node}] {cmd}"); return subprocess.CompletedProcess(cmd, 0, "0\n", "")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", node, cmd], capture_output=True, text=True)
nodes = sorted({g[0] for g in GPUS})
if not args.no_sync:
    for n in nodes:
        if not args.dry: subprocess.run(["rsync", "-az", "--exclude", ".git", "--exclude", "results", f"{ROOT}/", f"{n}:{REMOTE}/"], check=True)
        tgt = "u1_cuda" if any(g[0] == n and "cuda" in g[1] for g in GPUS) else "u1_vk"
        r = sh(n, f"cd {REMOTE} && make -s -C gpu {tgt} && make -s -C fast && mkdir -p results/shards")
        if r.returncode: print(f"!! build failed on {n}:\n{r.stderr}"); sys.exit(1)
(ROOT / "results/shards").mkdir(parents=True, exist_ok=True)
CH = 1 << args.chunk_log2; SPAN = 1 << 32
summary = []
for name, W, a, p, I, isa in ISAS:
    tag = f"{name}{'_bin' if args.binary else ''}"
    todo = queue.Queue(); [todo.put(k) for k in range(SPAN // CH)]
    lock = threading.Lock(); done = {}; t0 = time.perf_counter()
    def worker(node, binary, idx, label):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = f"results/shards/{tag}_{k:04d}.bin"
            cmd = (f"cd {REMOTE} && {binary} --gpu {idx} --W {W} --a {a} --p {p} --I {I} --isa {isa} {'--binary' if args.binary else ''} "
                   f"--lo {k * CH} --hi {(k + 1) * CH} --out {out}")
            r = sh(node, cmd)
            if r.returncode != 0:
                print(f"!! {node} {label} failed chunk {k}: {r.stderr.strip()[:200]} - chunk requeued, device retired"); todo.put(k); return
            with lock: done[k] = (node, out, r.stderr.strip())
    th = [threading.Thread(target=worker, args=g) for g in GPUS]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != SPAN // CH: print(f"!! {tag}: only {len(done)} of {SPAN // CH} chunks done"); sys.exit(1)
    secs = time.perf_counter() - t0
    if not args.dry:
        for node in nodes:
            files = [o for n, o, _ in done.values() if n == node]
            if files: subprocess.run(["scp", "-q"] + [f"{node}:{REMOTE}/{f}" for f in files] + [str(ROOT / "results/shards/")], check=True)
        r = subprocess.run([sys.executable, "fast/merge.py", *[str(ROOT / o) for _, o, _ in done.values()], "--out", f"results/exp03_{tag}.json"],
                           cwd=ROOT, capture_output=True, text=True); print(r.stdout.strip())
    print(f"{tag}: 2^32 programs in {secs:.1f}s ({SPAN / secs / 1e9:.2f} Gprog/s) on {len(GPUS)} GPUs")
    summary.append((tag, secs))
if not args.dry: subprocess.run([sys.executable, "cluster/summarize.py"], cwd=ROOT)
