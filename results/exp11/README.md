# exp11: the 914 Avida length-8 self-replicators (downloaded 2026-10-09)

`figshare/len8`: the public file of the 914 viable length-8 Avida genomes from the arXiv paper 1701.03993 (Avida enumeration of
all 26^8 length-8 sequences in Analyze Mode), figshare 10.6084/m9.figshare.4551559, CC BY 4.0, downloaded from
https://ndownloader.figshare.com/files/7370614 with the user's permission. SHA-256
`86a489c9003602a26a982d856c21be9fd41939ef12db96f41f572d827c8b3ea0`, 8,226 bytes, 914 lines of eight lower-case letters (Avida's
default 26-instruction alphabet: a nop-A, b nop-B, c nop-C, d if-n-equ, e if-less, f if-label, g mov-head, h jmp-head, i get-head,
j set-flow, k shift-r, l shift-l, m inc, n dec, o push, p pop, q swap-stk, r swap, s add, t sub, u nand, v h-copy, w h-alloc,
x h-divide, y IO, z h-search). Treated as data: nothing in this directory is executed.

## What the file shows (`stats.txt`, computed with a Python pass over the lines)

- All 914 are distinct; 898 remain distinct up to rotation (Avida genomes are circular, so 16 are rotations of another entry).
- Three instructions are in every genome: h-alloc, h-copy, h-divide (the allocate, copy, divide triple; one each in nearly all).
- The common body: 77 % contain nop-B, if-label and mov-head, i.e. the standard loop `if-label nop-B ... mov-head` that jumps back
  while the copy is incomplete; mov-head occurs 1,351 times (twice per genome in 690 of them). 29 % use jmp-head and swap instead.
- The remaining letters are fillers: 40 distinct letter multisets in total, and the eight largest (40 genomes each) are the same
  seven-instruction core `b f g g v w x` plus one free slot that takes h, i, j, k, l, m, n, o, ... in turn. Arithmetic (add, sub,
  nand, inc, dec, IO) appears in only 4 % of the genomes, always in that free slot.
- Single-substitution neighbourhoods (Hamming distance one over the 26-letter alphabet): 41 clusters, the largest 212, 199, 165
  and 96 genomes, 20 singletons.

## Against the Universe-1 copiers (results/exp06b_summary.md, docs/10_avida_comparison.md)

| | Avida length 8 | Universe-1 crawler, 4 bytes | crawler, 5 bytes |
|---|---:|---:|---:|
| space | 26^8 = 2.09e11 | 2^32 | 2^40 |
| self-copiers | 914 (viable replicators) | 141 (full copy, none intact) | 21,818 (3 intact) |
| density | 4.4e-9 | 3.3e-8 | 2.0e-8 |
| mandatory core | h-alloc, h-copy, h-divide in all | LDIND, STIND, INCM, JNZ (the whole ISA) | same |
| one-substitution clusters | 41 (largest 212), 20 singletons | 27 (two large), 15 singletons | not computed |

The Avida replicators have a 3-instruction mandatory core plus a 4-instruction loop body and one free slot; the Universe-1 copiers
have no free slot at all (8 words, every one a pointer or a loop instruction), which is why their fecundity is one (docs/12).

## exp11 (open)

Implement the Avida heads CPU for the default instruction set, validate it by reproducing exactly this set from all 26^8 length-8
sequences (and nothing at length 7), then enumerate lengths 9 and 10 and measure fecundity and robustness the way exp06c does.
