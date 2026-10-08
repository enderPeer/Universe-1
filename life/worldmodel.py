"""Learned world model for Universe-1 Life: a convolutional net that predicts the grid one tick ahead.

Input per cell (from a `--dump-every` grid d<t>.bin): the 32 genome bits, the 4-bit state (one-hot), alive, energy, age,
plus the tick's neighbour direction (t % 4, broadcast). Target: the grid at tick t+1 (alive, state, genome bits, energy).
The net therefore has to learn, from observation only, (a) the organisms' program semantics new_state = run(genome, state,
neighbour state) and (b) the world rule (colonisation, energy, death), except for the hash-driven randomness (random death,
mutation), which is unpredictable and bounds the achievable accuracy.

Streams from a directory that a running engine fills (`u1life_cuda --dump-every k`): new pairs are picked up while the
world runs; pairs with t >= --holdout are never trained on and serve as the in-world test set; --eval-dir points at a
second world (another seed) for the cross-world test. Writes <out>/log.csv, <out>/summary.json, <out>/model.pt.
usage (on a CUDA node): python life/worldmodel.py --dir results/life/jc_wm --N 1024 --out results/life/worldmodel [--steps 30000]
"""
import argparse, glob, json, os, time, random
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

ap = argparse.ArgumentParser()
ap.add_argument('--dir', required=True); ap.add_argument('--N', type=int, default=1024); ap.add_argument('--out', required=True)
ap.add_argument('--eval-dir'); ap.add_argument('--holdout', type=int, default=180000, help='pairs with t >= holdout are test only')
ap.add_argument('--steps', type=int, default=30000); ap.add_argument('--batch', type=int, default=8); ap.add_argument('--crop', type=int, default=256)
ap.add_argument('--channels', type=int, default=96); ap.add_argument('--layers', type=int, default=8); ap.add_argument('--lr', type=float, default=1e-3)
ap.add_argument('--reservoir', type=int, default=400, help='max training pairs held in RAM (16 MB each at N=1024)')
ap.add_argument('--eval-every', type=int, default=1000); ap.add_argument('--eval-pairs', type=int, default=8); ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--wait', type=int, default=900, help='seconds to wait for new dumps before deciding the world has ended')
args = ap.parse_args()
torch.manual_seed(args.seed); random.seed(args.seed); np.random.seed(args.seed)
dev = torch.device('cuda'); os.makedirs(args.out, exist_ok=True)
NN = args.N * args.N; FILE_BYTES = NN * 8

def load_grid(path):
    a = np.fromfile(path, dtype='<u4'); assert a.size == 2 * NN, path
    return a[:NN].reshape(args.N, args.N), a[NN:].reshape(args.N, args.N)

def complete_pairs(d):
    """(t, path_t, path_t1) for every dump pair whose two files are complete."""
    out = []
    for p in sorted(glob.glob(os.path.join(d, 'd[0-9]*.bin'))):
        t = int(os.path.basename(p)[1:9])
        q = os.path.join(d, f'd{t + 1:08d}.bin')
        if os.path.exists(q) and os.path.getsize(p) == FILE_BYTES and os.path.getsize(q) == FILE_BYTES and time.time() - os.path.getmtime(q) > 2:
            out.append((t, p, q))
    return out

def features(g, m, t):
    """(55, N, N) float input tensor from genome/meta arrays and the tick."""
    g = torch.from_numpy(g.astype(np.int64)); m = torch.from_numpy(m.astype(np.int64))
    bits = ((g.unsqueeze(0) >> torch.arange(32).view(32, 1, 1)) & 1).float()
    state = F.one_hot(m & 15, 16).permute(2, 0, 1).float()
    alive = ((m >> 4) & 1).float().unsqueeze(0); age = (((m >> 5) & 2047).float() / 1024).unsqueeze(0); energy = ((m >> 16).float() / 255).unsqueeze(0)
    direction = F.one_hot(torch.tensor(t % 4), 4).float().view(4, 1, 1).expand(4, *g.shape)
    return torch.cat([bits * alive, state * alive, alive, energy, age, direction])

def targets(g, m):
    g = torch.from_numpy(g.astype(np.int64)); m = torch.from_numpy(m.astype(np.int64))
    return dict(alive=((m >> 4) & 1).float(), state=(m & 15), bits=((g.unsqueeze(0) >> torch.arange(32).view(32, 1, 1)) & 1).float(), energy=(m >> 16).float() / 255)

class Block(nn.Module):
    def __init__(self, c):
        super().__init__(); self.a = nn.Conv2d(c, c, 3, padding=1, padding_mode='circular'); self.b = nn.Conv2d(c, c, 3, padding=1, padding_mode='circular')
    def forward(self, x): return x + self.b(F.gelu(self.a(x)))
class Net(nn.Module):
    def __init__(self, cin=55, c=96, layers=8):
        super().__init__(); self.inp = nn.Conv2d(cin, c, 3, padding=1, padding_mode='circular')
        self.blocks = nn.Sequential(*[Block(c) for _ in range(layers)]); self.out = nn.Conv2d(c, 1 + 16 + 32 + 1, 1)
    def forward(self, x): return self.out(self.blocks(F.gelu(self.inp(x))))

def split(y): return y[:, 0], y[:, 1:17], y[:, 17:49], y[:, 49]

def losses(y, tg):
    la, ls, lb, le = split(y); alive = tg['alive']; n = alive.sum().clamp(min=1)
    loss_alive = F.binary_cross_entropy_with_logits(la, alive)
    loss_state = (F.cross_entropy(ls, tg['state'], reduction='none') * alive).sum() / n
    loss_bits = (F.binary_cross_entropy_with_logits(lb, tg['bits'], reduction='none').mean(1) * alive).sum() / n
    loss_energy = (F.mse_loss(le, tg['energy'], reduction='none') * alive).sum() / n
    return loss_alive + loss_state + loss_bits + 4 * loss_energy, dict(alive=loss_alive.item(), state=loss_state.item(), bits=loss_bits.item(), energy=loss_energy.item())

@torch.no_grad()
def metrics(y, tg, prev):
    """Accuracies of the prediction and of the copy-previous-grid baseline, on the cells alive at t+1 (state, genome) or all cells (alive)."""
    la, ls, lb, le = split(y); alive = tg['alive'].bool(); n = alive.sum().clamp(min=1).item()
    pa = la > 0; ps = ls.argmax(1); pb = lb > 0
    out = dict(alive_acc=(pa == alive).float().mean().item(), state_acc=((ps == tg['state']) & alive).sum().item() / n,
               bits_acc=(((pb == tg['bits'].bool()).float().mean(1)) * alive).sum().item() / n,
               genome_acc=(((pb == tg['bits'].bool()).all(1)) & alive).sum().item() / n,
               energy_mae=((le - tg['energy']).abs() * alive).sum().item() / n * 255)
    pg, ps0, pb0 = prev['alive'].bool(), prev['state'], prev['bits'].bool()
    out.update(copy_alive_acc=(pg == alive).float().mean().item(), copy_state_acc=((ps0 == tg['state']) & alive).sum().item() / n,
               copy_genome_acc=((pb0 == tg['bits'].bool()).all(1) & alive).sum().item() / n)
    return out

def to_dev(d): return {k: v.to(dev, non_blocking=True) for k, v in d.items()}

model = Net(55, args.channels, args.layers).to(dev).to(memory_format=torch.channels_last)
opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.steps, pct_start=0.05)
print(f'params {sum(p.numel() for p in model.parameters()) / 1e6:.2f} M', flush=True)

reservoir = []  # list of (t, g0, m0, g1, m1) numpy; reservoir sampling over the stream, newest always kept
seen = set(); n_seen = 0; test_pairs = []
def ingest():
    global n_seen
    new = 0
    for t, p, q in complete_pairs(args.dir):
        if t in seen: continue
        seen.add(t); new += 1
        g0, m0 = load_grid(p); g1, m1 = load_grid(q)
        if t >= args.holdout:
            if len(test_pairs) < args.eval_pairs: test_pairs.append((t, g0, m0, g1, m1))
            continue
        n_seen += 1
        if len(reservoir) < args.reservoir: reservoir.append((t, g0, m0, g1, m1))
        else:
            j = random.randrange(n_seen)
            if j < args.reservoir: reservoir[j] = (t, g0, m0, g1, m1)
    return new

def batch():
    xs, ys = [], {k: [] for k in ('alive', 'state', 'bits', 'energy')}
    for _ in range(args.batch):
        t, g0, m0, g1, m1 = random.choice(reservoir)
        oy, ox = random.randrange(args.N), random.randrange(args.N)
        sl = lambda a: np.roll(np.roll(a, -oy, 0), -ox, 1)[:args.crop, :args.crop]
        xs.append(features(sl(g0), sl(m0), t)); tg = targets(sl(g1), sl(m1))
        for k in ys: ys[k].append(tg[k])
    return torch.stack(xs), {k: torch.stack(v) for k, v in ys.items()}

@torch.no_grad()
def evaluate(pairs):
    model.eval(); acc = {}
    for t, g0, m0, g1, m1 in pairs:
        x = features(g0, m0, t).unsqueeze(0).to(dev); tg = to_dev({k: v.unsqueeze(0) for k, v in targets(g1, m1).items()}); prev = to_dev({k: v.unsqueeze(0) for k, v in targets(g0, m0).items()})
        with torch.autocast('cuda', dtype=torch.bfloat16): y = model(x.to(memory_format=torch.channels_last)).float()
        for k, v in metrics(y, tg, prev).items(): acc[k] = acc.get(k, 0) + v / len(pairs)
    model.train(); return acc

log = open(os.path.join(args.out, 'log.csv'), 'w'); log.write('step,seconds,pairs_seen,reservoir,loss,l_alive,l_state,l_bits,l_energy,test_alive_acc,test_state_acc,test_bits_acc,test_genome_acc,test_energy_mae,copy_state_acc,copy_genome_acc,copy_alive_acc\n')
t0 = time.time(); step = 0; last_new = time.time(); world_done = False
while not reservoir:
    ingest();
    if not reservoir: print('waiting for the first dump pair...', flush=True); time.sleep(5)
while step < args.steps:
    if not world_done and step % 50 == 0:
        if ingest(): last_new = time.time()
        elif os.path.exists(os.path.join(args.dir, 'final.bin')) or time.time() - last_new > args.wait: world_done = True; print(f'world ended: {n_seen} training pairs seen, {len(test_pairs)} test pairs', flush=True)
    x, tg = batch(); x = x.to(dev, non_blocking=True).to(memory_format=torch.channels_last); tg = to_dev(tg)
    with torch.autocast('cuda', dtype=torch.bfloat16): y = model(x)
    loss, parts = losses(y.float(), tg)
    opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step(); step += 1
    if step % args.eval_every == 0 or step == args.steps:
        ev = evaluate(test_pairs) if test_pairs else {}
        row = [step, round(time.time() - t0, 1), n_seen, len(reservoir), round(loss.item(), 4), *[round(parts[k], 4) for k in ('alive', 'state', 'bits', 'energy')],
               *[round(ev.get(k, float('nan')), 4) for k in ('alive_acc', 'state_acc', 'bits_acc', 'genome_acc', 'energy_mae', 'copy_state_acc', 'copy_genome_acc', 'copy_alive_acc')]]
        log.write(','.join(map(str, row)) + '\n'); log.flush()
        print(f"step {step} {time.time() - t0:.0f}s pairs {n_seen} loss {loss.item():.4f} state {parts['state']:.4f} bits {parts['bits']:.4f} | test state {ev.get('state_acc', 0):.4f} (copy {ev.get('copy_state_acc', 0):.4f}) genome {ev.get('genome_acc', 0):.4f} (copy {ev.get('copy_genome_acc', 0):.4f}) alive {ev.get('alive_acc', 0):.4f} (copy {ev.get('copy_alive_acc', 0):.4f}) energy MAE {ev.get('energy_mae', 0):.2f}", flush=True)
        torch.save(model.state_dict(), os.path.join(args.out, 'model.pt'))
    elif step % 100 == 0: print(f"step {step} {time.time() - t0:.0f}s pairs {n_seen} loss {loss.item():.4f}", flush=True)

summary = dict(steps=step, seconds=time.time() - t0, training_pairs_seen=n_seen, reservoir=len(reservoir), test_pairs=[p[0] for p in test_pairs],
               params=sum(p.numel() for p in model.parameters()), in_world_test=evaluate(test_pairs) if test_pairs else None)
if args.eval_dir:
    cross = complete_pairs(args.eval_dir); sel = cross[:: max(1, len(cross) // args.eval_pairs)][: args.eval_pairs]
    pairs = [(t, *load_grid(p), *load_grid(q)) for t, p, q in sel]
    summary['cross_world_test'] = evaluate(pairs); summary['cross_world_pairs'] = [t for t, _, _ in sel]
json.dump(summary, open(os.path.join(args.out, 'summary.json'), 'w'), indent=1); print(json.dumps(summary, indent=1), flush=True)
