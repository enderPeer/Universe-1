//! Shard file format shared with fast/u1.c, gpu/u1_cuda.cu and gpu/u1_vk.c:
//! header 8 x u32 {magic, W, a, p, I, o, binary, nisa}, 3 x u64 {lo, hi, count}, nisa bytes of
//! primitive ids, then `count` records {key_lo u64, key_hi u64, program u32}.
use crate::machine::{Config, Prim};
use std::collections::HashMap;
use std::io::{Read, Write};

pub const MAGIC: u32 = 0x5531_4231;

pub struct Shard { pub cfg: Config, pub lo: u64, pub hi: u64, pub recs: Vec<((u64, u64), u32)> }

pub fn read(path: &str) -> Result<Shard, String> {
    let mut b = Vec::new();
    std::fs::File::open(path).and_then(|mut f| f.read_to_end(&mut b)).map_err(|e| format!("{}: {}", path, e))?;
    if b.len() < 56 { return Err(format!("{}: too short", path)); }
    let u32at = |o: usize| u32::from_le_bytes(b[o..o + 4].try_into().unwrap());
    let u64at = |o: usize| u64::from_le_bytes(b[o..o + 8].try_into().unwrap());
    if u32at(0) != MAGIC { return Err(format!("{}: bad magic", path)); }
    let (w, a, p, i, _o, bin, nisa) = (u32at(4), u32at(8), u32at(12), u32at(16), u32at(20), u32at(24), u32at(28) as usize);
    let (lo, hi, n) = (u64at(32), u64at(40), u64at(48) as usize);
    let isa = b[56..56 + nisa].iter().map(|&id| Prim::from_id(id).ok_or("bad prim id".to_string())).collect::<Result<Vec<_>, _>>()?;
    let cfg = Config::new(w, a, p, Some(i), isa, bin != 0)?;
    let off = 56 + nisa;
    if b.len() != off + n * 20 { return Err(format!("{}: size mismatch", path)); }
    let recs = (0..n).map(|k| { let o = off + k * 20; ((u64at(o), u64at(o + 8)), u32at(o + 16)) }).collect();
    Ok(Shard { cfg, lo, hi, recs })
}

pub fn write(path: &str, cfg: &Config, lo: u64, hi: u64, recs: &HashMap<(u64, u64), u32>) -> Result<(), String> {
    let mut f = std::io::BufWriter::new(std::fs::File::create(path).map_err(|e| format!("{}: {}", path, e))?);
    let mut out = Vec::new();
    for v in [MAGIC, cfg.w, cfg.a, cfg.p, cfg.i, cfg.o, cfg.binary as u32, cfg.isa.len() as u32] { out.extend_from_slice(&v.to_le_bytes()); }
    for v in [lo, hi, recs.len() as u64] { out.extend_from_slice(&v.to_le_bytes()); }
    for p in &cfg.isa { out.push(p.id()); }
    let mut sorted: Vec<_> = recs.iter().collect(); sorted.sort_by_key(|(_, p)| **p);
    for ((klo, khi), prog) in sorted { out.extend_from_slice(&klo.to_le_bytes()); out.extend_from_slice(&khi.to_le_bytes()); out.extend_from_slice(&prog.to_le_bytes()); }
    f.write_all(&out).map_err(|e| e.to_string())
}
