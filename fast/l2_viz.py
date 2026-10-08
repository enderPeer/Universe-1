"""Visualise exp06b: per-ISA summary charts from results/exp06b/<name>.json and space-time diagrams of individual L2 programs.

Space-time diagram: memory (16 words, code at 0..7, copy window at 8..15) on the vertical axis, steps on the horizontal, cell
colour = word value (16-colour map); the program counter is drawn as a white dot on the row it fetches from; a red dot marks a
write; the right margin shows the final copy score. usage:
  python fast/l2_viz.py summary results/exp06b/l2_ldst_ind.json            -> results/exp06b/l2_ldst_ind.png
  python fast/l2_viz.py trace ISA 0x1234abcd [out.png] [--steps 128]       -> space-time diagram of one program
"""
import json, sys
from pathlib import Path
import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); from sim.machine_l2 import ConfigL2, MachineL2
PAL = ListedColormap(plt.get_cmap('tab20').colors[:16])

def disasm(m, program):
    cfg = m.cfg; return '; '.join(f'{m.isa[c >> (cfg.I - m.o)]} {c & m.opmask}' for c in m.code(program))

def spacetime(ax, isa, program, steps=128, cfg=None):
    m = MachineL2(cfg or ConfigL2(), tuple(isa.split(','))); tr = m.trace(program, max_steps=steps); n = 1 << m.cfg.p; nM = 1 << m.cfg.a
    mem = np.array([snap[2] for snap in tr]).T                                  # (nM, T)
    ax.imshow(mem, cmap=PAL if m.cfg.W <= 4 else 'viridis', vmin=0, vmax=(1 << m.cfg.W) - 1, aspect='auto', interpolation='nearest')
    ax.scatter(range(len(tr)), [snap[0] for snap in tr], s=6, c='white', edgecolors='black', linewidths=.3, zorder=3)
    prev = m.load(program)
    for t, snap in enumerate(tr):
        for a in range(nM):
            if snap[2][a] != prev[a]: ax.scatter([t], [a], s=18, c='red', marker='s', zorder=4)
        prev = snap[2]
    ax.axhline(n - .5, color='white', lw=1.2); ax.set_yticks(range(nM)); ax.set_yticklabels([f'M{i}' + (' code' if i < n else '') for i in range(nM)], fontsize=6)
    ax.set_xlabel('step'); S = m.stats(program); width = (n * m.cfg.I + 3) // 4
    ax.set_title(f'0x{program:0{width}x}  {disasm(m, program)}\nbest copy {S["best"]}/{n} at offset {S["offset"]} (final {S["final"]}), ever_mod {S["ever_mod"]}, walker writes {S["walker_writes"]}, halts at {len(tr) if tr[-1][3] == "HALT" else "-"}', fontsize=8)
    return S

def summary(path):
    r = json.loads(Path(path).read_text()); name = r['name']; n = 1 << r['p']; isa = ','.join(r['isa']); P = r['programs']; cfg = ConfigL2(W=r.get('W', 4), a=r['a'], p=r['p'], I=r['I'])
    fig = plt.figure(figsize=(16, 9)); gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.3])
    ax = fig.add_subplot(gs[0, 0]); bc = [r['best_score_counts'][str(s)] for s in range(n + 1)]; fc = [r['final_score_counts'][str(s)] for s in range(n + 1)]
    ax.bar(np.arange(n + 1) - .2, np.maximum(bc, .5), .4, label='best over steps'); ax.bar(np.arange(n + 1) + .2, np.maximum(fc, .5), .4, label='at the end'); ax.set_yscale('log'); ax.set_xlabel('code words found in the copy window'); ax.set_title('copy score (all 2^32 programs)'); ax.legend(fontsize=8)
    ax = fig.add_subplot(gs[0, 1]); labels = ['code ever changed', 'code differs at end', 'walkers', 'full copy ever', 'copy persists', 'copy with code intact']
    vals = [r['ever_mod'], r['final_mod'], r['walkers'], r['copiers_ever'], r['copiers_final'], r['copiers_intact']]
    ax.barh(labels, [100 * v / P for v in vals]); ax.set_xscale('symlog', linthresh=1e-6); ax.set_xlabel('% of programs')
    for i, v in enumerate(vals): ax.text(100 * v / P if v else 1e-6, i, f' {v:,}', va='center', fontsize=8)
    ax.set_title('self-modification')
    ax = fig.add_subplot(gs[0, 2]); h = {int(k): v for k, v in r['first_full_copy_step_histogram'].items()}
    if h: ax.bar(list(h), list(h.values())); ax.set_xlabel('step of the first full copy'); ax.set_title(f'{sum(h.values()):,} full copiers')
    else: ax.text(.5, .5, 'no full copier', ha='center', va='center', transform=ax.transAxes); ax.set_title('first full copy')
    picks = []
    if r['intact_copiers_sample']: picks.append(('first copier with intact code', int(r['intact_copiers_sample'][0]['program'], 16)))
    if r['copiers_sample']: picks.append(('first full copier', int(r['copiers_sample'][0]['program'], 16)))
    for s in range(n, 0, -1):
        if str(s) in r['best_score_min_program'] and len(picks) < 3 and all(int(r['best_score_min_program'][str(s)], 16) != pg for _, pg in picks): picks.append((f'first program with best score {s}/{n}', int(r['best_score_min_program'][str(s)], 16)))
    for i, (lab, prog) in enumerate(picks[:3]):
        ax = fig.add_subplot(gs[1, i]); spacetime(ax, isa, prog, 128, cfg); ax.set_title(lab + '\n' + ax.get_title(), fontsize=8)
    fn_ = 'copy-only' if r['distinct_unary_functions'] is None else f'{r["distinct_unary_functions"]:,} unary functions at step 256'
    fig.suptitle(f'exp06b/c {name}: {isa} (layout L2, W={cfg.W}, {1 << cfg.a} words, o={max(1, (len(r["isa"]) - 1).bit_length())}, 2^{n * cfg.I} programs), {fn_}', fontsize=11)
    fig.tight_layout(); out = Path(path).with_suffix('.png'); fig.savefig(out, dpi=110); print('wrote', out); return out

if __name__ == '__main__':
    if sys.argv[1] == 'summary': summary(sys.argv[2])
    elif sys.argv[1] == 'trace':
        steps = int(sys.argv[sys.argv.index('--steps') + 1]) if '--steps' in sys.argv else 128
        fig, ax = plt.subplots(figsize=(14, 5)); spacetime(ax, sys.argv[2], int(sys.argv[3], 16), steps); fig.tight_layout()
        out = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else 'trace.png'; fig.savefig(out, dpi=120); print('wrote', out)
