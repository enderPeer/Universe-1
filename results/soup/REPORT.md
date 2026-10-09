# Design C soup, first ensemble (2026-10-09): bounded chains, no growth, and why

Rules, every explicit decision and the measurements behind them: `docs/12_design_c_soup.md`. Run list: `cluster/soup_runs.conf`.
Per-run table, chain tables, dominant genomes and the Bedau activity statistics against the neutral shadow: `ANALYSIS.md`
(`cluster/analyze_soup.py`; curves in `curves.png`, activity distributions in `activity.png`). Engines: `sim/soup.py` (reference)
and `life/u1soup.cu` (CUDA), bit-identical on ten configurations (`fast/check_soup.py`). Sixteen soups ran on adler40 (RTX 4090,
4080) and knecht24 (three RTX 3060), about 60 million ticks in all; nothing ran on the AMD nodes (no Vulkan port yet).

## The answer in one paragraph

The soup shows **transient novelty and bounded reproduction, not open-ended evolution**. Self-copying programs appear out of random
code (one per 20,000 to 130,000 ticks depending on the inflow), and in a sparse soup a single spontaneous copier starts a chain of up to
34 generations, every child a faithful copy made by the organism's own instructions. But every chain ends, no lineage ever grows, and no
genome ever outruns the neutral shadow. The reason is structural and was measured before the runs: on this machine every copy loop uses
its own instruction words as pointers, a 3-bit operand field survives eight increments, so a copier makes exactly one child and then
breaks. A population of fecundity-one organisms cannot grow, selection has nothing to amplify, and mutation can only shorten chains.
Open-ended evolution needs fecundity above one, and that needs pointers that are not code: the next experiment is a machine change, not
a longer run.

## What happened, run by run

| soup | what was asked | what happened |
|---|---|---|
| random soup, processor inflow (65,536 and 8,192 processors, mu 0 and 0.01; 1.6 to 2.5 M ticks, stopped as frozen) | does a soup that samples its own content find copiers? | No. The soup cools within 1,000 ticks: zeros and other fixed points spread (6 % of all placements land on all-zero words, inert under LDIND), the processor inflow then samples a frozen soup, and births stay at the 4 copiers of the initial random fill (0 at 8,192 processors). |
| random soup, random-code inflow, dense (65,536 processors, life 1,024 steps; 2.1 M ticks) | does a soup that keeps sampling program space find copiers, and do they reproduce? | Copiers appear (26 births, 24 of them isolated), but 7 of 26 children were overwritten before their processor attached and no chain exceeded 2. Each processor writes about 16 words per tick, so with one processor per 16 words every word of the soup is rewritten about once per tick; a copy needs 16 intact words for two ticks. |
| random-code inflow, 8,192 processors, life 1,024 (6 M ticks) | less stirring | 38 births in 20 chains, one chain of 14 generations; 3.3 copiers per million ticks. |
| random-code inflow, 2,048 processors, life 1,024 (6 M ticks) | less stirring still | 8 births, 7 chains, longest 2; the inflow (64 placements per tick) samples too slowly: one copier per 750,000 ticks. |
| **random-code inflow, 2,048 processors, life 128 steps (6 M ticks)** | the same stirring with 8x the sampling | **128 births in 46 chains: 34, 20, 12, 8, 4, 4, 4 generations and 36 single births; 112 faithful, 16 children altered by a neighbour's write before attaching, of which one (0x60328b40c9) copied itself once more with a further change; every chain is a single genome copied at one or two fixed offsets.** 7.7 copiers per million ticks. |
| random-code inflow, 8,192 processors, life 128 (6 M ticks) | more sampling, more stirring | 233 births in 138 chains (23 copiers per million ticks, three times the sparse soup), but shorter chains: 26, 17, 11, then ten of 4; 39 children altered before attaching, two of which reproduced once more. |
| random-code inflow, 65,536 processors, mu 0.01 (3 M ticks) | birth mutation in the dense soup | as the dense soup without mutation: 37 births in 35 chains, none longer than 2. |
| seeded: 4,096 ancestors cycling through the 462 robust exp06c copiers, processor inflow, mu 0.002 / 0.01 / 0.05 (0.5 to 0.8 M ticks) | the brief's soups | 839 / 843 / 806 births, all within the first few hundred ticks, then none: every ancestor made at most one child, and the children's chains ended under the stirring of 65,536 random processors. Births were mutant in 20 to 44 % of cases, mostly by overwrite rather than by mu. |
| seeded, closed (no inflow), mu 0.01 | pure Tierra: ancestors only | 12,767 births from 4,096 ancestors, extinct at tick 288: about 3 generations per ancestor on average, then nothing. |
| the fecundity-two copier 0x01b30b190e, 4,096 copies, mu 0.01 | the one program that made two children in the probe | 1,163 births, 917 faithful, 123 distinct genomes by birth mutation, all within the first 1,000 ticks; no persistent line. |
| random soup, processor inflow, 1 ray per tick | background mutation instead of birth mutation | 70 births, 64 of them "chains" of the uniform genome LDIND 7 x 8, which is not a copy loop (below); 6 real copiers, no chain above 1. |
| the three intact exp06c replicators, one ancestor each in the code+1 pattern they were found in, no inflow | the record | exactly one child each at tick 6 (offsets 16, 22, 21), both dead of age by tick 39. In a zero or random soup they never copy (docs/12, section 1). |

Two artefacts were found and removed from the counts: (a) a uniform genome (all eight words equal, e.g. LDIND 7 x 8) is "reproduced"
by any loop that writes that constant into eight words, which happens when the processor's own code has been overwritten into a writer;
these chains are listed separately in `ANALYSIS.md`. (b) Placements land on the same position by chance (P^2 / 2N pairs among the
living), so identical genomes with 2 to 4 copies occur in every census of soup and shadow alike; the Bedau activity maps are mostly
these collisions, which is why the shadow's maximum activity equals the soup's in every run and no genome counts as adaptive. The
chains of births (`births.tsv`, logged per birth) are the sensitive instrument in this soup.

## The three regimes

1. **Cold soup** (inflow of processors only): random code converges to fixed points (zeros, LDIND 7 blocks); the soup stops sampling
   program space; nothing happens after the initial fill. Rays at one per tick do not reheat it.
2. **Hot dense soup** (random-code inflow, one processor per 16 words): program space is sampled at 2,300 programs per tick and copiers
   appear every 20,000 to 80,000 ticks, but every word is rewritten about once per tick, so copies die before their processor attaches.
3. **Sparse soup** (one processor per 512 words, short processor life): copiers appear every 130,000 ticks and chains of up to 34
   generations form, each a faithful lineage of one genome, with occasional variation by overwrite. Chains end when a copy is damaged;
   with fecundity one there is no second line to carry on.

Sampling and stirring are the same quantity (placements bring code and processors write), so no setting of P, N and lifetime gives
both frequent copiers and long chains; the 2,048-processor, 128-step soup is the best compromise found, and its best lineage is 34
generations.

## Against the predictions written down before the runs (docs/12, section 6)

1. "A population of fecundity-one organisms decays; the birth rate stays at the inflow's copier rate unless a fecundity-two mutant
   appears and multiplies." Confirmed; no fecundity-two mutant appeared in 60 million ticks. The one observed two-step mutant line
   (0x61b28b40c9 to 0x60328b40c9 to 0x60328b4293) still had fecundity one.
2. "The dense soup overwrites finished copies before their processor attaches; the sparse soup shows whether chains live longer."
   Confirmed, with the numbers above (27 % of dense-soup children altered; chains of 34 in the sparse soup).
3. "Lengths cannot change; parasite reads are common and uninformative." Confirmed: a third to a half of all processors read beyond
   their own segment in every soup.

Not predicted: the cooling of the processor-inflow soup, and the degenerate uniform-genome "replicators".

## Verdict on open-endedness

By Bedau's classes the soup is class 1 to 2 at best: novelty exists (new copier genomes keep appearing from the inflow, 46 distinct
roots in the sparse soup), but none of it is adaptive by the shadow test, none accumulates, and no lineage persists beyond a few dozen
generations. The Life worlds reached flat equilibria because their phenotype space was finite and fitness external; the soup fails
earlier and for a sharper reason: the organisms cannot have more than one child.

## What to change next

- **Pointers out of the genome.** W = 6 (4-bit operands, 16 direct addresses, pointers that survive 16 increments, reach 64) makes a
  two-child loop encodable; the ISA is the same four primitives. Its copiers are unknown (2^48 per sweep), so the soup itself is the
  search: a sparse random-code soup at W = 6 either finds growing lineages or proves the same ceiling at two children.
- **A register for the pointer** (Tierra's and Avida's answer) is the other route and a different machine; it would also allow a
  divide instruction and variable length.
- **Keep the sparse regime** (one processor per 512 words, 128-step life, random-code inflow) as the baseline, and log births; the
  census-based activity statistics need a soup where lineages live longer than a census interval before they can say anything.
- **Vulkan port** of `life/u1soup.cu` for the four AMD cards, which doubles the cluster for this experiment.
