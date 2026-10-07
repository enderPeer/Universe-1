"""Sweep every ISA in cluster/isas_4byte.conf over all 2^32 programs on the 9 cluster GPUs.
Pattern from enderPeer/Dimension42 explorer/search3_run.py: one worker thread per GPU pulls
program-range chunks from a shared queue, so fast GPUs take more chunks. Each chunk is one
u1_cuda / u1_vk invocation over ssh that writes a shard file on the node; shards are copied
back and merged with fast/merge.py.

usage: python3 cluster/run_4byte_gpu.py [--binary] [--only NAME] [--chunk-log2 28] [--no-sync]
Prereq on nodes: repo at ~/universe-1, built with `make -C gpu u1_cuda` (NVIDIA) or `make -C gpu u1_vk` (AMD).
"""
import argparse, json, pathlib, queue, shlex, shutil, subprocess, sys, tarfile, tempfile, threading, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
REMOTE = "universe-1"
ap = argparse.ArgumentParser()
ap.add_argument("--binary", action="store_true"); ap.add_argument("--only"); ap.add_argument("--chunk-log2", type=int, default=28)
ap.add_argument("--no-sync", action="store_true"); ap.add_argument("--dry", action="store_true")
ap.add_argument("--cap-log2", type=int, help="hash capacity exponent (unary: 22, binary: 26)")
ap.add_argument("--resume", action="store_true")
args = ap.parse_args()
if args.cap_log2 is None: args.cap_log2 = 26 if args.binary else 22
if not 10 <= args.cap_log2 <= 28: ap.error("--cap-log2 must be between 10 and 28")
if not 1 <= args.chunk_log2 <= 32: ap.error("--chunk-log2 must be between 1 and 32")
GPUS = [tuple(x.strip() for x in l.split("|")) for l in (ROOT / "cluster/gpus.conf").read_text().splitlines() if l.strip() and not l.startswith("#")]
ISAS = []
for l in (ROOT / "cluster/isas_4byte.conf").read_text().splitlines():
    if not l.strip() or l.lstrip().startswith("#"): continue
    name, geom, isa = (x.strip() for x in l.split("|")); W, a, p, I = (int(x) for x in geom.split())
    if (1 << p) * I != 32: print(f"skip {name}: program bits != 32"); continue
    if args.only and args.only != name: continue
    if args.binary and (1 << W) ** 2 > 256:
        print(f"skip {name}: binary truth table exceeds the GPU's 256-entry limit", flush=True); continue
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
    result_path = ROOT / f"results/exp03_{tag}.json"
    if args.resume and result_path.exists():
        previous = json.loads(result_path.read_text())
        ranges = sorted(previous.get("programs_covered", []))
        if ranges and ranges[0][0] == 0 and ranges[-1][1] == SPAN and not previous.get("gaps"):
            print(f"resume: {tag} already complete", flush=True); continue
    todo = queue.Queue(); [todo.put(k) for k in range(SPAN // CH)]
    lock = threading.Lock(); done = {}; t0 = time.perf_counter()
    def worker(node, binary, idx, label):
        while True:
            try: k = todo.get_nowait()
            except queue.Empty: return
            out = f"results/shards/{tag}_{k:04d}.bin"
            cmd = (f"cd {REMOTE} && nice -n 19 ionice -c3 {binary} --gpu {idx} --W {W} --a {a} --p {p} --I {I} --isa {isa} {'--binary' if args.binary else ''} "
                   f"--cap-log2 {args.cap_log2} --lo {k * CH} --hi {(k + 1) * CH} --out {out}")
            r = sh(node, cmd)
            if r.returncode != 0:
                (ROOT / f"{out}.{node}.{idx}.failed.log").write_text(cmd + "\n" + r.stdout + "\n" + r.stderr)
                print(f"!! {node} {label} failed chunk {k}: {r.stderr.strip()[:200]} - chunk requeued, device retired"); todo.put(k); return
            with lock:
                done[k] = (node, out, r.stderr.strip())
                (ROOT / f"{out}.log").write_text(f"{node} {label}\n{cmd}\n{r.stdout}\n{r.stderr}")
                print(f"{tag}: chunk {k} complete on {node} {label} ({len(done)}/{SPAN // CH})", flush=True)
    th = [threading.Thread(target=worker, args=g) for g in GPUS]; [t.start() for t in th]; [t.join() for t in th]
    if len(done) != SPAN // CH: print(f"!! {tag}: only {len(done)} of {SPAN // CH} chunks done"); sys.exit(1)
    secs = time.perf_counter() - t0
    if not args.dry:
        for node in nodes:
            files = [o for n, o, _ in done.values() if n == node]
            if files:
                # One SSH transfer per node, rather than reconnecting for every shard.
                with tempfile.TemporaryFile() as archive:
                    subprocess.run(["ssh", "-o", "BatchMode=yes", node,
                                    f"cd {REMOTE} && tar -cf - " + " ".join(map(shlex.quote, files))],
                                   stdout=archive, check=True)
                    archive.seek(0)
                    with tarfile.open(fileobj=archive) as bundle:
                        received = set()
                        for member in bundle:
                            if member.name not in files or not member.isfile():
                                raise ValueError(f"Unexpected shard archive entry: {member.name}")
                            with bundle.extractfile(member) as src, (ROOT / member.name).open("wb") as dst:
                                shutil.copyfileobj(src, dst)
                            received.add(member.name)
                        if received != set(files): raise ValueError(f"Missing shards from {node}")
        r = subprocess.run([sys.executable, "fast/merge.py", *[str(ROOT / o) for _, o, _ in done.values()], "--out", f"results/exp03_{tag}.json"],
                           cwd=ROOT, capture_output=True, text=True, check=True); print(r.stdout.strip())
        result = json.loads(result_path.read_text())
        successful_devices = sorted({(ROOT / f"{out}.log").read_text().splitlines()[0] for _, out, _ in done.values()})
        result.update(wall_seconds=secs, programs_per_second=SPAN / secs, gpu_count=len(successful_devices),
                      configured_gpu_count=len(GPUS), successful_devices=successful_devices, cap_log2=args.cap_log2,
                      source_commit="7132c01", runner_notes="Vulkan dispatch limited to 32768 workgroups, or 1024 for tables over 16 entries; cap configurable; logs retained")
        result_path.write_text(json.dumps(result, indent=1))
    print(f"{tag}: 2^32 programs in {secs:.1f}s ({SPAN / secs / 1e9:.2f} Gprog/s) on {len(GPUS)} GPUs")
    summary.append((tag, secs))
if not args.dry: subprocess.run([sys.executable, "cluster/summarize.py"], cwd=ROOT)
