# Design C: a self-replicator soup (Tierra/Coreworld-style) on the crawler ISA (2026-10-09)

The Life worlds (docs/05, 06) reproduce and kill cells by the world rule, and the overnight ensemble (results/life/OVERNIGHT_RESULTS.md)
shows every one of them settling into a flat equilibrium: the phenotype space is finite and enumerated, and fitness is defined from
outside. Design C removes both: organisms are programs in one shared memory and copy themselves with their own instructions. The world
only notices a finished copy and attaches a processor to it, keeps the number of processors constant, and mutates. Code:
`sim/soup.py` (reference, normative), `life/u1soup.cu` (CUDA engine, bit-identical), `fast/check_soup.py` (the comparison),
`cluster/run_soup.py` + `cluster/soup_runs.conf` (the ensemble), `cluster/analyze_soup.py` (report); results in `results/soup/`.

## 1. The machine: layout L2, crawler ISA, segment-relative addressing

The crawler ISA `LDIND, STIND, INCM, JNZ` with W = 5 (2 opcode bits, 3 operand bits), as in exp06c (results/exp06b_summary.md):
`LDIND op: A = M[M[op]]`, `STIND op: M[M[op]] = A`, `INCM op: M[op] += 1`, `JNZ op: if A != 0: PC = op`.

**Addressing: segment-relative.** A processor sits at position B. Direct operands address `B + op` (op = 0..7), pointers address
`B + (v mod 32)` where v is the 5-bit word used as a pointer, the PC runs over `B .. B+7`. So a processor sees exactly the 32-word
memory of exp06c, placed at its own position: the 21,818 exp06c copiers and the three intact replicators are valid verbatim.
PC-relative addressing (pointer = PC + signed word) would re-interpret every pointer of every exp06c program and none would copy; wider
words (W = 16 or 20) would make a new ISA whose copiers are unknown. The price: a child must lie at an offset k with `8 <= k <= 24`,
within the 32-word reach, and the genome length is the code length, 8 words (section 7 says what a variable length would need).

**What the reference measured before the rules were fixed** (scratch probes on the 503 copiers listed in
`results/exp06b/l2c_crawl_w5_a5.json`; a lone organism in a 64-word soup, 1,000 steps, segment-relative addressing):

| | copies itself with the exp06c code+1 pre-fill | in a zero soup | in 5 random soups | children per lifetime (faithful copies of its birth genome, write mask reset after each) |
|---|---|---|---|---|
| the 3 intact replicators (0xa2c841f269, 0xa9344f2e8d, 0xd9b17359e8) | 3 of 3 | 0 of 3 | 0xa2c841f269 in 1 of 5, the others never | 0 in zero and random soups; 1 in the code+1 pattern |
| the 500 listed copiers | 500 | 466 | 465 to 469 | exactly 1 for 462 of them, 0 for 41 (environment-dependent), 2 for 2 programs (0x01b30b190e, 0x01b368190e, random soups only) |

Two facts follow. (a) The intact replicators are self-healing only because their pointers wrap round the whole 32-word ring, which
takes about 200 steps and depends on the window holding the code+1 pattern: they read the window and branch on it. In a soup they are
not seeds. (b) **Fecundity is one by construction.** The pointers of a copy loop are code words; a 5-bit word has 3 operand bits, so
eight increments change its opcode and the loop breaks. A copier can move exactly eight words before it destroys itself: one child.
Sustained reproduction needs a loop whose pointers are not its instructions, or a loop that heals, and the exhaustive sweep says no
40-bit program heals in a soup. The same holds in Dimension42's NANO machine (4-bit operands, 16 increments): of its 316 five-byte
replicators 314 have soup fecundity one and two have fecundity two (probe with the same rules, reach 16, L = 5), and all 52,261
"mutating replicators" have zero (their copy is not faithful by definition). So a population of these organisms can persist only as
chains, each organism replaced by its one child, and can grow only if mutation finds fecundity two. Whether it does, in a soup that
keeps supplying random programs, is the first question the experiment answers.

## 2. The world, rule by rule (everything explicit is listed here; nothing else is decided for the organisms)

| # | rule | why this and not something more implicit |
|---|---|---|
| 1 | Memory: a ring of N words of 5 bits (default 2^20). Not protected: anyone can write anywhere in reach, and an overwritten organism runs whatever is there now (Coreworld, not Tierra's allocation). | protection would be a second rule; the overwriting is the ecology |
| 2 | Processors: a fixed number P of slots; each one has a position B, A, PC, age, a 32-bit write mask over its reach, and its birth genome (the 8 words at B when it attached). | the processor is the only thing that is not a word; its state is what the machine needs |
| 3 | Time: every step every processor executes one instruction, reading the memory as it was at the start of the step; the writes are then applied, the highest slot winning a conflict, and every written word remembers its last writer. A tick is S = 32 steps. | lockstep is the only schedule a GPU and a Python reference can reproduce bit for bit; the conflict rule is arbitrary but fixed; the slice S only sets how long a finished child waits for its processor |
| 4 | Birth (the watcher): after a write, if a window of 8 words at offset 8..24 has every word written by this processor since its last division, this processor as every word's last writer, and equals its birth genome word for word, a birth is queued and the mask is cleared. | the ISA has no divide instruction (two opcode bits, all four used). Content-blind "8 contiguous written words" was measured and rejected: it fires at step 52 to 55 on a shifted copy at offset 8, before the real copy lands at offset 9 (step 64), and clearing the mask then loses the real child. Comparison with the current code was rejected: the copiers wear their pointers while copying, so at the moment the eighth word lands their code differs from what they copied (exp06c compared with the original code for the same reason). The last-writer condition is exp06c's "words the program has written" taken literally; without it the first test grew a population in Fibonacci numbers, parents being credited for copies their children had written into their stale mask. |
| 5 | At the tick end the children attach: if the births outnumber the free slots, the oldest living processors die to make room (Tierra's reaper, plain FIFO since the ISA has no faults); child i takes the i-th free slot, PC = 0, A = 0, age 0. | a slot limit is a resource; the oldest-dies rule is Tierra's and the simplest total order |
| 6 | Death by age: `max_age` steps (default 1,024, about 25 copy times). | without it a soup of sterile processors freezes; it is also what returns slots to the inflow (rule 7) |
| 7 | Placement: every slot still free after births and deaths receives a processor at a uniformly random position, with the words there as its birth genome. | processors are conserved; the soup samples its own content, so over time every 40-bit program gets its chance (copier density 2e-8 per placement) and nothing is chosen. Tierra and Avida seeded one hand-written ancestor; Coreworld and the Avida primordial-soup study started from random code, which is the version that cannot miss rare programs. Seeded soups are the control, not the default |
| 8 | Mutation: each word of a child is flipped (one random bit) with probability `mu` at the moment it attaches; `rays` random bit flips per tick anywhere. | with per-write copy errors the watcher could never see a mutant child as a copy; applying the same per-word error when the processor attaches gives the same heritable variation. A ray in a parent's code makes its copies differ from its birth genome, so rays damage rather than mutate lines. Both default to zero: the random inflow and the overwriting by neighbours are mutation enough, and the ensemble varies them |

Not rules, only observation: the owner map (which living processor's segment covers a word) serves the parasite statistic; the shadow
population (section 4) and the activity statistics do not touch the soup.

## 3. What is not in the world

No energy, no fitness, no length, no genome other than "the 8 words a processor started on", no protection, no divide instruction,
no template search. Selection exists only in the sense that a processor that writes a faithful copy of its own birth genome gets a
child and others do not. Parasitism in Tierra's sense (executing another organism's code) is impossible: the PC never leaves the own
segment; reading another organism's words is possible and is measured.

## 4. Measurement

`stats.csv` every `--report-every` ticks: living processors, cumulative births split into faithful (child genome equal to the
parent's birth genome) and mutant (anything else: a birth mutation or a neighbour's overwrite before the processor attached), deaths
by age and by the reaper, placements, rays, distinct birth genomes among the living, Shannon entropy, singletons, the most abundant
genome and its count, parasites (living processors that have read a word inside another living processor's segment), readers outside
their own segment, fertile (processors with at least one child), genomes new to the activity map in this interval, genomes in the map.
`census_<tick>.tsv`: the 50 most abundant birth genomes with count, first-seen tick and disassembly. `activity.tsv` at the end: every
genome that ever had two or more living copies at a census, first-seen, last-seen, cumulative activity (the sum of its census counts,
Bedau's component activity) and peak count. The genome is the birth genome, not the current code, because the copy loops rewrite their
code every step.

**Shadow soup** (Bedau's neutral shadow, on by default): a population of genomes without processors with exactly the soup's
demography: for every real birth a uniformly random living shadow genome is copied with the same `mu`; for every real death a random
shadow genome dies; for every placement the same placed genome enters. No selection. Its `shadow_activity.tsv` gives the activity that
drift and inflow alone produce, and the threshold above which a real genome's activity counts as adaptive.

## 5. Validation

`fast/check_soup.py` runs engine and reference on the same configuration and compares the final memory, every living processor's
state, the counters, every statistics row, every census and both activity files. Identical on seven configurations on adler40 and on
knecht24: a single copier's chain (zero soup), sixteen copiers with mutation and the reaper to extinction, a random soup with rays,
mixed seeds with inflow over 1,000 ticks, the pattern-filled intact replicator, and 462 robust copiers with inflow. Speed: 2^20 words
with 65,536 processors run at about 2,000 to 2,700 ticks per second on the RTX 4090 and 4080, 750 to 1,400 on an RTX 3060.

## 6. The first ensemble (`cluster/soup_runs.conf`) and the predictions written down before it ran

Twelve soups on the five NVIDIA cards: random soups (nothing chosen) at 65,536 and 8,192 processors, with and without birth
mutation and with rays; seeded soups with 4,096 ancestors cycling through the 462 robust copiers at `mu` 0.002, 0.01 and 0.05 with
inflow; a closed seeded soup (no inflow, pure Tierra style); the fecundity-two copier alone; and the three intact replicators in the
code+1 pattern as the record.

1. A population of fecundity-one organisms decays: each organism is replaced by at most one child, every failed copy ends a chain. Live
   processors stay at P because of the inflow; the signal is the birth rate, which stays at the inflow's copier rate (one copier per
   several thousand ticks, one child each) unless a fecundity-two mutant appears and multiplies.
2. In the dense soup (one processor per 16 words) a finished copy is often overwritten before its processor attaches; the sparse soup
   (one per 128 words) shows whether chains live longer when there is less stirring.
3. Lengths cannot change (the genome is the 8-word code); parasites in the measured sense (reads into other living processors) will be
   common and uninformative in a dense random soup, since a third of all processors read beyond their own 8 words.

## 7. What to change next if the predictions hold

The pointer words have to leave the genome. The cheapest version in this machine is a sixth word bit (W = 6: 4-bit operands, 16 direct
addresses, pointers that survive 16 increments, reach 64), which makes a two-child loop encodable; its copiers are unknown (a 2^48
sweep per ISA), so the search would have to be by evolution in the soup itself or by a sampled sweep. The alternative is a register for
the pointer (Tierra's approach), which is a different machine. A variable genome length needs either a divide instruction or a
watcher that accepts a length, and both are new rules.
