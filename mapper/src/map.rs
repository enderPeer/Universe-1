//! The function map: every distinct operator an (ISA, geometry) realizes, with its smallest
//! witness program, step cost, halting flag and name. Persisted compactly as the sorted list
//! of witness program ids (`.u1prog`); tables are recomputed on load.
use crate::classify::{Table, Vocab};
use crate::machine::{table_key, Config, Machine, Scratch};
use crate::shard;
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::{Arc, Mutex};

#[derive(Clone, Debug)]
pub struct Entry { pub table: Table, pub program: u64, pub steps: usize, pub halts: bool }

pub struct FunctionMap { pub cfg: Config, pub entries: Vec<Entry>, pub index: HashMap<Table, usize> }

pub const PROG_MAGIC: &[u8; 8] = b"U1PROG01";

impl FunctionMap {
    pub fn from_programs(cfg: Config, mut programs: Vec<u64>, threads: usize) -> FunctionMap {
        programs.sort_unstable(); programs.dedup();
        let cfg = Arc::new(cfg); let programs = Arc::new(programs);
        let out = Arc::new(Mutex::new(vec![None; programs.len()]));
        let th: Vec<_> = (0..threads.max(1)).map(|t| {
            let (cfg, programs, out) = (cfg.clone(), programs.clone(), out.clone());
            std::thread::spawn(move || {
                let m = Machine::new(&cfg); let mut sc = Scratch::new(&cfg); let mut local = Vec::new();
                for (k, &pb) in programs.iter().enumerate().skip(t).step_by(threads.max(1)) {
                    let (table, steps, halts) = m.table(&mut sc, pb);
                    local.push((k, Entry { table, program: pb, steps, halts }));
                }
                let mut o = out.lock().unwrap(); for (k, e) in local { o[k] = Some(e); }
            })
        }).collect();
        for t in th { t.join().unwrap(); }
        let entries: Vec<Entry> = Arc::try_unwrap(out).unwrap().into_inner().unwrap().into_iter().map(|e| e.unwrap()).collect();
        let mut index = HashMap::with_capacity(entries.len());
        let mut dedup = Vec::with_capacity(entries.len());
        for e in entries { if !index.contains_key(&e.table) { index.insert(e.table.clone(), dedup.len()); dedup.push(e); } }
        FunctionMap { cfg: Arc::try_unwrap(cfg).unwrap(), entries: dedup, index }
    }

    /// Build from shard files (all must share one config); verifies every witness key.
    pub fn from_shards(paths: &[String], threads: usize) -> Result<(FunctionMap, usize), String> {
        let mut cfg: Option<Config> = None; let mut progs = Vec::new(); let mut best: HashMap<(u64, u64), u32> = HashMap::new();
        for p in paths {
            let s = shard::read(p)?;
            match &cfg { None => cfg = Some(s.cfg.clone()), Some(c) => if c.isa_string() != s.cfg.isa_string() || c.w != s.cfg.w || c.a != s.cfg.a || c.p != s.cfg.p || c.i != s.cfg.i || c.binary != s.cfg.binary { return Err(format!("{}: config differs", p)); } }
            for (k, prog) in s.recs { let e = best.entry(k).or_insert(prog); if prog < *e { *e = prog; } }
        }
        let cfg = cfg.ok_or("no shards")?;
        for (_, p) in &best { progs.push(*p as u64); }
        let fm = FunctionMap::from_programs(cfg, progs, threads);
        let mut bad = 0;
        for e in &fm.entries { let k = table_key(&e.table, fm.cfg.w); if best.get(&k) != Some(&(e.program as u32)) { bad += 1; } }
        Ok((fm, bad))
    }

    pub fn save_programs(&self, path: &str) -> Result<(), String> {
        let mut out = Vec::new(); out.extend_from_slice(PROG_MAGIC);
        for v in [self.cfg.w, self.cfg.a, self.cfg.p, self.cfg.i, self.cfg.binary as u32, self.cfg.isa.len() as u32] { out.extend_from_slice(&v.to_le_bytes()); }
        for p in &self.cfg.isa { out.push(p.id()); }
        out.extend_from_slice(&(self.entries.len() as u64).to_le_bytes());
        let mut progs: Vec<u64> = self.entries.iter().map(|e| e.program).collect(); progs.sort_unstable();
        for p in progs { out.extend_from_slice(&p.to_le_bytes()); }
        std::fs::File::create(path).and_then(|mut f| f.write_all(&out)).map_err(|e| format!("{}: {}", path, e))
    }

    pub fn load_programs(path: &str, threads: usize) -> Result<FunctionMap, String> {
        let mut b = Vec::new();
        std::fs::File::open(path).and_then(|mut f| f.read_to_end(&mut b)).map_err(|e| format!("{}: {}", path, e))?;
        if b.len() < 32 || &b[..8] != PROG_MAGIC { return Err(format!("{}: not a u1prog file", path)); }
        let u32at = |o: usize| u32::from_le_bytes(b[o..o + 4].try_into().unwrap());
        let (w, a, p, i, bin, nisa) = (u32at(8), u32at(12), u32at(16), u32at(20), u32at(24), u32at(28) as usize);
        let isa = b[32..32 + nisa].iter().map(|&id| crate::machine::Prim::from_id(id).ok_or("bad prim".to_string())).collect::<Result<Vec<_>, _>>()?;
        let cfg = Config::new(w, a, p, Some(i), isa, bin != 0)?;
        let mut o = 32 + nisa; let n = u64::from_le_bytes(b[o..o + 8].try_into().unwrap()) as usize; o += 8;
        let progs = (0..n).map(|k| u64::from_le_bytes(b[o + k * 8..o + k * 8 + 8].try_into().unwrap())).collect();
        Ok(FunctionMap::from_programs(cfg, progs, threads))
    }

    pub fn get(&self, t: &[u8]) -> Option<&Entry> { self.index.get(t).map(|&i| &self.entries[i]) }

    /// Named operators as JSON lines, sorted by name.
    pub fn write_named_jsonl(&self, vocab: &Vocab, path: &str) -> Result<usize, String> {
        let mut rows: Vec<(String, &Entry)> = self.entries.iter().filter_map(|e| vocab.name(&e.table).map(|n| (n.clone(), e))).collect();
        rows.sort_by(|a, b| a.0.cmp(&b.0));
        let mut out = String::new();
        for (name, e) in &rows {
            out += &format!("{{\"name\":{},\"program\":{},\"hex\":\"{:0w$x}\",\"steps\":{},\"halts\":{},\"asm\":{},\"table\":{:?}}}\n",
                json_str(name), e.program, e.program, e.steps, e.halts, json_str(&self.cfg.disassemble(e.program).join(" ; ")), e.table, w = (self.cfg.program_bits() as usize + 3) / 4);
        }
        std::fs::write(path, out).map_err(|e| format!("{}: {}", path, e))?;
        Ok(rows.len())
    }

    pub fn stats(&self, vocab: &Vocab) -> String {
        let mut classes: HashMap<&str, usize> = HashMap::new(); let mut hist = [0usize; 9]; let mut halting = 0;
        for e in &self.entries {
            *classes.entry(vocab.class(&e.table)).or_default() += 1;
            let b = if e.steps >= 256 { 8 } else { ((usize::BITS - e.steps.leading_zeros()) as usize).min(7) }; hist[b] += 1;
            if e.halts { halting += 1; }
        }
        let named_total = vocab.by_table.len();
        let named_found = self.entries.iter().filter(|e| vocab.name(&e.table).is_some()).count();
        let mut cls: Vec<_> = classes.into_iter().collect(); cls.sort();
        format!("{{\"isa\":\"{}\",\"W\":{},\"a\":{},\"p\":{},\"I\":{},\"binary\":{},\"operators\":{},\"all_inputs_halt\":{},\"named_found\":{},\"vocabulary_size\":{},\"classes\":{{{}}},\"max_steps_histogram\":{{\"1\":{},\"2-3\":{},\"4-7\":{},\"8-15\":{},\"16-31\":{},\"32-63\":{},\"64-127\":{},\"128-255\":{},\"256\":{}}}}}",
            self.cfg.isa_string(), self.cfg.w, self.cfg.a, self.cfg.p, self.cfg.i, self.cfg.binary, self.entries.len(), halting, named_found, named_total,
            cls.iter().map(|(k, v)| format!("\"{}\":{}", k, v)).collect::<Vec<_>>().join(","),
            hist[1], hist[2], hist[3], hist[4], hist[5], hist[6], hist[7], 0, hist[8])
    }
}

pub fn json_str(s: &str) -> String { format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\"")) }
