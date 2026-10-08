# Experiment 05 (unary) completed

Completed at 2026-10-07 17:22:12Z (UTC); witness validation and packaging finished 17:44Z.

- 14 unary sweeps of the exp05 candidate ISAs completed on all nine GPUs; the binary sweeps have not been run yet.
- Every sweep covers all 4,294,967,296 programs without gaps or overlaps.
- Total program enumerations: 60,129,542,144 in 652 s of dispatcher wall time (10.9 min).
- 2,680 sampled witnesses passed the independent Python reference check (validation/exp05-witnesses.log).
- Witness shards are packaged in 163 verified archives (1.21 GiB) under results/witnesses, manifest entries tagged `"experiment": "exp05"`.
- Highest operator count: w4_o2_add_jc (SWAP,ADD,NAND,JC) with 8,533,818, 4.7x the exp03 champion.
- See exp05_summary.md and exp05_validation.md.
