# Universe-1 copiers versus the exhaustive Avida replicator enumeration (Nitash C G, LaBar, Hintze, Adami 2017)

Paper: "Origin of Life in a Digital Microcosm", arXiv:1701.03993 (q-bio.PE, 2017). All 26^8 = 2.09 x 10^11 Avida genomes of
length 8 were run through Avida's Analyze Mode; 914 are viable self-replicators (1 in 229 million, information content about
5.9 mers); none exist at length 5, 6 or 7, so 8 is the minimal replicator length in Avida. The replicators form clusters in the
Hamming-distance-1 network (four clusters of 212, 199, 165 and 95 hold about 75 %, 20 are singletons), split into two classes that
do not intermix (fg-type, hc-type), differ in evolvability, and three genotypes win about 65 % of primordial-soup competitions.
The 914 sequences are public (figshare 10.6084/m9.figshare.4551559, CC BY 4.0, one 8-kB text file).

## The two machines

| | Avida (heads instruction set) | Universe-1 layout L2, crawler ISA |
|---|---|---|
| alphabet | 26 instructions, including h-alloc, h-copy, h-divide, h-search, if-label, nop labels, heads | 4 primitives LDIND, STIND, INCM, JNZ (2 opcode + 2 operand bits) |
| genome | 8 instructions = 8 x log2(26) = 37.6 bits, 2.09 x 10^11 genomes | 8 instructions = 32 bits, 4.29 x 10^9 programs |
| replication machinery | built in: h-copy moves one instruction from the read head to the write head and advances both; h-alloc makes room; h-divide separates the child; nop templates and if-label close the loop | none: a copy loop must be built from pointer loads/stores and pointer increments, and the pointers are code words |
| what counts | a viable offspring identical to the parent, parent and child both alive after h-divide | all 8 code words written into a non-overlapping window (checked after every write); "intact" if the parent code is unchanged at that moment |
| result | 914 replicators, minimal length 8 | 141 copiers, 16 persisting to step 256, 0 intact; identical with 32 words of memory |
| density | 4.4 x 10^-9 | 3.3 x 10^-8 (copies), 0 (intact replicators) |
| clusters (Hamming-1) | 41 clusters, 13 with >= 14 members, 20 singletons | 27 clusters: two of 27, then 12, 11, 11, 10, 10, 10; 15 singletons |
| instruction content | h-copy, h-alloc, h-divide in 100 % of replicators; two dimers (fg, gb) in about 70 % | all four primitives in 100 % of copiers; most common pairs STIND>LDIND (165), LDIND>INCM (160); position 8 is JNZ in 118 of 141 |

## What transfers

1. **Minimal length is sharp in both systems.** Avida: nothing at 7, 914 at 8. Universe-1: nothing in any one-operand-bit ISA
   (they stop at 7 of 8 words), 141 copiers as soon as the operand field holds a pointer. The threshold is set by addressing, not by
   genome bits: Avida's 37.6-bit genomes carry a copy primitive, Universe-1's 32-bit genomes have to build one.
2. **Replicators cluster.** Both landscapes show a few large Hamming-1 clusters plus singletons. Avida's two non-mixing classes have a
   counterpart worth testing in the 141 copiers (which words are the pointers, which the loop).
3. **"Intact" is the real question.** Avida's criterion requires a living parent after division; Universe-1's and NANO's copiers
   all consume their pointers, which live in their code. Avida gets intactness for free from h-divide and separate heads. The
   Universe-1 analogue is a world rule in which the window is the child and the parent is read once (design C of the ALife plan).
4. **Evolvability and the soup** (10 populations per replicator, 200 soup competitions) are exactly the Life-world experiments that
   become possible once a replicator exists: the 16 persistent copiers are the candidate seed set.

## Can we run Avida's enumeration on the cluster? Yes, and it would validate itself

- Scale: 2.09 x 10^11 genomes of 8 instructions, one run each, a few hundred to a few thousand instructions per genome. The NANO
  5-byte alife census (1.1 x 10^12 programs, 482 s on 5 GPUs) and Universe-1's copy-only mode (37 M programs/s per card) put the
  whole L = 8 space at roughly 20 to 40 GPU-minutes on this cluster; L = 9 (5.4 x 10^12) at a few hours; L = 10 (1.4 x 10^14) at a
  few days. Avida itself never enumerated beyond 8.
- Implementation: a faithful GPU interpreter of the 26-instruction heads set (instruction pointer, read, write and flow heads, nop
  templates with complements, h-search, if-label, allocation and divide rules, the Analyze-Mode viability criterion). The semantics
  are documented only partially outside the Avida source (`devosoft/avida`, cHardwareCPU), so the implementation must be written from
  the source and validated against the published 914 sequences: the enumeration must reproduce exactly that set and find nothing at
  L = 7. That is a stronger validation than any of our sweeps has had.
- What it would add: the replicator counts at L = 9 and 10 (does the information-content model predict them?), the cluster structure
  at larger L, and a direct comparison of replicator density per genome bit between a machine built for copying and one that is not.
- What it does not do: Avida's instruction set is not a candidate ISA for Universe-1's maps (26 instructions need 5 opcode bits and
  heads, labels and stacks are outside the W-bit machine); it is a different universe to enumerate with the same tooling, exp11.

Sources: the paper (arXiv 1701.03993); Avida documentation of the heads instructions (avida-ed cpu tour, the Avida wiki's default
ancestor tour, the Lenski 2003 glossary); figshare 4551559 for the sequences.
