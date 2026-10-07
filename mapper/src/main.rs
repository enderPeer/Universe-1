mod catalog;
mod classify;
mod machine;
mod map;
mod shard;
mod synth;

use classify::Vocab;
use machine::{table_key, Config, Machine, Scratch};
use map::FunctionMap;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

const USAGE: &str = "u1map <command> [options]

  sweep    --W w --a a --p p [--I i] --isa LD,ST,... [--binary] [--lo L --hi H] --out shard.bin [--threads t]
           enumerate programs [lo,hi) and write a shard (same format as fast/u1)
  build    --shards a.bin b.bin ... --out map.u1prog [--named named.jsonl] [--stats stats.json]
           build the function map from sweep shards (recomputes and verifies every witness)
  build    --W .. --a .. --p .. --isa .. [--lo L --hi H] --out map.u1prog [--named ..] [--stats ..]
           build the map by sweeping directly (small spaces)
  info     --map map.u1prog [--named named.jsonl] [--stats stats.json] [--closure depth]
  list     --map map.u1prog [--filter substring] [--class named|permutation|predicate|constant|other] [--limit n]
  synth    --map map.u1prog (--target NAME | --table 0,1,2,...) [--depth d] [--extra n] [--fn name] [--out file.rs]
  translate --map map.u1prog --targets file --out-dir dir [--depth d] [--extra n] [--report file.jsonl] [--unary-map u.u1prog]
           (--unary-map: for a binary map, enables unary pre/post-op composition from the same ISA's unary map)
           batch synth: each line of `file` is `name|t0,t1,...`; writes dir/<name>.rs and a JSONL report
  catalog  --map map.u1prog --out catalog.tsv [--summary summary.json] [--deep]   (unary maps)
           --deep adds ANF degree/monomials, nearest named function + distance, best affine fit
           index every function with structural descriptors, sorted by class, name, steps, program id
  vocab    --W w [--binary]            list the target vocabulary (names the classifier knows)
  run      --W .. --a .. --p .. --isa .. --program 0x..   disassemble and tabulate one program
";

fn arg(args: &[String], k: &str) -> Option<String> { args.iter().position(|a| a == k).and_then(|i| args.get(i + 1).cloned()) }
fn flag(args: &[String], k: &str) -> bool { args.iter().any(|a| a == k) }
fn argn<T: std::str::FromStr>(args: &[String], k: &str, d: T) -> T { arg(args, k).and_then(|v| v.parse().ok()).unwrap_or(d) }
fn argu64(args: &[String], k: &str) -> Option<u64> { arg(args, k).map(|v| if let Some(h) = v.strip_prefix("0x") { u64::from_str_radix(h, 16).unwrap() } else { v.parse().unwrap() }) }
fn multi(args: &[String], k: &str) -> Vec<String> {
    let mut out = Vec::new();
    if let Some(i) = args.iter().position(|a| a == k) { for a in &args[i + 1..] { if a.starts_with("--") { break; } out.push(a.clone()); } }
    out
}
fn threads(args: &[String]) -> usize { argn(args, "--threads", std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4)) }

fn cfg_from_args(args: &[String]) -> Result<Config, String> {
    let isa = Config::parse_isa(&arg(args, "--isa").ok_or("--isa required")?)?;
    Config::new(argn(args, "--W", 4), argn(args, "--a", 2), argn(args, "--p", 3), arg(args, "--I").map(|v| v.parse().unwrap()), isa, flag(args, "--binary"))
}

fn sweep(cfg: &Config, lo: u64, hi: u64, nthreads: usize) -> HashMap<(u64, u64), u32> {
    let cfg = Arc::new(cfg.clone()); let next = Arc::new(Mutex::new(lo)); let chunk = 1u64 << 14;
    let th: Vec<_> = (0..nthreads).map(|_| { let (cfg, next) = (cfg.clone(), next.clone()); std::thread::spawn(move || {
        let m = Machine::new(&cfg); let mut sc = Scratch::new(&cfg); let mut set: HashMap<(u64, u64), u32> = HashMap::new();
        loop {
            let start = { let mut n = next.lock().unwrap(); let s = *n; if s >= hi { break; } *n = (s + chunk).min(hi); s };
            for pb in start..(start + chunk).min(hi) {
                let (t, _, _) = m.table(&mut sc, pb); let k = table_key(&t, cfg.w);
                let e = set.entry(k).or_insert(pb as u32); if (pb as u32) < *e { *e = pb as u32; }
            }
        }
        set }) }).collect();
    let mut all: HashMap<(u64, u64), u32> = HashMap::new();
    for t in th { for (k, p) in t.join().unwrap() { let e = all.entry(k).or_insert(p); if p < *e { *e = p; } } }
    all
}

fn range(args: &[String], cfg: &Config) -> (u64, u64) {
    let total = if cfg.program_bits() >= 64 { u64::MAX } else { 1u64 << cfg.program_bits() };
    (argu64(args, "--lo").unwrap_or(0), argu64(args, "--hi").unwrap_or(total))
}

fn finish_map(args: &[String], fm: &FunctionMap) -> Result<(), String> {
    let vocab = Vocab::new(fm.cfg.w, fm.cfg.binary);
    if let Some(o) = arg(args, "--out") { fm.save_programs(&o)?; eprintln!("wrote {} ({} operators)", o, fm.entries.len()); }
    if let Some(n) = arg(args, "--named") { let c = fm.write_named_jsonl(&vocab, &n)?; eprintln!("wrote {} ({} named operators)", n, c); }
    let stats = fm.stats(&vocab);
    if let Some(s) = arg(args, "--stats") { std::fs::write(&s, format!("{}\n", stats)).map_err(|e| e.to_string())?; }
    println!("{}", stats);
    Ok(())
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let Err(e) = run(&args) { eprintln!("error: {}", e); std::process::exit(1); }
}

fn run(args: &[String]) -> Result<(), String> {
    let cmd = args.first().cloned().unwrap_or_default();
    match cmd.as_str() {
        "sweep" => {
            let cfg = cfg_from_args(args)?; let (lo, hi) = range(args, &cfg); let t0 = std::time::Instant::now();
            let set = sweep(&cfg, lo, hi, threads(args));
            let out = arg(args, "--out").ok_or("--out required")?; shard::write(&out, &cfg, lo, hi, &set)?;
            let secs = t0.elapsed().as_secs_f64();
            eprintln!("W={} a={} p={} I={} o={} isa={} {} programs=[{},{}) distinct={} {:.1}s ({:.2} Mprog/s)", cfg.w, cfg.a, cfg.p, cfg.i, cfg.o, cfg.isa_string(), if cfg.binary { "binary" } else { "unary" }, lo, hi, set.len(), secs, (hi - lo) as f64 / secs / 1e6);
            println!("{}", set.len()); Ok(())
        }
        "build" => {
            let sh = multi(args, "--shards");
            let fm = if !sh.is_empty() {
                let (fm, bad) = FunctionMap::from_shards(&sh, threads(args))?;
                if bad > 0 { return Err(format!("{} witnesses did not reproduce their shard key", bad)); }
                eprintln!("{} shards, {} witnesses verified", sh.len(), fm.entries.len()); fm
            } else {
                let cfg = cfg_from_args(args)?; let (lo, hi) = range(args, &cfg);
                let set = sweep(&cfg, lo, hi, threads(args)); FunctionMap::from_programs(cfg, set.values().map(|&p| p as u64).collect(), threads(args))
            };
            finish_map(args, &fm)
        }
        "info" => {
            let fm = FunctionMap::load_programs(&arg(args, "--map").ok_or("--map required")?, threads(args))?;
            let a2: Vec<String> = args.iter().filter(|a| *a != "--out").cloned().collect(); finish_map(&a2, &fm)?;
            if let Some(d) = arg(args, "--closure") {
                let vocab = Vocab::new(fm.cfg.w, fm.cfg.binary);
                let c = synth::closure_count(&fm, &vocab, d.parse().unwrap(), argn(args, "--extra", 0));
                println!("closure under composition (operators reachable with 1..{} stages): {:?}", d, c);
            }
            Ok(())
        }
        "list" => {
            let fm = FunctionMap::load_programs(&arg(args, "--map").ok_or("--map required")?, threads(args))?;
            let vocab = Vocab::new(fm.cfg.w, fm.cfg.binary); let filt = arg(args, "--filter"); let cls = arg(args, "--class"); let limit: usize = argn(args, "--limit", 100);
            let mut rows: Vec<_> = fm.entries.iter().filter(|e| { let n = vocab.name(&e.table); cls.as_deref().map_or(true, |c| vocab.class(&e.table) == c) && filt.as_deref().map_or(true, |f| n.map_or(false, |n| n.contains(f))) }).collect();
            rows.sort_by_key(|e| (vocab.name(&e.table).is_none(), e.steps, e.program));
            for e in rows.iter().take(limit) {
                println!("{:<24} steps={:<3} halts={:<5} prog=0x{:x}  {}  table={:?}", vocab.name(&e.table).map(|s| s.as_str()).unwrap_or("-"), e.steps, e.halts, e.program, fm.cfg.disassemble(e.program).join(" ; "), e.table);
            }
            eprintln!("{} matching, {} shown", rows.len(), rows.len().min(limit)); Ok(())
        }
        "synth" => {
            let fm = FunctionMap::load_programs(&arg(args, "--map").ok_or("--map required")?, threads(args))?;
            let vocab = Vocab::new(fm.cfg.w, fm.cfg.binary);
            let (target, tname) = if let Some(n) = arg(args, "--target") { (vocab.table(&n).ok_or(format!("unknown target '{}' (see `u1map vocab --W {}`)", n, fm.cfg.w))?.clone(), n) }
                else if let Some(t) = arg(args, "--table") { let tb: Vec<u8> = t.split(',').map(|v| v.trim().parse().unwrap()).collect(); if tb.len() != fm.cfg.ntab() { return Err(format!("table needs {} entries", fm.cfg.ntab())); } (tb.clone(), vocab.name(&tb).cloned().unwrap_or("custom".into())) }
                else { return Err("--target or --table required".into()) };
            let plan = synth::synthesize(&fm, &vocab, &target, argn(args, "--depth", 3), argn(args, "--extra", 64)).ok_or("not synthesizable from this map within the search depth")?;
            println!("target {}: {} stage(s): {}", tname, plan.stages.len(), plan.stage_names.join(" -> "));
            for (k, e) in plan.stages.iter().enumerate() { println!("  stage {} program 0x{:x} steps<={} halts={}", k, e.program, e.steps, e.halts); for l in fm.cfg.disassemble(e.program) { println!("      {}", l); } }
            let fname = arg(args, "--fn").unwrap_or_else(|| sanitize(&tname));
            let src = synth::emit_rust(&fm.cfg, &plan, &fname, &tname);
            if let Some(o) = arg(args, "--out") { std::fs::write(&o, &src).map_err(|e| e.to_string())?; println!("wrote {}", o); } else { println!("{}", src); }
            Ok(())
        }
        "translate" => {
            let fm = FunctionMap::load_programs(&arg(args, "--map").ok_or("--map required")?, threads(args))?;
            // Refresh names/stats from this already loaded map, avoiding a second
            // full witness replay via a separate `info` invocation.
            if arg(args, "--named").is_some() || arg(args, "--stats").is_some() {
                finish_map(args, &fm)?;
            }
            let vocab = Vocab::new(fm.cfg.w, fm.cfg.binary);
            let targets = std::fs::read_to_string(arg(args, "--targets").ok_or("--targets required")?).map_err(|e| e.to_string())?;
            let dir = arg(args, "--out-dir").ok_or("--out-dir required")?; std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            let (depth, extra): (usize, usize) = (argn(args, "--depth", 3), argn(args, "--extra", 64));
            let t0 = std::time::Instant::now(); let sy = synth::Synth::new(&fm, &vocab, depth, extra);
            let um = match arg(args, "--unary-map") { Some(p) if fm.cfg.binary => Some(FunctionMap::load_programs(&p, threads(args))?), _ => None };
            let uv = um.as_ref().map(|u| Vocab::new(u.cfg.w, false));
            let sb = um.as_ref().map(|u| synth::SynthBinary::new(&fm, u, &vocab, uv.as_ref().unwrap(), extra));
            eprintln!("composition prefixes per level: {:?} ({:.1}s){}", sy.prefix_counts(), t0.elapsed().as_secs_f64(), if sb.is_some() { "; binary composition with unary map enabled" } else { "" });
            let mut report = String::new(); let (mut ok, mut total) = (0, 0);
            for line in targets.lines().filter(|l| !l.trim().is_empty() && !l.starts_with('#')) {
                let (name, tb) = line.split_once('|').ok_or(format!("bad target line: {}", line))?;
                let tb: Vec<u8> = tb.split(',').map(|v| v.trim().parse().map_err(|_| format!("bad table in {}", name))).collect::<Result<_, _>>()?;
                if tb.len() != fm.cfg.ntab() { return Err(format!("{}: table needs {} entries", name, fm.cfg.ntab())); }
                total += 1;
                match sb.as_ref().map_or_else(|| sy.synthesize(&tb), |b| b.synthesize(&tb)) {
                    Some(plan) => {
                        ok += 1; let fname = sanitize(name);
                        std::fs::write(format!("{}/{}.rs", dir, fname), synth::emit_rust(&fm.cfg, &plan, &fname, name)).map_err(|e| e.to_string())?;
                        report += &format!("{{\"name\":{},\"ok\":true,\"stages\":{},\"stage_names\":[{}],\"programs\":[{}],\"max_steps\":{},\"halts\":{},\"file\":\"{}/{}.rs\"}}\n",
                            map::json_str(name), plan.stages.len(), plan.stage_names.iter().map(|n| map::json_str(n)).collect::<Vec<_>>().join(","),
                            plan.stages.iter().map(|e| format!("\"0x{:x}\"", e.program)).collect::<Vec<_>>().join(","),
                            plan.stages.iter().map(|e| e.steps).sum::<usize>(), plan.stages.iter().all(|e| e.halts), dir, fname);
                        println!("{:<20} {} stage(s): {}", name, plan.stages.len(), plan.stage_names.join(" -> "));
                    }
                    None => { report += &format!("{{\"name\":{},\"ok\":false}}\n", map::json_str(name)); println!("{:<20} NOT SYNTHESIZABLE (depth {})", name, depth); }
                }
            }
            if let Some(r) = arg(args, "--report") { std::fs::write(&r, &report).map_err(|e| e.to_string())?; }
            eprintln!("{}/{} targets translated from {}", ok, total, fm.cfg.isa_string()); Ok(())
        }
        "catalog" => {
            let fm = FunctionMap::load_programs(&arg(args, "--map").ok_or("--map required")?, threads(args))?;
            if fm.cfg.binary { return Err("catalog supports unary maps (binary: use the cluster job in docs/07_catalog.md)".into()); }
            let vocab = Vocab::new(fm.cfg.w, false); let w = fm.cfg.w;
            let t0 = std::time::Instant::now();
            let mut rows: Vec<(u8, String, usize, u64, usize, catalog::Desc)> = fm.entries.iter().enumerate().map(|(i, e)| { let d = catalog::describe_unary(&e.table, w, &vocab); (catalog::class_rank(&d), d.name.clone(), e.steps, e.program, i, d) }).collect();
            rows.sort_by(|a, b| (a.0, &a.1, a.2, a.3).cmp(&(b.0, &b.1, b.2, b.3)));
            let out = arg(args, "--out").ok_or("--out required")?; let deep = flag(args, "--deep") && w == 4;
            // deep: nearest named vocabulary table (packed) for Hamming search, computed in parallel
            let vocab_packed: Vec<(u64, &String)> = vocab.by_table.iter().map(|(t, n)| (catalog::pack16(t), n)).collect();
            let deep_rows: Vec<String> = if deep {
                let entries: Vec<(usize, Vec<u8>)> = rows.iter().map(|r| (r.4, fm.entries[r.4].table.clone())).collect();
                let nthr = threads(args).max(1); let chunks: Vec<Vec<(usize, Vec<u8>)>> = (0..nthr).map(|t| entries.iter().skip(t).step_by(nthr).cloned().collect()).collect();
                let vp = std::sync::Arc::new(vocab_packed.iter().map(|(p, n)| (*p, (*n).clone())).collect::<Vec<(u64, String)>>());
                let results: Vec<Vec<(usize, String)>> = std::thread::scope(|sc| {
                    let hs: Vec<_> = chunks.iter().map(|ch| { let vp = vp.clone(); sc.spawn(move || ch.iter().map(|(i, t)| {
                        let (deg, mono, degs) = catalog::anf(t, 4); let p = catalog::pack16(t);
                        let mut best = (99u32, ""); for (q, n) in vp.iter() { let d = catalog::nibble_dist(p, *q); if d < best.0 { best = (d, n.as_str()); if d == 0 { break; } } }
                        let (err, a, b) = catalog::affine_fit(t, 4);
                        (*i, format!("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}", deg, mono, degs.iter().map(|d| d.to_string()).collect::<Vec<_>>().join(""), best.1, best.0, err, a, b))
                    }).collect::<Vec<_>>()) }).collect();
                    hs.into_iter().map(|h| h.join().unwrap()).collect()
                });
                let mut by_entry = vec![String::new(); fm.entries.len()]; for v in results { for (i, s) in v { by_entry[i] = s; } }
                rows.iter().map(|r| by_entry[r.4].clone()).collect()
            } else { Vec::new() };
            let mut f = std::io::BufWriter::new(std::fs::File::create(&out).map_err(|e| e.to_string())?);
            use std::io::Write; writeln!(f, "{}{}", catalog::header(), if deep { "\tanf_degree\tanf_monomials\tanf_degree_per_bit\tnearest_named\tnearest_dist\taffine_fit_errors\tfit_a\tfit_b" } else { "" }).map_err(|e| e.to_string())?;
            let mut counts: std::collections::BTreeMap<String, usize> = std::collections::BTreeMap::new();
            let (mut bij, mut inv, mut idem, mut xa, mut mono, mut full_dep) = (0, 0, 0, 0, 0, 0); let mut img_hist = vec![0usize; (1 << w) + 1]; let mut dep_hist = vec![0usize; 1 << w];
            for (k, (_, _, _, _, i, d)) in rows.iter().enumerate() {
                let e = &fm.entries[*i]; writeln!(f, "{}{}", catalog::row(k, e, d, w), if deep { format!("\t{}", deep_rows[k]) } else { String::new() }).map_err(|e| e.to_string())?;
                *counts.entry(catalog::class_name(catalog::class_rank(d)).to_string()).or_default() += 1;
                bij += d.bijective as usize; inv += d.involution as usize; idem += d.idempotent as usize; xa += d.xor_affine as usize; mono += d.monotone as usize; full_dep += (d.depends_mask == (1 << w) - 1) as usize;
                img_hist[d.image] += 1; dep_hist[d.depends_mask as usize] += 1;
            }
            let summary = format!("{{\"isa\":\"{}\",\"functions\":{},\"classes\":{{{}}},\"bijective\":{},\"involutions\":{},\"idempotent\":{},\"xor_affine\":{},\"monotone\":{},\"depend_on_all_bits\":{},\"image_size_histogram\":{:?},\"depends_mask_histogram\":{:?},\"seconds\":{:.1}}}",
                fm.cfg.isa_string(), rows.len(), counts.iter().map(|(k, v)| format!("\"{}\":{}", k, v)).collect::<Vec<_>>().join(","), bij, inv, idem, xa, mono, full_dep, img_hist, dep_hist, t0.elapsed().as_secs_f64());
            if let Some(sp) = arg(args, "--summary") { std::fs::write(&sp, format!("{}\n", summary)).map_err(|e| e.to_string())?; }
            println!("{}", summary); eprintln!("wrote {} ({} rows)", out, rows.len()); Ok(())
        }
        "vocab" => { let v = Vocab::new(argn(args, "--W", 4), flag(args, "--binary")); let mut names: Vec<_> = v.by_name.keys().collect(); names.sort(); for n in names { println!("{}", n); } eprintln!("{} names", v.by_name.len()); Ok(()) }
        "run" => {
            let cfg = cfg_from_args(args)?; let pb = argu64(args, "--program").ok_or("--program required")?;
            let m = Machine::new(&cfg); let mut sc = Scratch::new(&cfg); let (t, steps, halts) = m.table(&mut sc, pb);
            for l in cfg.disassemble(pb) { println!("{}", l); }
            let vocab = Vocab::new(cfg.w, cfg.binary);
            println!("table={:?} max_steps={} all_halt={} name={}", t, steps, halts, vocab.name(&t).map(|s| s.as_str()).unwrap_or("-")); Ok(())
        }
        _ => { eprint!("{}", USAGE); Err("unknown command".into()) }
    }
}

fn sanitize(n: &str) -> String {
    let s: String = n.chars().map(|c| if c.is_ascii_alphanumeric() { c } else { '_' }).collect();
    let s = s.trim_matches('_').to_string(); if s.is_empty() || s.chars().next().unwrap().is_ascii_digit() { format!("op_{}", s) } else { s }
}
