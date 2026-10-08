"""Plot the world-model training log and write results/life/worldmodel/REPORT.md from log.csv and summary.json.
usage: python life/worldmodel_report.py [results/life/worldmodel]"""
import csv, json, sys
from pathlib import Path
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
d = Path(sys.argv[1] if len(sys.argv) > 1 else 'results/life/worldmodel')
rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader((d / 'log.csv').read_text().splitlines())]
summ = json.loads((d / 'summary.json').read_text())
steps = [r['step'] for r in rows]
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
ax[0].plot(steps, [r['loss'] for r in rows], label='total'); ax[0].plot(steps, [r['l_state'] for r in rows], label='state CE'); ax[0].plot(steps, [r['l_bits'] for r in rows], label='genome bits BCE')
ax[0].set_yscale('log'); ax[0].set_title('training loss'); ax[0].legend()
for k, lab in (('test_state_acc', 'state (next tick)'), ('test_genome_acc', 'genome, all 32 bits'), ('test_alive_acc', 'alive')):
    ax[1].plot(steps, [r[k] for r in rows], label=lab)
for k, lab, ls in (('copy_state_acc', 'copy baseline: state', '--'), ('copy_genome_acc', 'copy baseline: genome', ':'), ('copy_alive_acc', 'copy baseline: alive', '-.')):
    ax[1].plot(steps, [r[k] for r in rows], ls, color='gray', label=lab)
ax[1].set_ylim(0, 1.02); ax[1].set_title('held-out accuracy (ticks >= 180,000 of the training world)'); ax[1].legend(fontsize=7)
ax[2].plot(steps, [r['test_energy_mae'] for r in rows]); ax[2].set_title('energy MAE (of 255)'); ax[2].set_yscale('log')
for a in ax: a.set_xlabel('optimizer step'); a.grid(alpha=.3)
fig.tight_layout(); fig.savefig(d / 'curves.png', dpi=110)
last = rows[-1]; iw = summ.get('in_world_test') or {}; cw = summ.get('cross_world_test') or {}
def pct(x): return f'{100 * x:.2f} %' if isinstance(x, (int, float)) else '-'
L = ['# Learned world model of Universe-1 Life (SWAP,ADD,NAND,JC world)', '',
     'A convolutional net (`life/worldmodel.py`) trained on the RTX 4090 to predict the grid one tick ahead while the world ran on the',
     'RTX 4080 (`u1life_cuda --dump-every 100`: grid pairs (t, t+1) every 100 ticks). Input per cell: 32 genome bits, state one-hot, alive,',
     'energy, age, and the tick\'s neighbour direction; output: alive, state (16-way), 32 genome bits, energy at t+1. Circular 3x3 convolutions',
     f"({summ['params'] / 1e6:.2f} M parameters), random 256^2 crops, bf16 autocast, AdamW with a one-cycle schedule.", '',
     f"Training: {summ['steps']:,} steps in {summ['seconds'] / 60:.1f} min on {summ['training_pairs_seen']} grid pairs (ticks < 180,000; reservoir of {summ['reservoir']} pairs in RAM).",
     f"Test: {len(summ['test_pairs'])} pairs with ticks >= 180,000 of the same world, and {len(summ.get('cross_world_pairs', []))} pairs of an independent seed-2 world.", '',
     '| metric (cells alive at t+1 unless noted) | model, same world | model, seed-2 world | copy-previous baseline |', '|---|---:|---:|---:|',
     f"| alive at t+1 (all cells) | {pct(iw.get('alive_acc'))} | {pct(cw.get('alive_acc'))} | {pct(iw.get('copy_alive_acc'))} |",
     f"| state at t+1 | {pct(iw.get('state_acc'))} | {pct(cw.get('state_acc'))} | {pct(iw.get('copy_state_acc'))} |",
     f"| genome at t+1, all 32 bits | {pct(iw.get('genome_acc'))} | {pct(cw.get('genome_acc'))} | {pct(iw.get('copy_genome_acc'))} |",
     f"| genome bits at t+1 (per bit) | {pct(iw.get('bits_acc'))} | {pct(cw.get('bits_acc'))} | - |",
     f"| energy at t+1, mean abs error (of 255) | {iw.get('energy_mae', float('nan')):.2f} | {cw.get('energy_mae', float('nan')):.2f} | - |", '',
     '![curves](curves.png)', '',
     'Reading the table: the state at t+1 is the output of running the cell\'s program on (state, neighbour state), so state accuracy measures',
     'how much of the program semantics the net learned from observation; the copy baseline is how often the state simply does not change.',
     'Genome accuracy measures the world rule (who colonises whom): the copy baseline is high because most cells keep their genome for a tick.',
     'Random death (1/512 per tick) and mutation on copy are hash-driven and unpredictable from the grid, so 100 % is not reachable.']
(d / 'REPORT.md').write_text('\n'.join(L) + '\n', encoding='utf-8'); print('wrote', d / 'REPORT.md')
