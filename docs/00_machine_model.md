# Universe-1 machine model: everything allocatable at machine level

Goal of Universe-1: the maximum number of distinct mathematical operators
realizable on the smallest possible bitmap (word width W in bits, W = 1..8).

Every entity below is a thing a program or an ISA can *allocate*: it costs
bits, and the whole machine state is the concatenation of all of them.
The total state is a single bit string `S`; one step of the machine is a
function `step: S -> S`. Brute force means enumerating `step` functions
(ISA search) and enumerating initial `S` / instruction streams (program search).

## 1. Allocatable storage entities

| # | Entity | Size (bits) | Notes |
|---|--------|-------------|-------|
| 1 | Word width `W` | the unit | 1..8. Everything else is measured in words or bits. |
| 2 | Accumulator `A` | W | Minimum register for any ALU; 1 is enough for a Turing-ish machine with memory. |
| 3 | General registers `R[0..r-1]` | r·W | r = 0,1,2,4. r=0 means accumulator-only / memory-to-memory. |
| 4 | Program counter `PC` | p | p = log2(code size). For 256 steps and ≤256 instructions, p ≤ 8. |
| 5 | Flags `F` | f | Z (zero), C (carry), N (sign), V (overflow). f = 0..4. For W=1 Z and N collapse. |
| 6 | Data memory `M[0..2^a-1]` | 2^a · W | a = address bits. a = 0 (none), 1, 2, 3, ... Can be W-wide or bit-addressed. |
| 7 | Code memory `C[0..2^p-1]` | 2^p · I | I = instruction width (see §3). Harvard (separate) or von Neumann (shared with M). |
| 8 | Stack pointer `SP` | s | Only if a stack exists. s = a when stack lives in M. |
| 9 | Stack region | k·W | Either a slice of M or a separate hardware stack of depth k. |
| 10 | Link register `LR` | p | Return address, cheaper than a stack for one-level calls. |
| 11 | I/O port(s) | W per port | Input stream / output stream, optional. Output is how a result is "observed". |
| 12 | Step counter `T` | 8 | Not addressable by the program; the harness halts at T = 256. |
| 13 | Halt flag `H` | 1 | Set by HALT; lets a program finish before 256 steps. |
| 14 | Carry-in / mode bits | 1..2 | Global mode that re-interprets opcodes (bank switching, ALU mode). |
| 15 | Immediate field | i | Part of the instruction, not state, but it consumes encoding space. |

Total state bits: `|S| = W(1 + r) + p + f + 2^a·W + 2^p·I + s + k·W + ... `.
The number of reachable configurations is bounded by `2^|S|`, so the smallest
`|S|` that still yields the operator set we want is the thing to minimize.

## 2. Allocatable *semantic* entities (what an operator can be)

An operator is any total function on some sub-part of the state. Catalogue
by arity and width:

| Class | Count for width W | Examples |
|-------|-------------------|----------|
| 1-input bitwise (W bits -> W bits, bit-parallel) | 4 per bit position (id, not, 0, 1) | NOT, CLR, SET |
| 2-input bitwise, bit-parallel | 16 (the 16 Boolean functions) | AND, OR, XOR, NAND, NOR, XNOR, IMPLY, ... |
| Arithmetic (carry-chained) | ADD, SUB, ADC, SBC, INC, DEC, NEG, MUL, DIV, MOD, CMP | carry couples bit positions |
| Shifts/rotates | SHL, SHR, SAR, ROL, ROR, RCL, RCR (× shift amount 1..W-1) | |
| Data movement | LD, ST, MOV, SWAP, PUSH, POP, LDI (immediate) | |
| Control | JMP, JZ, JNZ, JC, JNC, CALL, RET, SKIP, HALT, NOP | |
| Arbitrary W-bit unary function | 2^(W·2^W) total | the full universe for width W |
| Arbitrary W-bit binary function | 2^(W·2^(2W)) total | too large for W ≥ 3; must sample |

The "max number of mathematical operators" target is measured against the
*arbitrary function* rows: how many of the `2^(W·2^W)` unary and
`2^(W·2^(2W))` binary functions can a given ISA compute within 256 steps.

## 3. Instruction encoding (what the bitmap of one instruction buys)

An instruction of width I bits is split into fields:

```
| opcode (o) | reg-src (log2 r) | reg-dst (log2 r) | addr/imm (a or i) | mode (m) |
```

- `o` = opcode bits -> at most 2^o distinct primitive operations.
- With I = W (instruction width equals word width, the pure "bitmap" case)
  everything must fit in W bits: for W = 1 there are exactly 2 instructions,
  for W = 2 four, ..., for W = 8 two hundred fifty-six.
- Multi-word instructions (I = 2W, 3W) buy more fields at the cost of steps:
  each extra word is one more fetch, so a 256-step budget shrinks.

## 4. Memory structuring options to brute force

The memory map is itself a search dimension. The candidate layouts, from
smallest to largest:

### L0 — register-only (a = 0)
State = A (+ flags). No addressable memory. Only operators on the
accumulator itself are possible: unary functions of W bits, plus immediates.

### L1 — accumulator + flat data memory, Harvard
```
M: [0 .. 2^a-1]  data words, W bits each
C: [0 .. 2^p-1]  instructions, I bits each (read-only)
```
Cleanest for enumeration: code and data cannot alias, so a program is a
fixed string of 2^p·I bits and the data image is a separate 2^a·W bits.

### L2 — von Neumann, single flat space
```
[0 .. 2^a-1]  one address space; PC and LD/ST both index it
```
Self-modifying code becomes possible, which raises the operator count for a
fixed bit budget (the program can rewrite its own opcodes) but makes
enumeration harder (state space is the whole space, not code × data).

### L3 — memory-mapped registers and I/O
```
[0]            A   (accumulator aliased to address 0)
[1]            F   (flags)
[2]            PC
[3]            SP / IN / OUT
[4 .. 2^a-1]   general data
```
Everything is addressable through one LD/ST pair, so the opcode space can
be spent on operators instead of on MOV-between-register variants. This is
the layout that maximizes "operators per opcode bit" and is the recommended
default for Universe-1.

### L4 — banked / paged
```
bank bit(s) b in a mode register; effective address = bank·2^a + addr
```
Trades one mode bit of state for 2^b times the memory, at the cost of a
bank-switch instruction in the opcode table.

### L5 — stack machine
```
[0 .. 2^a-1]   data; SP grows down from the top
opcodes are zero-address: PUSH imm, ADD, DUP, SWAP, DROP, OVER, JZ, ...
```
Zero-address encoding means almost all I bits go to the opcode, so for tiny
W a stack machine gets the most primitives per instruction. Cost: SP bits
and a stack region.

### L6 — bit-addressed memory
```
M is 2^a individual bits; LD/ST move one bit into/out of A's LSB
```
For W = 1 this is the natural layout. Every Boolean function of n inputs is
computable with NAND + bit moves; the question becomes the step cost.

## 5. Harness-level entities (not part of the machine, but allocated by the experiment)

- Step budget: 256 steps, hard cap (T wraps at 8 bits).
- Observation: final A, or final M, or the OUT stream. Choose one per experiment.
- Equivalence: two programs are the same operator if they map every input to the same observation.
- Input injection: initial A, initial M[0..n], or IN stream. Choose one per experiment.

## 6. Recommended minimal configurations per width

| W | Layout | r | a | p | I | State bits | Why |
|---|--------|---|---|---|---|------------|-----|
| 1 | L6 | 0 | 2 | 3 | 1 | ~1+4+8+3 | 1-bit opcode (two instructions); needs memory to do anything |
| 2 | L3 | 0 | 2 | 4 | 2 | ~2+8+32+4 | 4 opcodes: LD, ST, NAND, JZ |
| 3 | L3 | 0 | 3 | 5 | 3 | ~3+24+96+5 | 8 opcodes: adds ADD, SHL, LDI, HALT |
| 4 | L3 | 1 | 4 | 6 | 4 | ~8+64+256+6 | 16 opcodes: full bitwise set + arithmetic |
| 8 | L3/L5 | 2 | 8 | 8 | 8 | ~24+2048+2048+8 | 256 opcodes: the full catalogue in §2 fits |

These are the starting points; experiments 01 and 02 search around them.
