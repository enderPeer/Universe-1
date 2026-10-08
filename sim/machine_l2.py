"""Layout L2 (von Neumann) reference machine for exp06b: code and data share one flat memory of 2^a words.

Differences from sim/machine.py (layout L3):
- M[0 .. 2^a-1] is one address space; A is a separate register (no address aliases A).
- The 2^p instructions of the program are loaded into M[0 .. 2^p-1] at start; fetch reads M[PC & pmask], so a program can
  rewrite itself (ST, STIND, INCM, DECM into the code words) and a rewritten word is executed on the next fetch.
- Direct operands address M[op] (op is the (I - o)-bit operand field); LDIND/STIND use M[op] as a pointer into the whole memory.
- Unary input x in A; binary input y in M[2^p] (the first data word after the code). HALT stops; otherwise MAX_STEPS steps.
- The copy window M[2^p .. 2^(p+1)-1] starts as (code word + 1) mod 16 at every position, so the self-copy score (words of the
  initial code found there after the run) can only be earned by writing; the all-zero program does not score trivially.
Observation: A at the end (the function), the final memory image (for the self-copy test) and the step count.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
MAX_STEPS = 256

@dataclass
class ConfigL2:
    W: int = 4; a: int = 4; p: int = 3; I: int = 4
    def __post_init__(self):
        self.mask = (1 << self.W) - 1; self.amask = (1 << self.a) - 1; self.pmask = (1 << self.p) - 1
        assert (1 << self.p) <= (1 << self.a), 'code must fit in memory'

@dataclass
class StateL2:
    A: int = 0; Z: int = 1; C: int = 0; PC: int = 0; H: int = 0; M: List[int] = field(default_factory=list)

class MachineL2:
    def __init__(self, cfg: ConfigL2, isa: Tuple[str, ...]):
        self.cfg = cfg; self.isa = isa
        self.o = max(1, (len(isa) - 1).bit_length()); assert len(isa) == 1 << self.o and self.o <= cfg.I
        self.opmask = (1 << (cfg.I - self.o)) - 1

    def load(self, program: int) -> List[int]:
        cfg = self.cfg; M = [0] * (1 << cfg.a)
        for k in range(1 << cfg.p):
            M[k] = (program >> (k * cfg.I)) & ((1 << cfg.I) - 1)
            M[(1 << cfg.p) + k] = (M[k] + 1) & cfg.mask   # copy window pre-filled to differ from the code at every word: a match needs a write
        return M

    def run(self, program: int, init_A: int = 0, y: Optional[int] = None, max_steps: int = MAX_STEPS) -> Tuple[StateL2, int, str]:
        cfg = self.cfg; mask, amask, pmask, W = cfg.mask, cfg.amask, cfg.pmask, cfg.W
        st = StateL2(A=init_A & mask, M=self.load(program)); st.Z = int(st.A == 0)
        if y is not None: st.M[1 << cfg.p] = y & mask
        M = st.M
        def rd(addr): return M[addr & amask]
        def wr(addr, v): M[addr & amask] = v & mask
        def setA(v, carry=None):
            st.A = v & mask; st.Z = int(st.A == 0)
            if carry is not None: st.C = int(carry)
        for t in range(max_steps):
            ins = M[st.PC & pmask]; opc = ins >> (cfg.I - self.o); op = ins & self.opmask
            st.PC = (st.PC + 1) & pmask; name = self.isa[opc]; A = st.A
            if name == 'NOP': pass
            elif name == 'HALT': st.H = 1; return st, t + 1, 'halt'
            elif name == 'LD': setA(rd(op))
            elif name == 'ST': wr(op, A)
            elif name == 'LDI': setA(op)
            elif name == 'CLR': setA(0)
            elif name == 'SET': setA(mask)
            elif name == 'NOT': setA(~A)
            elif name == 'AND': setA(A & rd(op))
            elif name == 'OR': setA(A | rd(op))
            elif name == 'XOR': setA(A ^ rd(op))
            elif name == 'NAND': setA(~(A & rd(op)))
            elif name == 'NOR': setA(~(A | rd(op)))
            elif name == 'XNOR': setA(~(A ^ rd(op)))
            elif name == 'ADD': v = A + rd(op); setA(v, v > mask)
            elif name == 'ADC': v = A + rd(op) + st.C; setA(v, v > mask)
            elif name == 'SUB': v = A - rd(op); setA(v, v < 0)
            elif name == 'INC': v = A + 1; setA(v, v > mask)
            elif name == 'DEC': v = A - 1; setA(v, v < 0)
            elif name == 'NEG': setA(-A, A != 0)
            elif name == 'SHL': setA(A << 1, (A >> (W - 1)) & 1)
            elif name == 'SHR': setA(A >> 1, A & 1)
            elif name == 'ROL': setA((A << 1) | (A >> (W - 1)))
            elif name == 'ROR': setA((A >> 1) | ((A & 1) << (W - 1)))
            elif name == 'RCL': setA((A << 1) | st.C, (A >> (W - 1)) & 1)
            elif name == 'MUL': setA(A * rd(op))
            elif name == 'SWAP': tt = rd(op); wr(op, A); setA(tt)
            elif name == 'JMP': st.PC = op & pmask
            elif name == 'JZ':
                if st.Z: st.PC = op & pmask
            elif name == 'JNZ':
                if not st.Z: st.PC = op & pmask
            elif name == 'JC':
                if st.C: st.PC = op & pmask
            elif name == 'SKZ':
                if st.Z: st.PC = (st.PC + 1) & pmask
            elif name == 'SKNZ':
                if not st.Z: st.PC = (st.PC + 1) & pmask
            elif name == 'INCM': wr(op, rd(op) + 1)
            elif name == 'DECM': wr(op, rd(op) - 1)
            elif name == 'LDIND': setA(rd(rd(op)))
            elif name == 'STIND': wr(rd(op), A)
            else: raise ValueError(name)
        return st, max_steps, 'budget'

    def table_unary(self, program: int, max_steps: int = MAX_STEPS) -> Tuple[int, ...]:
        return tuple(self.run(program, init_A=x, max_steps=max_steps)[0].A for x in range(1 << self.cfg.W))

    def copy_score(self, program: int, init_A: int = 0, max_steps: int = MAX_STEPS) -> Tuple[int, int]:
        """(words of the initial code found at M[2^p .. 2^(p+1)-1] after the run, position-wise; 1 if that whole window equals the code)."""
        cfg = self.cfg; n = 1 << cfg.p; code = self.load(program)[:n]
        st, _, _ = self.run(program, init_A=init_A, max_steps=max_steps)
        match = sum(st.M[n + k] == code[k] for k in range(n))
        return match, int(match == n)
