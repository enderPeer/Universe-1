# Overnight plan 2026-10-08 -> 2026-10-09 (check this when you are back)

**Outcome (2026-10-09 morning):** 17 of 19 runs ended `exit 0` between 05:00 and 06:58 Berlin, the adler40 CPU world and the
2048^2 swap world on falke64 by about 10:30; nothing went extinct. Results and the reading: `results/life/OVERNIGHT_RESULTS.md`,
per-run rows in `results/life/ANALYSIS.md`. exp06c (3 intact 5-byte self-copiers) and the exp09 binary maps committed themselves.

Launched 19:11 Berlin by `cluster/overnight.py` from `cluster/overnight_plan.conf`. Every node runs `results/life/overnight.sh`
on its own (nohup, survives the workstation session); GPU chains started when the node's 5-byte crawler share ended, CPU worlds
started at once at nice 19. Progress per node: `results/life/overnight_status.txt` (start/end lines) and each run's `run.log`.

## What is running and when it should end (Berlin time, from measured speeds; +-20 %)

| node | slot | run | world | question it answers | expected end |
|---|---|---|---|---|---|
| adler40 | RTX 4090 | jc_4096_s1 | JC ISA, 4096^2 cells, 1,000,000 ticks, frame every 2,000 | the largest and longest world so far: does the JC world keep losing diversity, do domains reach the size of the torus, what succeeds the two dominant families | ~06:30 |
| adler40 | RTX 4080 | champ512_2048_s1 | champion, 512-step clock, income 36, 2048^2, 1,800,000 ticks | long-run behaviour of the extended clock (the 200k-tick run showed the strongest dominance of any world) | ~05:40 |
| adler40 | CPU x18 | cpu_jc_512_s1 | JC, 512^2, 2,500,000 ticks | a small world over many more generations than any GPU world | ~05:30 |
| knecht24 | RTX 3060 #0 | jc_long_s1 | JC, 1024^2, 4,500,000 ticks | 22x longer than phase B: late succession | ~05:40 |
| knecht24 | RTX 3060 #1 | jc_long_s2 | same, seed 2 | seed dependence over the long run | ~05:40 |
| knecht24 | RTX 3060 #2 | jc_s3, then jc_long_mu512 | phase B's missing third JC seed (200k), then JC with mu_bits 512 for 4,000,000 ticks | completes Life phase B for JC; low mutation on the long run | ~05:10 |
| knecht24 | CPU x16 | cpu_champ512_512_s1 | champion 512-step clock, 512^2, 1,000,000 ticks | small-world control for the 512-step clock | ~05:00 |
| falke64 | R9700 #0 | shrmul_s1, then swap_2048_s1 | Codex's SHR/MUL ISA (phase B), then swap ISA at 2048^2 for 3,000,000 ticks | phase B; a halting ISA on a 4x bigger torus for very long | ~06:50 |
| falke64 | R9700 #1 | shrmul_s2, then swap_long_rc64, then shrmul_long_s1 | phase B; swap with cheap reproduction 6,000,000 ticks; SHR/MUL ISA 6,000,000 ticks | phase B; the two halting ISAs over the longest clocks | ~05:30 |
| falke64 | CPU x8 | cpu_swap_512_s1 | swap ISA, 512^2, 2,500,000 ticks | CPU control | ~06:00 |
| specht32 | RX 9070 XT | shrmul_s3, then swap_long_s2 | phase B; swap seed 2, 4,000,000 ticks | phase B complete (jc_s3, shrmul_s1-3); long swap world | ~05:50 |
| specht32 | RX 9060 XT | swap_long_s3 | swap seed 3, 4,000,000 ticks | seed dependence of the swap world over the long run | ~05:00 |
| specht32 | CPU x8 | cpu_jc_512_mu32 | JC, 512^2, mu_bits 32, 1,000,000 ticks | high mutation on the long run, small world | ~06:00 |

Also finishing by themselves tonight, each committed and pushed automatically when done:
- exp06c, the 5-byte crawler sweep (2^40 programs; copiers with intact code?) -> `results/exp06b/l2c_crawl_w5_a5.json` + figure.
- exp09 binary, the last per-step maps of the champion -> `results/exp09_binary_summary.md` (named binary functions over the clock).

## Morning checklist

1. Status of every run: `for n in adler40 knecht24 falke64 specht32; do ssh $n 'cat universe-1/results/life/overnight_status.txt; tail -1 universe-1/results/life/*/run.log'; done`
   (an `end <run> exit 0` line per run; `extinct at tick` in a run.log is a result, not a failure).
2. Pull results to the workstation: stats.csv, run.log, final.bin, final.ppm per run (`scp`), frames as one tar stream per run
   (`ssh node 'cd universe-1/results/life/<run> && tar cf - t*.ppm' | tar xf - -C results/life/<run>`), then add the runs to
   `results/life/status.json` and run `python cluster/analyze_life.py` (reads cluster/life_runs.conf; add the overnight lines or
   point it at overnight_plan.conf).
3. Videos: `python cluster/showcase_video.py results/life/<run> <ppm-every>` per run (4096^2 frames are 50 MB each; the 4090 run
   has 500 of them, 25 GB; use `--grid 704` as is, the composer downsamples).
4. Read the two automatic results (exp06c, exp09 binary) in the repo; if the 5-byte sweep found an intact copier, its program and
   space-time diagram are in the figure.
5. Disk: the frames stay on the nodes (adler40 ~30 GB, knecht24 ~14 GB, others small); delete after the videos are made.

## If something went wrong

- A chain that never started: the node's sweep driver was still running (`pgrep -f exp06b_node.py`); the chain starts by itself when it ends.
- A run that died: its `run.log` has the error; relaunch by hand with the options in `cluster/overnight_plan.conf`.
- The 4090 world (1,000,000 ticks at 4096^2) is the only run that could overrun 08:00 if the measured 25 ticks/s does not hold at that size; it can be stopped (`pkill -f jc_4096_s1`) and still has its stats and frames up to that point; final.bin is only written at the end.
