//! Synthesis: find a program (or a chain of programs) realizing a target function, and emit
//! it as assembly, hex, and self-contained Rust source.
use crate::classify::{Table, Vocab};
use crate::machine::Config;
use crate::map::{Entry, FunctionMap};
use std::collections::{HashMap, HashSet};

pub struct Plan { pub target: Table, pub stages: Vec<Entry>, pub stage_names: Vec<String>, pub stage_binary: Vec<bool> }

/// Precomputed composition prefixes for one map, so that many targets can be synthesized
/// cheaply. `levels[k]` holds every function reachable by composing k+1 basis operators
/// (as table -> basis index path). Level 0 uses the full basis (named + `extra` cheapest
/// unnamed); deeper levels extend with the elementary basis (names without parentheses).
pub struct Synth<'a> { fm: &'a FunctionMap, vocab: &'a Vocab, full: Vec<&'a Entry>, levels: Vec<HashMap<Table, Vec<usize>>> }

impl<'a> Synth<'a> {
    pub fn new(fm: &'a FunctionMap, vocab: &'a Vocab, depth: usize, extra: usize) -> Synth<'a> {
        let mut cheap: Vec<&Entry> = fm.entries.iter().filter(|e| vocab.name(&e.table).is_none()).collect();
        cheap.sort_by_key(|e| (e.steps, e.program));
        let mut full: Vec<&Entry> = fm.entries.iter().filter(|e| vocab.name(&e.table).is_some()).collect();
        full.sort_by_key(|e| (e.steps, e.program)); full.extend(cheap.into_iter().take(extra));
        let mut levels: Vec<HashMap<Table, Vec<usize>>> = Vec::new();
        if !fm.cfg.binary && depth >= 2 {
            let mut l0: HashMap<Table, Vec<usize>> = HashMap::new();
            for (i, e) in full.iter().enumerate() { l0.entry(e.table.clone()).or_insert_with(|| vec![i]); }
            levels.push(l0);
            let elem: Vec<usize> = (0..full.len()).filter(|&i| vocab.name(&full[i].table).map_or(true, |n| !n.contains('('))).collect();
            for _ in 2..depth {
                let prev = levels.last().unwrap(); let mut next: HashMap<Table, Vec<usize>> = HashMap::new();
                for (t, path) in prev.iter() { for &bi in &elem {
                    let nt: Table = t.iter().map(|&v| full[bi].table[v as usize]).collect();
                    if !levels.iter().any(|l| l.contains_key(&nt)) && !next.contains_key(&nt) { let mut p = path.clone(); p.push(bi); next.insert(nt, p); }
                } }
                if next.is_empty() { break; } levels.push(next);
            }
        }
        Synth { fm, vocab, full, levels }
    }
    pub fn prefix_counts(&self) -> Vec<usize> { self.levels.iter().map(|l| l.len()).collect() }

    pub fn synthesize(&self, target: &Table) -> Option<Plan> {
        let name_of = |e: &Entry| self.vocab.name(&e.table).cloned().unwrap_or_else(|| "unnamed".into());
        if let Some(e) = self.fm.get(target) {
            return Some(Plan { target: target.clone(), stages: vec![e.clone()], stage_names: vec![name_of(e)], stage_binary: vec![self.fm.cfg.binary] });
        }
        let n = self.fm.cfg.nin();
        // target = last(prefix(x)): prefix from level k, last from the full basis
        for level in &self.levels {
            for (pt, path) in level.iter() {
                let mut need = vec![255u8; n]; let mut ok = true;
                for (x, &px) in pt.iter().enumerate() { let t = target[x]; let slot = &mut need[px as usize]; if *slot == 255 { *slot = t; } else if *slot != t { ok = false; break; } }
                if !ok { continue; }
                if let Some(last) = self.full.iter().position(|e| e.table.iter().enumerate().all(|(v, &sv)| need[v] == 255 || need[v] == sv)) {
                    let idxs: Vec<usize> = path.iter().copied().chain(std::iter::once(last)).collect();
                    let stages: Vec<Entry> = idxs.iter().map(|&i| self.full[i].clone()).collect();
                    let names = stages.iter().map(|e| name_of(e)).collect();
                    let k = stages.len(); return Some(Plan { target: target.clone(), stages, stage_names: names, stage_binary: vec![false; k] });
                }
            }
        }
        None
    }
}

/// Composition for binary targets t(x, y): stages are run in sequence with A carried over
/// and M[1] = y re-supplied to every binary stage. Forms searched, in order:
///   b(x,y)            direct witness in the binary map
///   u(b(x,y))         unary post-op (u from the unary map of the same ISA)
///   b(u(x), y)        unary pre-op on x
///   u2(b(u1(x), y))   pre-op (elementary only) and post-op
///   b2(b1(x,y), y)    two binary stages (y re-supplied), optionally with a unary post-op
pub struct SynthBinary<'a> { bin: &'a FunctionMap, un: &'a FunctionMap, vocab_b: &'a Vocab, vocab_u: &'a Vocab, bfull: Vec<&'a Entry>, ufull: Vec<&'a Entry>, uelem: Vec<usize> }

impl<'a> SynthBinary<'a> {
    pub fn new(bin: &'a FunctionMap, un: &'a FunctionMap, vocab_b: &'a Vocab, vocab_u: &'a Vocab, extra: usize) -> SynthBinary<'a> {
        let basis = |fm: &'a FunctionMap, v: &Vocab| -> Vec<&'a Entry> {
            let mut cheap: Vec<&Entry> = fm.entries.iter().filter(|e| v.name(&e.table).is_none()).collect();
            cheap.sort_by_key(|e| (e.steps, e.program));
            let mut full: Vec<&Entry> = fm.entries.iter().filter(|e| v.name(&e.table).is_some()).collect();
            full.sort_by_key(|e| (e.steps, e.program)); full.extend(cheap.into_iter().take(extra)); full
        };
        let bfull = basis(bin, vocab_b); let ufull = basis(un, vocab_u);
        let uelem = (0..ufull.len()).filter(|&i| vocab_u.name(&ufull[i].table).map_or(true, |n| !n.contains('('))).collect();
        SynthBinary { bin, un, vocab_b, vocab_u, bfull, ufull, uelem }
    }

    fn post_op(&self, inner: &Table, target: &Table) -> Option<usize> {
        let n = self.un.cfg.nin(); let mut need = vec![255u8; n];
        for (i, &v) in inner.iter().enumerate() { let t = target[i]; let slot = &mut need[v as usize]; if *slot == 255 { *slot = t; } else if *slot != t { return None; } }
        self.ufull.iter().position(|e| e.table.iter().enumerate().all(|(v, &sv)| need[v] == 255 || need[v] == sv))
    }

    pub fn synthesize(&self, target: &Table) -> Option<Plan> {
        let nb = |e: &Entry| self.vocab_b.name(&e.table).cloned().unwrap_or_else(|| "unnamed".into());
        let nu = |e: &Entry| self.vocab_u.name(&e.table).cloned().unwrap_or_else(|| "unnamed".into());
        let n = self.bin.cfg.nin();
        if let Some(e) = self.bin.get(target) { return Some(Plan { target: target.clone(), stages: vec![e.clone()], stage_names: vec![nb(e)], stage_binary: vec![true] }); }
        for b in &self.bfull {
            if let Some(u) = self.post_op(&b.table, target) {
                return Some(Plan { target: target.clone(), stages: vec![(*b).clone(), self.ufull[u].clone()], stage_names: vec![nb(b), nu(self.ufull[u])], stage_binary: vec![true, false] });
            }
        }
        let pre = |u: &Entry, b: &Entry| -> Table { (0..n).flat_map(|x| (0..n).map(move |y| (x, y))).map(|(x, y)| b.table[u.table[x] as usize * n + y]).collect() };
        for u in &self.ufull { for b in &self.bfull {
            if pre(u, b) == *target { return Some(Plan { target: target.clone(), stages: vec![(*u).clone(), (*b).clone()], stage_names: vec![nu(u), nb(b)], stage_binary: vec![false, true] }); }
        } }
        for &ui in &self.uelem { let u = self.ufull[ui]; for b in &self.bfull {
            let inner = pre(u, b);
            if let Some(u2) = self.post_op(&inner, target) {
                return Some(Plan { target: target.clone(), stages: vec![u.clone(), (*b).clone(), self.ufull[u2].clone()], stage_names: vec![nu(u), nb(b), nu(self.ufull[u2])], stage_binary: vec![false, true, false] });
            }
        } }
        // two binary stages: b2(b1(x,y), y) == t  <=>  b2[b1[x,y]*n + y] == t[x,y]
        let chain2 = |b1: &Entry, b2: &Entry| -> Table { (0..n * n).map(|i| b2.table[b1.table[i] as usize * n + i % n]).collect() };
        for b1 in &self.bfull {
            let mut need = vec![255u8; n * n]; let mut ok = true;
            for i in 0..n * n { let slot = &mut need[b1.table[i] as usize * n + i % n]; if *slot == 255 { *slot = target[i]; } else if *slot != target[i] { ok = false; break; } }
            if !ok { continue; }
            if let Some(b2) = self.bfull.iter().find(|e| e.table.iter().enumerate().all(|(v, &sv)| need[v] == 255 || need[v] == sv)) {
                return Some(Plan { target: target.clone(), stages: vec![(*b1).clone(), (*b2).clone()], stage_names: vec![nb(b1), nb(b2)], stage_binary: vec![true, true] });
            }
        }
        for b1 in &self.bfull { for b2 in &self.bfull {
            let inner = chain2(b1, b2);
            if let Some(u) = self.post_op(&inner, target) {
                return Some(Plan { target: target.clone(), stages: vec![(*b1).clone(), (*b2).clone(), self.ufull[u].clone()], stage_names: vec![nb(b1), nb(b2), nu(self.ufull[u])], stage_binary: vec![true, true, false] });
            }
        } }
        None
    }
}

/// One-shot convenience wrapper.
pub fn synthesize(fm: &FunctionMap, vocab: &Vocab, target: &Table, depth: usize, extra: usize) -> Option<Plan> {
    Synth::new(fm, vocab, depth, extra).synthesize(target)
}

/// Closure of the map under composition up to `depth` stages over the basis: how many new
/// operators chaining unlocks (usability of the ISA as a building-block set).
pub fn closure_count(fm: &FunctionMap, vocab: &Vocab, depth: usize, extra: usize) -> Vec<usize> {
    let mut basis: Vec<&Entry> = fm.entries.iter().filter(|e| vocab.name(&e.table).is_some()).collect();
    let mut cheap: Vec<&Entry> = fm.entries.iter().filter(|e| vocab.name(&e.table).is_none()).collect();
    cheap.sort_by_key(|e| e.steps); basis.extend(cheap.into_iter().take(extra));
    let mut all: HashSet<Table> = fm.entries.iter().map(|e| e.table.clone()).collect();
    let mut frontier: Vec<Table> = basis.iter().map(|e| e.table.clone()).collect();
    let mut counts = vec![all.len()];
    for _ in 1..depth {
        let mut nf = Vec::new();
        for f in &frontier { for b in &basis { let t: Table = f.iter().map(|&v| b.table[v as usize]).collect(); if all.insert(t.clone()) { nf.push(t); } } }
        counts.push(all.len()); frontier = nf; if frontier.is_empty() { break; }
    }
    counts
}

pub fn emit_rust(cfg: &Config, plan: &Plan, fn_name: &str, target_name: &str) -> String {
    let w = cfg.w; let ty = "u8"; let n = cfg.nin(); let bin = cfg.binary;
    let mut s = String::new();
    s += &format!("//! Synthesized by u1map from the Universe-1 baseline.\n//! Target: {}  (W={}, ISA {}, a={}, p={}, I={}, {})\n//! Stages: {}\n\n",
        target_name, w, cfg.isa_string(), cfg.a, cfg.p, cfg.i, if bin { "binary: x in A, y in M[1]" } else { "unary: x in A" }, plan.stage_names.join(" -> "));
    s += &format!("pub const W: u32 = {};\npub const A_BITS: u32 = {};\npub const P_BITS: u32 = {};\npub const I_BITS: u32 = {};\npub const O_BITS: u32 = {};\n", w, cfg.a, cfg.p, cfg.i, cfg.o);
    s += &format!("pub const ISA: [&str; {}] = [{}];\n", cfg.isa.len(), cfg.isa.iter().map(|p| format!("\"{}\"", p.name())).collect::<Vec<_>>().join(", "));
    s += &format!("/// Program images, one per stage; instruction k = (program >> (k*I_BITS)) & ((1<<I_BITS)-1).\npub const PROGRAMS: [u64; {}] = [{}];\n",
        plan.stages.len(), plan.stages.iter().map(|e| format!("0x{:x}", e.program)).collect::<Vec<_>>().join(", "));
    for (k, e) in plan.stages.iter().enumerate() {
        s += &format!("// stage {} ({}): {}\n", k, plan.stage_names[k], cfg.disassemble(e.program).join(" ; "));
    }
    s += &format!("\n/// The synthesized operator as a verified lookup table{}.\npub const TABLE: [{}; {}] = {:?};\n\n", if bin { format!(" (index = x * {} + y)", n) } else { String::new() }, ty, plan.target.len(), plan.target);
    if bin {
        s += &format!("#[inline]\npub fn {}(x: {}, y: {}) -> {} {{ TABLE[((x as usize) & {}) * {} + ((y as usize) & {})] }}\n\n", fn_name, ty, ty, ty, n - 1, n, n - 1);
        s += "/// Runs the program on the embedded Universe-1 machine (reference semantics).\n";
        s += &format!("/// Which stages take y in M[1] (binary) versus only A (unary post/pre-ops).\npub const STAGE_BINARY: [bool; {}] = {:?};\n", plan.stages.len(), plan.stage_binary);
        s += &format!("pub fn {}_emulated(x: {}, y: {}) -> {} {{\n    let mut v = x as u32;\n    for (k, &p) in PROGRAMS.iter().enumerate() {{ v = machine::run(p, v, if STAGE_BINARY[k] {{ Some(y as u32) }} else {{ None }}); }}\n    v as {}\n}}\n\n", fn_name, ty, ty, ty, ty);
    } else {
        s += &format!("#[inline]\npub fn {}(x: {}) -> {} {{ TABLE[(x as usize) & {}] }}\n\n", fn_name, ty, ty, n - 1);
        s += "/// Runs the stage programs on the embedded Universe-1 machine (reference semantics).\n";
        s += &format!("pub fn {}_emulated(x: {}) -> {} {{\n    let mut v = x as u32;\n    for &p in PROGRAMS.iter() {{ v = machine::run(p, v, None); }}\n    v as {}\n}}\n\n", fn_name, ty, ty, ty);
    }
    s += MACHINE_RS;
    if bin {
        s += &format!("\n#[cfg(test)]\nmod tests {{\n    use super::*;\n    #[test]\n    fn emulation_matches_table() {{\n        for x in 0..{n} {{ for y in 0..{n} {{ assert_eq!({f}_emulated(x as u8, y as u8), {f}(x as u8, y as u8), \"inputs {{}} {{}}\", x, y); }} }}\n    }}\n}}\n", n = n, f = fn_name);
    } else {
        s += &format!("\n#[cfg(test)]\nmod tests {{\n    use super::*;\n    #[test]\n    fn emulation_matches_table() {{\n        for x in 0..{} {{ assert_eq!({}_emulated(x as u8), {}(x as u8), \"input {{}}\", x); }}\n    }}\n}}\n", n, fn_name, fn_name);
    }
    s
}

const MACHINE_RS: &str = r#"pub mod machine {
    use super::*;
    const MAX_STEPS: usize = 256;
    /// Run one program image with A = x (and M[1] = y for binary operators); returns A at HALT /
    /// step 256 (periodic runs are exact: the state at step 256 is reconstructed from the cycle).
    pub fn run(program: u64, x: u32, y: Option<u32>) -> u32 {
        let mask = (1u32 << W) - 1; let amask = (1u32 << A_BITS) - 1; let pmask = (1u32 << P_BITS) - 1;
        let nins = 1usize << P_BITS; let opmask = (1u32 << (I_BITS - O_BITS)) - 1;
        let code: Vec<(&str, u32)> = (0..nins).map(|k| { let ins = ((program >> (k as u32 * I_BITS)) & ((1u64 << I_BITS) - 1)) as u32; (ISA[(ins >> (I_BITS - O_BITS)) as usize], ins & opmask) }).collect();
        let (mut a, mut z, mut c, mut pc) = (x & mask, (x & mask == 0) as u32, 0u32, 0u32);
        let mut m = vec![0u32; 1 << A_BITS];
        if let Some(y) = y { m[1] = y & mask; }
        let mut hist: Vec<Vec<u32>> = Vec::new();
        let snap = |a: u32, z: u32, c: u32, pc: u32, m: &Vec<u32>| { let mut v = vec![a, z, c, pc]; v.extend_from_slice(&m[1..]); v };
        hist.push(snap(a, z, c, pc, &m));
        for t in 0..MAX_STEPS {
            let (op, n) = code[(pc & pmask) as usize]; pc = (pc + 1) & pmask;
            let rd = |a: u32, m: &Vec<u32>, ad: u32| { let ad = ad & amask; if ad == 0 { a } else { m[ad as usize] } };
            macro_rules! wr { ($ad:expr, $v:expr) => {{ let ad = $ad & amask; let v = $v & mask; if ad == 0 { a = v } else { m[ad as usize] = v } }}; }
            macro_rules! seta { ($v:expr) => {{ a = $v & mask; z = (a == 0) as u32; }}; }
            match op {
                "NOP" => {}, "HALT" => return a,
                "LD" => seta!(rd(a, &m, n)), "ST" => wr!(n, a), "LDI" => seta!(n), "CLR" => seta!(0), "SET" => seta!(mask), "NOT" => seta!(!a),
                "AND" => seta!(a & rd(a, &m, n)), "OR" => seta!(a | rd(a, &m, n)), "XOR" => seta!(a ^ rd(a, &m, n)),
                "NAND" => seta!(!(a & rd(a, &m, n))), "NOR" => seta!(!(a | rd(a, &m, n))), "XNOR" => seta!(!(a ^ rd(a, &m, n))),
                "ADD" => { let v = a + rd(a, &m, n); seta!(v); c = (v > mask) as u32 }
                "ADC" => { let v = a + rd(a, &m, n) + c; seta!(v); c = (v > mask) as u32 }
                "SUB" => { let v = a.wrapping_sub(rd(a, &m, n)); seta!(v); c = ((v as i32) < 0) as u32 }
                "INC" => { let v = a + 1; seta!(v); c = (v > mask) as u32 }
                "DEC" => { let v = a.wrapping_sub(1); seta!(v); c = ((v as i32) < 0) as u32 }
                "NEG" => { let cy = (a != 0) as u32; seta!(a.wrapping_neg()); c = cy }
                "SHL" => { let cy = (a >> (W - 1)) & 1; seta!(a << 1); c = cy }
                "SHR" => { let cy = a & 1; seta!(a >> 1); c = cy }
                "ROL" => seta!((a << 1) | (a >> (W - 1))), "ROR" => seta!((a >> 1) | ((a & 1) << (W - 1))),
                "RCL" => { let cy = (a >> (W - 1)) & 1; seta!((a << 1) | c); c = cy }
                "MUL" => seta!(a.wrapping_mul(rd(a, &m, n))),
                "SWAP" => { let ta = a; let tt = rd(a, &m, n); wr!(n, ta); seta!(tt) }
                "JMP" => pc = n & pmask, "JZ" => if z != 0 { pc = n & pmask }, "JNZ" => if z == 0 { pc = n & pmask }, "JC" => if c != 0 { pc = n & pmask },
                "SKZ" => if z != 0 { pc = (pc + 1) & pmask }, "SKNZ" => if z == 0 { pc = (pc + 1) & pmask },
                "INCM" => { let v = rd(a, &m, n) + 1; wr!(n, v) }, "DECM" => { let v = rd(a, &m, n).wrapping_sub(1); wr!(n, v) }
                "LDIND" => { let ad = rd(a, &m, n); seta!(rd(a, &m, ad)) }, "STIND" => { let ad = rd(a, &m, n); wr!(ad, a) }
                _ => unreachable!(),
            }
            let st = snap(a, z, c, pc, &m);
            if let Some(start) = hist.iter().position(|h| *h == st) {
                let period = (t + 1) - start; let idx = start + (MAX_STEPS - start) % period; return hist[idx][0];
            }
            hist.push(st);
        }
        a
    }
}
"#;
