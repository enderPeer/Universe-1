//! Universe-1 Life, CPU reference implementation of docs/06_life_spec.md.
mod machine;
use machine::{mix, Config, Machine, Scratch};
use std::io::Write;
use std::sync::{Arc, Mutex};

#[derive(Clone, Debug)]
pub struct Params { pub n: usize, pub seed: u64, pub density: f64, pub start_energy: u32, pub income: u32, pub trigger: u32,
    pub repro_cost: u32, pub max_energy: u32, pub mu_bits: u64, pub max_age: u32, pub death_rate: u64, pub ticks: u64, pub report_every: u64 }
impl Default for Params { fn default() -> Params { Params { n: 256, seed: 1, density: 0.05, start_energy: 64, income: 20, trigger: 15,
    repro_cost: 128, max_energy: 255, mu_bits: 128, max_age: 1024, death_rate: 512, ticks: 10000, report_every: 100 } } }

#[inline] pub fn h(seed: u64, tick: u64, cell: u64, k: u64) -> u64 {
    mix(seed ^ mix(tick.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(cell)) ^ k.wrapping_mul(0xD1B54A32D192ED03))
}
#[inline] fn st(m: u32) -> u32 { m & 15 }
#[inline] fn alive(m: u32) -> bool { (m >> 4) & 1 == 1 }
#[inline] fn age(m: u32) -> u32 { (m >> 5) & 2047 }
#[inline] fn energy(m: u32) -> u32 { m >> 16 }
#[inline] fn pack(state: u32, alive: bool, age: u32, energy: u32) -> u32 { (state & 15) | ((alive as u32) << 4) | (age.min(2047) << 5) | (energy.min(65535) << 16) }
const DX: [i64; 4] = [0, 1, 0, -1]; const DY: [i64; 4] = [-1, 0, 1, 0];

pub struct World { pub p: Params, pub cfg: Config, pub genome: Vec<u32>, pub meta: Vec<u32>, pub tick: u64, pub births: u64, pub deaths: u64 }

impl World {
    pub fn new(p: Params, cfg: Config) -> World {
        let nn = p.n * p.n; let mut genome = vec![0u32; nn]; let mut meta = vec![0u32; nn];
        let thr = (p.density * 4294967296.0) as u64;
        for c in 0..nn as u64 {
            if (h(p.seed, 0, c, 0) >> 32) < thr {
                genome[c as usize] = h(p.seed, 0, c, 1) as u32;
                meta[c as usize] = pack((h(p.seed, 0, c, 2) & 15) as u32, true, 0, p.start_energy);
            }
        }
        World { p, cfg, genome, meta, tick: 0, births: 0, deaths: 0 }
    }
    fn idx(&self, x: i64, y: i64) -> usize { let n = self.p.n as i64; ((y.rem_euclid(n)) * n + x.rem_euclid(n)) as usize }

    pub fn step(&mut self, threads: usize) {
        let n = self.p.n; let nn = n * n; let t = self.tick; let d = (t % 4) as usize;
        // phase 1: new_state (u8) and cost (u8) and energy_after (u16) per cell, packed as u32
        let cfg = Arc::new(self.cfg.clone()); let genome = Arc::new(std::mem::take(&mut self.genome)); let meta = Arc::new(std::mem::take(&mut self.meta));
        let p1 = Arc::new(Mutex::new(vec![0u32; nn])); let p = self.p.clone();
        let th: Vec<_> = (0..threads.max(1)).map(|ti| { let (cfg, genome, meta, p1, p) = (cfg.clone(), genome.clone(), meta.clone(), p1.clone(), p.clone()); std::thread::spawn(move || {
            let m = Machine::new(&cfg); let mut sc = Scratch::new(&cfg); let mut local = Vec::new();
            for c in (ti..nn).step_by(threads.max(1)) {
                let me = meta[c]; if !alive(me) { continue; }
                let (x, y) = ((c % n) as i64, (c / n) as i64); let nb = ((y + DY[d]).rem_euclid(n as i64) as usize) * n + (x + DX[d]).rem_euclid(n as i64) as usize;
                let nbs = if alive(meta[nb]) { st(meta[nb]) } else { 0 };
                let r = m.run(&mut sc, genome[c] as u64, st(me), Some(nbs));
                let cost = ((r.steps + 15) / 16) as u32;
                let ea = (energy(me) + p.income).min(p.max_energy).saturating_sub(cost);
                local.push((c, (r.a & 15) | (cost << 4) | (ea << 16)));
            }
            let mut g = p1.lock().unwrap(); for (c, v) in local { g[c] = v; }
        }) }).collect();
        for t in th { t.join().unwrap(); }
        let p1 = Arc::try_unwrap(p1).unwrap().into_inner().unwrap();
        let genome = Arc::try_unwrap(genome).unwrap(); let meta = Arc::try_unwrap(meta).unwrap();
        let ns = |c: usize| p1[c] & 15; let ea = |c: usize| p1[c] >> 16;
        let qualifies = |c: usize| alive(meta[c]) && ns(c) == p.trigger && ea(c) >= p.repro_cost;
        let colonised_by = |child: usize, parent: usize| qualifies(parent) && !(alive(meta[child]) && ns(child) == p.trigger && ea(child) >= ea(parent));
        // phase 2
        let mut ng = vec![0u32; nn]; let mut nm = vec![0u32; nn]; let (mut births, mut deaths) = (0u64, 0u64);
        for c in 0..nn {
            let (x, y) = ((c % n) as i64, (c / n) as i64);
            let parent = self.idx(x - DX[d], y - DY[d]); let child = self.idx(x + DX[d], y + DY[d]);
            if colonised_by(c, parent) {
                let mut g = genome[parent];
                for k in 0..32u64 { if h(p.seed, t, c as u64, 16 + k) % p.mu_bits == 0 { g ^= 1 << k; } }
                ng[c] = g; nm[c] = pack(0, true, 0, p.start_energy); births += 1; if alive(meta[c]) { deaths += 1; }
            } else if alive(meta[c]) {
                let a = age(meta[c]) + 1; let mut e = ea(c);
                if colonised_by(child, c) { e -= p.repro_cost; }
                if e == 0 || a > p.max_age || h(p.seed, t, c as u64, 8) % p.death_rate == 0 { deaths += 1; continue; }
                ng[c] = genome[c]; nm[c] = pack(ns(c), true, a, e);
            }
        }
        self.genome = ng; self.meta = nm; self.tick += 1; self.births += births; self.deaths += deaths;
    }

    pub fn stats(&self, threads: usize) -> (usize, usize, f64, f64, f64) {
        let live: Vec<usize> = (0..self.genome.len()).filter(|&c| alive(self.meta[c])).collect();
        let mut gs: Vec<u32> = live.iter().map(|&c| self.genome[c]).collect(); gs.sort_unstable(); gs.dedup();
        let me: f64 = if live.is_empty() { 0.0 } else { live.iter().map(|&c| energy(self.meta[c]) as f64).sum::<f64>() / live.len() as f64 };
        // cost / halting over distinct genomes with x=state, y=0..15 is expensive; use x=current state, y=0 as a proxy per distinct genome
        let cfg = Arc::new(self.cfg.clone()); let gs = Arc::new(gs); let acc = Arc::new(Mutex::new((0u64, 0u64)));
        let th: Vec<_> = (0..threads.max(1)).map(|ti| { let (cfg, gs, acc) = (cfg.clone(), gs.clone(), acc.clone()); std::thread::spawn(move || {
            let m = Machine::new(&cfg); let mut sc = Scratch::new(&cfg); let (mut cs, mut hs) = (0u64, 0u64);
            for g in gs.iter().skip(ti).step_by(threads.max(1)) { let (_, steps, halts) = m.table(&mut sc, *g as u64); cs += steps as u64; hs += halts as u64; }
            let mut a = acc.lock().unwrap(); a.0 += cs; a.1 += hs; }) }).collect();
        for t in th { t.join().unwrap(); }
        let (cs, hs) = *acc.lock().unwrap(); let ng = gs.len().max(1) as f64;
        (live.len(), gs.len(), me, cs as f64 / ng, hs as f64 / ng)
    }

    pub fn write_ppm(&self, path: &str) -> std::io::Result<()> {
        let n = self.p.n; let mut f = std::io::BufWriter::new(std::fs::File::create(path)?);
        write!(f, "P6\n{} {}\n255\n", n, n)?;
        let mut buf = Vec::with_capacity(n * n * 3);
        for c in 0..n * n {
            if !alive(self.meta[c]) { buf.extend_from_slice(&[0, 0, 0]); continue; }
            let hsh = mix(self.genome[c] as u64); let b = 96 + (st(self.meta[c]) * 10) as u64;
            buf.push(((hsh & 255) * b / 255) as u8); buf.push((((hsh >> 8) & 255) * b / 255) as u8); buf.push((((hsh >> 16) & 255) * b / 255) as u8);
        }
        f.write_all(&buf)
    }
    pub fn dump(&self, path: &str) -> std::io::Result<()> {
        let mut out = Vec::with_capacity(self.genome.len() * 8);
        for g in &self.genome { out.extend_from_slice(&g.to_le_bytes()); } for m in &self.meta { out.extend_from_slice(&m.to_le_bytes()); }
        std::fs::write(path, out)
    }
    pub fn load(&mut self, path: &str) -> std::io::Result<()> {
        let b = std::fs::read(path)?; let nn = self.genome.len(); assert_eq!(b.len(), nn * 8, "dump size mismatch");
        for c in 0..nn { self.genome[c] = u32::from_le_bytes(b[c * 4..c * 4 + 4].try_into().unwrap()); self.meta[c] = u32::from_le_bytes(b[nn * 4 + c * 4..nn * 4 + c * 4 + 4].try_into().unwrap()); }
        Ok(())
    }
}

fn arg(args: &[String], k: &str) -> Option<String> { args.iter().position(|a| a == k).and_then(|i| args.get(i + 1).cloned()) }
fn argn<T: std::str::FromStr>(args: &[String], k: &str, d: T) -> T { arg(args, k).and_then(|v| v.parse().ok()).unwrap_or(d) }

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help") || args.is_empty() {
        eprintln!("u1life [--N 256] [--seed 1] [--density 0.05] [--ticks 10000] [--report-every 100] [--isa SWAP,ADD,NAND,SKZ --a 2 --p 3 --I 4]\n       [--income 8] [--trigger 15] [--repro-cost 32] [--max-energy 255] [--mu-bits 32] [--max-age 1024] [--death-rate 512] [--start-energy 64]\n       [--out-dir dir] [--ppm-every 0] [--dump-final] [--load dump.bin] [--threads t]"); std::process::exit(2);
    }
    let mut p = Params::default();
    p.n = argn(&args, "--N", p.n); p.seed = argn(&args, "--seed", p.seed); p.density = argn(&args, "--density", p.density); p.ticks = argn(&args, "--ticks", p.ticks);
    p.report_every = argn(&args, "--report-every", p.report_every); p.income = argn(&args, "--income", p.income); p.trigger = argn(&args, "--trigger", p.trigger);
    p.repro_cost = argn(&args, "--repro-cost", p.repro_cost); p.max_energy = argn(&args, "--max-energy", p.max_energy); p.mu_bits = argn(&args, "--mu-bits", p.mu_bits);
    p.max_age = argn(&args, "--max-age", p.max_age); p.death_rate = argn(&args, "--death-rate", p.death_rate); p.start_energy = argn(&args, "--start-energy", p.start_energy);
    let isa = Config::parse_isa(&arg(&args, "--isa").unwrap_or("SWAP,ADD,NAND,SKZ".into())).unwrap_or_else(|e| { eprintln!("{}", e); std::process::exit(2) });
    let cfg = Config::new(4, argn(&args, "--a", 2), argn(&args, "--p", 3), Some(argn(&args, "--I", 4)), isa, true).unwrap_or_else(|e| { eprintln!("{}", e); std::process::exit(2) });
    let threads: usize = argn(&args, "--threads", std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4));
    let out_dir = arg(&args, "--out-dir").unwrap_or(".".into()); std::fs::create_dir_all(&out_dir).unwrap();
    let ppm_every: u64 = argn(&args, "--ppm-every", 0);
    let mut w = World::new(p.clone(), cfg);
    if let Some(l) = arg(&args, "--load") { w.load(&l).unwrap(); }
    let mut csv = std::fs::File::create(format!("{}/stats.csv", out_dir)).unwrap();
    writeln!(csv, "tick,alive,distinct_genomes,mean_energy,mean_steps,halting_fraction,births,deaths").unwrap();
    let t0 = std::time::Instant::now();
    for _ in 0..p.ticks {
        if w.tick % p.report_every == 0 {
            let (a, g, me, mc, hf) = w.stats(threads);
            writeln!(csv, "{},{},{},{:.2},{:.1},{:.4},{},{}", w.tick, a, g, me, mc, hf, w.births, w.deaths).unwrap();
            eprintln!("tick {:>7} alive {:>8} genomes {:>7} energy {:>7.1} steps {:>6.1} halting {:.3} births {} deaths {} ({:.1}s)", w.tick, a, g, me, mc, hf, w.births, w.deaths, t0.elapsed().as_secs_f64());
            w.births = 0; w.deaths = 0;
            if a == 0 { eprintln!("extinct at tick {}", w.tick); break; }
        }
        if ppm_every > 0 && w.tick % ppm_every == 0 { w.write_ppm(&format!("{}/t{:08}.ppm", out_dir, w.tick)).unwrap(); }
        w.step(threads);
    }
    if args.iter().any(|a| a == "--dump-final") { w.dump(&format!("{}/final.bin", out_dir)).unwrap(); }
    w.write_ppm(&format!("{}/final.ppm", out_dir)).unwrap();
    eprintln!("done: {} ticks in {:.1}s", w.tick, t0.elapsed().as_secs_f64());
}
