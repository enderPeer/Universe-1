// Universe-1 exp09/exp10 kernel (CUDA): the truth table of every program at EVERY step T in [T_lo, T_hi] (T <= 512), not only at step 256.
// Same machine semantics and shard format as gpu/u1_cuda.cu; one shard file per checkpoint T: <out>.T<nnn>.bin.
// usage: u1_multi --gpu g --W w --a a --p p --I i --isa SWAP,ADD,... [--binary] --lo L --hi H --T-lo 1 --T-hi 64 --out prefix
// Checkpoint semantics = mapper `u1map budgets --every 1`: A after exactly T steps; HALT (or a fixed point) freezes A.
// Per program one thread runs all inputs once, records A at every checkpoint, then inserts each checkpoint's table into
// that checkpoint's own hash table (keys[T], his[T], progs[T] = minimum program id). Unary: up to 64 checkpoints per pass
// (64 x 16 B of local memory per thread); binary: up to 4 checkpoints per pass (256-entry tables).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <string>
#include <vector>
typedef unsigned long long ull;

enum { P_NOP, P_HALT, P_LD, P_ST, P_LDI, P_CLR, P_SET, P_NOT, P_AND, P_OR, P_XOR,
       P_NAND, P_NOR, P_XNOR, P_ADD, P_ADC, P_SUB, P_INC, P_DEC, P_NEG, P_SHL, P_SHR,
       P_ROL, P_ROR, P_RCL, P_MUL, P_SWAP, P_JMP, P_JZ, P_JNZ, P_JC, P_SKZ, P_SKNZ,
       P_INCM, P_DECM, P_LDIND, P_STIND, P_COUNT };
static const char *PNAME[P_COUNT] = {
  "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR",
  "ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP",
  "JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND" };

struct Cfg { int W, a, p, I, o, binary, nins, nM, nin, ntab, Tlo, nT; unsigned mask, amask, pmask, opmask; };
__constant__ Cfg C;
__constant__ unsigned char ISA[256];
#define MAX_STEPS 512     // exp10: the clock runs to 512; T-hi selects how far a pass simulates
#define MAXM 16
#define MAXTBL 4096      // checkpoints x table entries held per thread (64 x 16 unary, 16 x 256 binary)
#define EMPTY 0xFFFFFFFFFFFFFFFFull

__device__ __forceinline__ ull mix(ull x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }

struct St { unsigned A, Z, Cf, PC, chg; unsigned M[MAXM]; };
__device__ __forceinline__ unsigned rd(St &s, unsigned addr) { addr &= C.amask; return addr == 0 ? s.A : s.M[addr]; }
__device__ __forceinline__ void wr(St &s, unsigned addr, unsigned v) {
  addr &= C.amask; v &= C.mask;
  if (addr == 0) { s.chg |= (s.A != v); s.A = v; } else { s.chg |= (s.M[addr] != v); s.M[addr] = v; }
}
__device__ __forceinline__ void setA(St &s, unsigned v) {
  v &= C.mask; s.chg |= (s.A != v); s.A = v; unsigned z = (v == 0); s.chg |= (s.Z != z); s.Z = z;
}
__device__ __forceinline__ void setC(St &s, unsigned cy) { s.chg |= (s.Cf != cy); s.Cf = cy; }

// Runs up to MAX_STEPS steps; writes A after step t into snap[(t - Tlo) * stride] for Tlo <= t <= Tlo + nT - 1.
// On HALT or a fixed point the remaining checkpoints receive the frozen A.
__device__ void run_snap(const unsigned char *opc, const unsigned char *opnd, unsigned initA, unsigned y, int have_y, unsigned char *snap, int stride) {
  St s; s.A = initA & C.mask; s.Z = (s.A == 0); s.Cf = 0; s.PC = 0;
  for (int i = 0; i < C.nM; i++) s.M[i] = 0;
  if (have_y) s.M[1] = y;
  int Thi = C.Tlo + C.nT - 1;
  for (int t = 1; t <= Thi; t++) {
    unsigned pc0 = s.PC, k = s.PC & C.pmask, op = opnd[k];
    s.PC = (s.PC + 1) & C.pmask; s.chg = 0;
    unsigned v, cy; int stop = 0;
    switch (opc[k]) {
    case P_NOP: break;
    case P_HALT: stop = 1; break;
    case P_LD: setA(s, rd(s, op)); break;
    case P_ST: wr(s, op, s.A); break;
    case P_LDI: setA(s, op); break;
    case P_CLR: setA(s, 0); break;
    case P_SET: setA(s, C.mask); break;
    case P_NOT: setA(s, ~s.A); break;
    case P_AND: setA(s, s.A & rd(s, op)); break;
    case P_OR: setA(s, s.A | rd(s, op)); break;
    case P_XOR: setA(s, s.A ^ rd(s, op)); break;
    case P_NAND: setA(s, ~(s.A & rd(s, op))); break;
    case P_NOR: setA(s, ~(s.A | rd(s, op))); break;
    case P_XNOR: setA(s, ~(s.A ^ rd(s, op))); break;
    case P_ADD: v = s.A + rd(s, op); setA(s, v); setC(s, v > C.mask); break;
    case P_ADC: v = s.A + rd(s, op) + s.Cf; setA(s, v); setC(s, v > C.mask); break;
    case P_SUB: v = s.A - rd(s, op); cy = (int)v < 0; setA(s, v); setC(s, cy); break;
    case P_INC: v = s.A + 1; setA(s, v); setC(s, v > C.mask); break;
    case P_DEC: v = s.A - 1; cy = (int)v < 0; setA(s, v); setC(s, cy); break;
    case P_NEG: cy = s.A != 0; setA(s, -s.A); setC(s, cy); break;
    case P_SHL: cy = (s.A >> (C.W - 1)) & 1; setA(s, s.A << 1); setC(s, cy); break;
    case P_SHR: cy = s.A & 1; setA(s, s.A >> 1); setC(s, cy); break;
    case P_ROL: setA(s, (s.A << 1) | (s.A >> (C.W - 1))); break;
    case P_ROR: setA(s, (s.A >> 1) | ((s.A & 1) << (C.W - 1))); break;
    case P_RCL: cy = (s.A >> (C.W - 1)) & 1; setA(s, (s.A << 1) | s.Cf); setC(s, cy); break;
    case P_MUL: setA(s, s.A * rd(s, op)); break;
    case P_SWAP: { unsigned tA = s.A, tt = rd(s, op); wr(s, op, tA); setA(s, tt); } break;
    case P_JMP: s.PC = op & C.pmask; break;
    case P_JZ: if (s.Z) s.PC = op & C.pmask; break;
    case P_JNZ: if (!s.Z) s.PC = op & C.pmask; break;
    case P_JC: if (s.Cf) s.PC = op & C.pmask; break;
    case P_SKZ: if (s.Z) s.PC = (s.PC + 1) & C.pmask; break;
    case P_SKNZ: if (!s.Z) s.PC = (s.PC + 1) & C.pmask; break;
    case P_INCM: wr(s, op, rd(s, op) + 1); break;
    case P_DECM: wr(s, op, rd(s, op) - 1); break;
    case P_LDIND: setA(s, rd(s, rd(s, op))); break;
    case P_STIND: wr(s, rd(s, op), s.A); break;
    }
    if (!stop && !s.chg && s.PC == pc0) stop = 1;   // fixed point: nothing changes from here on
    if (stop) { for (int u = (t > C.Tlo ? t : C.Tlo); u <= Thi; u++) snap[(u - C.Tlo) * stride] = s.A; return; }
    if (t >= C.Tlo) snap[(t - C.Tlo) * stride] = s.A;
  }
}

__device__ void table_key(const unsigned char *tbl, ull &lo, ull &hi) {
  int n = C.ntab, W = C.W;
  if (n * W <= 128) {
    ull l = 0, h = 0;
    for (int i = 0; i < n; i++) { int sh = i * W;
      if (sh < 64) { l |= (ull)tbl[i] << sh; if (sh + W > 64) h |= (ull)tbl[i] >> (64 - sh); }
      else h |= (ull)tbl[i] << (sh - 64); }
    lo = l; hi = h; return;
  }
  ull a = 0x9E3779B97F4A7C15ULL, b = 0xD1B54A32D192ED03ULL;
  for (int i = 0; i < n; i++) { a = mix(a ^ tbl[i]); b = mix(b + tbl[i] * 0x100000001b3ULL); }
  lo = a; hi = b;
}

// per checkpoint j: keys[j*cap..], his, progs; misc[j*4 + 0] = min program with the sentinel key, [1] = sentinel seen, [2] = overflow count
__global__ void sweep(ull lo, ull count, ull *keys, ull *his, unsigned *progs, unsigned cap_log2, unsigned *misc) {
  ull i = blockIdx.x * (ull)blockDim.x + threadIdx.x;
  if (i >= count) return;
  ull pb = lo + i;
  unsigned char opc[256], opnd[256], tbl[MAXTBL];   // tbl[j * ntab + input]
  for (int k = 0; k < C.nins; k++) {
    unsigned ins = (unsigned)((pb >> (k * C.I)) & ((1u << C.I) - 1));
    opc[k] = ISA[ins >> (C.I - C.o)]; opnd[k] = ins & C.opmask;
  }
  int ntab = C.ntab;
  if (!C.binary) for (int x = 0; x < C.nin; x++) run_snap(opc, opnd, x, 0, 0, tbl + x, ntab);
  else for (int x = 0; x < C.nin; x++) for (int y = 0; y < C.nin; y++) run_snap(opc, opnd, x, y, 1, tbl + x * C.nin + y, ntab);
  ull cap = 1ull << cap_log2, mask = cap - 1; unsigned prog = (unsigned)pb;
  for (int j = 0; j < C.nT; j++) {
    ull klo, khi; table_key(tbl + j * ntab, klo, khi);
    ull *K = keys + j * cap, *H = his + j * cap; unsigned *P = progs + j * cap, *M = misc + j * 4;
    if (klo == EMPTY) { atomicMin(&M[0], prog); M[1] = 1; continue; }
    ull h = mix(klo ^ mix(khi)) & mask; bool done = false;
    for (unsigned probe = 0; probe < 4096; probe++) {
      ull old = atomicCAS(&K[h], EMPTY, klo);
      if (old == EMPTY || old == klo) { if (old == EMPTY) H[h] = khi; atomicMin(&P[h], prog); done = true; break; }
      h = (h + 1) & mask;
    }
    if (!done) atomicAdd(&M[2], 1u);
  }
}

int main(int argc, char **argv) {
  Cfg c; memset(&c, 0, sizeof c); c.W = 4; c.a = 2; c.p = 3; c.I = -1; c.Tlo = 1; int Thi = 64;
  const char *isa_s = nullptr, *out = nullptr; int gpu = 0; ull lo = 0, hi = 0; int have = 0; unsigned cap_log2 = 21;
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--W")) c.W = atoi(argv[++i]); else if (ARG("--a")) c.a = atoi(argv[++i]);
    else if (ARG("--p")) c.p = atoi(argv[++i]); else if (ARG("--I")) c.I = atoi(argv[++i]);
    else if (ARG("--isa")) isa_s = argv[++i]; else if (ARG("--out")) out = argv[++i];
    else if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--cap-log2")) cap_log2 = atoi(argv[++i]);
    else if (ARG("--T-lo")) c.Tlo = atoi(argv[++i]); else if (ARG("--T-hi")) Thi = atoi(argv[++i]);
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have = 1; } else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have = 1; }
    else if (!strcmp(argv[i], "--binary")) c.binary = 1;
    else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  if (!isa_s || !out) { fprintf(stderr, "need --isa and --out\n"); return 2; }
  if (c.I < 0) c.I = c.W;
  c.mask = (1u << c.W) - 1; c.amask = (1u << c.a) - 1; c.pmask = (1u << c.p) - 1; c.nins = 1 << c.p; c.nM = 1 << c.a; c.nin = 1 << c.W;
  c.ntab = c.binary ? c.nin * c.nin : c.nin; c.nT = Thi - c.Tlo + 1;
  if (c.Tlo < 1 || Thi > MAX_STEPS || c.nT < 1 || c.nT * c.ntab > MAXTBL) { fprintf(stderr, "checkpoint range must satisfy 1 <= T-lo <= T-hi <= 512 and nT * table entries <= %d\n", MAXTBL); return 2; }
  if (c.nM > MAXM || c.ntab > 256 || c.nins > 256) { fprintf(stderr, "config exceeds compiled limits (a<=4, table<=256, instr<=256)\n"); return 2; }
  unsigned char isa[256]; int nisa = 0; char buf[2048]; strncpy(buf, isa_s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
  for (char *t = strtok(buf, ","); t; t = strtok(nullptr, ",")) { int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(t, PNAME[k])) id = k;
    if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa++] = id; }
  if (nisa & (nisa - 1)) { fprintf(stderr, "ISA length must be power of two\n"); return 2; }
  c.o = 0; while ((1 << c.o) < nisa) c.o++; if (c.o == 0) c.o = 1;
  if (c.o > c.I) { fprintf(stderr, "opcode bits > I\n"); return 2; }
  c.opmask = (1u << (c.I - c.o)) - 1;
  int pbits = c.nins * c.I; if (pbits > 64) { fprintf(stderr, "program bits > 64\n"); return 2; }
  ull total = pbits == 64 ? UINT64_MAX : (1ull << pbits); if (!have) { lo = 0; hi = total; }

  cudaSetDevice(gpu); cudaDeviceProp prop; cudaGetDeviceProperties(&prop, gpu);
  cudaMemcpyToSymbol(C, &c, sizeof c); cudaMemcpyToSymbol(ISA, isa, 256);
  ull cap = 1ull << cap_log2, nT = c.nT; ull *d_keys, *d_his; unsigned *d_progs, *d_misc;
  if (cudaMalloc(&d_keys, nT * cap * 8) || cudaMalloc(&d_his, nT * cap * 8) || cudaMalloc(&d_progs, nT * cap * 4) || cudaMalloc(&d_misc, nT * 16)) { fprintf(stderr, "ERROR out of GPU memory for %llu tables of 2^%u slots\n", nT, cap_log2); return 1; }
  cudaMemset(d_keys, 0xFF, nT * cap * 8); cudaMemset(d_progs, 0xFF, nT * cap * 4);
  std::vector<unsigned> misc0(nT * 4, 0); for (ull j = 0; j < nT; j++) misc0[j * 4] = 0xFFFFFFFFu;
  cudaMemcpy(d_misc, misc0.data(), nT * 16, cudaMemcpyHostToDevice);
  auto t0 = std::chrono::steady_clock::now();
  const ull SUB = 1ull << 26;
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
#ifdef EMU_LAUNCH
    EMU_LAUNCH(sweep, (unsigned)((n + 127) / 128), 128, off, n, d_keys, d_his, d_progs, cap_log2, d_misc);
#else
    sweep<<<(unsigned)((n + 127) / 128), 128>>>(off, n, d_keys, d_his, d_progs, cap_log2, d_misc);
#endif
    cudaError_t e = cudaDeviceSynchronize(); if (e != cudaSuccess) { fprintf(stderr, "ERROR %s\n", cudaGetErrorString(e)); return 1; }
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::vector<ull> keys(cap), his(cap); std::vector<unsigned> progs(cap), misc(nT * 4);
  cudaMemcpy(misc.data(), d_misc, nT * 16, cudaMemcpyDeviceToHost);
  std::string prefix = out; if (prefix.size() > 4 && prefix.substr(prefix.size() - 4) == ".bin") prefix.resize(prefix.size() - 4);
  ull total_records = 0;
  for (ull j = 0; j < nT; j++) {
    unsigned *M = &misc[j * 4];
    if (M[2]) { fprintf(stderr, "ERROR hash table overflow at T=%llu (%u programs dropped); rerun with --cap-log2 %u or a smaller range\n", c.Tlo + j, M[2], cap_log2 + 1); return 1; }
    cudaMemcpy(keys.data(), d_keys + j * cap, cap * 8, cudaMemcpyDeviceToHost); cudaMemcpy(his.data(), d_his + j * cap, cap * 8, cudaMemcpyDeviceToHost);
    cudaMemcpy(progs.data(), d_progs + j * cap, cap * 4, cudaMemcpyDeviceToHost);
    ull n = M[1] ? 1 : 0; for (ull i = 0; i < cap; i++) n += keys[i] != EMPTY;
    char name[4096]; snprintf(name, sizeof name, "%s.T%03llu.bin", prefix.c_str(), c.Tlo + j);
    FILE *f = fopen(name, "wb"); if (!f) { perror(name); return 1; }
    unsigned hdr[8] = { 0x55314231u, (unsigned)c.W, (unsigned)c.a, (unsigned)c.p, (unsigned)c.I, (unsigned)c.o, (unsigned)c.binary, (unsigned)nisa };
    fwrite(hdr, 4, 8, f); fwrite(&lo, 8, 1, f); fwrite(&hi, 8, 1, f); fwrite(&n, 8, 1, f); fwrite(isa, 1, nisa, f);
    for (ull i = 0; i < cap; i++) if (keys[i] != EMPTY) { fwrite(&keys[i], 8, 1, f); fwrite(&his[i], 8, 1, f); fwrite(&progs[i], 4, 1, f); }
    if (M[1]) { ull k = EMPTY, h = 0; fwrite(&k, 8, 1, f); fwrite(&h, 8, 1, f); fwrite(&M[0], 4, 1, f); }
    fclose(f); total_records += n;
  }
  fprintf(stderr, "W=%d a=%d p=%d I=%d o=%d isa=%s %s programs=[%llu,%llu) T=[%d,%d] records=%llu %.2fs (%.1f Mprog/s) %s\n", c.W, c.a, c.p, c.I, c.o, isa_s,
          c.binary ? "binary" : "unary", lo, hi, c.Tlo, Thi, total_records, secs, (hi - lo) / secs / 1e6, prop.name);
  printf("%llu\n", total_records);
  return 0;
}
