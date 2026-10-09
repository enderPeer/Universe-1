"""Analyse a finished Life ensemble (results/life/<run>/stats.csv, run.log, final.bin, final.ppm).

Writes results/life/ANALYSIS.md, analysis.json, curves.png, final_montage.png and <run>/final.png.
Phenotypes of the most abundant genomes are computed with the Python reference machine (sim/machine.py):
new_state(s, nb) = final A after running the genome with A = s, M[1] = nb (<= 256 steps), as in docs/06_life_spec.md.
usage: python cluster/analyze_life.py [--top 100]
"""
import argparse, collections, csv, json, math, re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from sim.machine import Config, Machine
LIFE = ROOT / 'results/life'
DEFAULTS = dict(N=256, seed=1, density=0.05, start_energy=64, max_energy=255, income=20, trigger=15, repro_cost=128, mu_bits=128, max_age=1024, death_rate=512, ticks=10000, max_steps=256)
ap = argparse.ArgumentParser(); ap.add_argument('--top', type=int, default=100); args = ap.parse_args()

def parse_options(opts):
    p = dict(DEFAULTS); toks = opts.split()
    for i, t in enumerate(toks):
        if t.startswith('--') and i + 1 < len(toks):
            k = t[2:].replace('-', '_'); v = toks[i + 1]
            p[k] = v if k == 'isa' else int(v)
    return p
runs = []
for line in (ROOT / 'cluster/life_runs.conf').read_text().splitlines():
    if line.strip() and not line.startswith('#'):
        name, opts = (x.strip() for x in line.split('|')); runs.append((name, parse_options(opts)))
status = json.loads((LIFE / 'status.json').read_text())

def phenotype(machine, genome, budget=256):
    code = [(genome >> (4 * k)) & 15 for k in range(8)]
    table = []; steps_sum = 0; halts = 0; costs = []
    for s in range(16):
        row = []
        for nb in range(16):
            st, steps, reason = machine.run(code, init_A=s, init_M=[0, nb, 0, 0], max_steps=budget)
            row.append(st.A); steps_sum += steps; halts += reason == 'halt'; costs.append(max(1, math.ceil(steps / 16)))
        table.append(tuple(row))
    trig = sum(v == 15 for row in table for v in row) / 256
    nb_dep = sum(len(set(row)) > 1 for row in table)  # states whose outcome depends on the neighbour
    self_dep = sum(len({table[s][nb] for s in range(16)}) > 1 for nb in range(16))
    return dict(table=tuple(table), trigger_fraction=trig, neighbour_dependent_states=nb_dep, state_dependent_neighbours=self_dep,
                halting_fraction=halts / 256, mean_steps=steps_sum / 256, mean_cost=sum(costs) / 256)

def disassemble(machine, genome):
    I = machine.cfg.I; o = machine.o; out = []
    for k in range(8):
        ins = (genome >> (4 * k)) & 15; opc = ins >> (I - o); opnd = ins & machine.opmask
        out.append(machine.isa[opc] + (f' {opnd}' if I > o else ''))
    return '; '.join(out)

report = {}; curves = {}
for name, p in runs:
    d = LIFE / name
    if not (d / 'final.bin').exists() or name not in status: print(f'{name}: not run yet, skipped'); continue
    rows = list(csv.DictReader((d / 'stats.csv').read_text().splitlines()))
    rows = [{k: float(v) for k, v in r.items()} for r in rows]
    m = re.search(r'done:? (\d+) ticks in ([0-9.]+)s', (d / 'run.log').read_text(errors='replace'))   # CUDA/Vulkan print "done", the Rust reference "done:"
    gpu_seconds = float(m[2]); ticks_done = int(m[1])
    isa = tuple(p['isa'].split(',')); machine = Machine(Config(W=4, a=2, p=3, I=4), isa)
    b = (d / 'final.bin').read_bytes(); nn = len(b) // 8
    genome = struct.unpack_from(f'<{nn}I', b, 0); meta = struct.unpack_from(f'<{nn}I', b, nn * 4)
    live = [c for c in range(nn) if meta[c] & 16]
    counts = collections.Counter(genome[c] for c in live)
    states = collections.Counter(meta[c] & 15 for c in live)
    ages = [(meta[c] >> 5) & 2047 for c in live]; energies = [meta[c] >> 16 for c in live]
    top = counts.most_common(args.top)
    phen = {}; classes = collections.Counter(); covered = 0
    for g, n in top:
        ph = phenotype(machine, g, p['max_steps']); phen[g] = ph; classes[ph['table']] += n; covered += n
    final = rows[-1]
    at = {int(t): next((r['distinct_genomes'] for r in rows if r['tick'] == t), None) for t in (1000, 10000, 50000, 100000, 200000)}
    after = [r for r in rows if r['tick'] >= 1000]
    r = dict(isa=p['isa'], seed=p['seed'], N=p['N'], income=p['income'], mu_bits=p['mu_bits'], repro_cost=p['repro_cost'], max_steps=p['max_steps'],
             node=status[name]['node'], gpu=status[name]['gpu'], gpu_seconds=gpu_seconds, dispatcher_seconds=status[name]['wall_seconds'],
             ticks=ticks_done, ticks_per_second=ticks_done / gpu_seconds, cell_updates_per_second=ticks_done * nn / gpu_seconds,
             final_alive=len(live), final_fill=len(live) / nn, min_alive=min(r['alive'] for r in rows), min_alive_after_1000=min(r['alive'] for r in after),
             extinct=min(r['alive'] for r in rows) == 0, final_distinct_genomes=len(counts), genomes_at=at,
             max_distinct_after_1000=max(r['distinct_genomes'] for r in after), min_distinct_after_1000=min(r['distinct_genomes'] for r in after),
             births_per_tick_final=final['births'] / 1000, deaths_per_tick_final=final['deaths'] / 1000, mean_energy_final=final['mean_energy'],
             mean_age=sum(ages) / len(ages), mean_energy_dump=sum(energies) / len(energies),
             state_histogram=[states[s] / len(live) for s in range(16)], trigger_state_fraction=states[15] / len(live),
             top_coverage=covered / len(live), top_count=len(top), distinct_phenotypes_in_top=len(classes),
             top_phenotype_share=classes.most_common(1)[0][1] / len(live),
             top_genomes=[dict(genome=f'0x{g:08x}', count=n, share=n / len(live), asm=disassemble(machine, g),
                               **{k: v for k, v in phen[g].items() if k != 'table'},
                               new_state_from_state_with_nb0=[phen[g]['table'][s][0] for s in range(16)]) for g, n in top[:3]])
    report[name] = r; curves[name] = rows
    print(f"{name}: {r['ticks_per_second']:.0f} ticks/s on {r['gpu']}, alive {len(live)} ({r['final_fill']:.1%}), genomes {len(counts)}, "
          f"top3 {[t['share'] for t in r['top_genomes']]}, trigger-state {r['trigger_state_fraction']:.1%}", flush=True)

# ---- images -----------------------------------------------------------------
from PIL import Image
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
thumbs = []
for name, _ in runs:
    if name not in report: continue
    im = Image.open(LIFE / name / 'final.ppm'); im.save(LIFE / name / 'final.png', optimize=True)
    thumbs.append((name, im.resize((336, 336), Image.BOX)))
cols = 3; rws = (len(thumbs) + cols - 1) // cols
montage = Image.new('RGB', (cols * 340, rws * 356), (24, 24, 24))
from PIL import ImageDraw
draw = ImageDraw.Draw(montage)
for i, (name, im) in enumerate(thumbs):
    x, y = (i % 3) * 340 + 2, (i // 3) * 356 + 2; montage.paste(im, (x, y + 16)); draw.text((x + 2, y), name, fill=(230, 230, 230))
montage.save(LIFE / 'final_montage.png', optimize=True)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
for name, rows in curves.items():
    t = [r['tick'] for r in rows]; style = '-' if name.startswith('champ') else '--' if name in ('swap_s1', 'swap_s2', 'swap_s3') else ':'
    axes[0].plot(t, [r['distinct_genomes'] for r in rows], style, label=name)
    axes[1].plot(t, [r['alive'] for r in rows], style, label=name)
    axes[2].plot(t[1:], [r['births'] / 1000 for r in rows[1:]], style, label=name)
axes[0].set_yscale('log'); axes[0].set_title('distinct genomes'); axes[1].set_title('live cells (of 1,048,576)'); axes[2].set_title('births per tick')
for ax in axes: ax.set_xlabel('tick'); ax.grid(alpha=.3)
axes[0].legend(fontsize=7, ncol=2); fig.tight_layout(); fig.savefig(LIFE / 'curves.png', dpi=110)

# ---- report -----------------------------------------------------------------
(LIFE / 'analysis.json').write_text(json.dumps(report, indent=1) + '\n')
L = ['# Life ensemble: analysis of the nine 1024^2 x 200,000-tick runs', '',
     'Source commit of the engines: `eed02f8` (CUDA on adler40/knecht24, Vulkan on specht32/falke64, verified bit-identical to the',
     'CPU reference on all nine GPUs before the run). Configuration: `cluster/life_runs.conf`; dispatch: `cluster/run_life.py`;',
     'this report: `cluster/analyze_life.py`. Phenotypes below use the Python reference machine on the dumped final grids.', '',
     '## Runs, speed, survival', '',
     '| run | ISA | seed | mu_bits | repro_cost | income | steps | GPU | GPU s | ticks/s | M cell-updates/s | final alive | min alive (t>=1000) | extinct |',
     '|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|']
for name, r in report.items():
    L.append(f"| {name} | {r['isa']} | {r['seed']} | {r['mu_bits']} | {r['repro_cost']} | {r['income']} | {r['max_steps']} | {r['node']} {r['gpu']} | {r['gpu_seconds']:.0f} | "
             f"{r['ticks_per_second']:.0f} | {r['cell_updates_per_second'] / 1e6:.0f} | {r['final_alive']:,} ({r['final_fill']:.1%}) | {int(r['min_alive_after_1000']):,} | {'yes' if r['extinct'] else 'no'} |")
L += ['', 'GPU seconds are the engine\'s own `done ... ticks in ...s`; the dispatcher wall time in RUNS.md adds the copy-back.', '',
      '## Genome diversity (distinct genomes among live cells)', '',
      '| run | t=0 (initial) | 1,000 | 10,000 | 50,000 | 100,000 | 200,000 | max after 1,000 | min after 1,000 | births/tick at end | mean energy at end |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for name, r in report.items():
    a = r['genomes_at']; init = int(curves[name][0]['distinct_genomes'])
    L.append(f"| {name} | {init:,} | {int(a[1000]):,} | {int(a[10000]):,} | {int(a[50000]):,} | {int(a[100000]):,} | {int(a[200000]):,} | "
             f"{int(r['max_distinct_after_1000']):,} | {int(r['min_distinct_after_1000']):,} | {r['births_per_tick_final']:,.0f} | {r['mean_energy_final']:.1f} |")
L += ['', '![curves](curves.png)', '', '## Final populations: most common genomes', '',
      f"Each run's {args.top} most abundant genomes were executed on all 256 (state, neighbour state) inputs. `trigger` is the fraction of inputs",
      'whose new state is 15 (reproduction); `nb-dep` is how many of the 16 own states give a neighbour-dependent outcome; `halt` is the',
      'fraction of inputs that reach HALT (the champion ISA has none, so every genome costs the full budget: cost 16 at 256 steps, 32 at 512).', '',
      '| run | genome | share | trigger | nb-dep states | halt | mean steps | mean cost | program |', '|---|---|---:|---:|---:|---:|---:|---:|---|']
for name, r in report.items():
    for g in r['top_genomes']:
        L.append(f"| {name} | `{g['genome']}` | {g['share']:.1%} | {g['trigger_fraction']:.2f} | {g['neighbour_dependent_states']} | {g['halting_fraction']:.2f} | "
                 f"{g['mean_steps']:.0f} | {g['mean_cost']:.1f} | `{g['asm']}` |")
L += ['', '| run | top-3 share | top-N share | distinct phenotypes in top-N | largest phenotype share | cells in state 15 | mean age |', '|---|---:|---:|---:|---:|---:|---:|']
for name, r in report.items():
    L.append(f"| {name} | {sum(g['share'] for g in r['top_genomes']):.1%} | {r['top_coverage']:.1%} | {r['distinct_phenotypes_in_top']} | "
             f"{r['top_phenotype_share']:.1%} | {r['trigger_state_fraction']:.1%} | {r['mean_age']:.0f} |")
L += ['', '![final grids](final_montage.png)', '', 'Per-run full-resolution renders: `<run>/final.png` (hue = hash of genome, dark = empty, brightness = state).',
      'Final grids (`final.bin`, 8 MB each, genome[] then meta[] as little-endian u32) stay on the coordinator and the producing nodes.', '',
      '## Findings (ensemble of 2026-10-07; jc_s1 added 2026-10-08; the 17 overnight runs of 2026-10-08/09 are read in `OVERNIGHT_RESULTS.md`)', '',
      '- **jc_s1 (SWAP,ADD,NAND,JC, the exp05 operator-count winner) behaves like a champion world.** 87 % fill, diversity 237 k -> 64 k, two genome families hold 20 % of the cells and reproduce on 44 % of inputs with neighbour-dependent outcomes for all 16 states; the dominant genome uses JC (`ADD 3; JC 2; ...`), its runner-up is the same program without the jump. 405 ticks/s on the RTX 4090 while writing a frame every 100 ticks; video `jc_s1/jc_s1_512_small.mp4`, key frames `jc_s1/keyframes.png`.',
      '- **No extinction.** Every world filled to 80-100 % within 2,000 ticks and stayed there; the lowest live count after tick 1,000 was 29 % (champion runs, during the first turnover wave).',
      '- **The two ISAs evolve differently.** Champion worlds (no HALT: every genome costs 16) lose diversity steadily (270 k -> 51-58 k genomes) and are dominated by a few genome families: the top three genomes hold 9-25 % of the cells and the largest phenotype 15-22 %. Swap worlds (HALT available) keep 225-240 k genomes; every abundant genome halts on all 256 inputs in 7-8 steps (cost 1), so cost is flat and the top genome holds under 1 % (2 % in swap_s3). Selection there acts on the trigger table, not on cost.',
      '- **Neighbour-dependent strategies dominate.** In 22 of the 27 listed top genomes the outcome depends on the neighbour state for all 16 own states; the champion winners reproduce on 44-48 % of inputs. champ_s3 is the exception: three one-instruction variants of one genome (a neutral network on the first instruction) reproduce on only 5 % of inputs yet hold 15 % of the cells, which suggests a protective, rarely reproducing strategy can beat prolific ones.',
      '- **Mutation rate sets the regime.** mu_bits=32 (one flip per copy on average) gives 99 % fill, 229 k genomes and a top genome at 0.03 %: mutation, not selection, shapes the population. mu_bits=512 gives 94 k genomes, the patchiest world (visible domains), and the lowest minimum diversity (54 k). The default 128 sits between.',
      '- **Cheap reproduction (repro_cost=64) quadruples turnover** (45 k births per tick vs 12 k), fills the torus (99.8 %) and drives diversity down to 63 k, close to the champion worlds.',
      '- **Mean age is 190-260 ticks**, far below max_age=1024 and below the 512-tick random-death horizon: most deaths are overwrites by a reproducing neighbour.',
      '- **Speed.** CUDA matched the spec estimates: 400 ticks/s on the RTX 4090 and 133 on an RTX 3060 for the champion (every cell runs 256 steps); 1,100-1,150 ticks/s on an RTX 3060 for the halting swap ISA. The Vulkan engine on AMD is the outlier: swap_s3 on the RX 9070 XT ran at 115 ticks/s, ten times slower than the same workload on an RTX 3060, and the R9700 reached 200-450. The next engineering step is profiling the Vulkan kernel (workgroup size, early exit on HALT, divergence), not more GPUs.',
      '- **Seeds matter less than parameters.** The three seeds of each ISA agree on fill, diversity and birth rate within a few per cent; the three parameter variants differ by factors of 2-4.']
(LIFE / 'ANALYSIS.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
print('wrote', LIFE / 'ANALYSIS.md')
