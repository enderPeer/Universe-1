# Experiments (for Codex to run)

Both runners are pure Python 3, no dependencies. Run from the repo root.
Results land in `results/` as JSON; commit them.

## exp01 — ISA enumeration
```
python experiments/exp01_isa_enum/run.py --W 1 --a 2 --p 2
python experiments/exp01_isa_enum/run.py --W 2 --a 2 --p 2 --max-programs 2000 --max-isas 20000
python experiments/exp01_isa_enum/run.py --W 3 --a 3 --p 3 --max-programs 500 --max-isas 5000
```
Deliver: best ISA per W, its score (distinct unary operators out of the
universe `(2^W)^(2^W)`), state bits.

## exp02 — program enumeration on a fixed ISA, 256-step runtime
```
python experiments/exp02_program_enum/run.py --W 1 --a 2 --p 3 --isa NAND,JZ
python experiments/exp02_program_enum/run.py --W 2 --a 2 --p 3 --isa LD,ST,NAND,JZ --binary
python experiments/exp02_program_enum/run.py --W 3 --a 3 --p 4 --isa LD,ST,LDI,NAND,ADD,SHL,JZ,HALT --max-programs 200000 --binary
python experiments/exp02_program_enum/run.py --W 4 --a 4 --p 4 --isa LD,ST,LDI,NOT,AND,OR,XOR,ADD,SUB,SHL,SHR,JMP,JZ,JC,SWAP,HALT --max-programs 200000 --binary
```
Deliver: unary and binary operator counts vs universe, distribution of
halt/budget/loop, and the shortest program per discovered operator.

## What to report back (results/expNN_summary.md)
1. Table W × best-ISA × score × state bits.
2. Which memory layout (docs/00_machine_model.md §4) won per W.
3. Where the 256-step budget binds (programs ending in "budget" not "halt").
4. Proposed next sweep.

## exp03 — exhaustive 4-byte sweep on the cluster (GPU + CPU)
See `docs/02_4byte_run.md`. Engines: `fast/u1` (CPU), `gpu/u1_cuda` (NVIDIA), `gpu/u1_vk` (AMD).
Dispatch: `python3 cluster/run_4byte_gpu.py` (9 GPUs) or `cluster/run_4byte.sh` (72 CPU threads).
