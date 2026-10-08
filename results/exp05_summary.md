# exp05: 4-byte (2^32 program) exhaustive sweeps

Wall time includes dispatch and GPU work; excludes shard download and merge.

| W | run | a | p | I | opcode bits | ISA | mode | distinct operators | universe | seconds | M programs/s | coverage |
|---|---|---|---|---|---|---|---|---:|---|---:|---:|---|
| 4 | exp05_w4_o2_add_jc | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,JC | unary | 8533818 | 2^64 | 56.25 | 76.36 | complete |
| 4 | exp05_w4_o2_adc | 2 | 3 | 4 | 2 | SWAP,ADC,NAND,SKZ | unary | 7873949 | 2^64 | 61.44 | 69.9 | complete |
| 4 | exp05_w4_o2_add_jz | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,JZ | unary | 5181022 | 2^64 | 55.52 | 77.35 | complete |
| 4 | exp05_w4_codex_shr_mul | 2 | 3 | 4 | 3 | SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT | unary | 3038671 | 2^64 | 30.9 | 139.02 | complete |
| 4 | exp05_w4_o2_rol | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,ROL | unary | 1259140 | 2^64 | 38.28 | 112.21 | complete |
| 4 | exp05_w4_o2_sub | 2 | 3 | 4 | 2 | SWAP,SUB,NAND,SKZ | unary | 1123714 | 2^64 | 58.14 | 73.87 | complete |
| 4 | exp05_w4_o2_nocond | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,SHR | unary | 1055395 | 2^64 | 40.03 | 107.3 | complete |
| 4 | exp05_w4_o2_add_sknz | 2 | 3 | 4 | 2 | SWAP,ADD,NAND,SKNZ | unary | 1043408 | 2^64 | 62.42 | 68.81 | complete |
| 4 | exp05_w4_o2_xor | 2 | 3 | 4 | 2 | SWAP,ADD,XOR,SKZ | unary | 547533 | 2^64 | 56.41 | 76.13 | complete |
| 4 | exp05_w4_o2_xor_shr | 2 | 3 | 4 | 2 | SWAP,ADD,XOR,SHR | unary | 500264 | 2^64 | 39.56 | 108.56 | complete |
| 4 | exp05_w4_o2_shr | 2 | 3 | 4 | 2 | SWAP,ADD,SHR,SKZ | unary | 331839 | 2^64 | 55.39 | 77.54 | complete |
| 4 | exp05_w4_prop_combined | 2 | 3 | 4 | 3 | SWAP,ADD,NAND,SKZ,HALT,LD,ST,LDI | unary | 228409 | 2^64 | 31.45 | 136.55 | complete |
| 4 | exp05_w4_i8_o4 | 4 | 2 | 8 | 4 | LD,ST,LDI,NOT,AND,OR,XOR,ADD,SUB,SHL,SHR,JMP,JZ,JC,SWAP,HALT | unary | 4926 | 2^64 | 38.13 | 112.65 | complete |
| 4 | exp05_w4_i8_o3 | 2 | 2 | 8 | 3 | SWAP,ADD,NAND,SKZ,HALT,LDI,SHR,ROL | unary | 1157 | 2^64 | 28.1 | 152.86 | complete |

## Highest counts among completed candidates

- W=4, unary: exp05_w4_o2_add_jc (8533818 operators).

These rankings compare only the configured candidate ISAs; they do not prove global optimality.
All runs use layout L3 (address 0 aliases A), so no memory-layout winner is established.
Raw shards and minimum-program witnesses are in results/shards/ on the coordinator and producing worker.
W<=4 unary and W<=2 binary use exact keys; larger tables are represented by hashes.
GPU engines do not report halt/loop/budget distributions. W=8 binary exceeds the current GPU table limit.
