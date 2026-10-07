//! The Universe-1 W-bit machine. Semantics are identical to sim/machine.py and fast/u1.c
//! (layout L3: address 0 aliases A; the harness caps a run at 256 steps; a repeated state
//! means the run is periodic and the state at step 256 is reconstructed from the history).

pub const MAX_STEPS: usize = 256;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Prim {
    Nop, Halt, Ld, St, Ldi, Clr, Set, Not, And, Or, Xor, Nand, Nor, Xnor, Add, Adc, Sub, Inc, Dec,
    Neg, Shl, Shr, Rol, Ror, Rcl, Mul, Swap, Jmp, Jz, Jnz, Jc, Skz, Sknz, Incm, Decm, Ldind, Stind,
}

pub const PRIM_NAMES: [&str; 37] = [
    "NOP", "HALT", "LD", "ST", "LDI", "CLR", "SET", "NOT", "AND", "OR", "XOR", "NAND", "NOR", "XNOR",
    "ADD", "ADC", "SUB", "INC", "DEC", "NEG", "SHL", "SHR", "ROL", "ROR", "RCL", "MUL", "SWAP",
    "JMP", "JZ", "JNZ", "JC", "SKZ", "SKNZ", "INCM", "DECM", "LDIND", "STIND",
];

impl Prim {
    pub fn from_id(id: u8) -> Option<Prim> {
        use Prim::*;
        const ALL: [Prim; 37] = [
            Nop, Halt, Ld, St, Ldi, Clr, Set, Not, And, Or, Xor, Nand, Nor, Xnor, Add, Adc, Sub, Inc, Dec,
            Neg, Shl, Shr, Rol, Ror, Rcl, Mul, Swap, Jmp, Jz, Jnz, Jc, Skz, Sknz, Incm, Decm, Ldind, Stind,
        ];
        ALL.get(id as usize).copied()
    }
    pub fn id(self) -> u8 { self as u8 }
    pub fn name(self) -> &'static str { PRIM_NAMES[self as usize] }
    pub fn parse(s: &str) -> Option<Prim> {
        PRIM_NAMES.iter().position(|n| *n == s).map(|i| Prim::from_id(i as u8).unwrap())
    }
    /// Does this primitive read the operand field?
    pub fn uses_operand(self) -> bool {
        use Prim::*;
        matches!(self, Ld | St | Ldi | And | Or | Xor | Nand | Nor | Xnor | Add | Adc | Sub | Mul | Swap
            | Jmp | Jz | Jnz | Jc | Incm | Decm | Ldind | Stind)
    }
}

#[derive(Clone, Debug)]
pub struct Config {
    pub w: u32,   // word width
    pub a: u32,   // address bits
    pub p: u32,   // pc bits
    pub i: u32,   // instruction width
    pub o: u32,   // opcode bits
    pub isa: Vec<Prim>,
    pub binary: bool,
}

impl Config {
    pub fn new(w: u32, a: u32, p: u32, i: Option<u32>, isa: Vec<Prim>, binary: bool) -> Result<Config, String> {
        let i = i.unwrap_or(w);
        if !(1..=8).contains(&w) { return Err("W must be 1..8".into()); }
        if a > 8 || p == 0 || p > 8 { return Err("a <= 8, 1 <= p <= 8".into()); }
        if isa.is_empty() || !isa.len().is_power_of_two() { return Err("ISA length must be a power of two".into()); }
        let mut o = 0; while (1usize << o) < isa.len() { o += 1; } let o = o.max(1);
        if o > i { return Err(format!("opcode bits {} > instruction width {}", o, i)); }
        if binary && a < 1 { return Err("binary mode needs a >= 1".into()); }
        Ok(Config { w, a, p, i, o, isa, binary })
    }
    pub fn mask(&self) -> u32 { (1 << self.w) - 1 }
    pub fn amask(&self) -> u32 { (1 << self.a) - 1 }
    pub fn pmask(&self) -> u32 { (1 << self.p) - 1 }
    pub fn opmask(&self) -> u32 { (1 << (self.i - self.o)) - 1 }
    pub fn nins(&self) -> usize { 1 << self.p }
    pub fn nm(&self) -> usize { 1 << self.a }
    pub fn nin(&self) -> usize { 1 << self.w }
    pub fn ntab(&self) -> usize { if self.binary { self.nin() * self.nin() } else { self.nin() } }
    pub fn program_bits(&self) -> u32 { self.nins() as u32 * self.i }
    pub fn program_count(&self) -> u128 { 1u128 << self.program_bits() }
    /// bits of packed full state (A, Z, C, PC, M[1..])
    pub fn state_bits(&self) -> u32 { self.w + 2 + self.p + (self.nm() as u32 - 1) * self.w }
    pub fn isa_string(&self) -> String { self.isa.iter().map(|p| p.name()).collect::<Vec<_>>().join(",") }
    pub fn parse_isa(s: &str) -> Result<Vec<Prim>, String> {
        s.split(',').map(|t| Prim::parse(t.trim()).ok_or_else(|| format!("unknown primitive {}", t))).collect()
    }
    pub fn decode(&self, pb: u64) -> Vec<(Prim, u32)> {
        let imask = (1u64 << self.i) - 1;
        (0..self.nins()).map(|k| {
            let ins = ((pb >> (k as u32 * self.i)) & imask) as u32;
            (self.isa[(ins >> (self.i - self.o)) as usize], ins & self.opmask())
        }).collect()
    }
    pub fn encode(&self, code: &[(Prim, u32)]) -> Option<u64> {
        let mut pb = 0u64;
        for (k, (prim, opnd)) in code.iter().enumerate() {
            let opc = self.isa.iter().position(|p| p == prim)? as u64;
            let ins = (opc << (self.i - self.o)) | (*opnd as u64 & self.opmask() as u64);
            pb |= ins << (k as u32 * self.i);
        }
        Some(pb)
    }
    pub fn disassemble(&self, pb: u64) -> Vec<String> {
        self.decode(pb).iter().enumerate().map(|(k, (p, op))| {
            if self.i > self.o && p.uses_operand() { format!("{:>2}: {:<5} {}", k, p.name(), op) } else { format!("{:>2}: {}", k, p.name()) }
        }).collect()
    }
}

#[derive(Clone, Debug)]
pub struct State { pub a: u32, pub z: u32, pub c: u32, pub pc: u32, pub m: Vec<u32> }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum End { Halt, Budget, Loop }

#[derive(Clone, Debug)]
pub struct RunResult { pub a: u32, pub steps: usize, pub end: End }

/// Per-thread scratch for cycle detection.
pub struct Scratch { stamp: Vec<u32>, cur: u32, hist: Vec<u32>, decoded: Vec<(Prim, u32)> }

impl Scratch {
    pub fn new(cfg: &Config) -> Scratch {
        let sb = cfg.state_bits();
        let stamp = if sb <= 26 { vec![0u32; 1 << sb] } else { Vec::new() };
        Scratch { stamp, cur: 0, hist: Vec::with_capacity(MAX_STEPS + 1), decoded: Vec::new() }
    }
}

#[inline] fn pack(cfg: &Config, s: &State) -> u32 {
    let mut k = s.a | (s.z << cfg.w) | (s.c << (cfg.w + 1)) | (s.pc << (cfg.w + 2));
    let mut sh = cfg.w + 2 + cfg.p;
    for i in 1..cfg.nm() { k |= s.m[i] << sh; sh += cfg.w; }
    k
}
#[inline] fn unpack(cfg: &Config, k: u32, s: &mut State) {
    s.a = k & cfg.mask(); s.z = (k >> cfg.w) & 1; s.c = (k >> (cfg.w + 1)) & 1; s.pc = (k >> (cfg.w + 2)) & cfg.pmask();
    let mut sh = cfg.w + 2 + cfg.p;
    for i in 1..cfg.nm() { s.m[i] = (k >> sh) & cfg.mask(); sh += cfg.w; }
}

pub struct Machine<'a> { pub cfg: &'a Config }

impl<'a> Machine<'a> {
    pub fn new(cfg: &'a Config) -> Machine<'a> { Machine { cfg } }

    /// Run program `pb` with A = x (and M[1] = y when `y` is Some) for at most 256 steps.
    pub fn run(&self, sc: &mut Scratch, pb: u64, x: u32, y: Option<u32>) -> RunResult {
        let cfg = self.cfg;
        sc.decoded = cfg.decode(pb);
        self.run_decoded(sc, x, y)
    }

    pub fn run_decoded(&self, sc: &mut Scratch, x: u32, y: Option<u32>) -> RunResult {
        let cfg = self.cfg;
        let mask = cfg.mask(); let amask = cfg.amask(); let pmask = cfg.pmask(); let w = cfg.w;
        let mut s = State { a: x & mask, z: 0, c: 0, pc: 0, m: vec![0; cfg.nm()] };
        s.z = (s.a == 0) as u32;
        if let Some(y) = y { s.m[1] = y & mask; }
        let vis = !sc.stamp.is_empty();
        if vis {
            sc.cur = sc.cur.wrapping_add(1);
            if sc.cur == 0 { for v in sc.stamp.iter_mut() { *v = 0; } sc.cur = 1; }
            sc.hist.clear();
            let k = pack(cfg, &s); sc.stamp[k as usize] = sc.cur; sc.hist.push(k);
        }
        macro_rules! rd { ($addr:expr) => {{ let ad = $addr & amask; if ad == 0 { s.a } else { s.m[ad as usize] } }}; }
        macro_rules! wr { ($addr:expr, $v:expr) => {{ let ad = $addr & amask; let v = $v & mask; if ad == 0 { s.a = v } else { s.m[ad as usize] = v } }}; }
        macro_rules! seta { ($v:expr) => {{ s.a = $v & mask; s.z = (s.a == 0) as u32; }}; }
        macro_rules! seta_c { ($v:expr, $c:expr) => {{ let c = $c; s.a = $v & mask; s.z = (s.a == 0) as u32; s.c = c; }}; }
        for t in 0..MAX_STEPS {
            let pc0 = s.pc;
            let (prim, op) = sc.decoded[(s.pc & pmask) as usize];
            s.pc = (s.pc + 1) & pmask;
            use Prim::*;
            match prim {
                Nop => {}
                Halt => return RunResult { a: s.a, steps: t + 1, end: End::Halt },
                Ld => seta!(rd!(op)),
                St => wr!(op, s.a),
                Ldi => seta!(op),
                Clr => seta!(0),
                Set => seta!(mask),
                Not => seta!(!s.a),
                And => seta!(s.a & rd!(op)),
                Or => seta!(s.a | rd!(op)),
                Xor => seta!(s.a ^ rd!(op)),
                Nand => seta!(!(s.a & rd!(op))),
                Nor => seta!(!(s.a | rd!(op))),
                Xnor => seta!(!(s.a ^ rd!(op))),
                Add => { let v = s.a + rd!(op); seta_c!(v, (v > mask) as u32) }
                Adc => { let v = s.a + rd!(op) + s.c; seta_c!(v, (v > mask) as u32) }
                Sub => { let v = s.a.wrapping_sub(rd!(op)); seta_c!(v, ((v as i32) < 0) as u32) }
                Inc => { let v = s.a + 1; seta_c!(v, (v > mask) as u32) }
                Dec => { let v = s.a.wrapping_sub(1); seta_c!(v, ((v as i32) < 0) as u32) }
                Neg => { let c = (s.a != 0) as u32; seta_c!(s.a.wrapping_neg(), c) }
                Shl => { let c = (s.a >> (w - 1)) & 1; seta_c!(s.a << 1, c) }
                Shr => { let c = s.a & 1; seta_c!(s.a >> 1, c) }
                Rol => seta!((s.a << 1) | (s.a >> (w - 1))),
                Ror => seta!((s.a >> 1) | ((s.a & 1) << (w - 1))),
                Rcl => { let c = (s.a >> (w - 1)) & 1; seta_c!((s.a << 1) | s.c, c) }
                Mul => seta!(s.a.wrapping_mul(rd!(op))),
                Swap => { let ta = s.a; let tt = rd!(op); wr!(op, ta); seta!(tt) }
                Jmp => s.pc = op & pmask,
                Jz => if s.z != 0 { s.pc = op & pmask },
                Jnz => if s.z == 0 { s.pc = op & pmask },
                Jc => if s.c != 0 { s.pc = op & pmask },
                Skz => if s.z != 0 { s.pc = (s.pc + 1) & pmask },
                Sknz => if s.z == 0 { s.pc = (s.pc + 1) & pmask },
                Incm => { let v = rd!(op) + 1; wr!(op, v) }
                Decm => { let v = rd!(op).wrapping_sub(1); wr!(op, v) }
                Ldind => { let ad = rd!(op); seta!(rd!(ad)) }
                Stind => { let ad = rd!(op); wr!(ad, s.a) }
            }
            if vis {
                let k = pack(cfg, &s);
                if sc.stamp[k as usize] == sc.cur {
                    let start = sc.hist.iter().position(|h| *h == k).unwrap();
                    let period = (t + 1) - start;
                    let idx = start + (MAX_STEPS - start) % period;
                    unpack(cfg, sc.hist[idx], &mut s);
                    return RunResult { a: s.a, steps: MAX_STEPS, end: End::Loop };
                }
                sc.stamp[k as usize] = sc.cur; sc.hist.push(k);
            }
            let _ = pc0;
        }
        RunResult { a: s.a, steps: MAX_STEPS, end: End::Budget }
    }

    /// Run program `pb` for 256 steps with A = x (M[1] = y if given) and return A at every `every`-th step
    /// (no cycle fast-forward; HALT freezes A for the remaining checkpoints).
    pub fn run_snapshots(&self, sc: &mut Scratch, pb: u64, x: u32, y: Option<u32>, every: usize) -> Vec<u32> {
        let cfg = self.cfg; sc.decoded = cfg.decode(pb);
        let mask = cfg.mask(); let amask = cfg.amask(); let pmask = cfg.pmask(); let w = cfg.w;
        let mut s = State { a: x & mask, z: 0, c: 0, pc: 0, m: vec![0; cfg.nm()] }; s.z = (s.a == 0) as u32;
        if let Some(y) = y { s.m[1] = y & mask; }
        let mut out = Vec::with_capacity(MAX_STEPS / every); let mut halted = false;
        for t in 1..=MAX_STEPS {
            if !halted {
                let (prim, op) = sc.decoded[(s.pc & pmask) as usize]; s.pc = (s.pc + 1) & pmask;
                let rd = |s: &State, a: u32| { let ad = a & amask; if ad == 0 { s.a } else { s.m[ad as usize] } };
                use Prim::*;
                match prim {
                    Nop => {}, Halt => halted = true,
                    Ld => { s.a = rd(&s, op); s.z = (s.a == 0) as u32 } St => { let ad = op & amask; if ad == 0 { } else { s.m[ad as usize] = s.a } }
                    Ldi => { s.a = op & mask; s.z = (s.a == 0) as u32 } Clr => { s.a = 0; s.z = 1 } Set => { s.a = mask; s.z = 0 }
                    Not => { s.a = !s.a & mask; s.z = (s.a == 0) as u32 }
                    And => { s.a &= rd(&s, op); s.z = (s.a == 0) as u32 } Or => { s.a |= rd(&s, op); s.z = (s.a == 0) as u32 } Xor => { s.a ^= rd(&s, op); s.z = (s.a == 0) as u32 }
                    Nand => { s.a = !(s.a & rd(&s, op)) & mask; s.z = (s.a == 0) as u32 } Nor => { s.a = !(s.a | rd(&s, op)) & mask; s.z = (s.a == 0) as u32 } Xnor => { s.a = !(s.a ^ rd(&s, op)) & mask; s.z = (s.a == 0) as u32 }
                    Add => { let v = s.a + rd(&s, op); s.a = v & mask; s.z = (s.a == 0) as u32; s.c = (v > mask) as u32 }
                    Adc => { let v = s.a + rd(&s, op) + s.c; s.a = v & mask; s.z = (s.a == 0) as u32; s.c = (v > mask) as u32 }
                    Sub => { let v = s.a.wrapping_sub(rd(&s, op)); s.a = v & mask; s.z = (s.a == 0) as u32; s.c = ((v as i32) < 0) as u32 }
                    Inc => { let v = s.a + 1; s.a = v & mask; s.z = (s.a == 0) as u32; s.c = (v > mask) as u32 }
                    Dec => { let v = s.a.wrapping_sub(1); s.a = v & mask; s.z = (s.a == 0) as u32; s.c = ((v as i32) < 0) as u32 }
                    Neg => { let c = (s.a != 0) as u32; s.a = s.a.wrapping_neg() & mask; s.z = (s.a == 0) as u32; s.c = c }
                    Shl => { let c = (s.a >> (w - 1)) & 1; s.a = (s.a << 1) & mask; s.z = (s.a == 0) as u32; s.c = c }
                    Shr => { let c = s.a & 1; s.a >>= 1; s.z = (s.a == 0) as u32; s.c = c }
                    Rol => { s.a = ((s.a << 1) | (s.a >> (w - 1))) & mask; s.z = (s.a == 0) as u32 } Ror => { s.a = ((s.a >> 1) | ((s.a & 1) << (w - 1))) & mask; s.z = (s.a == 0) as u32 }
                    Rcl => { let c = (s.a >> (w - 1)) & 1; s.a = ((s.a << 1) | s.c) & mask; s.z = (s.a == 0) as u32; s.c = c }
                    Mul => { s.a = s.a.wrapping_mul(rd(&s, op)) & mask; s.z = (s.a == 0) as u32 }
                    Swap => { let ta = s.a; let tt = rd(&s, op); let ad = op & amask; if ad != 0 { s.m[ad as usize] = ta & mask; } s.a = tt & mask; s.z = (s.a == 0) as u32 }
                    Jmp => s.pc = op & pmask, Jz => if s.z != 0 { s.pc = op & pmask }, Jnz => if s.z == 0 { s.pc = op & pmask }, Jc => if s.c != 0 { s.pc = op & pmask },
                    Skz => if s.z != 0 { s.pc = (s.pc + 1) & pmask }, Sknz => if s.z == 0 { s.pc = (s.pc + 1) & pmask },
                    Incm => { let ad = op & amask; let v = rd(&s, op) + 1; if ad == 0 { s.a = v & mask } else { s.m[ad as usize] = v & mask } }
                    Decm => { let ad = op & amask; let v = rd(&s, op).wrapping_sub(1); if ad == 0 { s.a = v & mask } else { s.m[ad as usize] = v & mask } }
                    Ldind => { let ad = rd(&s, op); s.a = rd(&s, ad); s.z = (s.a == 0) as u32 }
                    Stind => { let ad = rd(&s, op) & amask; if ad == 0 { } else { s.m[ad as usize] = s.a } }
                }
            }
            if t % every == 0 { out.push(s.a); }
        }
        out
    }

    /// Truth table of program `pb`: unary -> nin entries (x in A); binary -> nin*nin entries (x in A, y in M[1]).
    /// Also returns the maximum step count over all inputs and whether every input halted.
    pub fn table(&self, sc: &mut Scratch, pb: u64) -> (Vec<u8>, usize, bool) {
        let cfg = self.cfg;
        sc.decoded = cfg.decode(pb);
        let n = cfg.nin() as u32;
        let mut tbl = Vec::with_capacity(cfg.ntab());
        let mut max_steps = 0; let mut all_halt = true;
        if !cfg.binary {
            for x in 0..n { let r = self.run_decoded(sc, x, None); tbl.push(r.a as u8); max_steps = max_steps.max(r.steps); all_halt &= r.end == End::Halt; }
        } else {
            for x in 0..n { for y in 0..n { let r = self.run_decoded(sc, x, Some(y)); tbl.push(r.a as u8); max_steps = max_steps.max(r.steps); all_halt &= r.end == End::Halt; } }
        }
        (tbl, max_steps, all_halt)
    }
}

/// Shard key of a table: exact packing when it fits 128 bits, else the 2x64 mix hash (same as fast/u1.c).
pub fn table_key(tbl: &[u8], w: u32) -> (u64, u64) {
    let n = tbl.len();
    if n as u32 * w <= 128 {
        let (mut l, mut h) = (0u64, 0u64);
        for (i, &t) in tbl.iter().enumerate() {
            let sh = i as u32 * w;
            if sh < 64 { l |= (t as u64) << sh; if sh + w > 64 { h |= (t as u64) >> (64 - sh); } } else { h |= (t as u64) << (sh - 64); }
        }
        (l, h)
    } else {
        let (mut a, mut b) = (0x9E3779B97F4A7C15u64, 0xD1B54A32D192ED03u64);
        for &t in tbl { a = mix(a ^ t as u64); b = mix(b.wrapping_add((t as u64).wrapping_mul(0x100000001b3))); }
        (a, b)
    }
}
pub fn mix(mut x: u64) -> u64 {
    x ^= x >> 33; x = x.wrapping_mul(0xff51afd7ed558ccd); x ^= x >> 33; x = x.wrapping_mul(0xc4ceb9fe1a85ec53); x ^= x >> 33; x
}
