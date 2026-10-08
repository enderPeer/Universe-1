"""Universe-1 Life ensemble on all cluster GPUs: each run in cluster/life_runs.conf goes to the next free GPU slot
(cluster/gpus.conf); stats.csv, final.ppm and final.bin are copied back to results/life/<run>/.
usage: python3 cluster/run_life.py [--only NAME] [--no-sync] [--dry]
Prereq on nodes: repo at ~/universe-1; `make -C life u1life_cuda` (NVIDIA) or `make -C life u1life_vk` (AMD)."""
import argparse, json, pathlib, queue, subprocess, sys, threading, time
ROOT = pathlib.Path(__file__).resolve().parents[1]; REMOTE = "universe-1"
ap = argparse.ArgumentParser(); ap.add_argument("--only"); ap.add_argument("--no-sync", action="store_true"); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
GPUS = [tuple(x.strip() for x in l.split("|")) for l in (ROOT / "cluster/gpus.conf").read_text().splitlines() if l.strip() and not l.startswith("#")]
RUNS = [tuple(x.strip() for x in l.split("|", 1)) for l in (ROOT / "cluster/life_runs.conf").read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]
if a.only: RUNS = [r for r in RUNS if r[0] == a.only]
def sh(node, cmd):
    if a.dry: print(f"[{node}] {cmd}"); return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(["ssh", "-o", "BatchMode=yes", node, cmd], capture_output=True, text=True)
nodes = sorted({g[0] for g in GPUS})
if not a.no_sync:
    for n in nodes:
        if not a.dry: subprocess.run(["rsync", "-az", "--exclude", ".git", "--exclude", "results", "--exclude", "target", f"{ROOT}/", f"{n}:{REMOTE}/"], check=True)
        tgt = "u1life_cuda" if any(g[0] == n and "cuda" in g[1] for g in GPUS) else "u1life_vk"
        r = sh(n, f"cd {REMOTE} && make -s -C life {tgt}")
        if r.returncode: print(f"!! build failed on {n}:\n{r.stderr}"); sys.exit(1)
todo = queue.Queue(); [todo.put(r) for r in RUNS]; lock = threading.Lock(); done = []; status={}
(ROOT/'results/life').mkdir(parents=True,exist_ok=True)
def save_status():
    target=ROOT/'results/life/status.json'; temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(status,indent=2)); temp.replace(target)
def worker(node, binary, idx, label):
    exe = binary.replace("gpu/u1_cuda", "life/u1life_cuda").replace("gpu/u1_vk", "life/u1life_vk")
    while True:
        try: name, opts = todo.get_nowait()
        except queue.Empty: return
        out = f"results/life/{name}"; t0 = time.perf_counter()
        with lock:
            status[name]={'state':'running','node':node,'gpu':label,'gpu_index':idx,'options':opts,'source_commit':'eed02f8','started_unix':time.time()}; save_status()
        r = sh(node, f"cd {REMOTE} && mkdir -p {out} && nice -n 19 ionice -c3 {exe} --gpu {idx} {opts} --out-dir {out} --dump-final > {out}/run.log 2>&1")
        secs = time.perf_counter() - t0
        if r.returncode:
            failure=sh(node,f'cd {REMOTE} && tail -40 {out}/run.log').stdout
            with lock: status[name].update(state='failed',error=failure or r.stderr); save_status()
            print(f"!! {node} {label} failed {name}: {failure[-1000:]} (requeued, device retired)"); todo.put((name, opts)); return
        if not a.dry:
            (ROOT / out).mkdir(parents=True, exist_ok=True)
            subprocess.run(["scp", "-q", f"{node}:{REMOTE}/{out}/stats.csv", f"{node}:{REMOTE}/{out}/final.ppm", f"{node}:{REMOTE}/{out}/final.bin", f"{node}:{REMOTE}/{out}/run.log", str(ROOT / out)], check=True)
        with lock:
            status[name].update(state='complete',wall_seconds=secs); save_status()
            done.append((name, node, label, secs)); print(f"{name}: done on {node} {label} in {secs:.0f}s", flush=True)
th = [threading.Thread(target=worker, args=g) for g in GPUS]; [t.start() for t in th]; [t.join() for t in th]
print(f"{len(done)}/{len(RUNS)} runs complete")
if len(done)!=len(RUNS): raise SystemExit('Life ensemble incomplete; inspect status.json and worker logs')
(ROOT / "results/life").mkdir(parents=True, exist_ok=True)
(ROOT / "results/life/RUNS.md").write_text("| run | node | GPU | wall s |\n|---|---|---|---:|\n" + "".join(f"| {n} | {nd} | {l} | {s:.0f} |\n" for n, nd, l, s in done))
