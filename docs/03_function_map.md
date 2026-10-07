# Function map and synthesizer (`mapper/`, Rust)

The sweeps in experiment 03 produce, per ISA, the set of distinct operators and one witness
program each (the smallest program id realizing the operator). Codex published the raw shards
as `results/witnesses/*.zip`. The function map turns them into something usable:

1. **Map** (`results/maps/<isa>.u1prog`): the sorted witness program ids of every operator.
   Tables are recomputed on load by the embedded machine, so a 1.8 M-operator map is 14 MB.
2. **Named operators** (`results/maps/<isa>.named.jsonl`): one line per operator whose truth
   table matches a name in the vocabulary (`u1map vocab --W 4`): program, hex, assembly,
   step cost, halting flag, table.
3. **Stats** (`results/maps/<isa>.stats.json`): operator count, named count, class breakdown
   (named / permutation / predicate / constant / other), step-cost histogram.
4. **Usability matrix** (`results/maps/usability.md`): operator x ISA grid with the step cost of
   the cheapest witness. This answers "which ISA gives me which math operators at what cost".
5. **Synthesizer** (`u1map synth`): given a target (a vocabulary name or an explicit truth
   table), finds a witness program or a chain of 2..d programs whose composition realizes it,
   and emits self-contained Rust: the program images, a verified lookup table, and an embedded
   reference machine with a `#[test]` proving emulation == table.

## Vocabulary (the naming / target language)
Unary, width W: `x`, constants, `!x`, `-x`, `x+k`, `k-x`, `x*k`, `x^k`, `x&k`, `x|k`, `x/k`,
`x%k`, `x<<k`, `x>>k`, `rol(x,k)`, `sar(x)`, `x*x`, `popcount(x)`, `parity(x)`, `bitrev(x)`,
`sign(x)`, `abs(x)`, `clz(x)`, `ctz(x)`, `lowbit(x)`, `swaphalves(x)`, predicates `x==k`,
`x<k`, `x>=k`, `x==0`, `x!=0`, `min(x,k)`, `max(x,k)`, plus every depth-2 composition
`f(g(x))` of these, written `f((g))`, e.g. `!(x*x)`. Shortest name wins.
Binary (x in A, y in M[1]): `x+y`, `x-y`, `y-x`, `x*y`, `x/y`, `x%y`, the 16 Boolean pairs
(`x&y`, `!(x&y)`, `x&!y`, ...), `min`, `max`, comparisons, `x<<y`, `x>>y`, `rol(x,y)`,
`carry(x+y)`, `borrow(x-y)`, `avg`, `|x-y|`, selects, `gcd`, and one unary pre- or post-op on
any of them.

## Results of this build (from the published witnesses)
| ISA | mode | operators | named | notes |
|---|---|---:|---:|---|
| SWAP,ADD,NAND,SKZ (o=2) | unary | 1,829,051 | 2,703 | no HALT: everything is 256-step |
| SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | unary | 1,463,824 | 4,045 | most named ops; 2-stage closure = 2,543,086 |
| LD,ST,LDI,NAND,ADD,SHL,JZ,HALT | unary / binary | 62,880 / 1,020,901 | 1,329 / 917 | `x+y` in 2 steps, `x-y` in 4 |
| LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT | unary / binary | 24,420 / 339,877 | 707 / 367 | `x*3` in 4 steps |
| LD,ST,NOT,AND,OR,XOR,SKZ,HALT | unary / binary | 16 / 11,946 | 11 / 46 | `x^y` in 2 steps |
| 16-opcode zero-address ISA (a=1) | unary | 302,301 | 3,290 | partial: 19 of 64 shards published |
| LD,ST,NAND,JZ (o=2) | unary | 16 | 11 | operand bits spent, opcode too weak |
| W=2 NAND,JZ | unary | 12 of 256 | 11 | |
| W=1 NAND,JZ / NAND,SKZ | unary | 4 of 4 | 4 | complete |

Every witness was re-executed by the Rust machine and reproduced its shard key (1,829,051 of
1,829,051 for the largest map). The Rust machine itself is byte-identical to `fast/u1` on
ranges of all five widths/modes tested (`fast/compare_shards.py`).

## Usage
```bash
cd mapper && cargo build --release && cd ..
U=mapper/target/release/u1map
# build a map from shards (verifies every witness)
$U build --shards results/shards/w4_o2_add_[0-9]*.bin --out results/maps/w4_o2_add.u1prog \
   --named results/maps/w4_o2_add.named.jsonl --stats results/maps/w4_o2_add.stats.json
# or sweep a small space directly
$U build --W 2 --a 2 --p 3 --isa LD,ST,NAND,JZ --out /tmp/m.u1prog
# browse
$U list --map results/maps/w4_o3_swap.u1prog --filter "x*" --limit 30
$U info --map results/maps/w4_o3_swap.u1prog --closure 3 --extra 64
# synthesize + emit Rust (direct witness, or a chain of up to --depth programs)
$U synth --map results/maps/w4_o2_add.u1prog --target "x*x" --depth 3 --out op_sq.rs
$U synth --map results/maps/w4_o2_add.u1prog --table 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1 --fn ge8 --out ge8.rs
rustc --edition 2021 --test op_sq.rs -o t && ./t        # emulation == table
# usability matrix
python3 mapper/usability.py results/maps/*.named.jsonl --out results/maps/usability.md
```
Generated Rust is dependency-free: `PROGRAMS` (stage images), `TABLE`, `fn <name>(x)` (table
lookup), `fn <name>_emulated(x)` (runs the stages on the embedded machine), and a test.

## Caveats
- Composition in `synth` is sequential (stage k's output becomes stage k+1's A); memory is reset
  between stages. A chain is therefore `p_k * 256` steps worst case, not one program.
- Hashed tables (W=8 unary, W>=3 binary) are recomputed exactly from the witness; the hash is
  only used to match the shard key.
- `steps` for non-halting programs is 256; the value at step 256 is still exact.

## For Codex
1. Publish the remaining shards: `w4_o4_full` parts (45 of 64 missing) and `w8_o4`.
2. Rebuild maps on the head node after each new archive (`u1map build ...`) and commit
   `results/maps/`; rerun `mapper/usability.py`.
3. Next sweep candidates suggested by the matrix: an ISA with HALT *and* SWAP/ADD/NAND
   (the two best unary ISAs lack either HALT or memory ops), and binary mode for
   `SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT`.
