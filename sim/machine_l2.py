"""Layout L2 (von Neumann) reference machine for exp06b: code and data share one flat memory of 2^a words.

Differences from sim/machine.py (layout L3):
- M[0 .. 2^a-1] is one address space; A is a separate register (no address aliases A).
- The 2^p instructions of the program are loaded into M[0 .. 2^p-1] at start; fetch reads M[PC & pmask], so a program can
  rewrite itself (ST, STIND, INCM, DECM, SWAP into the code words) and a rewritten word is executed on the next fetch.
- Direct operands address M[op] (op is the (I - o)-bit operand field); LDIND/STIND use M[op] as a pointer into the whole memory.
- Unary input x in A; binary input y in M[2^p] (the first data word after the code). HALT stops; otherwise MAX_STEPS steps.
- The copy window M[2^p .. 2^(p+1)-1] starts as (code word + 1) mod 16 at every position, so the self-copy score (words of the
  initial code found there, position-wise) can only be earned by writing; the all-zero program does not score trivially.
Observation: A at the end (the function), and for the x = 0 run the self-modification statistics of exp06b (lessons from the
Dimension42 NANO sweeps): best copy score over all steps and at the end, the step of the first full copy and whether the code was
still intact then, whether the code was ever changed / differs at the end, and the walker count (writes into code that changed
only the operand field).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
MAX_STEPS = 256

@dataclass
class ConfigL2:
    W: int = 4; a: int = 4; p: int = 3; I: int = 4
    def __post_init__(self):
        self.mask = (1 << self.W) - 1; self.amask = (1 << self.a) - 1; self.pmask = (1 << self.p) - 1
        assert (1 << self.p) * 2 <= (1 << self.a), 'code and copy window must fit in memory'; assert self.I == self.W, 'L2 needs instruction width = word width'
        self.nM = 1 << self.a

@dataclass
class StateL2:
    A: int = 0; Z: int = 1; C: int = 0; PC: int = 0; H: int = 0; M: List[int] = field(default_factory=list)

class MachineL2:
    def __init__(self, cfg: ConfigL2, isa: Tuple[str, ...]):
        self.cfg = cfg; self.isa = isa
        self.o = max(1, (len(isa) - 1).bit_length()); assert len(isa) == 1 << self.o and self.o <= cfg.I
        self.opmask = (1 << (cfg.I - self.o)) - 1

    def code(self, program: int) -> List[int]:
        return [(program >> (k * self.cfg.I)) & ((1 << self.cfg.I) - 1) for k in range(1 << self.cfg.p)]

    def load(self, program: int) -> List[int]:
        """Code at M[0..2^p-1]; every other word holds (code[i mod 2^p] + 1) mod 2^W, so no non-overlapping window equals the code before a write."""
        cfg = self.cfg; n = 1 << cfg.p; code = self.code(program)
        M = [(code[i % n] + 1) & cfg.mask for i in range(1 << cfg.a)]
        for k, c in enumerate(code): M[k] = c
        return M

    def copy_score(self, M: List[int], code: List[int], written) -> Tuple[int, int]:
        """(best number of code words found position-wise, in words the program has written, at a non-overlapping offset k in
        [2^p, 2^a - 2^p], that offset). Pre-filled contents never count, so a copy must be written entirely."""
        n = len(code); best, where = 0, n
        for k in range(n, len(M) - n + 1):
            sc = sum(M[k + j] == code[j] and (k + j) in written for j in range(n))
            if sc > best: best, where = sc, k
        return best, where

    def run(self, program: int, init_A: int = 0, y: Optional[int] = None, max_steps: int = MAX_STEPS, stats: bool = False):
        """Returns (state, steps, reason) and, with stats=True, a dict of the exp06b statistics of this run."""
        cfg = self.cfg; mask, amask, pmask, W = cfg.mask, cfg.amask, cfg.pmask, cfg.W; n = 1 << cfg.p
        code = self.code(program); st = StateL2(A=init_A & mask, M=self.load(program)); st.Z = int(st.A == 0)
        if y is not None: st.M[n] = y & mask
        M = st.M; opfield = self.opmask
        S = dict(best=0, final=0, first_full=0, intact=0, ever_mod=0, final_mod=0, walker_writes=0, offset=n); written = set()
        def rd(addr): return M[addr & amask]
        def wr(addr, v):
            addr &= amask; v &= mask; old = M[addr]; M[addr] = v; written.add(addr)
            if stats and addr < n and old != v:
                S['ever_mod'] = 1
                if (old >> (cfg.I - self.o)) == (v >> (cfg.I - self.o)): S['walker_writes'] += 1
            if stats and addr >= n:
                sc, where = self.copy_score(M, code, written)
                if sc > S['best']:
                    S['best'] = sc
                    if sc == n: S['first_full'] = t + 1; S['offset'] = where; S['intact'] = int(M[:n] == code)
        def setA(v, carry=None):
            st.A = v & mask; st.Z = int(st.A == 0)
            if carry is not None: st.C = int(carry)
        t = 0; reason = 'budget'; steps = max_steps
        for t in range(max_steps):
            ins = M[st.PC & pmask]; opc = ins >> (cfg.I - self.o); op = ins & opfield
            st.PC = (st.PC + 1) & pmask; name = self.isa[opc]; A = st.A
            if name == 'NOP': pass
            elif name == 'HALT': st.H = 1; reason = 'halt'; steps = t + 1; break
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
        if stats:
            S['final'] = self.copy_score(M, code, written)[0]; S['final_mod'] = int(M[:n] != code); S['walker'] = int(S['walker_writes'] >= 4); S['nonzero'] = sum(c != 0 for c in code)
            S['copier'] = int(S['best'] == n and S['nonzero'] >= 2)   # NANO rule: at least 2 nonzero code words
            return st, steps, reason, S
        return st, steps, reason

    def trace(self, program: int, init_A: int = 0, max_steps: int = MAX_STEPS):
        """Per-step snapshots for visualisation: list of (PC before the step, A before the step, memory after the step)."""
        snaps = []; orig = self.run
        cfg = self.cfg; mask, amask, pmask, W = cfg.mask, cfg.amask, cfg.pmask, cfg.W; n = 1 << cfg.p
        st = StateL2(A=init_A & mask, M=self.load(program)); st.Z = int(st.A == 0); M = st.M
        for t in range(max_steps):
            pc0, a0 = st.PC, st.A
            ins = M[st.PC & pmask]; opc = ins >> (cfg.I - self.o); op = ins & self.opmask; name = self.isa[opc]
            # re-use run() semantics by stepping a one-step machine: simplest is to run the full step logic via a nested call
            nxt = self._step(st, name, op)
            snaps.append((pc0, a0, list(M), name, op))
            if nxt == 'halt': break
        return snaps

    def _step(self, st, name, op):
        cfg = self.cfg; mask, amask, pmask, W = cfg.mask, cfg.amask, cfg.pmask, cfg.W; M = st.M
        def rd(addr): return M[addr & amask]
        def wr(addr, v): M[addr & amask] = v & mask
        def setA(v, carry=None):
            st.A = v & mask; st.Z = int(st.A == 0)
            if carry is not None: st.C = int(carry)
        st.PC = (st.PC + 1) & pmask; A = st.A
        if name == 'NOP': pass
        elif name == 'HALT': st.H = 1; return 'halt'
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
        return 'ok'

    def table_unary(self, program: int, max_steps: int = MAX_STEPS) -> Tuple[int, ...]:
        return tuple(self.run(program, init_A=x, max_steps=max_steps)[0].A for x in range(1 << self.cfg.W))

    def stats(self, program: int, max_steps: int = MAX_STEPS) -> Dict[str, int]:
        return self.run(program, init_A=0, max_steps=max_steps, stats=True)[3]
