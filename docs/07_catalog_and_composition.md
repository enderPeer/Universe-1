# The champion catalog, and how far composition reaches

## 1. Catalog of every function of the champion ISA (unary)
`u1map catalog` indexes a map: every function gets a row with structural descriptors, sorted by class,
then name, then step cost, then program id. Output for `SWAP,ADD,NAND,SKZ`:
`results/catalog/w4_o2_add.tsv.gz` (1,829,051 rows, 35 MB compressed) and `w4_o2_add.summary.json`.

Columns: `index, program, name, class, sort_class, image (distinct outputs), fixed_points, bijective,
involution, idempotent, affine_a, affine_b (f = a*x+b mod 16 when set), xor_affine (linear over GF(2) plus a
constant), monotone, depends_bits (which input bits change the output), settle_iters (iterations of f until
the image stops shrinking), cycles (cycle type for permutations, e.g. "1^14 2^1" = one transposition),
steps, halts, table`.

| sort class | count | meaning |
|---|---:|---|
| constant | 16 | all 16 constants |
| affine-mod16 | 240 | every a*x+b with a != 0: all 256 affine maps exist (with the constants) |
| xor-affine | 3,708 | GF(2)-linear maps plus constant: 3,820 in total incl. those also named |
| named | 1,891 | other functions with a vocabulary name (`!(x*x)`, `bitrev(x)<10`, ...) |
| permutation | 14,526 | bijections without a name; 15,378 bijections in total, 1,615 involutions |
| near-predicate | 41,614 | image size <= 2 without a name |
| other | 1,767,056 | everything else: 1.63 M of them depend on all four input bits |

Image-size histogram (how many outputs a function can produce): 16 -> 15,378, 15 -> 14,678, ..., peak at
image 4-8 (about 200,000 each), 1 -> 16. Only 1,679 functions are monotone. 46,013 are idempotent.
No witness halts (the ISA has no HALT), so every function costs 256 steps.

Querying: `zcat results/catalog/w4_o2_add.tsv.gz | awk -F'\t' '$8==1 && $9==1'` lists all involutive
permutations; `$5=="affine-mod16"` the affine maps; `$15=="0011"` functions of the low two bits only.
Rebuild for any unary map: `u1map catalog --map results/maps/<m>.u1prog --out <m>.tsv --summary <m>.json`
(28 s for the champion on 4 threads). The binary map (24.68 M functions) needs the same command on a
64 GB node; descriptors for binary functions (commutative, associative, has identity, latin square,
depends on x only / y only) are the next addition.

## 2. "4 bytes is not much": what composition buys

A chain of programs is composition of functions: stage k's output becomes stage k+1's input (A is
carried, memory is reset, y is re-supplied for binary stages). The chained function is f_k o ... o f_1.

**Exact result.** The champion map contains `x+1` (a 16-cycle, program 0x56), the transposition of 0 and 15
(program 0xc8, table 15,1,2,...,14,0) and functions of image size 15 (14,678 of them, e.g. 0x88c). A 16-cycle
and a transposition generate the full symmetric group S_16; S_16 plus any map of rank 15 generates the
full transformation monoid T_16. Therefore **every one of the 16^16 = 1.8e19 unary 4-bit functions is a
composition of champion programs.** The 32-bit genome is not the limit; the number of stages is.

**How many stages.** With |G| = 1,829,051 generators, at most |G|^d functions are reachable with d stages:
d=1: 1.8e6, d=2: <= 3.3e12, d=3: <= 6.1e18, d=4: <= 1.1e25 > 1.8e19. So some functions need at least 4
stages, and most are expected at 4-5. Measured so far (basis-restricted search, not the full map): the swap
ISA goes 1.46 M -> 2.54 M distinct functions at 2 stages over a 4,000-function basis; the corpus gained
`x*x`, `x>=8`, `(x+y)*3+5` and others at 2-3 stages. Cost is linear in stages: 256 steps per champion
stage, 2-16 per halting stage of the swap ISA.

**What the cluster can do exactly.**
| question | work | feasible? |
|---|---|---|
| is target f a 2-stage composition? (full map) | for each g: constraint table; if g bijective, h = f o g^-1 is one hash lookup; rank-15/14/13 g: 16/256/4096 fills | yes: ~1e8 lookups per target, thousands of targets per minute on one GPU (lower bound on depth-2 reach; low-rank g need the fill enumeration, exponential) |
| exact number of distinct 2-stage functions | 3.3e12 compositions, dedup | no: the set itself does not fit (terabytes); estimate by sampling random pairs into a 2^36-bit sketch (8 GB) on the 4090 |
| is f a 3-stage composition? (full map) | 3.3e12 pairs x constraint check per target | borderline: about 1 minute per target on 9 GPUs; fine for the 16 missing corpus functions, not for bulk |
| 4+ stages | 6e18 | only with a restricted basis (what `u1map translate --depth 4` does) |

**Bigger programs instead of chains.** 5-byte programs (2^40) are a 256x larger sweep: Dimension42 ran
2^40 five-byte programs on the same 9 GPUs in 92 s with 64-step runs; our 256-step, 16-input runs are
about 4x more work, so **one 5-byte unary sweep is roughly 10 minutes**, binary about 2.5 hours. The
distinct-function set may reach 1e9+ entries (20+ GB), which needs CPU-side merging on a 64 GB node instead
of the per-GPU hash table. 6 bytes (2^48) is 256x more again: days per ISA, sampling only. So the realistic
frontier is: exhaustive to 5 bytes, exact chain search to 2 stages for any target and 3 stages for a few,
heuristic beyond.

**Recommended experiments (exp07).**
1. Depth-2 reach of the champion: sample 100,000 random 4-bit functions, test 2-stage membership with the
   high-rank-g method; report the fraction reached (lower bound) and the 16 missing corpus functions.
2. 5-byte sweep of the champion in unary mode (10 min) with CPU-side merge: how many of the 1.8e19
   functions does one extra byte buy, versus one extra stage?
3. Binary catalog of the 24.68 M map on adler40.
