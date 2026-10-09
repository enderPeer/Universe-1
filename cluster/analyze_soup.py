"""Analyse the Design C soup ensemble (results/soup/<run>/stats.csv, census_*.tsv, activity.tsv, shadow_activity.tsv; docs/12_design_c_soup.md).

Writes results/soup/ANALYSIS.md (per-run table, Bedau activity statistics against the shadow, the dominant genomes), analysis.json,
curves.png (births per 1,000 ticks, fertile processors, non-singleton genomes, new genomes per interval real vs shadow) and
activity.png (activity distributions real vs shadow). The verdict per run follows Bedau, Snyder and Packard (1998): a genome is an
adaptive component if its cumulative activity exceeds every shadow genome's; the number of adaptive components over time (by first-seen
tick) says whether adaptive novelty is absent, transient, bounded or still growing at the end.
usage: python cluster/analyze_soup.py [--runs a,b,...]"""
import argparse, collections, csv, json, math, re, sys, warnings
warnings.filterwarnings('ignore')
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]; SOUP = ROOT / 'results/soup'
ap = argparse.ArgumentParser(); ap.add_argument('--runs'); args = ap.parse_args()
conf = {}
for line in (ROOT / 'cluster/soup_runs.conf').read_text().splitlines():
    if line.strip() and not line.startswith('#'): name, opts = (x.strip() for x in line.split('|', 1)); conf[name] = opts
runs = args.runs.split(',') if args.runs else [n for n in conf if (SOUP / n / 'stats.csv').exists()]
status = json.loads((SOUP / 'status.json').read_text()) if (SOUP / 'status.json').exists() else {}

def read_stats(p):
    rows = list(csv.DictReader(open(p))); out = {}
    for k in rows[0]:
        vals = [r[k] for r in rows]
        try: out[k] = np.array([float(v) if v != '' else np.nan for v in vals])
        except ValueError: out[k] = vals
    return out
def read_activity(p):
    if not p.exists(): return []
    rows = []
    with open(p) as f:
        next(f)
        for l in f:
            g, first, last, act, peak = l.split('\t'); rows.append((g, int(first), int(last), int(act), int(peak)))
    return rows
def opt(opts, key, default):
    m = re.search(r'--' + key + r' (\S+)', opts); return m.group(1) if m else default

res = {}; L = ['# Design C soup ensemble: analysis', '', 'Rules and predictions: `docs/12_design_c_soup.md`. Runs: `cluster/soup_runs.conf`. One row per run; "adaptive genomes" are',
               'birth genomes whose cumulative activity (sum of census counts) exceeds the largest activity any genome of the neutral shadow reached.', '',
               '| run | processors | mu | rays | inflow | ticks | births | faithful | fertile at end | genomes in map | shadow map | max activity real / shadow | adaptive genomes | first / last adaptive seen | verdict |', '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---|---|']
fig, axes = plt.subplots(2, 2, figsize=(14, 9)); fig2, ax2 = plt.subplots(1, 1, figsize=(8, 5))
for name in runs:
    d = SOUP / name; st = read_stats(d / 'stats.csv'); opts = conf.get(name, status.get(name, {}).get('options', ''))
    t = st['tick']; births = st['births']; dt = np.diff(t); rate = np.diff(births) / np.maximum(dt, 1) * 1000
    act = read_activity(d / 'activity.tsv'); sact = read_activity(d / 'shadow_activity.tsv')
    amax = max((a[3] for a in act), default=0); smax = max((a[3] for a in sact), default=0)
    adaptive = [a for a in act if a[3] > smax] if sact else []
    first_ad = [a[1] for a in adaptive]
    ticks_done = int(t[-1]); third = ticks_done / 3
    n_early = sum(1 for f in first_ad if f < third); n_mid = sum(1 for f in first_ad if third <= f < 2 * third); n_late = sum(1 for f in first_ad if f >= 2 * third)
    if not adaptive: verdict = 'none: no genome outran the shadow'
    elif n_late == 0 and n_mid == 0: verdict = 'transient: adaptive genomes only in the first third'
    elif n_late > 0 and n_late >= n_mid: verdict = 'ongoing: adaptive genomes still appearing in the last third'
    else: verdict = 'bounded: adaptive genomes appear, fewer late than early'
    if births[-1] == 0: verdict = 'none: no birth at all'
    extinct = 'extinct' if st['live'][-1] == 0 else ''
    fert = int(st['fertile'][-1]); P = int(opt(opts, 'P', 65536)); mu = opt(opts, 'mu', '0'); rays = opt(opts, 'rays', '0'); inflow = 'no' if opt(opts, 'spontaneous', '1') == '0' else 'yes'
    L.append(f'| {name} | {P:,} | {mu} | {rays} | {inflow} | {ticks_done:,}{" " + extinct if extinct else ""} | {int(births[-1]):,} | {int(st["faithful"][-1]):,} | {fert:,} | {len(act):,} | {len(sact):,} | {amax:,} / {smax:,} | {len(adaptive):,} | {min(first_ad) if first_ad else "-"} / {max(first_ad) if first_ad else "-"} | {verdict} |')
    res[name] = dict(options=opts, ticks=ticks_done, births=int(births[-1]), faithful=int(st['faithful'][-1]), mutant=int(st['mutant'][-1]), fertile_end=fert, live_end=int(st['live'][-1]),
                     genomes_in_map=len(act), shadow_genomes_in_map=len(sact), max_activity=amax, shadow_max_activity=smax, adaptive_genomes=len(adaptive), adaptive_first_seen_thirds=[n_early, n_mid, n_late], verdict=verdict,
                     top_adaptive=[dict(genome=a[0], first_seen=a[1], last_seen=a[2], activity=a[3], peak=a[4]) for a in sorted(adaptive, key=lambda a: -a[3])[:20]])
    lab = name
    if len(t) > 1:
        axes[0, 0].plot(t[1:], rate, label=lab); axes[0, 1].plot(t, st['fertile'], label=lab); axes[1, 0].plot(t, st['distinct_genomes'] - st['singletons'], label=lab)
        axes[1, 1].plot(t, st['new_genomes'], label=lab + ' real'); axes[1, 1].plot(t, st['shadow_new'], ':', label=lab + ' shadow')
    if act:
        xs = np.array(sorted(a[3] for a in act)); ax2.step(xs, 1 - np.arange(len(xs)) / len(xs), where='post', label=lab + ' real')
    if sact:
        xs = np.array(sorted(a[3] for a in sact)); ax2.step(xs, 1 - np.arange(len(xs)) / len(xs), ':', where='post', label=lab + ' shadow')
for ax, title in zip(axes.flat, ['births per 1,000 ticks', 'fertile processors (with a child) among the living', 'birth genomes with >= 2 living copies', 'genomes entering the activity map per report interval (real solid, shadow dotted)']):
    ax.set_title(title); ax.set_xlabel('tick'); ax.set_xscale('symlog', linthresh=1000); ax.grid(alpha=.3)
axes[0, 0].set_yscale('symlog', linthresh=1); axes[1, 1].set_yscale('symlog', linthresh=1); axes[0, 1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(SOUP / 'curves.png', dpi=110)
ax2.set_xscale('log'); ax2.set_yscale('log'); ax2.set_xlabel('cumulative activity of a birth genome'); ax2.set_ylabel('fraction of genomes with at least this activity'); ax2.set_title('activity distributions, real vs neutral shadow'); ax2.legend(fontsize=6); ax2.grid(alpha=.3)
fig2.tight_layout(); fig2.savefig(SOUP / 'activity.png', dpi=110)
L += ['', '![curves](curves.png)', '', '![activity](activity.png)', '']
for name in runs:
    r = res[name]
    if r['top_adaptive']:
        L += [f'## {name}: adaptive genomes (activity above the shadow maximum {r["shadow_max_activity"]:,})', '', '| genome | first seen | last seen | activity | peak count | disassembly |', '|---|---:|---:|---:|---:|---|']
        for a in r['top_adaptive']:
            g = int(a['genome'], 16); words = [(g >> (5 * k)) & 31 for k in range(8)]; dis = '; '.join(f'{["LDIND", "STIND", "INCM", "JNZ"][w >> 3]} {w & 7}' for w in words)
            L.append(f'| {a["genome"]} | {a["first_seen"]:,} | {a["last_seen"]:,} | {a["activity"]:,} | {a["peak"]:,} | {dis} |')
        L.append('')
    cens = sorted((SOUP / name).glob('census_*.tsv'))
    if cens:
        last = cens[-1]; rows = [l.rstrip('\n').split('\t') for l in open(last)][1:6]
        L += [f'## {name}: most abundant birth genomes at the last census ({last.name})', '', '| genome | count | first seen | disassembly |', '|---|---:|---:|---|'] + [f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} |' for r in rows] + ['']
(SOUP / 'ANALYSIS.md').write_text('\n'.join(L) + '\n'); (SOUP / 'analysis.json').write_text(json.dumps(res, indent=1))
print('\n'.join(L[5:5 + 2 + len(runs)]))
