"""exp11 reference: Avida's heads CPU (cHardwareCPU, hardware type 0) with the default 26-instruction heads set, and Avida's
Analyze-Mode viability test (cTestCPU::TestGenome), written from the Avida 2.14.0 source (byte-identical to devosoft/avida master
for every file read: cHardwareCPU.cc, cHardwareBase.cc, cHeadCPU.h/.cc, cCPUMemory.cc, cCPUStack.h, cCodeLabel.h, cTestCPU.cc,
cCPUTestInfo.cc, nHardware.h, Definitions.h, cAvidaConfig.h, instset-heads.cfg, avida.cfg). Every semantic decision and where it
comes from is listed in docs/14_exp11_avida.md; the section numbers in the comments below refer to that document.

Genome: a string of letters a..z (instset-heads.cfg order) or a list of opcodes 0..25. Genome index (for sweeps): sum op_i * 26^i,
position 0 least significant (the project's word packing convention).

run_test(genome) -> dict: the Analyze-Mode verdict (viable, depth_found, ...) plus the first-divide statistics of the depth-0
organism (step, child, parent memory after the divide, intact) and the lifetime fecundity (divides within AGE_LIMIT * L cycles).
"""
from __future__ import annotations
from typing import List, Optional, Sequence, Tuple, Union

ALPHABET = 'abcdefghijklmnopqrstuvwxyz'
NAMES = ['nop-A', 'nop-B', 'nop-C', 'if-n-equ', 'if-less', 'if-label', 'mov-head', 'jmp-head', 'get-head', 'set-flow',
         'shift-r', 'shift-l', 'inc', 'dec', 'push', 'pop', 'swap-stk', 'swap', 'add', 'sub', 'nand', 'h-copy', 'h-alloc',
         'h-divide', 'IO', 'h-search']
NOP_A, NOP_B, NOP_C, IF_N_EQU, IF_LESS, IF_LABEL, MOV_HEAD, JMP_HEAD, GET_HEAD, SET_FLOW, SHIFT_R, SHIFT_L, INC, DEC, PUSH, POP, \
    SWAP_STK, SWAP, ADD, SUB, NAND, H_COPY, H_ALLOC, H_DIVIDE, IO, H_SEARCH = range(26)
NUM_NOPS = 3; NUM_REGISTERS = 3; REG_AX, REG_BX, REG_CX = 0, 1, 2
HEAD_IP, HEAD_READ, HEAD_WRITE, HEAD_FLOW = 0, 1, 2, 3           # nHardware::tHeads
STACK_SIZE = 10                                                  # nHardware::STACK_SIZE
MAX_LABEL = 10                                                   # cCodeLabel::MAX_LENGTH
MIN_GENOME_LENGTH, MAX_GENOME_LENGTH = 8, 2048                   # avida/core/Definitions.h
INST_ERROR = 255                                                 # cInstSet::GetInstError (never a nop)
INST_DEFAULT = 0                                                 # tInstLib def = 0 -> nop-A fills allocated memory (cCPUMemory::Resize SetOp(0))
# avida.cfg defaults (section 4 of docs/14)
TEST_CPU_TIME_MOD = 20; TEST_CPU_GENERATIONS = 3; OFFSPRING_SIZE_RANGE = 2.0; MIN_COPIED_LINES = 0.5; MIN_EXE_LINES = 0.5
MAX_LABEL_EXE_SIZE = 1; AGE_LIMIT = 20
INPUTS = (0x0f13149f, 0x3308e53e, 0x556241eb)                    # cEnvironment::SetupInputs, deterministic (non-random) inputs

def s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v

def parse(genome: Union[str, Sequence[int]]) -> List[int]:
    if isinstance(genome, str): return [ALPHABET.index(c) for c in genome.strip()]
    return list(genome)

def to_str(ops: Sequence[int]) -> str: return ''.join(ALPHABET[o] for o in ops)

def index_of(ops: Sequence[int]) -> int:
    g = 0
    for i, o in enumerate(ops): g += o * 26 ** i
    return g

def genome_of(index: int, length: int) -> List[int]:
    ops = []
    for _ in range(length): ops.append(index % 26); index //= 26
    return ops

class Stack:
    """cCPUStack: 10 ints, circular; push decrements the pointer, pop reads, zeroes the slot and increments (empty pops read 0)."""
    __slots__ = ('s', 'p')
    def __init__(self): self.s = [0] * STACK_SIZE; self.p = 0
    def push(self, v: int):
        self.p = STACK_SIZE - 1 if self.p == 0 else self.p - 1; self.s[self.p] = v
    def pop(self) -> int:
        v = self.s[self.p]; self.s[self.p] = 0; self.p += 1
        if self.p == STACK_SIZE: self.p = 0
        return v
    def clear(self): self.s = [0] * STACK_SIZE; self.p = 0

class Organism:
    """One Avida organism on a heads CPU (single thread). genome = the injected sequence (cOrganism::GetGenome(), never changes);
    mem = cCPUMemory (grows with h-alloc, shrinks at divide); executed/copied = the per-site flags used by Divide_CheckViable."""
    def __init__(self, genome: Sequence[int], trace: Optional[list] = None):
        self.genome = list(genome); self.mem = list(genome); n = len(genome)
        self.executed = [False] * n; self.copied = [False] * n
        self.reg = [0, 0, 0]; self.heads = [0, 0, 0, 0]; self.local = Stack(); self.glob = Stack(); self.cur_stack = 0
        self.read_label: List[int] = []; self.next_label: List[int] = []
        self.mal_active = False; self.advance_ip = True
        self.time_used = 0; self.num_divides = 0; self.offspring: Optional[List[int]] = None; self.copy_true = False
        self.input_ptr = 0; self.trace = trace
        # exp11 statistics of the first divide
        self.first_divide_step = 0; self.first_child: Optional[List[int]] = None; self.first_parent_after: Optional[List[int]] = None
        self.divides_true = 0; self.alloc_step = 0

    # ---- heads (cHeadCPU) ----
    def adjust(self, pos: int) -> int:
        """cHeadCPU::fullAdjust: in range -> unchanged; empty memory or negative -> 0; < 2*size -> pos - size; else pos mod size."""
        size = len(self.mem)
        if 0 <= pos < size: return pos
        if size == 0 or pos < 0: return 0
        return pos - size if pos < 2 * size else pos % size
    def adjust_head(self, h: int): self.heads[h] = self.adjust(self.heads[h])
    def advance(self, h: int): self.heads[h] = self.adjust(self.heads[h] + 1)
    def ip(self) -> int: return self.heads[HEAD_IP]
    def next_inst(self) -> int:
        """cHeadCPU::GetNextInst: the instruction after the IP, or the error instruction at the last position (no wrap)."""
        p = self.heads[HEAD_IP]
        return INST_ERROR if p + 1 == len(self.mem) else self.mem[p + 1]
    @staticmethod
    def is_nop(inst: int) -> bool: return inst < NUM_NOPS
    def set_executed(self, pos: int):
        if 0 <= pos < len(self.mem): self.executed[pos] = True

    # ---- nop modification (cHardwareCPU::FindModifiedRegister/Head, ReadLabel) ----
    def find_modified(self, default: int) -> int:
        if self.is_nop(self.next_inst()):
            self.advance(HEAD_IP); default = self.mem[self.ip()]; self.set_executed(self.ip())
        return default
    def read_next_label(self, max_size: int = MAX_LABEL):
        self.next_label = []; count = 0
        while self.is_nop(self.next_inst()) and count < max_size:
            count += 1; self.advance(HEAD_IP); self.next_label.append(self.mem[self.ip()])
            if len(self.next_label) <= MAX_LABEL_EXE_SIZE: self.set_executed(self.ip())
    @staticmethod
    def complement(label: List[int]) -> List[int]: return [(x + 1) % NUM_NOPS for x in label]      # cCodeLabel::Rotate(1, NUM_NOPS)

    def find_label_forward(self, label: List[int], pos: int) -> int:
        """cHardwareCPU::FindLabel_Forward, literally (including the initial skip of label_size positions and the block jumps)."""
        mem = self.mem; size = len(mem); search_start = pos; ls = len(label); found = False
        pos += ls
        while pos < size:
            if self.is_nop(mem[pos]):
                start_pos = pos; end_pos = pos + 1
                while start_pos > search_start and self.is_nop(mem[start_pos - 1]): start_pos -= 1
                while end_pos < size and self.is_nop(mem[end_pos]): end_pos += 1
                max_offset = end_pos - start_pos - ls + 1
                offset = start_pos
                while offset < start_pos + max_offset:
                    matches = 0
                    while matches < ls:
                        if label[matches] != mem[offset + matches]: break
                        matches += 1
                    if matches == ls: found = True; break
                    offset += 1
                if found: pos = ls + offset; break
                pos = end_pos
            pos += ls
        return pos if found else -1

    def find_label(self) -> int:
        """cHardwareCPU::FindLabel(0): position of the last nop of the complement label found from the start of memory, or the IP."""
        if not self.next_label: return self.ip()
        found = self.find_label_forward(self.next_label, 0)
        return self.adjust(found - 1) if found >= 0 else self.ip()

    # ---- stacks ----
    def stack(self) -> Stack: return self.local if self.cur_stack == 0 else self.glob

    # ---- allocation and division ----
    def allocate_main(self, allocated: int) -> bool:
        if self.mal_active: return False                                  # REQUIRE_ALLOCATE 1: one allocation per divide
        if allocated < 1: return False
        old = len(self.mem); new = old + allocated
        if new > MAX_GENOME_LENGTH or new < MIN_GENOME_LENGTH: return False
        if allocated > int(old * OFFSPRING_SIZE_RANGE): return False
        if old > int(allocated * OFFSPRING_SIZE_RANGE): return False
        self.mem += [INST_DEFAULT] * allocated; self.executed += [False] * allocated; self.copied += [False] * allocated
        self.mal_active = True
        if self.alloc_step == 0: self.alloc_step = self.time_used
        return True

    def divide_check_viable(self, parent_size: int, child_size: int) -> bool:
        """cHardwareBase::Divide_CheckViable with avida.cfg defaults (JUV_PERIOD 0, MIN_CYCLES 0, MIN/MAX_GENOME_SIZE 0 = off)."""
        g = len(self.genome)
        min_size = max(MIN_GENOME_LENGTH, int(g / OFFSPRING_SIZE_RANGE)); max_size = min(MAX_GENOME_LENGTH, int(g * OFFSPRING_SIZE_RANGE))
        if child_size < min_size or child_size > max_size: return False
        if parent_size < min_size or parent_size > max_size: return False
        executed = sum(self.executed[:parent_size])
        if executed < int(parent_size * MIN_EXE_LINES): return False
        copied = sum(self.copied[parent_size:parent_size + child_size])
        if copied < int(child_size * MIN_COPIED_LINES): return False
        return True                                                       # cOrganism::Divide_CheckViable: no required task/reaction, fertile, merit L > 0

    def divide_main(self, div_point: int, extra_lines: int) -> bool:
        child_size = len(self.mem) - div_point - extra_lines
        if not self.divide_check_viable(div_point, child_size): return False
        child = self.mem[div_point:div_point + child_size]
        self.offspring = child; self.copy_true = child == self.genome
        self.mem = self.mem[:div_point]; self.executed = self.executed[:div_point]; self.copied = self.copied[:div_point]
        self.mal_active = False; self.advance_ip = False                  # DIVIDE_METHOD 1 (split)
        self.num_divides += 1; self.divides_true += self.copy_true
        if self.num_divides == 1: self.first_divide_step = self.time_used; self.first_child = list(child); self.first_parent_after = list(self.mem)
        # parent alive: Reset() = internalReset (registers, heads, stacks, labels, mal_active) and ClearFlags
        self.reg = [0, 0, 0]; self.heads = [0, 0, 0, 0]; self.local.clear(); self.glob.clear(); self.cur_stack = 0
        self.read_label = []; self.next_label = []; self.mal_active = False
        self.executed = [False] * len(self.mem); self.copied = [False] * len(self.mem)
        return True

    # ---- one CPU cycle (cHardwareCPU::SingleProcess) ----
    def step(self):
        self.time_used += 1
        self.advance_ip = True
        self.adjust_head(HEAD_IP); ip = self.ip(); inst = self.mem[ip]
        if self.trace is not None: self.trace.append(self.snapshot(inst))
        self.set_executed(ip)
        self.execute(inst)
        if self.advance_ip: self.advance(HEAD_IP)

    def execute(self, inst: int):
        reg = self.reg; heads = self.heads
        if inst < NUM_NOPS: return
        if inst == IF_N_EQU:
            op1 = self.find_modified(REG_BX); op2 = (op1 + 1) % NUM_REGISTERS
            if reg[op1] == reg[op2]: self.advance(HEAD_IP)
        elif inst == IF_LESS:
            op1 = self.find_modified(REG_BX); op2 = (op1 + 1) % NUM_REGISTERS
            if reg[op1] >= reg[op2]: self.advance(HEAD_IP)
        elif inst == IF_LABEL:
            self.read_next_label(); lab = self.complement(self.next_label)
            if lab != self.read_label: self.advance(HEAD_IP)
        elif inst == MOV_HEAD:
            h = self.find_modified(HEAD_IP); heads[h] = heads[HEAD_FLOW]
            if h == HEAD_IP: self.advance_ip = False
        elif inst == JMP_HEAD:
            h = self.find_modified(HEAD_IP); heads[h] = self.adjust(s32(heads[h] + reg[REG_CX]))
        elif inst == GET_HEAD:
            h = self.find_modified(HEAD_IP); reg[REG_CX] = heads[h]
        elif inst == SET_FLOW:
            r = self.find_modified(REG_CX); heads[HEAD_FLOW] = self.adjust(reg[r])
        elif inst == SHIFT_R:
            r = self.find_modified(REG_BX); reg[r] = reg[r] >> 1                       # arithmetic shift of a signed int
        elif inst == SHIFT_L:
            r = self.find_modified(REG_BX); reg[r] = s32(reg[r] << 1)
        elif inst == INC:
            r = self.find_modified(REG_BX); reg[r] = s32(reg[r] + 1)
        elif inst == DEC:
            r = self.find_modified(REG_BX); reg[r] = s32(reg[r] - 1)
        elif inst == PUSH:
            r = self.find_modified(REG_BX); self.stack().push(reg[r])
        elif inst == POP:
            r = self.find_modified(REG_BX); reg[r] = self.stack().pop()
        elif inst == SWAP_STK:
            self.cur_stack ^= 1
        elif inst == SWAP:
            op1 = self.find_modified(REG_BX); op2 = (op1 + 1) % NUM_REGISTERS; reg[op1], reg[op2] = reg[op2], reg[op1]
        elif inst == ADD:
            d = self.find_modified(REG_BX); reg[d] = s32(reg[REG_BX] + reg[REG_CX])
        elif inst == SUB:
            d = self.find_modified(REG_BX); reg[d] = s32(reg[REG_BX] - reg[REG_CX])
        elif inst == NAND:
            d = self.find_modified(REG_BX); reg[d] = s32(~(reg[REG_BX] & reg[REG_CX]))
        elif inst == H_COPY:
            self.adjust_head(HEAD_READ); self.adjust_head(HEAD_WRITE)
            r = self.mem[heads[HEAD_READ]]
            if self.is_nop(r):
                if len(self.read_label) < MAX_LABEL: self.read_label.append(r)    # cCodeLabel::AddNop ignores beyond MAX_LENGTH
            else: self.read_label = []
            self.mem[heads[HEAD_WRITE]] = r; self.copied[heads[HEAD_WRITE]] = True
            self.advance(HEAD_READ); self.advance(HEAD_WRITE)
        elif inst == H_ALLOC:
            cur = len(self.mem); alloc = min(int(OFFSPRING_SIZE_RANGE * cur), MAX_GENOME_LENGTH - cur)
            if self.allocate_main(alloc): reg[REG_AX] = cur
        elif inst == H_DIVIDE:
            for h in range(4): self.adjust_head(h)
            div_pos = heads[HEAD_READ]; child_end = heads[HEAD_WRITE]
            if child_end == 0: child_end = len(self.mem)
            self.divide_main(div_pos, len(self.mem) - child_end)
            for h in range(4): self.adjust_head(h)
        elif inst == IO:
            r = self.find_modified(REG_BX)
            if self.input_ptr >= len(INPUTS): self.input_ptr = 0
            reg[r] = INPUTS[self.input_ptr]; self.input_ptr += 1
        elif inst == H_SEARCH:
            self.read_next_label(); self.next_label = self.complement(self.next_label)
            found = self.find_label()
            reg[REG_BX] = found - self.ip(); reg[REG_CX] = len(self.next_label)
            heads[HEAD_FLOW] = found; self.advance(HEAD_FLOW)
        else: raise ValueError(inst)

    def snapshot(self, inst: int) -> dict:
        return dict(t=self.time_used, ip=self.ip(), inst=NAMES[inst], heads=list(self.heads), reg=list(self.reg), mem=to_str(self.mem),
                    divides=self.num_divides, read_label=to_str(self.read_label), mal=int(self.mal_active))

def gestation(genome: Sequence[int], trace: Optional[list] = None) -> Organism:
    """cTestCPU::ProcessGestation: run until the first divide or TEST_CPU_TIME_MOD * L cycles."""
    org = Organism(genome, trace); budget = TEST_CPU_TIME_MOD * len(genome)
    while org.time_used < budget and org.num_divides == 0: org.step()
    return org

def test_genome(genome: Union[str, Sequence[int]]) -> dict:
    """cTestCPU::TestGenome / TestGenome_Body with generation_tests = 3: returns viable, depth_found, max_depth, and the organisms."""
    genome = parse(genome); orgs: List[Organism] = []; res = dict(viable=False, depth_found=-1, max_depth=-1, cycle_to=-1)
    def body(g: List[int], depth: int) -> bool:
        res['max_depth'] = max(res['max_depth'], depth)
        org = gestation(g); orgs.append(org)
        if org.num_divides == 0: return False
        if org.copy_true: res['depth_found'] = depth; res['viable'] = True; return True
        for anc in range(depth):
            if org.offspring == orgs[anc].genome: res['depth_found'] = depth; res['viable'] = True; res['cycle_to'] = anc; return True
        if depth + 1 < TEST_CPU_GENERATIONS: return body(org.offspring, depth + 1)
        return False
    body(genome, 0); res['orgs'] = orgs
    return res

def lifetime(genome: Union[str, Sequence[int]]) -> Organism:
    """exp11 fecundity run: the same CPU for AGE_LIMIT * L cycles (Avida's DEATH_METHOD 2 lifetime), continuing after divides
    with DIVIDE_METHOD 1 (the parent keeps memory[0..div_point) and is reset)."""
    genome = parse(genome); org = Organism(genome); budget = AGE_LIMIT * len(genome)
    while org.time_used < budget: org.step()
    return org

def run_test(genome: Union[str, Sequence[int]]) -> dict:
    """Everything exp11 records per genome: the Analyze-Mode verdict and the depth-0 organism's first divide, plus the lifetime
    fecundity (all divides and copy-true divides within AGE_LIMIT * L cycles)."""
    ops = parse(genome); t = test_genome(ops); o0 = t['orgs'][0]; life = lifetime(ops)
    return dict(genome=to_str(ops), viable=t['viable'], depth_found=t['depth_found'], max_depth=t['max_depth'],
                divides=o0.num_divides, first_divide_step=o0.first_divide_step, alloc_step=o0.alloc_step,
                child=to_str(o0.first_child) if o0.first_child is not None else '', copy_true=o0.copy_true,
                parent_after=to_str(o0.first_parent_after) if o0.first_parent_after is not None else '',
                intact=o0.first_parent_after == ops if o0.first_parent_after is not None else False,
                fecundity=life.num_divides, fecundity_true=life.divides_true)

if __name__ == '__main__':
    import sys
    for g in sys.argv[1:]:
        r = run_test(g); print(r)
