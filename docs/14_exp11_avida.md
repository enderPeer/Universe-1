# exp11: Avida's heads CPU and Analyze-Mode viability, every semantic decision and where it comes from

The target is the enumeration of arXiv 1701.03993 (Nitash C G, LaBar, Hintze, Adami 2017): all 26^8 Avida genomes of length 8 run
through Avida's Analyze Mode, 914 viable; nothing at length 7. The paper names the software (Avida 2.14, Methods) and the mode
(Analyze Mode, "Data analysis") but describes neither the CPU nor the viability test; both live only in the source. Everything below
was read from the Avida source at tag `2.14.0` (devosoft/avida, commit c6179ff); every file consulted is byte-identical to the
current master branch (`cHardwareCPU.cc`, `cHardwareCPU.h`, `cHardwareBase.cc`, `cHeadCPU.h`, `cHeadCPU.cc`, `cCPUMemory.cc`,
`cCPUStack.h`, `cCodeLabel.h`, `cCodeLabel.cc`, `cTestCPU.cc`, `cCPUTestInfo.cc`, `nHardware.h`), so the two versions do not differ
here. The implementation is `sim/avida.py` (reference), `gpu/u1_avida.cu` (CUDA, also compiles to a CPU emulation) and
`gpu/u1_avida.comp` + `gpu/u1_avida_vk.c` (Vulkan); `fast/check_avida.py` compares an engine with the reference field by field.
The standard for this list is docs/11 section 3: say what is implicit, where it hides and what would move if it were different.

## 1. What is enumerated and what "viable" means

| # | Decision | Source | What would move |
|---|---|---|---|
| 1.1 | Each genome is tested alone in a test CPU: `cTestCPU::TestGenome` creates a fresh organism, runs it, and checks its offspring. No population, no mutations (the test CPU's `cMutationRates` default-construct to zero; `COPY_MUT_PROB` etc. in `avida.cfg` apply only to population runs). | `cTestCPU.cc` `TestGenome_Body`, `cCPUTestInfo.cc` constructor, `cMutationRates.h` | with population mutation rates the sweep would be stochastic |
| 1.2 | Gestation = the organism runs until its first successful divide or until `TEST_CPU_TIME_MOD` x length = **20 L CPU cycles** (160 for L = 8, 140 for L = 7, 180 for L = 9); one cycle = one `SingleProcess` = one instruction. | `cTestCPU::ProcessGestation`; `cAvidaConfig.h` `TEST_CPU_TIME_MOD 20` | the viable count: 100 of the 914 first divide at cycles 147..156, so a budget of 16 L would lose them |
| 1.3 | Viable (`is_viable`) = (a) the genome divides and its offspring equals the genome (`CopyTrue`, compared with the injected genome, not with the memory at divide time); or (b) the offspring differs, is itself run as a fresh organism (its own 20 x length budget) and its offspring equals it or an ancestor; recursively to **3 generations** (`TEST_CPU_GENERATIONS = 3`: depths 0, 1, 2; at depth d the offspring is compared with the genomes at depths 0..d). | `cTestCPU::TestGenome_Body` cases 1-4, `nHardware.h` | 51 of the 914 are viable only through (b) (depth 1): a copy-true-only test would find 863 |
| 1.4 | The paper filtered on viability (and on non-zero fitness, which every dividing organism has: merit = min(executed, copied, length) > 0, gestation > 0). | paper, "Experimental Design"; `cPhenotype::CalcSizeMerit` with `BASE_MERIT_METHOD 4` | none |
| 1.5 | Genome index for sweeps: g = sum op_i 26^i, position 0 least significant (letters a..z = instructions 0..25 in `instset-heads.cfg` order). This is our convention, not Avida's; it only fixes chunk boundaries. | project word-packing convention | nothing |

## 2. The heads CPU: state

| # | Decision | Source |
|---|---|---|
| 2.1 | One thread (`MAX_CPU_THREADS 1`), three 32-bit signed registers AX, BX, CX (all 0 at start), four heads IP, READ, WRITE, FLOW (all at position 0 at start), two stacks of 10 ints (a thread-local and a global one, `cur_stack` 0 = local; `swap-stk` toggles), two labels (`read_label`: the nops copied most recently; `next_label`: the template read after `if-label`/`h-search`), `mal_active` (an allocation is pending), `advance_ip`. | `cHardwareCPU::cLocalThread::Reset`, `internalReset`, `cHardwareCPU.h` |
| 2.2 | Memory = the genome's instructions, with per-site flags `executed` and `copied` (all clear at start). Memory grows by `h-alloc` and is cut at divide. Heads address memory positions; there is no separate child memory space (`GetMemory(int)` returns the one memory). | `cCPUMemory`, `cHardwareCPU.h` `GetMemory` |
| 2.3 | Stack push: pointer decrements (wrapping 0 -> 9), writes; pop: reads the slot, zeroes it, pointer increments (wrapping 9 -> 0). Popping an empty stack yields 0. | `cCPUStack.h` |
| 2.4 | Head adjustment (`cHeadCPU::fullAdjust`): a position inside memory is kept; a negative position (or an empty memory) becomes 0 (**no backward wrap**); a position in [size, 2 size) has size subtracted; larger ones are taken mod size. Adjustment happens in `Set`, `Jump`, `Advance`, at the start of every cycle for the IP, in `h-copy` for READ/WRITE, and in `h-divide` for all heads; `mov-head` copies a position without adjusting. | `cHeadCPU.h`, `cHeadCPU.cc` |
| 2.5 | `GetNextInst` at the last memory position returns the error instruction (op 255, not a nop): **nop modifiers and labels never wrap** around the end of memory. | `cHeadCPU::GetNextInst`, `cInstSet::GetInstError` |
| 2.6 | A nop modifier is consumed only if the next instruction is a nop (`FindModifiedRegister/Head`): the IP advances onto it and it is flagged executed. nop-A/B/C select AX/BX/CX or the IP/READ/WRITE head (the FLOW head cannot be named). | `cHardwareCPU.cc` 1622-1676, `initInstLib` nop table |
| 2.7 | `ReadLabel`: consumes the following nops (at most `cCodeLabel::MAX_LENGTH = 10`) into `next_label`, advancing the IP over them; only the first nop is flagged executed (`MAX_LABEL_EXE_SIZE 1`). The complement of a label is every nop rotated by one (A->B->C->A). | `cHardwareCPU::ReadLabel`, `cCodeLabel::Rotate` |
| 2.8 | Every cycle: adjust the IP, flag the IP position executed, execute, then advance the IP unless the instruction cleared `advance_ip` (`mov-head` on the IP, a successful divide). No instruction costs, no stalls, no promoters, no energy (all off in `avida.cfg`). | `cHardwareCPU::SingleProcess` |
| 2.9 | Integers are 32-bit two's complement: `inc`/`dec`/`add`/`sub`/`shift-l` wrap, `shift-r` is an arithmetic shift, a head jump adds CX with wrap before adjustment. (C++ signed overflow is formally undefined; the compiled Avida wraps.) | `Inst_Inc` etc.; our choice where C++ leaves it open |

## 3. The 26 instructions (default heads set, `instset-heads.cfg`; `?BX?` = BX unless a nop follows)

| letter | instruction | semantics as implemented (`cHardwareCPU.cc` function) |
|---|---|---|
| a b c | nop-A/B/C | nothing (`Inst_Nop`); as a modifier see 2.6, 2.7; nop-A (op 0) is also the content of freshly allocated memory |
| d | if-n-equ | r1 = ?BX?, r2 = the register after r1 (A->B->C->A, not nop-modifiable); if reg[r1] == reg[r2] skip the next instruction (`Inst_IfNEqu`) |
| e | if-less | same registers; if reg[r1] >= reg[r2] skip the next instruction (`Inst_IfLess`) |
| f | if-label | read the template (2.7), complement it; if it differs from `read_label` skip the next instruction. An empty template equals an empty read label (`Inst_IfLabel`) |
| g | mov-head | head ?IP? (nop-A IP, nop-B READ, nop-C WRITE) is set to the FLOW head's position; if it was the IP, the IP is not advanced this cycle (`Inst_MoveHead`) |
| h | jmp-head | head ?IP? jumps by CX (then adjusted, 2.4); the IP still advances afterwards (`Inst_JumpHead`, the "@JEB probably shouldn't" comment is left as is) |
| i | get-head | CX = position of head ?IP? (`Inst_GetHead`) |
| j | set-flow | FLOW = reg ?CX? (adjusted) (`Inst_SetFlow`) |
| k l | shift-r / shift-l | ?BX? >>= 1 (arithmetic) / <<= 1 (`Inst_ShiftR/L`) |
| m n | inc / dec | ?BX? +- 1 (`Inst_Inc/Dec`) |
| o p | push / pop | push ?BX? on / pop into ?BX? from the current stack (`Inst_Push/Pop`, 2.3) |
| q | swap-stk | toggle the current stack (`Inst_SwitchStack`) |
| r | swap | swap ?BX? with the register after it (`Inst_Swap`) |
| s t u | add / sub / nand | ?BX? = BX + CX / BX - CX / ~(BX & CX): the operands are always BX and CX, only the destination is modifiable (`Inst_Add/Sub/Nand`) |
| v | h-copy | adjust READ and WRITE; read the instruction at READ: a nop is appended to `read_label` (at most 10 kept), anything else clears it; write it at WRITE and flag that site copied; advance both heads. Not nop-modifiable (`Inst_HeadCopy`) |
| w | h-alloc | `Inst_MaxAlloc`: allocate min(2 x memory size, 2048 - size) sites of nop-A at the end of memory and set AX = old size. Fails (no effect) if an allocation is already pending (`REQUIRE_ALLOCATE 1`, `m_mal_active`), if the new size leaves [8, 2048], or if the amount exceeds 2 x the old size / the old size exceeds 2 x the amount (`Allocate_Main`, `OFFSPRING_SIZE_RANGE 2.0`, `ALLOC_METHOD 0`) |
| x | h-divide | `Inst_HeadDivideMut` -> `Divide_Main`: adjust all heads; parent = memory[0 .. READ), child = memory[READ .. WRITE) (WRITE at 0 means "to the end"); the divide succeeds iff (section 4) and then: the offspring is the child, the memory is cut to the parent part, the parent is reset (registers, heads, stacks, labels, `mal_active`) and its flags cleared (`DIVIDE_METHOD 1`), and the IP is not advanced. A failed divide changes nothing but the head adjustments |
| y | IO | ?BX? = the next of the three deterministic inputs 0x0f13149f, 0x3308e53e, 0x556241eb (cycling); the output goes to the task library, which cannot affect viability here (no required task, 1.4) (`Inst_TaskIO`, `cEnvironment::SetupInputs` non-random branch) |
| z | h-search | read the template (2.7), complement it. Empty template: BX = 0, CX = 0, FLOW = IP + 1. Otherwise search **from position 0** with `FindLabel_Forward` (section 5): found -> BX = (position of the label's last nop) - IP, CX = label length, FLOW = the instruction after the label; not found -> BX = 0, CX = label length, FLOW = IP + 1 (`Inst_HeadSearch`, `FindLabel(0)`) |

## 4. When a divide succeeds (`cHardwareBase::Divide_CheckViable`, avida.cfg defaults)

| # | Condition | Values for L = 8 | Source |
|---|---|---|---|
| 4.1 | child size and parent size both in [max(8, int(L / 2)), min(2048, int(2 L))]; **8 is Avida's hard minimum genome length** (`MIN_GENOME_LENGTH`), independent of L | [8, 16] | `Definitions.h`, `OFFSPRING_SIZE_RANGE 2.0`; `MIN/MAX_GENOME_SIZE 0` = off |
| 4.2 | executed sites in the parent part >= int(parent size x `MIN_EXE_LINES` 0.5) | >= 4 of the first 8 | flags of section 2 |
| 4.3 | copied sites in the child part >= int(child size x `MIN_COPIED_LINES` 0.5) | >= 4 | |
| 4.4 | age checks `JUV_PERIOD 0`, `MIN_CYCLES 0`; no required task, reaction or bonus; parent fertile; merit > 0; `REQUIRE_EXACT_COPY 0` | always true | `cOrganism::Divide_CheckViable` |

4.1 is what forbids length-7 replicators directly: a length-7 genome can allocate (7 -> 21) and divide, but child and parent part must
each be >= 8, so the child can never equal the parent; it could still be viable through 1.3(b) if its longer child replicated, which
the length-7 sweep (zero viable among 26^7, 565 genomes divide at all) rules out.

## 5. `FindLabel_Forward` (the template search of `h-search`), ported literally

Searching for label S of length n in memory M from position 0: pos = n; while pos < size: if M[pos] is a nop, extend to the whole
nop run [start, end) containing pos (start cannot go below 0); for every offset in [start, end - n], test M[offset .. offset+n) == S;
on a match return offset + n; otherwise pos = end; then pos += n (so the search advances in blocks of n and can skip a short nop
run entirely). Not found: -1. The quirks kept on purpose: the first n positions are never the start of a match (it skips off the
"template we are on" even when the search starts at 0), and a run is scanned once from its start. These are Avida's semantics,
not ours.

## 6. Avida-faithful measurements added for exp11 (not part of the viability test)

| # | Quantity | Definition | Why this definition |
|---|---|---|---|
| 6.1 | first divide | the cycle (1-based) of the first successful divide of the depth-0 organism | the Analyze-Mode gestation time |
| 6.2 | copy-true | the first child equals the genome | `cPhenotype::CopyTrue` |
| 6.3 | intact | after the first divide the parent part equals the genome (READ at L and memory[0..L) unchanged) | exp06c's "original intact at the copy" |
| 6.4 | fecundity | number of successful divides of the depth-0 organism within `AGE_LIMIT` x L = 20 L cycles, continuing after each divide as in a population run (`DIVIDE_METHOD 1`: the parent keeps memory[0..READ) and is reset); `fecundity_true` counts the divides whose child equals the genome | Avida's lifetime (`DEATH_METHOD 2`, `AGE_LIMIT 20`): an organism dies after 20 L instructions in a population too, so this is the number of children it can have |

## 7. Validation

- `sim/avida.py` on the 914 published genomes: 914 viable (863 copy-true at depth 0, 51 at depth 1), 904 with the parent intact,
  fecundity 1 (907) or 2 (7); on 20,000 random length-8 genomes: 0 viable.
- `fast/check_avida.py`: the CUDA engine (RTX 3060), its CPU emulation (g++ with `gpu/cuda_shim.h`) and the Vulkan engine (R9700,
  RX 9070 XT, RX 9060 XT) agree with the reference on every field (viable, depth, first divide, intact, copy-true, fecundity,
  copy-true fecundity) for 65,536 random length-8 genomes plus the 914, and for 2,048 random length-7 genomes.
- **Avida 2.14.0 itself**, built from the `2.14.0` tag on falke64 (`git submodule update --init`, cmake with
  `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`) and run in Analyze Mode on its default configuration (`results/exp11/avida214_analyze.cfg`,
  `avida214_analyze_detail.dat`): viability agrees with `sim/avida.py` for all 936 genomes tested (914 published, 2 extra, 20 random),
  and Avida's `gest_time` equals our first-divide cycle for every viable genome (936 of 936 fields).
- The sweeps (results/exp11_summary.md): all 26^7 length-7 genomes -> 0 viable; all 26^8 -> the 914 published genomes plus
  `vwsfgxgb` and `vwsxfggb`, which Avida 2.14.0 also reports viable (gestation 97 and 110). Nothing in sections 1-6 can separate
  these two from their published neighbours `vwtfgxgb`/`vwufgxgb` (sub/nand in the place of add, identical behaviour with
  BX = CX = 0), so the published file is short by two, not the semantics.

## 8. What is still a choice of ours

- 2.9 (integer wrap) and the cap of 128 memory sites per organism (3 x 4 L, enough for every organism the 3-generation test can
  create at L <= 10; `allocate_main` would refuse a larger allocation, which cannot happen at these lengths).
- The genome index convention 1.5 and the chunking of the sweep.
- Everything in section 6.
