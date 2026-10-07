# Experiment 03: 4-byte (2^32 program) exhaustive sweeps

Wall time includes dispatch and GPU work; excludes shard download and merge.

| W | run | a | p | I | opcode bits | ISA | mode | distinct operators | universe | seconds | M programs/s | coverage |
|---|---|---|---|---|---|---|---|---:|---|---:|---:|---|
| 1 | exp03_w1_nand_jz | 2 | 5 | 1 | 1 | NAND,JZ | unary | 4 | 2^2 | 11.91 | 360.5 | complete |
| 1 | exp03_w1_nand_skz | 2 | 5 | 1 | 1 | NAND,SKZ | unary | 4 | 2^2 | 12.43 | 345.63 | complete |
| 2 | exp03_w2_o1 | 2 | 4 | 2 | 1 | NAND,JZ | unary | 12 | 2^8 | 13.42 | 320.05 | complete |
| 2 | exp03_w2_o1_swap | 2 | 4 | 2 | 1 | SWAP,SKNZ | unary | 2 | 2^8 | 19.14 | 224.37 | complete |
| 4 | exp03_w4_o2_add | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,SKZ | unary | 1829051 | 2^64 | 54.97 | 78.13 | complete |
| 4 | exp03_w4_o3_swap | 2 | 3 | 4 | 3 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | unary | 1463824 | 2^64 | 29.79 | 144.18 | complete |
| 4 | exp03_w4_o4_full | 1 | 3 | 4 | 4 | LD,ST,NOT,AND,OR,XOR,ADD,SUB,INC,DEC,SHL,SHR,ROL,SKZ,SKNZ,HALT | unary | 977928 | 2^64 | 42.99 | 99.91 | complete |
| 4 | exp03_w4_o3_core | 2 | 3 | 4 | 3 | LD,ST,LDI,NAND,ADD,SHL,JZ,HALT | unary | 62880 | 2^64 | 27.05 | 158.79 | complete |
| 4 | exp03_w4_o3_arith | 2 | 3 | 4 | 3 | LD,ST,ADD,SUB,SHL,SHR,JNZ,HALT | unary | 24420 | 2^64 | 35.02 | 122.64 | complete |
| 4 | exp03_w4_o2_nand | 2 | 3 | 4 | 2 | LD,ST,NAND,JZ | unary | 16 | 2^64 | 41.01 | 104.72 | complete |
| 4 | exp03_w4_o3_bool | 2 | 3 | 4 | 3 | LD,ST,NOT,AND,OR,XOR,SKZ,HALT | unary | 16 | 2^64 | 20.95 | 205.03 | complete |
| 8 | exp03_w8_o4 | 4 | 2 | 8 | 4 | LD,ST,LDI,NOT,AND,OR,XOR,ADD,SUB,SHL,SHR,JMP,JZ,JC,SWAP,HALT | unary | 7119 | 2^2048 | 677.31 | 6.34 | complete |

## Highest counts among completed candidates

- W=1, unary: exp03_w1_nand_jz, exp03_w1_nand_skz (4 operators).
- W=2, unary: exp03_w2_o1 (12 operators).
- W=4, unary: exp03_w4_o2_add (1829051 operators).
- W=8, unary: exp03_w8_o4 (7119 operators).

These rankings compare only the configured candidate ISAs; they do not prove global optimality.
All runs use layout L3 (address 0 aliases A), so no memory-layout winner is established.
Raw shards and minimum-program witnesses are in results/shards/ on the coordinator and producing worker.
W<=4 unary and W<=2 binary use exact keys; larger tables are represented by hashes.
GPU engines do not report halt/loop/budget distributions. W=8 binary exceeds the current GPU table limit.
