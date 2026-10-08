# Life ensemble: analysis of the nine 1024^2 x 200,000-tick runs

Source commit of the engines: `eed02f8` (CUDA on adler40/knecht24, Vulkan on specht32/falke64, verified bit-identical to the
CPU reference on all nine GPUs before the run). Configuration: `cluster/life_runs.conf`; dispatch: `cluster/run_life.py`;
this report: `cluster/analyze_life.py`. Phenotypes below use the Python reference machine on the dumped final grids.

## Runs, speed, survival

| run | ISA | seed | mu_bits | repro_cost | income | steps | GPU | GPU s | ticks/s | M cell-updates/s | final alive | min alive (t>=1000) | extinct |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| champ_s1 | SWAP,ADD,NAND,SKZ | 1 | 128 | 128 | 20 | 256 | adler40 RTX 4090 | 500 | 400 | 419 | 882,215 (84.1%) | 311,933 | no |
| champ_s2 | SWAP,ADD,NAND,SKZ | 2 | 128 | 128 | 20 | 256 | adler40 RTX 4080 | 530 | 377 | 395 | 900,669 (85.9%) | 312,129 | no |
| champ_s3 | SWAP,ADD,NAND,SKZ | 3 | 128 | 128 | 20 | 256 | knecht24 RTX 3060 #0 | 1499 | 133 | 140 | 952,442 (90.8%) | 305,170 | no |
| swap_s1 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 1 | 128 | 128 | 8 | 256 | knecht24 RTX 3060 #1 | 179 | 1117 | 1172 | 869,286 (82.9%) | 835,894 | no |
| swap_s2 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 2 | 128 | 128 | 8 | 256 | knecht24 RTX 3060 #2 | 174 | 1153 | 1209 | 859,658 (82.0%) | 831,548 | no |
| swap_s3 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 3 | 128 | 128 | 8 | 256 | specht32 RX 9070 XT | 1738 | 115 | 121 | 855,590 (81.6%) | 820,895 | no |
| swap_mu32 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 1 | 32 | 128 | 8 | 256 | specht32 RX 9060 XT | 1700 | 118 | 123 | 1,039,320 (99.1%) | 1,016,041 | no |
| swap_mu512 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 1 | 512 | 128 | 8 | 256 | falke64 R9700 #0 | 996 | 201 | 211 | 884,981 (84.4%) | 791,731 | no |
| swap_rc64 | SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT | 1 | 128 | 64 | 8 | 256 | falke64 R9700 #1 | 444 | 451 | 473 | 1,046,089 (99.8%) | 1,043,366 | no |
| jc_s1 | SWAP,ADD,NAND,JC | 1 | 128 | 128 | 20 | 256 | adler40 RTX 4090 | 494 | 405 | 425 | 916,979 (87.4%) | 215,352 | no |
| jc_s2 | SWAP,ADD,NAND,JC | 2 | 128 | 128 | 20 | 256 | adler40 RTX 4080 | 531 | 377 | 395 | 928,638 (88.6%) | 194,467 | no |
| champ512_s1 | SWAP,ADD,NAND,SKZ | 1 | 128 | 128 | 36 | 512 | adler40 RTX 4080 | 1017 | 197 | 206 | 916,394 (87.4%) | 314,234 | no |

GPU seconds are the engine's own `done ... ticks in ...s`; the dispatcher wall time in RUNS.md adds the copy-back.

## Genome diversity (distinct genomes among live cells)

| run | t=0 (initial) | 1,000 | 10,000 | 50,000 | 100,000 | 200,000 | max after 1,000 | min after 1,000 | births/tick at end | mean energy at end |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| champ_s1 | 52,579 | 137,122 | 197,059 | 107,129 | 82,074 | 51,219 | 271,221 | 51,219 | 8,609 | 186.7 |
| champ_s2 | 52,104 | 136,972 | 198,252 | 96,303 | 77,726 | 50,923 | 268,489 | 50,923 | 8,550 | 189.7 |
| champ_s3 | 52,687 | 134,435 | 184,353 | 102,730 | 75,936 | 58,444 | 267,697 | 58,052 | 9,526 | 186.4 |
| swap_s1 | 52,579 | 299,252 | 234,736 | 274,103 | 231,916 | 224,903 | 299,252 | 181,802 | 12,615 | 208.2 |
| swap_s2 | 52,104 | 296,208 | 223,035 | 276,923 | 239,543 | 232,652 | 296,208 | 175,429 | 12,021 | 209.5 |
| swap_s3 | 52,687 | 298,263 | 236,709 | 280,447 | 272,551 | 238,780 | 298,263 | 187,204 | 11,841 | 210.6 |
| swap_mu32 | 52,579 | 717,907 | 370,772 | 272,681 | 223,535 | 229,298 | 717,907 | 218,010 | 18,739 | 198.8 |
| swap_mu512 | 52,579 | 95,433 | 70,997 | 98,961 | 103,858 | 93,516 | 105,374 | 53,784 | 14,657 | 202.4 |
| swap_rc64 | 52,579 | 324,911 | 183,627 | 92,456 | 74,605 | 62,614 | 324,911 | 61,556 | 44,999 | 198.4 |
| jc_s1 | 52,579 | 92,695 | 163,068 | 90,733 | 76,158 | 63,826 | 236,784 | 63,826 | 10,029 | 184.8 |
| jc_s2 | 52,104 | 84,056 | 161,396 | 103,362 | 83,580 | 71,090 | 242,090 | 70,891 | 10,700 | 180.9 |
| champ512_s1 | 52,579 | 134,923 | 202,527 | 104,466 | 90,497 | 89,144 | 273,500 | 82,974 | 10,251 | 172.7 |

![curves](curves.png)

## Final populations: most common genomes

Each run's 100 most abundant genomes were executed on all 256 (state, neighbour state) inputs. `trigger` is the fraction of inputs
whose new state is 15 (reproduction); `nb-dep` is how many of the 16 own states give a neighbour-dependent outcome; `halt` is the
fraction of inputs that reach HALT (the champion ISA has none, so every genome costs the full budget: cost 16 at 256 steps, 32 at 512).

| run | genome | share | trigger | nb-dep states | halt | mean steps | mean cost | program |
|---|---|---:|---:|---:|---:|---:|---:|---|
| champ_s1 | `0x02a49326` | 10.1% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 2; SWAP 2; SWAP 3; NAND 1; ADD 0; NAND 2; SWAP 2; SWAP 0` |
| champ_s1 | `0x92530541` | 8.3% | 0.48 | 7 | 0.00 | 256 | 16.0 | `SWAP 1; ADD 0; ADD 1; SWAP 0; SWAP 3; ADD 1; SWAP 2; NAND 1` |
| champ_s1 | `0x320b4936` | 6.0% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 2; SWAP 3; NAND 1; ADD 0; NAND 3; SWAP 0; SWAP 2; SWAP 3` |
| champ_s2 | `0x2a490326` | 6.0% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 2; SWAP 2; SWAP 3; SWAP 0; NAND 1; ADD 0; NAND 2; SWAP 2` |
| champ_s2 | `0x2a493026` | 1.6% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 2; SWAP 2; SWAP 0; SWAP 3; NAND 1; ADD 0; NAND 2; SWAP 2` |
| champ_s2 | `0xb1425360` | 1.4% | 0.39 | 13 | 0.00 | 256 | 16.0 | `SWAP 0; ADD 2; SWAP 3; ADD 1; SWAP 2; ADD 0; SWAP 1; NAND 3` |
| champ_s3 | `0x6a49237d` | 5.3% | 0.05 | 8 | 0.00 | 256 | 16.0 | `SKZ 1; ADD 3; SWAP 3; SWAP 2; NAND 1; ADD 0; NAND 2; ADD 2` |
| champ_s3 | `0x6a49237f` | 5.1% | 0.05 | 8 | 0.00 | 256 | 16.0 | `SKZ 3; ADD 3; SWAP 3; SWAP 2; NAND 1; ADD 0; NAND 2; ADD 2` |
| champ_s3 | `0x6a49237c` | 4.8% | 0.05 | 8 | 0.00 | 256 | 16.0 | `SKZ 0; ADD 3; SWAP 3; SWAP 2; NAND 1; ADD 0; NAND 2; ADD 2` |
| swap_s1 | `0xf0765913` | 0.7% | 0.50 | 16 | 1.00 | 8 | 1.0 | `LDI 1; SWAP 1; ROL 1; NAND 1; ADD 0; ADD 1; SWAP 0; HALT 1` |
| swap_s1 | `0xf0765813` | 0.7% | 0.50 | 16 | 1.00 | 8 | 1.0 | `LDI 1; SWAP 1; ROL 0; NAND 1; ADD 0; ADD 1; SWAP 0; HALT 1` |
| swap_s1 | `0xe0765913` | 0.7% | 0.50 | 16 | 1.00 | 8 | 1.0 | `LDI 1; SWAP 1; ROL 1; NAND 1; ADD 0; ADD 1; SWAP 0; HALT 0` |
| swap_s2 | `0x2f765913` | 0.2% | 0.50 | 16 | 1.00 | 7 | 1.0 | `LDI 1; SWAP 1; ROL 1; NAND 1; ADD 0; ADD 1; HALT 1; LDI 0` |
| swap_s2 | `0xced65777` | 0.2% | 0.42 | 16 | 1.00 | 7 | 1.0 | `ADD 1; ADD 1; ADD 1; NAND 1; ADD 0; INC 1; HALT 0; INC 0` |
| swap_s2 | `0x8f765913` | 0.2% | 0.50 | 16 | 1.00 | 7 | 1.0 | `LDI 1; SWAP 1; ROL 1; NAND 1; ADD 0; ADD 1; HALT 1; ROL 0` |
| swap_s3 | `0xec657770` | 2.2% | 0.42 | 16 | 1.00 | 8 | 1.0 | `SWAP 0; ADD 1; ADD 1; ADD 1; NAND 1; ADD 0; INC 0; HALT 0` |
| swap_s3 | `0xfc657770` | 2.1% | 0.42 | 16 | 1.00 | 8 | 1.0 | `SWAP 0; ADD 1; ADD 1; ADD 1; NAND 1; ADD 0; INC 0; HALT 1` |
| swap_s3 | `0xfd657770` | 2.0% | 0.42 | 16 | 1.00 | 8 | 1.0 | `SWAP 0; ADD 1; ADD 1; ADD 1; NAND 1; ADD 0; INC 1; HALT 1` |
| swap_mu32 | `0xce8859c3` | 0.0% | 0.50 | 16 | 1.00 | 7 | 1.0 | `LDI 1; INC 0; ROL 1; NAND 1; ROL 0; ROL 0; HALT 0; INC 0` |
| swap_mu32 | `0x5f8859c3` | 0.0% | 0.50 | 16 | 1.00 | 7 | 1.0 | `LDI 1; INC 0; ROL 1; NAND 1; ROL 0; ROL 0; HALT 1; NAND 1` |
| swap_mu32 | `0xbf8859c3` | 0.0% | 0.50 | 16 | 1.00 | 7 | 1.0 | `LDI 1; INC 0; ROL 1; NAND 1; ROL 0; ROL 0; HALT 1; SKNZ 1` |
| swap_mu512 | `0xe51695b4` | 0.3% | 0.37 | 15 | 1.00 | 7 | 1.0 | `NAND 0; SKNZ 1; NAND 1; ROL 1; ADD 0; SWAP 1; NAND 1; HALT 0` |
| swap_mu512 | `0xf5685b40` | 0.3% | 0.37 | 15 | 1.00 | 7 | 1.0 | `SWAP 0; NAND 0; SKNZ 1; NAND 1; ROL 0; ADD 0; NAND 1; HALT 1` |
| swap_mu512 | `0xed605777` | 0.2% | 0.42 | 16 | 1.00 | 8 | 1.0 | `ADD 1; ADD 1; ADD 1; NAND 1; SWAP 0; ADD 0; INC 1; HALT 0` |
| swap_rc64 | `0xe9859c37` | 0.3% | 0.50 | 16 | 1.00 | 8 | 1.0 | `ADD 1; LDI 1; INC 0; ROL 1; NAND 1; ROL 0; ROL 1; HALT 0` |
| swap_rc64 | `0xe9859d37` | 0.2% | 0.50 | 16 | 1.00 | 8 | 1.0 | `ADD 1; LDI 1; INC 1; ROL 1; NAND 1; ROL 0; ROL 1; HALT 0` |
| swap_rc64 | `0xe8859c37` | 0.2% | 0.50 | 16 | 1.00 | 8 | 1.0 | `ADD 1; LDI 1; INC 0; ROL 1; NAND 1; ROL 0; ROL 0; HALT 0` |
| jc_s1 | `0x23a492e7` | 10.5% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 3; JC 2; SWAP 2; NAND 1; ADD 0; NAND 2; SWAP 3; SWAP 2` |
| jc_s1 | `0x023a4927` | 9.4% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 3; SWAP 2; NAND 1; ADD 0; NAND 2; SWAP 3; SWAP 2; SWAP 0` |
| jc_s1 | `0x45441d28` | 2.9% | 0.28 | 16 | 0.00 | 256 | 16.0 | `NAND 0; SWAP 2; JC 1; SWAP 1; ADD 0; ADD 0; ADD 1; ADD 0` |
| jc_s2 | `0x32b4936d` | 12.1% | 0.44 | 16 | 0.00 | 256 | 16.0 | `JC 1; ADD 2; SWAP 3; NAND 1; ADD 0; NAND 3; SWAP 2; SWAP 3` |
| jc_s2 | `0x2a493206` | 5.2% | 0.44 | 16 | 0.00 | 256 | 16.0 | `ADD 2; SWAP 0; SWAP 2; SWAP 3; NAND 1; ADD 0; NAND 2; SWAP 2` |
| jc_s2 | `0xb6a49273` | 4.0% | 0.41 | 16 | 0.00 | 256 | 16.0 | `SWAP 3; ADD 3; SWAP 2; NAND 1; ADD 0; NAND 2; ADD 2; NAND 3` |
| champ512_s1 | `0x6a375582` | 20.0% | 0.38 | 15 | 0.00 | 512 | 32.0 | `SWAP 2; NAND 0; ADD 1; ADD 1; ADD 3; SWAP 3; NAND 2; ADD 2` |
| champ512_s1 | `0x6a357582` | 11.7% | 0.38 | 15 | 0.00 | 512 | 32.0 | `SWAP 2; NAND 0; ADD 1; ADD 3; ADD 1; SWAP 3; NAND 2; ADD 2` |
| champ512_s1 | `0xb7377755` | 1.5% | 0.24 | 16 | 0.00 | 512 | 32.0 | `ADD 1; ADD 1; ADD 3; ADD 3; ADD 3; SWAP 3; ADD 3; NAND 3` |

| run | top-3 share | top-N share | distinct phenotypes in top-N | largest phenotype share | cells in state 15 | mean age |
|---|---:|---:|---:|---:|---:|---:|
| champ_s1 | 24.5% | 56.1% | 31 | 21.7% | 7.0% | 229 |
| champ_s2 | 9.0% | 52.6% | 22 | 15.3% | 5.6% | 236 |
| champ_s3 | 15.2% | 58.0% | 28 | 19.3% | 7.0% | 232 |
| swap_s1 | 2.1% | 20.5% | 6 | 14.7% | 4.7% | 202 |
| swap_s2 | 0.7% | 17.5% | 2 | 10.5% | 4.5% | 204 |
| swap_s3 | 6.2% | 20.6% | 15 | 13.1% | 4.4% | 208 |
| swap_mu32 | 0.1% | 2.4% | 2 | 2.0% | 5.3% | 260 |
| swap_mu512 | 0.8% | 9.3% | 20 | 2.5% | 5.0% | 190 |
| swap_rc64 | 0.8% | 15.1% | 4 | 8.9% | 5.4% | 244 |
| jc_s1 | 22.9% | 50.5% | 41 | 23.4% | 6.6% | 233 |
| jc_s2 | 21.2% | 48.3% | 42 | 19.4% | 7.6% | 227 |
| champ512_s1 | 33.2% | 47.6% | 32 | 32.2% | 6.8% | 224 |

![final grids](final_montage.png)

Per-run full-resolution renders: `<run>/final.png` (hue = hash of genome, dark = empty, brightness = state).
Final grids (`final.bin`, 8 MB each, genome[] then meta[] as little-endian u32) stay on the coordinator and the producing nodes.

## Findings (ensemble of 2026-10-07; jc_s1 added 2026-10-08)

- **jc_s1 (SWAP,ADD,NAND,JC, the exp05 operator-count winner) behaves like a champion world.** 87 % fill, diversity 237 k -> 64 k, two genome families hold 20 % of the cells and reproduce on 44 % of inputs with neighbour-dependent outcomes for all 16 states; the dominant genome uses JC (`ADD 3; JC 2; ...`), its runner-up is the same program without the jump. 405 ticks/s on the RTX 4090 while writing a frame every 100 ticks; video `jc_s1/jc_s1_512_small.mp4`, key frames `jc_s1/keyframes.png`.
- **No extinction.** Every world filled to 80-100 % within 2,000 ticks and stayed there; the lowest live count after tick 1,000 was 29 % (champion runs, during the first turnover wave).
- **The two ISAs evolve differently.** Champion worlds (no HALT: every genome costs 16) lose diversity steadily (270 k -> 51-58 k genomes) and are dominated by a few genome families: the top three genomes hold 9-25 % of the cells and the largest phenotype 15-22 %. Swap worlds (HALT available) keep 225-240 k genomes; every abundant genome halts on all 256 inputs in 7-8 steps (cost 1), so cost is flat and the top genome holds under 1 % (2 % in swap_s3). Selection there acts on the trigger table, not on cost.
- **Neighbour-dependent strategies dominate.** In 22 of the 27 listed top genomes the outcome depends on the neighbour state for all 16 own states; the champion winners reproduce on 44-48 % of inputs. champ_s3 is the exception: three one-instruction variants of one genome (a neutral network on the first instruction) reproduce on only 5 % of inputs yet hold 15 % of the cells, which suggests a protective, rarely reproducing strategy can beat prolific ones.
- **Mutation rate sets the regime.** mu_bits=32 (one flip per copy on average) gives 99 % fill, 229 k genomes and a top genome at 0.03 %: mutation, not selection, shapes the population. mu_bits=512 gives 94 k genomes, the patchiest world (visible domains), and the lowest minimum diversity (54 k). The default 128 sits between.
- **Cheap reproduction (repro_cost=64) quadruples turnover** (45 k births per tick vs 12 k), fills the torus (99.8 %) and drives diversity down to 63 k, close to the champion worlds.
- **Mean age is 190-260 ticks**, far below max_age=1024 and below the 512-tick random-death horizon: most deaths are overwrites by a reproducing neighbour.
- **Speed.** CUDA matched the spec estimates: 400 ticks/s on the RTX 4090 and 133 on an RTX 3060 for the champion (every cell runs 256 steps); 1,100-1,150 ticks/s on an RTX 3060 for the halting swap ISA. The Vulkan engine on AMD is the outlier: swap_s3 on the RX 9070 XT ran at 115 ticks/s, ten times slower than the same workload on an RTX 3060, and the R9700 reached 200-450. The next engineering step is profiling the Vulkan kernel (workgroup size, early exit on HALT, divergence), not more GPUs.
- **Seeds matter less than parameters.** The three seeds of each ISA agree on fill, diversity and birth rate within a few per cent; the three parameter variants differ by factors of 2-4.
