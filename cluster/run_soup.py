"""Design C soup ensemble on the NVIDIA GPUs of the cluster: every run of cluster/soup_runs.conf goes to the next free CUDA slot of
cluster/gpus.conf (u1_cuda lines), detached on the node (nohup, survives this process); results come back to results/soup/<run>/
(stats.csv, census_*.tsv, activity.tsv, shadow_activity.tsv, run.log, run.out). Resumable: finished runs are skipped, a run still
going on a node is picked up again. usage: python cluster/run_soup.py [--only NAME[,NAME]] [--no-sync] [--dry] [--collect]
Prereq on nodes: ~/universe-1 with sim/, life/, fast/, cluster/ (synced here by scp); `make -C life u1soup_cuda`."""
import argparse, json, pathlib, subprocess, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]; REMOTE = "universe-1"; OUT = ROOT / "results/soup"
ap = argparse.ArgumentParser(); ap.add_argument("--only"); ap.add_argument("--no-sync", action="store_true"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--collect", action="store_true", help="only copy back finished runs"); a = ap.parse_args()
GPUS = [tuple(x.strip() for x in l.split("|")) for l in (ROOT / "cluster/gpus.conf").read_text().splitlines() if l.strip() and not l.startswith("#")]
GPUS = [(n, int(i), lab) for n, b, i, lab in GPUS if "cuda" in b]
RUNS = [tuple(x.strip() for x in l.split("|", 1)) for l in (ROOT / "cluster/soup_runs.conf").read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]
if a.only: RUNS = [r for r in RUNS if r[0] in a.only.split(",")]
nodes = sorted({g[0] for g in GPUS}); OUT.mkdir(parents=True, exist_ok=True); STATUS = OUT / "status.json"
status = json.loads(STATUS.read_text()) if STATUS.exists() else {}
def sh(node, cmd, check=False):
    if a.dry: print(f"[{node}] {cmd}"); return subprocess.CompletedProcess(cmd, 0, "", "")
    r = subprocess.run(["ssh", "-n", "-o", "BatchMode=yes", node, cmd], capture_output=True, text=True)
    if check and r.returncode: sys.exit(f"!! {node}: {cmd}\n{r.stderr}")
    return r
def save():
    if not a.dry: STATUS.write_text(json.dumps(status, indent=1))
if not a.no_sync and not a.collect:
    files = ["sim/soup.py", "sim/machine_l2.py", "life/u1soup.cu", "life/Makefile", "fast/check_soup.py", "cluster/soup_runs.conf", "cluster/soup_seeds_robust.txt"]
    for n in nodes:
        sh(n, f"mkdir -p {REMOTE}/sim {REMOTE}/life {REMOTE}/fast {REMOTE}/cluster {REMOTE}/results/soup", check=True)
        for f in files:
            if not a.dry: subprocess.run(["scp", "-q", str(ROOT / f), f"{n}:{REMOTE}/{f}"], check=True)
        sh(n, f"cd {REMOTE} && make -s -C life u1soup_cuda", check=True)
def collect(name, node):
    d = OUT / name; d.mkdir(parents=True, exist_ok=True)
    if a.dry: return
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", node, f"cd {REMOTE}/results/soup/{name} && tar cf - stats.csv run.log run.out activity.tsv shadow_activity.tsv census_*.tsv 2>/dev/null"], capture_output=True)
    subprocess.run(["tar", "xf", "-", "-C", str(d)], input=r.stdout, check=True)
def finished(name, node):
    r = sh(node, f"cat {REMOTE}/results/soup/{name}/exit 2>/dev/null"); return r.stdout.strip() if r.stdout.strip() else None
if a.collect:
    for name, _ in RUNS:
        st = status.get(name)
        if st and st.get("state") == "running" and (code := finished(name, st["node"])) is not None:
            collect(name, st["node"]); st.update(state="complete" if code == "0" else "failed", exit=code); save(); print(f"{name}: collected (exit {code})")
    sys.exit(0)
todo = [r for r in RUNS if status.get(r[0], {}).get("state") != "complete"]
busy = {}   # (node, gpu) -> run name
for name, st in status.items():   # pick up runs still going on the nodes
    if st.get("state") == "running" and any(r[0] == name for r in todo):
        code = finished(name, st["node"])
        if code is None: busy[(st["node"], st["gpu_index"])] = name; todo = [r for r in todo if r[0] != name]; print(f"{name}: still running on {st['node']} gpu {st['gpu_index']}")
t0 = time.time()
while todo or busy:
    for node, idx, label in GPUS:
        key = (node, idx)
        if key in busy:
            code = finished(busy[key], node)
            if code is not None:
                name = busy.pop(key); collect(name, node); status[name].update(state="complete" if code == "0" else "failed", exit=code, wall_seconds=time.time() - status[name]["started_unix"]); save()
                print(f"{name}: done on {node} {label} exit {code} ({(time.time() - t0) / 60:.0f} min)", flush=True)
        if key not in busy and todo:
            name, opts = todo.pop(0); out = f"results/soup/{name}"
            sh(node, f"cd {REMOTE} && rm -rf {out} && mkdir -p {out}; setsid nohup sh -c 'life/u1soup_cuda --gpu {idx} {opts} --out-dir {out} --dump-final > {out}/run.out 2>&1; echo $? > {out}/exit' < /dev/null > /dev/null 2>&1 &")
            status[name] = dict(state="running", node=node, gpu=label, gpu_index=idx, options=opts, started_unix=time.time()); busy[key] = name; save()
            print(f"{name}: started on {node} {label}", flush=True)
    if a.dry: break
    time.sleep(30)
print("all runs finished" if not a.dry else "dry run")
