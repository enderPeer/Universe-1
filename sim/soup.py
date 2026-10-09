"""Design C reference: a Tierra/Coreworld-style soup for self-replicating programs on a Universe-1 layout-L2 ISA (docs/12_design_c_soup.md).
Normative for life/u1soup.cu; fast/check_soup.py compares the two.

World (every rule listed; nothing else is decided for the organisms):
- Memory: a ring of N words of W bits. Processors (at most P slots): position B, A, PC, age, write mask over the 2^a-word reach,
  birth genome (the L = 2^p words at B when the processor attached). Segment-relative addressing: direct operands address B+op,
  pointers B + (v mod 2^a), the PC runs over B .. B+L-1. Exactly the exp06c machine placed at B: the exp06c copiers are valid verbatim.
- Time: every step every live processor executes one instruction reading the memory as it was at the start of the step; the writes
  are then applied in slot order (the highest slot wins a conflict) and each written word remembers its last writer. A tick is S steps;
  births, deaths, placements, rays and the statistics happen at tick ends.
- Birth (the watcher): after a write, if some window of L words at offset k in [L, 2^a - L] from B has every word written by this
  processor since its last division, this processor as every word's last writer, and equals its birth genome word for word, the write
  mask is cleared and a birth is queued (one per processor per tick). At the tick end: if the births outnumber the free slots, the
  oldest living processors die to make room (Tierra's reaper); the children's words are mutated in memory (each word independently
  with probability mu: one random bit flipped), then child i (parents in slot order) attaches to the i-th free slot with the words as
  they now are as its birth genome; PC = 0, A = 0, age 0, empty mask. The parent runs on.
- Death: age >= max_age steps (checked after the births). Memory is not protected (Coreworld): an overwritten organism runs whatever
  is there now. The owner map (which living processor's segment covers a word, the highest slot when segments overlap) only serves
  the parasite statistic (reads from another living organism's segment).
- Placement (--spontaneous 1): every slot still free after births and deaths receives a processor at a uniformly random position, with
  the words there as its birth genome. Processors are conserved; the soup samples its own content and nothing is chosen.
- Rays: --rays R expected single-bit flips per tick anywhere in memory.
- Shadow (Bedau's neutral shadow for the activity statistics): a population of genomes without processors: for every real birth a
  copy of a uniformly random living shadow genome, mutated with the same mu; for every real death a random shadow death; for every
  placement the same placed genome. Same size as the soup at every tick end, no selection.
- Statistics (stats.csv every --report-every ticks, census_<tick>.tsv every --census-every ticks, activity.tsv and shadow_activity.tsv
  at the end): the genome is the birth genome. The activity map keeps a genome once it has had at least two living copies at one
  census, and from then on accumulates its census counts (Bedau's component activity); single copies are counted as singletons.
usage: python sim/soup.py --N 4096 --P 256 --ticks 1000 --seed 1 [--ancestors 0x01b30b20c9[,...]|@file --n-ancestors 1 --spontaneous 0]
       [--fill zero|random|pattern] [--mu 0.01] [--rays 0] [--S 32] [--max-age 1024] [--report-every 10] [--census-every 100] [--out-dir d] [--dump-final]
"""
from __future__ import annotations
import argparse, collections, csv, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.machine_l2 import ConfigL2
M64 = (1 << 64) - 1

def mix(x):
    x &= M64; x ^= x >> 33; x = (x * 0xff51afd7ed558ccd) & M64; x ^= x >> 33; x = (x * 0xc4ceb9fe1a85ec53) & M64; x ^= x >> 33; return x
def hsh(seed, tick, cell, k):
    return mix(seed ^ mix((tick * 0x9E3779B97F4A7C15 + cell) & M64) ^ ((k * 0xD1B54A32D192ED03) & M64))
SHADOW_SEED = 0x5AD0

class Activity:
    """Bedau component activity over the census ticks, bounded: a genome enters when it has >= 2 copies at a census."""
    def __init__(self): self.first = {}; self.last = {}; self.act = collections.Counter(); self.peak = collections.Counter(); self.singletons = 0; self.new = 0
    def census(self, counts, tick):
        self.singletons = 0; self.new = 0
        for g, c in counts.items():
            if g not in self.first:
                if c < 2: self.singletons += 1; continue
                self.first[g] = tick; self.new += 1
            self.act[g] += c; self.last[g] = tick; self.peak[g] = max(self.peak[g], c)
    def write(self, path, width):
        with open(path, 'w') as f:
            f.write('genome\tfirst_seen\tlast_seen\tactivity\tpeak\n')
            for g in sorted(self.first, key=lambda g: (-self.act[g], g)): f.write(f'0x{g:0{width}x}\t{self.first[g]}\t{self.last[g]}\t{self.act[g]}\t{self.peak[g]}\n')

class Shadow:
    def __init__(self): self.g = []; self.live = []   # g grows with every shadow birth; live: indices of the living (random picks)
    def add(self, genome): self.g.append(genome); self.live.append(len(self.g) - 1)
    def kill_random(self, r): i = r % len(self.live); self.live[i] = self.live[-1]; self.live.pop()
    def parent_random(self, r): return self.g[self.live[r % len(self.live)]]
    def counts(self): return collections.Counter(self.g[i] for i in self.live)

class Soup:
    def __init__(self, a):
        self.a = a; cfg = ConfigL2(W=a.W, a=a.a, p=a.p, I=a.W); self.cfg = cfg; self.isa = tuple(a.isa.split(','))
        self.o = max(1, (len(self.isa) - 1).bit_length()); self.opmask = (1 << (cfg.I - self.o)) - 1; self.sh = cfg.I - self.o
        self.N, self.P, self.L, self.R = a.N, a.P, 1 << a.p, 1 << a.a; self.mask = cfg.mask; self.amask = cfg.amask; self.W = a.W
        assert self.L * 2 <= self.R and self.L * a.W <= 64, 'L <= reach/2 and genome <= 64 bits'
        self.seed = a.seed; self.mu_thr = int(a.mu * (1 << 32)); self.width = (self.L * a.W + 3) // 4
        self.M = [0] * self.N; self.owner = [-1] * self.N; self.last_writer = [-1] * self.N
        P = self.P; self.alive = [0] * P; self.B = [0] * P; self.A = [0] * P; self.PC = [0] * P; self.age = [0] * P; self.wmask = [0] * P
        self.genome = [0] * P; self.pending = [-1] * P; self.children = [0] * P; self.ext_read = [0] * P; self.out_read = [0] * P; self.seq = [0] * P
        self.nseq = 0; self.shadow = Shadow() if a.shadow else None
        self.c = dict(births=0, faithful=0, mutant=0, deaths_age=0, deaths_reaper=0, placements=0, rays=0)
        self.act = Activity(); self.sact = Activity(); self.tick = 0; self.init()

    # ---- helpers
    def code_words(self, prog): return [(prog >> (k * self.W)) & self.mask for k in range(self.L)]
    def read_genome(self, B): return sum(self.M[(B + j) % self.N] << (j * self.W) for j in range(self.L))
    def attach(self, slot, B, genome):
        self.alive[slot] = 1; self.B[slot] = B % self.N; self.A[slot] = 0; self.PC[slot] = 0; self.age[slot] = 0; self.wmask[slot] = 0
        self.genome[slot] = genome; self.pending[slot] = -1; self.children[slot] = 0; self.ext_read[slot] = 0; self.out_read[slot] = 0
        self.seq[slot] = self.nseq; self.nseq += 1
        for j in range(self.L): x = (B + j) % self.N; self.owner[x] = max(self.owner[x], slot)
    def kill(self, slot):
        self.alive[slot] = 0; self.pending[slot] = -1
        for j in range(self.L):
            x = (self.B[slot] + j) % self.N
            if self.owner[x] == slot: self.owner[x] = -1
    def free_slots(self): return [s for s in range(self.P) if not self.alive[s]]
    def disasm(self, g): return '; '.join(f'{self.isa[w >> self.sh]} {w & self.opmask}' for w in self.code_words(g))

    # ---- initialisation
    def init(self):
        a = self.a; anc = []
        if a.ancestors.startswith('@'): anc = [int(l.split()[0], 16) for l in open(a.ancestors[1:]) if l.strip() and not l.startswith('#')]   # @file: one program per line
        elif a.ancestors: anc = [int(x, 16) for x in a.ancestors.split(',')]
        if a.fill == 'random':
            for i in range(self.N): self.M[i] = hsh(self.seed, 0, i, 0) & self.mask
        elif a.fill == 'pattern':
            assert anc, 'pattern fill needs an ancestor'; code = self.code_words(anc[0])
            for i in range(self.N): self.M[i] = (code[i % self.L] + 1) & self.mask
        n = a.n_ancestors if anc else 0; assert n <= self.P
        for i in range(n):
            B = (i * self.N) // n; code = self.code_words(anc[i % len(anc)])
            for j in range(self.L): self.M[(B + j) % self.N] = code[j]
        for i in range(n):
            B = (i * self.N) // n; self.attach(i, B, self.read_genome(B))
            if self.shadow: self.shadow.add(self.genome[i])
        self.place_spontaneous()

    def place_spontaneous(self):
        """Every free slot (in slot order) gets a processor at a random position; draw j for the j-th free slot."""
        if not self.a.spontaneous: return
        for j, s in enumerate(self.free_slots()):
            B = hsh(self.seed, self.tick, 2, j) % self.N; self.attach(s, B, self.read_genome(B)); self.c['placements'] += 1
            if self.shadow: self.shadow.add(self.genome[s])

    # ---- one step for all processors
    def step(self):
        M, N, L, amask, mask = self.M, self.N, self.L, self.amask, self.mask; isa = self.isa; sh = self.sh; opmask = self.opmask
        writes = []; wrote = []   # (address, value, slot) in slot order; the last entry per address wins
        for s in range(self.P):
            if not self.alive[s]: continue
            B = self.B[s]; ins = M[(B + self.PC[s]) % N]; name = isa[ins >> sh]; op = ins & opmask; self.PC[s] = (self.PC[s] + 1) % L; A = self.A[s]
            def rd(addr): return M[(B + (addr & amask)) % N]
            def wr(addr, v): writes.append(((B + (addr & amask)) % N, v & mask, s)); self.wmask[s] |= 1 << (addr & amask)
            def setA(v): self.A[s] = v & mask
            if name == 'LDIND':
                p = rd(op) & amask; x = (B + p) % N; setA(M[x])
                if p >= L: self.out_read[s] = 1
                if self.owner[x] not in (-1, s): self.ext_read[s] = 1
            elif name == 'STIND': wr(rd(op), A)
            elif name == 'INCM': wr(op, rd(op) + 1)
            elif name == 'DECM': wr(op, rd(op) - 1)
            elif name == 'JNZ':
                if A != 0: self.PC[s] = op % L
            elif name == 'JZ':
                if A == 0: self.PC[s] = op % L
            elif name == 'JMP': self.PC[s] = op % L
            elif name == 'NOP': pass
            elif name == 'LD': setA(rd(op))
            elif name == 'ST': wr(op, A)
            elif name == 'LDI': setA(op)
            elif name == 'NAND': setA(~(A & rd(op)))
            elif name == 'ADD': setA(A + rd(op))
            elif name == 'SWAP': wr(op, A); setA(rd(op))
            elif name == 'SKZ':
                if A == 0: self.PC[s] = (self.PC[s] + 1) % L
            elif name == 'SKNZ':
                if A != 0: self.PC[s] = (self.PC[s] + 1) % L
            elif name == 'HALT': self.PC[s] = (self.PC[s] - 1) % L   # a halted processor spins on HALT until it dies
            else: raise ValueError(name)
            if name in ('STIND', 'INCM', 'DECM', 'ST', 'SWAP'): wrote.append(s)
            self.age[s] += 1
        for x, v, s in writes: M[x] = v; self.last_writer[x] = s
        full = (1 << L) - 1
        for s in wrote:   # the watcher: a window counts only where this processor wrote every word and nobody wrote it since
            if self.pending[s] >= 0: continue
            m = self.wmask[s]; B = self.B[s]; g = self.genome[s]
            for k in range(L, self.R - L + 1):
                if (m >> k) & full == full and all(self.last_writer[(B + k + j) % N] == s for j in range(L)) and self.read_genome(B + k) == g: self.pending[s] = k; self.wmask[s] = 0; break

    # ---- tick end: reaper, births, deaths by age, placements, rays, shadow
    def tick_end(self):
        a = self.a; parents = [s for s in range(self.P) if self.alive[s] and self.pending[s] >= 0]; free = self.free_slots(); deaths = 0
        Bc = [(self.B[s] + self.pending[s]) % self.N for s in parents]
        if len(parents) > len(free):   # the reaper: the oldest living processors make room (a reaped parent's child still attaches)
            victims = sorted((s for s in range(self.P) if self.alive[s]), key=lambda s: self.seq[s])[:len(parents) - len(free)]
            for s in victims: self.kill(s)
            self.c['deaths_reaper'] += len(victims); deaths += len(victims); free = self.free_slots()
        palive = [self.alive[s] for s in parents]; pgs = [self.genome[s] for s in parents]   # snapshots before any child attaches (a child may take a reaped parent's slot)
        for i, s in enumerate(parents):   # all birth mutations first (bit flips commute), then the genomes are read
            for j in range(self.L):
                r = hsh(self.seed, self.tick, 1, i * self.L + j)
                if (r & 0xFFFFFFFF) < self.mu_thr: x = (Bc[i] + j) % self.N; self.M[x] ^= 1 << ((r >> 32) % self.W)
        births = []
        for i, s in enumerate(parents):
            pg = pgs[i]; self.pending[s] = -1; g = self.read_genome(Bc[i])
            if palive[i]: self.children[s] += 1
            self.attach(free[i], Bc[i], g); self.c['births'] += 1; self.c['faithful' if g == pg else 'mutant'] += 1; births.append(g)
        for s in range(self.P):
            if self.alive[s] and self.age[s] >= a.max_age: self.kill(s); self.c['deaths_age'] += 1; deaths += 1
        if self.shadow:   # births first, then deaths: the shadow is never empty while the soup is not
            sh = self.shadow
            for i, g in enumerate(births):
                p = sh.parent_random(hsh(self.seed ^ SHADOW_SEED, self.tick, 3, i)); gm = p
                for j in range(self.L):
                    r = hsh(self.seed ^ SHADOW_SEED, self.tick, 1, i * self.L + j)
                    if (r & 0xFFFFFFFF) < self.mu_thr: gm ^= 1 << (j * self.W + (r >> 32) % self.W)
                sh.add(gm)
            for i in range(deaths): sh.kill_random(hsh(self.seed ^ SHADOW_SEED, self.tick, 2, i))
        self.place_spontaneous()
        nr = int(a.rays) + (1 if (hsh(self.seed, self.tick, 3, 0) & 0xFFFFFFFF) < int((a.rays - int(a.rays)) * (1 << 32)) else 0)
        for i in range(nr):
            r = hsh(self.seed, self.tick, 3, 1 + i); self.M[r % self.N] ^= 1 << ((r >> 40) % self.W); self.c['rays'] += 1
        if self.shadow: assert len(self.shadow.live) == sum(self.alive)

    def run(self):
        a = self.a; out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
        csvf = open(out / 'stats.csv', 'w', newline=''); w = csv.writer(csvf)
        w.writerow('tick live births faithful mutant deaths_age deaths_reaper placements rays distinct_genomes entropy singletons top_count top_genome parasites out_readers fertile new_genomes genomes_ever shadow_distinct shadow_entropy shadow_singletons shadow_new shadow_ever'.split())
        for t in range(a.ticks + 1):
            self.tick = t
            if t % a.report_every == 0: self.report(w, out, t % a.census_every == 0)
            if t == a.ticks: break
            for _ in range(a.S): self.step()
            self.tick_end()
            if not any(self.alive): self.tick = t + 1; self.report(w, out, True); print(f'extinct at tick {t + 1}'); break
        csvf.close(); self.act.write(out / 'activity.tsv', self.width)
        if self.shadow: self.sact.write(out / 'shadow_activity.tsv', self.width)
        if a.dump_final: self.dump(out / 'final.txt')

    def report(self, w, out, census):
        live = [s for s in range(self.P) if self.alive[s]]; cnt = collections.Counter(self.genome[s] for s in live); n = len(live)
        self.act.census(cnt, self.tick)
        H = 0.0 - sum(c / n * math.log2(c / n) for c in cnt.values()) if n else 0.0; top = cnt.most_common(1)[0] if cnt else (0, 0)
        row = [self.tick, n, self.c['births'], self.c['faithful'], self.c['mutant'], self.c['deaths_age'], self.c['deaths_reaper'], self.c['placements'], self.c['rays'],
               len(cnt), f'{H:.4f}', self.act.singletons, top[1], f'0x{top[0]:0{self.width}x}', sum(self.ext_read[s] for s in live), sum(self.out_read[s] for s in live),
               sum(self.children[s] > 0 for s in live), self.act.new, len(self.act.first)]
        if self.shadow:
            scnt = self.shadow.counts(); self.sact.census(scnt, self.tick); sn = sum(scnt.values())
            sH = 0.0 - sum(c / sn * math.log2(c / sn) for c in scnt.values()) if sn else 0.0
            row += [len(scnt), f'{sH:.4f}', self.sact.singletons, self.sact.new, len(self.sact.first)]
        else: row += [''] * 5
        w.writerow(row)
        if census:
            with open(out / f'census_{self.tick:08d}.tsv', 'w') as f:
                f.write('genome\tcount\tfirst_seen\tdisassembly\n')
                for g, c in cnt.most_common(50): f.write(f'0x{g:0{self.width}x}\t{c}\t{self.act.first.get(g, self.tick)}\t{self.disasm(g)}\n')

    def dump(self, path):
        """Full state for fast/check_soup.py: memory as two hex digits per word, then one line per living slot, then the counters."""
        with open(path, 'w') as f:
            f.write(f'soup N {self.N} P {self.P} W {self.W} a {self.a.a} p {self.a.p} tick {self.tick}\n')
            f.write(''.join(f'{v:02x}' for v in self.M) + '\n')
            for s in range(self.P):
                if self.alive[s]: f.write(f'{s} B {self.B[s]} A {self.A[s]} PC {self.PC[s]} age {self.age[s]} wmask {self.wmask[s]:08x} genome {self.genome[s]:x} children {self.children[s]} ext {self.ext_read[s]} out {self.out_read[s]} seq {self.seq[s]}\n')
            f.write('counters ' + json.dumps(self.c, sort_keys=True) + '\n')

def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--N', type=int, default=4096); ap.add_argument('--P', type=int, default=256); ap.add_argument('--W', type=int, default=5); ap.add_argument('--a', type=int, default=5); ap.add_argument('--p', type=int, default=3)
    ap.add_argument('--isa', default='LDIND,STIND,INCM,JNZ'); ap.add_argument('--S', type=int, default=32); ap.add_argument('--ticks', type=int, default=1000); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--fill', default='random', choices=['zero', 'random', 'pattern']); ap.add_argument('--ancestors', default=''); ap.add_argument('--n-ancestors', type=int, default=1)
    ap.add_argument('--spontaneous', type=int, default=1); ap.add_argument('--mu', type=float, default=0.0); ap.add_argument('--rays', type=float, default=0.0); ap.add_argument('--max-age', type=int, default=1024)
    ap.add_argument('--report-every', type=int, default=10); ap.add_argument('--census-every', type=int, default=100); ap.add_argument('--shadow', type=int, default=1)
    ap.add_argument('--out-dir', default='results/soup/ref'); ap.add_argument('--dump-final', action='store_true')
    return ap.parse_args(argv)

if __name__ == '__main__':
    a = parse(); s = Soup(a); s.run()
    print(f'tick {s.tick}: live {sum(s.alive)} births {s.c["births"]} (faithful {s.c["faithful"]}, mutant {s.c["mutant"]}) deaths age/reaper {s.c["deaths_age"]}/{s.c["deaths_reaper"]} placements {s.c["placements"]} genomes in the activity map {len(s.act.first)}')
