"""Parametric W-bit machine for Universe-1.

State: accumulator A (W bits), flags Z/C, program counter PC (p bits),
data memory M (2**a words of W bits), code C (2**p instructions, I bits).
Layout L3 (memory-mapped): address 0 aliases A. Harness caps at 256 steps.

An ISA is a tuple of primitive names, one per opcode value 0..2**I-1.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

MAX_STEPS = 256


@dataclass
class Config:
    W: int = 2          # word width
    a: int = 2          # address bits -> 2**a data words
    p: int = 4          # pc bits -> 2**p instructions
    I: Optional[int] = None  # instruction width; default = W

    def __post_init__(self):
        if self.I is None:
            self.I = self.W
        self.mask = (1 << self.W) - 1
        self.amask = (1 << self.a) - 1
        self.pmask = (1 << self.p) - 1


@dataclass
class State:
    A: int = 0
    Z: int = 1
    C: int = 0
    PC: int = 0
    H: int = 0
    M: List[int] = field(default_factory=list)

    def key(self) -> Tuple:
        return (self.A, self.Z, self.C, self.PC, self.H, tuple(self.M))


# ---- primitive catalogue -------------------------------------------------
# Each primitive: fn(cfg, st, operand) -> None. operand = low bits of the
# instruction after the opcode field (may be 0 bits wide, then operand == 0).
# Memory operand: M[operand & amask]; address 0 aliases A (layout L3).

def _rd(cfg, st, addr):
    addr &= cfg.amask
    return st.A if addr == 0 else st.M[addr]

def _wr(cfg, st, addr, v):
    addr &= cfg.amask
    v &= cfg.mask
    if addr == 0:
        st.A = v
    else:
        st.M[addr] = v

def _setA(cfg, st, v, carry=None):
    st.A = v & cfg.mask
    st.Z = int(st.A == 0)
    if carry is not None:
        st.C = carry

def p_nop(cfg, st, op): pass
def p_halt(cfg, st, op): st.H = 1
def p_ld(cfg, st, op): _setA(cfg, st, _rd(cfg, st, op))
def p_st(cfg, st, op): _wr(cfg, st, op, st.A)
def p_ldi(cfg, st, op): _setA(cfg, st, op)
def p_clr(cfg, st, op): _setA(cfg, st, 0)
def p_set(cfg, st, op): _setA(cfg, st, cfg.mask)
def p_not(cfg, st, op): _setA(cfg, st, ~st.A)
def p_and(cfg, st, op): _setA(cfg, st, st.A & _rd(cfg, st, op))
def p_or(cfg, st, op): _setA(cfg, st, st.A | _rd(cfg, st, op))
def p_xor(cfg, st, op): _setA(cfg, st, st.A ^ _rd(cfg, st, op))
def p_nand(cfg, st, op): _setA(cfg, st, ~(st.A & _rd(cfg, st, op)))
def p_nor(cfg, st, op): _setA(cfg, st, ~(st.A | _rd(cfg, st, op)))
def p_xnor(cfg, st, op): _setA(cfg, st, ~(st.A ^ _rd(cfg, st, op)))
def p_add(cfg, st, op):
    s = st.A + _rd(cfg, st, op); _setA(cfg, st, s, int(s > cfg.mask))
def p_adc(cfg, st, op):
    s = st.A + _rd(cfg, st, op) + st.C; _setA(cfg, st, s, int(s > cfg.mask))
def p_sub(cfg, st, op):
    s = st.A - _rd(cfg, st, op); _setA(cfg, st, s, int(s < 0))
def p_inc(cfg, st, op):
    s = st.A + 1; _setA(cfg, st, s, int(s > cfg.mask))
def p_dec(cfg, st, op):
    s = st.A - 1; _setA(cfg, st, s, int(s < 0))
def p_neg(cfg, st, op): _setA(cfg, st, -st.A, int(st.A != 0))
def p_shl(cfg, st, op): _setA(cfg, st, st.A << 1, (st.A >> (cfg.W - 1)) & 1)
def p_shr(cfg, st, op): _setA(cfg, st, st.A >> 1, st.A & 1)
def p_rol(cfg, st, op):
    _setA(cfg, st, (st.A << 1) | (st.A >> (cfg.W - 1)))
def p_ror(cfg, st, op):
    _setA(cfg, st, (st.A >> 1) | ((st.A & 1) << (cfg.W - 1)))
def p_rcl(cfg, st, op):
    c = (st.A >> (cfg.W - 1)) & 1; _setA(cfg, st, (st.A << 1) | st.C, c)
def p_mul(cfg, st, op): _setA(cfg, st, st.A * _rd(cfg, st, op))
def p_swap(cfg, st, op):
    t = _rd(cfg, st, op); _wr(cfg, st, op, st.A); _setA(cfg, st, t)
def p_jmp(cfg, st, op): st.PC = op & cfg.pmask
def p_jz(cfg, st, op):
    if st.Z: st.PC = op & cfg.pmask
def p_jnz(cfg, st, op):
    if not st.Z: st.PC = op & cfg.pmask
def p_jc(cfg, st, op):
    if st.C: st.PC = op & cfg.pmask
def p_skz(cfg, st, op):
    if st.Z: st.PC = (st.PC + 1) & cfg.pmask
def p_sknz(cfg, st, op):
    if not st.Z: st.PC = (st.PC + 1) & cfg.pmask
def p_incm(cfg, st, op): _wr(cfg, st, op, _rd(cfg, st, op) + 1)
def p_decm(cfg, st, op): _wr(cfg, st, op, _rd(cfg, st, op) - 1)
def p_ldind(cfg, st, op): _setA(cfg, st, _rd(cfg, st, _rd(cfg, st, op)))
def p_stind(cfg, st, op): _wr(cfg, st, _rd(cfg, st, op), st.A)

PRIMS: Dict[str, Callable] = {
    "NOP": p_nop, "HALT": p_halt,
    "LD": p_ld, "ST": p_st, "LDI": p_ldi, "CLR": p_clr, "SET": p_set,
    "NOT": p_not, "AND": p_and, "OR": p_or, "XOR": p_xor,
    "NAND": p_nand, "NOR": p_nor, "XNOR": p_xnor,
    "ADD": p_add, "ADC": p_adc, "SUB": p_sub, "INC": p_inc, "DEC": p_dec,
    "NEG": p_neg, "SHL": p_shl, "SHR": p_shr, "ROL": p_rol, "ROR": p_ror,
    "RCL": p_rcl, "MUL": p_mul, "SWAP": p_swap,
    "JMP": p_jmp, "JZ": p_jz, "JNZ": p_jnz, "JC": p_jc,
    "SKZ": p_skz, "SKNZ": p_sknz,
    "INCM": p_incm, "DECM": p_decm, "LDIND": p_ldind, "STIND": p_stind,
}

# Primitives that read an operand field (others ignore it; the field can be 0 wide)
USES_OPERAND = {"LD", "ST", "LDI", "AND", "OR", "XOR", "NAND", "NOR", "XNOR",
                "ADD", "ADC", "SUB", "MUL", "SWAP", "JMP", "JZ", "JNZ", "JC",
                "INCM", "DECM", "LDIND", "STIND"}


class Machine:
    def __init__(self, cfg: Config, isa: Tuple[str, ...]):
        self.cfg = cfg
        self.isa = isa
        self.o = max(1, (len(isa) - 1).bit_length())  # opcode bits
        assert len(isa) == 1 << self.o, "ISA length must be a power of two"
        assert self.o <= cfg.I, "opcode field wider than instruction"
        self.opmask = (1 << (cfg.I - self.o)) - 1
        self.fns = [PRIMS[n] for n in isa]

    def run(self, code: List[int], init_A: int = 0, init_M: Optional[List[int]] = None,
            max_steps: int = MAX_STEPS) -> Tuple[Optional[State], int, str]:
        """Return (final_state, steps, reason). reason: halt | budget | loop.
        loop = a state repeated, so the run is periodic and the state at step
        max_steps is computed by cycle arithmetic instead of simulated."""
        cfg = self.cfg
        st = State(A=init_A & cfg.mask, Z=int((init_A & cfg.mask) == 0),
                   M=list(init_M) if init_M else [0] * (1 << cfg.a))
        st.M[0] = 0  # address 0 is A; keep slot unused
        seen = {st.key(): 0}
        hist = [st.key()]
        for t in range(max_steps):
            ins = code[st.PC & cfg.pmask]
            opc = ins >> (cfg.I - self.o)
            opnd = ins & self.opmask
            st.PC = (st.PC + 1) & cfg.pmask
            self.fns[opc](cfg, st, opnd)
            if st.H:
                return st, t + 1, "halt"
            k = st.key()
            if k in seen:
                # periodic: fast-forward to the state at step max_steps
                start = seen[k]
                period = (t + 1) - start
                idx = start + (max_steps - start) % period
                fk = hist[idx]
                fs = State(A=fk[0], Z=fk[1], C=fk[2], PC=fk[3], H=fk[4], M=list(fk[5]))
                return fs, max_steps, "loop"
            seen[k] = t + 1
            hist.append(k)
        return st, max_steps, "budget"

    def truth_table_unary(self, code: List[int]) -> Optional[Tuple[int, ...]]:
        """Observation = A at step 256 (or at HALT) for each input x placed in A."""
        out = []
        for x in range(1 << self.cfg.W):
            st, _, _ = self.run(code, init_A=x)
            out.append(st.A)
        return tuple(out)

    def truth_table_binary(self, code: List[int]) -> Optional[Tuple[int, ...]]:
        """Inputs x in A, y in M[1]; observation = final A."""
        if self.cfg.a < 1:
            return None
        out = []
        n = 1 << self.cfg.W
        for x in range(n):
            for y in range(n):
                M = [0] * (1 << self.cfg.a); M[1] = y
                st, _, _ = self.run(code, init_A=x, init_M=M)
                out.append(st.A)
        return tuple(out)


def state_bits(cfg: Config) -> int:
    return cfg.W + 2 + cfg.p + (1 << cfg.a) * cfg.W + (1 << cfg.p) * cfg.I + 1
