//! Synthesized by u1map from the Universe-1 baseline.
//! Target: popcount  (W=4, ISA SWAP,LDI,NAND,ADD,ROL,SKNZ,INC,HALT, a=2, p=3, I=4)
//! Stages: (popcount(x))*9 -> x*9

pub const W: u32 = 4;
pub const A_BITS: u32 = 2;
pub const P_BITS: u32 = 3;
pub const I_BITS: u32 = 4;
pub const O_BITS: u32 = 3;
pub const ISA: [&str; 8] = ["SWAP", "LDI", "NAND", "ADD", "ROL", "SKNZ", "INC", "HALT"];
/// Program images, one per stage; instruction k = (program >> (k*I_BITS)) & ((1<<I_BITS)-1).
pub const PROGRAMS: [u64; 2] = [0xa87c417, 0xa17];
// stage 0 ((popcount(x))*9):  0: ADD   1 ;  1: SWAP  1 ;  2: NAND  0 ;  3: INC ;  4: ADD   1 ;  5: ROL ;  6: SKNZ ;  7: SWAP  0
// stage 1 (x*9):  0: ADD   1 ;  1: SWAP  1 ;  2: SKNZ ;  3: SWAP  0 ;  4: SWAP  0 ;  5: SWAP  0 ;  6: SWAP  0 ;  7: SWAP  0

/// The synthesized operator as a verified lookup table.
pub const TABLE: [u8; 16] = [0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4];

#[inline]
pub fn popcount(x: u8) -> u8 { TABLE[(x as usize) & 15] }

/// Runs the stage programs on the embedded Universe-1 machine (reference semantics).
pub fn popcount_emulated(x: u8) -> u8 {
    let mut v = x as u32;
    for &p in PROGRAMS.iter() { v = machine::run(p, v); }
    v as u8
}

pub mod machine {
    use super::*;
    const MAX_STEPS: usize = 256;
    /// Run one program image with A = x; returns A at HALT / step 256 (periodic runs are exact:
    /// the state at step 256 is reconstructed from the detected cycle).
    pub fn run(program: u64, x: u32) -> u32 {
        let mask = (1u32 << W) - 1; let amask = (1u32 << A_BITS) - 1; let pmask = (1u32 << P_BITS) - 1;
        let nins = 1usize << P_BITS; let opmask = (1u32 << (I_BITS - O_BITS)) - 1;
        let code: Vec<(&str, u32)> = (0..nins).map(|k| { let ins = ((program >> (k as u32 * I_BITS)) & ((1u64 << I_BITS) - 1)) as u32; (ISA[(ins >> (I_BITS - O_BITS)) as usize], ins & opmask) }).collect();
        let (mut a, mut z, mut c, mut pc) = (x & mask, (x & mask == 0) as u32, 0u32, 0u32);
        let mut m = vec![0u32; 1 << A_BITS];
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
        for x in 0..16 { assert_eq!(popcount_emulated(x as u8), popcount(x as u8), "input {}", x); }
    }
}
