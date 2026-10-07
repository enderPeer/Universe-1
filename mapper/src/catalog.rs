//! Structural descriptors for W-bit functions, used by `u1map catalog` to index and sort a map.
use crate::classify::Vocab;
use crate::map::Entry;

pub struct Desc { pub class: &'static str, pub name: String, pub image: usize, pub fixed: usize, pub bijective: bool, pub involution: bool,
    pub idempotent: bool, pub constant: bool, pub affine: Option<(u32, u32)>, pub xor_affine: bool, pub monotone: bool, pub depends_mask: u32,
    pub nilpotent_steps: u8, pub cycle_structure: String }

/// unary descriptors for a table over n = 2^w inputs
pub fn describe_unary(t: &[u8], w: u32, vocab: &Vocab) -> Desc {
    let n = 1usize << w; let mask = (n - 1) as u32;
    let mut seen = vec![false; n]; let mut image = 0; for &v in t { if !seen[v as usize] { seen[v as usize] = true; image += 1; } }
    let fixed = (0..n).filter(|&x| t[x] as usize == x).count();
    let bijective = image == n; let constant = image == 1;
    let involution = (0..n).all(|x| t[t[x] as usize] as usize == x);
    let idempotent = (0..n).all(|x| t[t[x] as usize] == t[x]);
    // affine mod 2^w: f(x) = a x + b with b = f(0), a = f(1) - f(0)
    let b = t[0] as u32; let a = (t[1] as u32).wrapping_sub(b) & mask;
    let affine = if (0..n).all(|x| (a.wrapping_mul(x as u32).wrapping_add(b)) & mask == t[x] as u32) { Some((a, b)) } else { None };
    // XOR-affine: f(x) = M x ^ c over GF(2): check f(x ^ y) = f(x) ^ f(y) ^ f(0)
    let c = t[0]; let xor_affine = (0..n).all(|x| (0..n).all(|y| t[x ^ y] == t[x] ^ t[y] ^ c));
    let monotone = (0..n - 1).all(|x| t[x] <= t[x + 1]);
    let mut depends_mask = 0u32; for bit in 0..w { let m = 1usize << bit; if (0..n).any(|x| t[x] != t[x ^ m]) { depends_mask |= 1 << bit; } }
    // iterate f until it stabilizes (f^k constant image) up to n times: how many iterations until the image stops shrinking
    let mut cur: Vec<u8> = t.to_vec(); let mut steps = 1u8; let mut prev_img = image;
    for _ in 0..n { let nxt: Vec<u8> = cur.iter().map(|&v| t[v as usize]).collect(); let mut s2 = vec![false; n]; let mut im = 0; for &v in &nxt { if !s2[v as usize] { s2[v as usize] = true; im += 1; } } if im == prev_img { break; } prev_img = im; cur = nxt; steps += 1; }
    // cycle structure for bijections (e.g. "1^2 2^1 4^3" = two fixed points, one 2-cycle, three 4-cycles)
    let cycle_structure = if bijective {
        let mut vis = vec![false; n]; let mut lens = std::collections::BTreeMap::new();
        for s in 0..n { if vis[s] { continue; } let mut x = s; let mut l = 0; while !vis[x] { vis[x] = true; x = t[x] as usize; l += 1; } *lens.entry(l).or_insert(0) += 1; }
        lens.iter().map(|(l, c)| format!("{}^{}", l, c)).collect::<Vec<_>>().join(" ")
    } else { String::new() };
    let name = vocab.name(t).cloned().unwrap_or_default();
    let class = if !name.is_empty() { "named" } else if constant { "constant" } else if bijective { "permutation" } else if t.iter().all(|&v| v <= 1) { "predicate" } else { "other" };
    Desc { class, name, image, fixed, bijective, involution, idempotent, constant, affine, xor_affine, monotone, depends_mask, nilpotent_steps: steps, cycle_structure }
}

pub fn class_rank(d: &Desc) -> u8 {
    if d.constant { 0 } else if d.affine.is_some() { 1 } else if d.xor_affine { 2 } else if !d.name.is_empty() { 3 } else if d.bijective { 4 } else if d.image <= 2 { 5 } else { 6 }
}

pub fn header() -> &'static str {
    "index\tprogram\tname\tclass\tsort_class\timage\tfixed_points\tbijective\tinvolution\tidempotent\taffine_a\taffine_b\txor_affine\tmonotone\tdepends_bits\tsettle_iters\tcycles\tsteps\thalts\ttable"
}
pub fn row(idx: usize, e: &Entry, d: &Desc, w: u32) -> String {
    let tbl: Vec<String> = e.table.iter().map(|v| v.to_string()).collect();
    format!("{}\t0x{:08x}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{:0w$b}\t{}\t{}\t{}\t{}\t{}", idx, e.program, d.name, d.class, class_name(class_rank(d)), d.image, d.fixed,
        d.bijective as u8, d.involution as u8, d.idempotent as u8, d.affine.map(|a| a.0.to_string()).unwrap_or_default(), d.affine.map(|a| a.1.to_string()).unwrap_or_default(),
        d.xor_affine as u8, d.monotone as u8, d.depends_mask, d.nilpotent_steps, d.cycle_structure, e.steps, e.halts as u8, tbl.join(","), w = w as usize)
}
pub fn class_name(r: u8) -> &'static str { ["constant", "affine-mod16", "xor-affine", "named", "permutation", "near-predicate", "other"][r as usize] }
