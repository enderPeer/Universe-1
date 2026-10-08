"""Dissect a Life final grid: the masses (connected domains of one genome), the families they belong to,
and what the dominant genomes compute. Usage: python3 life/dissect.py final.bin N --isa SWAP,ADD,NAND,JC [--top 8]"""
import sys, struct, collections, argparse, subprocess, json
sys.path.insert(0, '.')
from sim.machine import Config, Machine, PRIMS
ap = argparse.ArgumentParser(); ap.add_argument('dump'); ap.add_argument('N', type=int); ap.add_argument('--isa', default='SWAP,ADD,NAND,JC'); ap.add_argument('--top', type=int, default=8)
a = ap.parse_args(); N = a.N; nn = N * N
b = open(a.dump, 'rb').read(); g = struct.unpack_from(f'<{nn}I', b, 0); m = struct.unpack_from(f'<{nn}I', b, nn * 4)
alive = [(m[i] >> 4) & 1 for i in range(nn)]; state = [m[i] & 15 for i in range(nn)]
live = sum(alive); print(f'live cells {live} ({100*live/nn:.1f}%)')
# genome abundance
cnt = collections.Counter(g[i] for i in range(nn) if alive[i]); print(f'distinct genomes {len(cnt)}')
# connected components of identical genome (4-neighbour, torus)
comp = [-1] * nn; sizes = []; cg = []
for s in range(nn):
    if not alive[s] or comp[s] >= 0: continue
    k = len(sizes); stack = [s]; comp[s] = k; n = 0; gs = g[s]
    while stack:
        c = stack.pop(); n += 1; x, y = c % N, c // N
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            d = ((y+dy) % N) * N + (x+dx) % N
            if alive[d] and comp[d] < 0 and g[d] == gs: comp[d] = k; stack.append(d)
    sizes.append(n); cg.append(gs)
order = sorted(range(len(sizes)), key=lambda k: -sizes[k])
print(f'\nsame-genome domains: {len(sizes)}; largest: {[sizes[k] for k in order[:10]]} cells')
# families: cluster genomes by Hamming distance <= 2 to a family head (greedy by abundance)
heads = []; fam = {}
for gen, c in cnt.most_common():
    for h in heads:
        if bin(gen ^ h).count('1') <= 2: fam[gen] = h; break
    else: heads.append(gen); fam[gen] = gen
fcnt = collections.Counter(); 
for i in range(nn):
    if alive[i]: fcnt[fam[g[i]]] += 1
# family domains (4-neighbour, same family)
comp2 = [-1] * nn; fsizes = []; fheads = []
for s in range(nn):
    if not alive[s] or comp2[s] >= 0: continue
    k = len(fsizes); stack = [s]; comp2[s] = k; n = 0; fh = fam[g[s]]
    while stack:
        c = stack.pop(); n += 1; x, y = c % N, c // N
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            d = ((y+dy) % N) * N + (x+dx) % N
            if alive[d] and comp2[d] < 0 and fam[g[d]] == fh: comp2[d] = k; stack.append(d)
    fsizes.append(n); fheads.append(fh)
forder = sorted(range(len(fsizes)), key=lambda k: -fsizes[k])
print(f'families (genomes within 2 bit flips of a head): {len(heads)}; family domains: {len(fsizes)}; largest family domains: {[fsizes[k] for k in forder[:10]]} cells')
print(f'top families by cells: {[(hex(h), c, round(100*c/live,1)) for h, c in fcnt.most_common(6)]}')
# what the dominant genomes compute
cfg = Config(W=4, a=2, p=3, I=4); mach = Machine(cfg, tuple(a.isa.split(',')))
print('\ndominant family heads: what they do (x = own state, y = neighbour state)')
for h, c in fcnt.most_common(a.top):
    code = [(h >> (4*k)) & 15 for k in range(8)]
    names = a.isa.split(','); o = max(1, (len(names) - 1).bit_length()); omask = (1 << (4 - o)) - 1
    asm = '; '.join(f"{names[ins >> (4 - o)]} {ins & omask}" for ins in code)
    tbl = mach.truth_table_binary(code)
    trig = sum(1 for v in tbl if v == 15) / 256
    nbdep = sum(1 for x in range(16) if len(set(tbl[x*16:(x+1)*16])) > 1)
    # which own states lead to 15 for which neighbour states
    rule = {x: [y for y in range(16) if tbl[x*16+y] == 15] for x in range(16)}
    reach15 = {x: ys for x, ys in rule.items() if ys}
    members = [gen for gen in cnt if fam[gen] == h]
    print(f"\n  family {hex(h)}  cells {c} ({100*c/live:.1f}%)  member genomes {len(members)}  largest same-genome domain {max(sizes[k] for k in range(len(sizes)) if fam[cg[k]] == h)}")
    print(f"    asm: {asm}")
    print(f"    reproduces on {trig*100:.0f}% of (state,neighbour) inputs; neighbour-dependent for {nbdep}/16 own states")
    comp15 = ', '.join(f"x={x}:y∈{ys if len(ys) < 8 else 'most'}" for x, ys in list(reach15.items())[:6])
    print(f"    reaches trigger 15 from: {comp15}{' ...' if len(reach15) > 6 else ''}")
    # self-interaction: what happens when the neighbour is the same family in a typical state
    print(f"    state distribution of its cells: {collections.Counter(state[i] for i in range(nn) if alive[i] and fam[g[i]] == h).most_common(4)}")
# relatedness between heads
hs = [h for h, _ in fcnt.most_common(a.top)]
print('\nHamming distance (bits) between family heads:')
for i, h in enumerate(hs): print('  ' + hex(h) + ' ' + ' '.join(f"{bin(h ^ h2).count('1'):2d}" for h2 in hs))
