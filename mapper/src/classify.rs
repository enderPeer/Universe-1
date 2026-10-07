//! Names for W-bit functions. A vocabulary of elementary operators and their depth-2
//! compositions is generated as truth tables; a function is "named" when its table is in
//! the vocabulary. The same vocabulary doubles as the target language of `u1map synth`.
use std::collections::HashMap;

pub type Table = Vec<u8>;

pub struct Vocab { pub w: u32, pub binary: bool, pub by_table: HashMap<Table, String>, pub by_name: HashMap<String, Table> }

fn ops_unary(w: u32) -> Vec<(String, Box<dyn Fn(u32) -> u32>)> {
    let n = 1u32 << w; let mask = n - 1;
    let mut v: Vec<(String, Box<dyn Fn(u32) -> u32>)> = Vec::new();
    v.push(("x".into(), Box::new(|x| x)));
    v.push(("!x".into(), Box::new(move |x| !x & mask)));
    v.push(("-x".into(), Box::new(move |x| x.wrapping_neg() & mask)));
    v.push(("x*x".into(), Box::new(move |x| x.wrapping_mul(x) & mask)));
    v.push(("popcount(x)".into(), Box::new(|x| x.count_ones())));
    v.push(("parity(x)".into(), Box::new(|x| x.count_ones() & 1)));
    v.push(("bitrev(x)".into(), Box::new(move |x| x.reverse_bits() >> (32 - w))));
    v.push(("sar(x)".into(), Box::new(move |x| (x >> 1) | (x & (1 << (w - 1))))));
    v.push(("sign(x)".into(), Box::new(move |x| x >> (w - 1))));
    v.push(("abs(x)".into(), Box::new(move |x| if x >> (w - 1) == 1 { x.wrapping_neg() & mask } else { x })));
    v.push(("clz(x)".into(), Box::new(move |x| if x == 0 { w } else { x.leading_zeros() - (32 - w) })));
    v.push(("ctz(x)".into(), Box::new(move |x| if x == 0 { w } else { x.trailing_zeros() })));
    v.push(("x==0".into(), Box::new(|x| (x == 0) as u32)));
    v.push(("x!=0".into(), Box::new(|x| (x != 0) as u32)));
    v.push(("lowbit(x)".into(), Box::new(|x| x & x.wrapping_neg())));
    if w >= 2 { v.push(("swaphalves(x)".into(), Box::new(move |x| ((x << (w / 2)) | (x >> (w - w / 2))) & mask))); }
    for k in 0..n {
        v.push((format!("{}", k), Box::new(move |_| k)));
        if k > 0 {
            v.push((format!("x+{}", k), Box::new(move |x| (x + k) & mask)));
            v.push((format!("x^{}", k), Box::new(move |x| x ^ k)));
            v.push((format!("{}-x", k), Box::new(move |x| k.wrapping_sub(x) & mask)));
            v.push((format!("x=={}", k), Box::new(move |x| (x == k) as u32)));
            v.push((format!("x<{}", k), Box::new(move |x| (x < k) as u32)));
            v.push((format!("x>={}", k), Box::new(move |x| (x >= k) as u32)));
            v.push((format!("min(x,{})", k), Box::new(move |x| x.min(k))));
            v.push((format!("max(x,{})", k), Box::new(move |x| x.max(k))));
        }
        if k > 1 { v.push((format!("x*{}", k), Box::new(move |x| x.wrapping_mul(k) & mask))); }
        if k > 0 && k < mask { v.push((format!("x&{}", k), Box::new(move |x| x & k))); v.push((format!("x|{}", k), Box::new(move |x| x | k))); }
        if k > 0 && k < n { v.push((format!("x/{}", k), Box::new(move |x| x / k))); v.push((format!("x%{}", k), Box::new(move |x| x % k))); }
    }
    for k in 1..w {
        v.push((format!("x<<{}", k), Box::new(move |x| (x << k) & mask)));
        v.push((format!("x>>{}", k), Box::new(move |x| x >> k)));
        v.push((format!("rol(x,{})", k), Box::new(move |x| ((x << k) | (x >> (w - k))) & mask)));
    }
    v
}

fn ops_binary(w: u32) -> Vec<(String, Box<dyn Fn(u32, u32) -> u32>)> {
    let n = 1u32 << w; let mask = n - 1;
    let mut v: Vec<(String, Box<dyn Fn(u32, u32) -> u32>)> = Vec::new();
    v.push(("x".into(), Box::new(|x, _| x)));
    v.push(("y".into(), Box::new(|_, y| y)));
    v.push(("x+y".into(), Box::new(move |x, y| (x + y) & mask)));
    v.push(("x-y".into(), Box::new(move |x, y| x.wrapping_sub(y) & mask)));
    v.push(("y-x".into(), Box::new(move |x, y| y.wrapping_sub(x) & mask)));
    v.push(("x*y".into(), Box::new(move |x, y| x.wrapping_mul(y) & mask)));
    v.push(("x/y".into(), Box::new(move |x, y| if y == 0 { mask } else { x / y })));
    v.push(("x%y".into(), Box::new(move |x, y| if y == 0 { x } else { x % y })));
    v.push(("x&y".into(), Box::new(|x, y| x & y)));
    v.push(("x|y".into(), Box::new(|x, y| x | y)));
    v.push(("x^y".into(), Box::new(|x, y| x ^ y)));
    v.push(("!(x&y)".into(), Box::new(move |x, y| !(x & y) & mask)));
    v.push(("!(x|y)".into(), Box::new(move |x, y| !(x | y) & mask)));
    v.push(("!(x^y)".into(), Box::new(move |x, y| !(x ^ y) & mask)));
    v.push(("x&!y".into(), Box::new(move |x, y| x & !y & mask)));
    v.push(("x|!y".into(), Box::new(move |x, y| (x | !y) & mask)));
    v.push(("min(x,y)".into(), Box::new(|x, y| x.min(y))));
    v.push(("max(x,y)".into(), Box::new(|x, y| x.max(y))));
    v.push(("x==y".into(), Box::new(|x, y| (x == y) as u32)));
    v.push(("x!=y".into(), Box::new(|x, y| (x != y) as u32)));
    v.push(("x<y".into(), Box::new(|x, y| (x < y) as u32)));
    v.push(("x<=y".into(), Box::new(|x, y| (x <= y) as u32)));
    v.push(("x>y".into(), Box::new(|x, y| (x > y) as u32)));
    v.push(("x>=y".into(), Box::new(|x, y| (x >= y) as u32)));
    v.push(("x<<y".into(), Box::new(move |x, y| if y >= w { 0 } else { (x << y) & mask })));
    v.push(("x>>y".into(), Box::new(move |x, y| if y >= w { 0 } else { x >> y })));
    v.push(("rol(x,y)".into(), Box::new(move |x, y| { let k = y % w; if k == 0 { x } else { ((x << k) | (x >> (w - k))) & mask } })));
    v.push(("carry(x+y)".into(), Box::new(move |x, y| ((x + y) > mask) as u32)));
    v.push(("borrow(x-y)".into(), Box::new(|x, y| (x < y) as u32)));
    v.push(("avg(x,y)".into(), Box::new(|x, y| (x + y) / 2)));
    v.push(("|x-y|".into(), Box::new(|x, y| x.abs_diff(y))));
    v.push(("y?x:0".into(), Box::new(|x, y| if y != 0 { x } else { 0 })));
    v.push(("x?y:0".into(), Box::new(|x, y| if x != 0 { y } else { 0 })));
    v.push(("gcd(x,y)".into(), Box::new(|x, y| { let (mut a, mut b) = (x, y); while b != 0 { let t = a % b; a = b; b = t; } a })));
    v
}

impl Vocab {
    pub fn new(w: u32, binary: bool) -> Vocab {
        let n = 1u32 << w;
        let mut by_table: HashMap<Table, String> = HashMap::new();
        let mut add = |t: Table, name: String| {
            let e = by_table.entry(t).or_insert_with(|| name.clone());
            if name.len() < e.len() { *e = name; }
        };
        let un = ops_unary(w);
        if !binary {
            // depth 1 and depth 2 compositions of unary elementary ops
            let tabs: Vec<Table> = un.iter().map(|(_, f)| (0..n).map(|x| f(x) as u8).collect()).collect();
            for (i, (name, _)) in un.iter().enumerate() { add(tabs[i].clone(), name.clone()); }
            for (i, (nf, f)) in un.iter().enumerate() {
                if nf == "x" || nf.parse::<u32>().is_ok() { continue; }
                for (j, (ng, _)) in un.iter().enumerate() {
                    if ng == "x" || ng.parse::<u32>().is_ok() || i == j { continue; }
                    let t: Table = tabs[j].iter().map(|&g| f(g as u32) as u8).collect();
                    add(t, nf.replace('x', &format!("({})", ng)));
                }
            }
        } else {
            let bi = ops_binary(w);
            let btabs: Vec<Table> = bi.iter().map(|(_, f)| (0..n).flat_map(|x| (0..n).map(move |y| (x, y))).map(|(x, y)| f(x, y) as u8).collect()).collect();
            for (i, (name, _)) in bi.iter().enumerate() { add(btabs[i].clone(), name.clone()); }
            // unary post-op on a binary result, and unary pre-op on one argument
            for (nf, f) in &un {
                if nf == "x" { continue; }
                for (j, (nb, b)) in bi.iter().enumerate() {
                    if nb == "x" || nb == "y" { continue; }
                    let t: Table = btabs[j].iter().map(|&v| f(v as u32) as u8).collect();
                    add(t, nf.replace('x', &format!("({})", nb)));
                    let tx: Table = (0..n).flat_map(|x| (0..n).map(move |y| (x, y))).map(|(x, y)| b(f(x), y) as u8).collect();
                    add(tx, nb.replace('x', &format!("({})", nf)));
                    let ty: Table = (0..n).flat_map(|x| (0..n).map(move |y| (x, y))).map(|(x, y)| b(x, f(y)) as u8).collect();
                    add(ty, nb.replace('y', &format!("({})", nf.replace('x', "y"))));
                }
            }
        }
        let by_name = by_table.iter().map(|(t, n)| (n.clone(), t.clone())).collect();
        Vocab { w, binary, by_table, by_name }
    }
    pub fn name(&self, t: &[u8]) -> Option<&String> { self.by_table.get(t) }
    pub fn table(&self, name: &str) -> Option<&Table> { self.by_name.get(name) }

    /// Coarse class of an unnamed table, for statistics.
    pub fn class(&self, t: &[u8]) -> &'static str {
        if let Some(_) = self.name(t) { return "named"; }
        if t.iter().all(|&v| v == t[0]) { return "constant"; }
        if !self.binary {
            let mut seen = vec![false; 1 << self.w];
            let bij = t.iter().all(|&v| { let s = seen[v as usize]; seen[v as usize] = true; !s });
            if bij { return "permutation"; }
            if t.iter().all(|&v| v <= 1) { return "predicate"; }
            return "other";
        }
        if t.iter().all(|&v| v <= 1) { "predicate" } else { "other" }
    }
}
