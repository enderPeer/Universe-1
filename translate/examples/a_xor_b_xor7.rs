//! Synthesized by u1map from the Universe-1 baseline.
//! Target: a_xor_b_xor7  (W=4, ISA SWAP,ADD,NAND,SKZ, a=2, p=3, I=4, binary: x in A, y in M[1])
//! Stages: x^y -> x^7

pub const W: u32 = 4;
pub const A_BITS: u32 = 2;
pub const P_BITS: u32 = 3;
pub const I_BITS: u32 = 4;
pub const O_BITS: u32 = 2;
pub const ISA: [&str; 4] = ["SWAP", "ADD", "NAND", "SKZ"];
/// Program images, one per stage; instruction k = (program >> (k*I_BITS)) & ((1<<I_BITS)-1).
pub const PROGRAMS: [u64; 2] = [0x2b93, 0x1826];
// stage 0 (x^y):  0: SWAP  3 ;  1: NAND  1 ;  2: NAND  3 ;  3: SWAP  2 ;  4: SWAP  0 ;  5: SWAP  0 ;  6: SWAP  0 ;  7: SWAP  0
// stage 1 (x^7):  0: ADD   2 ;  1: SWAP  2 ;  2: NAND  0 ;  3: SWAP  1 ;  4: SWAP  0 ;  5: SWAP  0 ;  6: SWAP  0 ;  7: SWAP  0

/// The synthesized operator as a verified lookup table (index = x * 16 + y).
pub const TABLE: [u8; 256] = [7, 6, 5, 4, 3, 2, 1, 0, 15, 14, 13, 12, 11, 10, 9, 8, 6, 7, 4, 5, 2, 3, 0, 1, 14, 15, 12, 13, 10, 11, 8, 9, 5, 4, 7, 6, 1, 0, 3, 2, 13, 12, 15, 14, 9, 8, 11, 10, 4, 5, 6, 7, 0, 1, 2, 3, 12, 13, 14, 15, 8, 9, 10, 11, 3, 2, 1, 0, 7, 6, 5, 4, 11, 10, 9, 8, 15, 14, 13, 12, 2, 3, 0, 1, 6, 7, 4, 5, 10, 11, 8, 9, 14, 15, 12, 13, 1, 0, 3, 2, 5, 4, 7, 6, 9, 8, 11, 10, 13, 12, 15, 14, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 14, 15, 12, 13, 10, 11, 8, 9, 6, 7, 4, 5, 2, 3, 0, 1, 13, 12, 15, 14, 9, 8, 11, 10, 5, 4, 7, 6, 1, 0, 3, 2, 12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3, 11, 10, 9, 8, 15, 14, 13, 12, 3, 2, 1, 0, 7, 6, 5, 4, 10, 11, 8, 9, 14, 15, 12, 13, 2, 3, 0, 1, 6, 7, 4, 5, 9, 8, 11, 10, 13, 12, 15, 14, 1, 0, 3, 2, 5, 4, 7, 6, 8, 9, 10, 11, 12, 13, 14, 15, 0, 1, 2, 3, 4, 5, 6, 7];

#[inline]
pub fn a_xor_b_xor7(x: u8, y: u8) -> u8 { TABLE[((x as usize) & 15) * 16 + ((y as usize) & 15)] }

/// Runs the program on the embedded Universe-1 machine (reference semantics).
/// Which stages take y in M[1] (binary) versus only A (unary post/pre-ops).
pub const STAGE_BINARY: [bool; 2] = [true, false];
pub fn a_xor_b_xor7_emulated(x: u8, y: u8) -> u8 {
    let mut v = x as u32;
    for (k, &p) in PROGRAMS.iter().enumerate() { v = machine::run(p, v, if STAGE_BINARY[k] { Some(y as u32) } else { None }); }
    v as u8
}

pub mod machine {
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

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn emulation_matches_table() {
        for x in 0..16 { for y in 0..16 { assert_eq!(a_xor_b_xor7_emulated(x as u8, y as u8), a_xor_b_xor7(x as u8, y as u8), "inputs {} {}", x, y); } }
    }
}
