// Universe-1 exp06b kernel (CUDA): layout L2 (von Neumann). Code and data share one memory of 2^a words; the 2^p program words are
// loaded at M[0..2^p-1], fetch reads M[PC], so programs can rewrite themselves. Semantics = sim/machine_l2.py.
// Per program: the unary truth table A(x) at step 256 (or HALT), x = 0..15 -> same shard format as u1_cuda (distinct keys, min
// program); and, on the x = 0 run, the self-modification statistics (lessons of the Dimension42 NANO sweeps):
//   copy score = code words found position-wise in the copy window M[2^p..2^(p+1)-1] (pre-filled with code+1, so a match needs a
//   write): best over all steps and at the end; step of the first full copy and whether the code was still intact then; whether the
//   code was ever changed / differs at the end; walker = at least 4 writes into code that changed only the operand field.
// Output: <out> (function shard) and <out>.copy (text: histograms and counts, plus up to --max-copiers full copiers with flags).
// usage: u1_l2 --gpu g --W 4 --a 4 --p 3 --I 4 --isa LD,ST,LDIND,STIND,INCM,ADD,JNZ,HALT --lo L --hi H --out file [--cap-log2 22] [--max-copiers 100000]
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

struct Cfg { int W, a, p, I, o, nins, nM, nin; unsigned mask, amask, pmask, opmask; };
__constant__ Cfg C;
__constant__ unsigned char ISA[256];
#define MAX_STEPS 256
#define MAXM 16
#define EMPTY 0xFFFFFFFFFFFFFFFFull

__device__ __forceinline__ ull mix(ull x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }

struct Stats { int best, final, first_full, intact, ever_mod, final_mod, walker_writes; };
struct St { unsigned A, Z, Cf, PC; unsigned char M[MAXM]; unsigned char code[8]; Stats *S; int t; };
__device__ __forceinline__ unsigned rd(St &s, unsigned addr) { return s.M[addr & C.amask]; }
__device__ __forceinline__ int score(St &s) { int sc = 0; for (int k = 0; k < C.nins; k++) sc += s.M[C.nins + k] == s.code[k]; return sc; }
__device__ __forceinline__ void wr(St &s, unsigned addr, unsigned v) {
  addr &= C.amask; v &= C.mask; unsigned old = s.M[addr]; s.M[addr] = (unsigned char)v;
  if (!s.S) return;
  if (addr < (unsigned)C.nins) { if (old != v) { s.S->ever_mod = 1; if ((old >> (C.I - C.o)) == (v >> (C.I - C.o))) s.S->walker_writes++; } }
  else { int sc = score(s); if (sc > s.S->best) { s.S->best = sc; if (sc == C.nins) { s.S->first_full = s.t + 1; int ok = 1; for (int k = 0; k < C.nins; k++) ok &= s.M[k] == s.code[k]; s.S->intact = ok; } } }
}
__device__ __forceinline__ void setA(St &s, unsigned v) { s.A = v & C.mask; s.Z = (s.A == 0); }

// runs program pb with A = x (y into M[nins] if have_y); S != nullptr collects the exp06b statistics; returns final A
__device__ unsigned run(ull pb, unsigned x, unsigned y, int have_y, Stats *S) {
  St s; s.A = x & C.mask; s.Z = (s.A == 0); s.Cf = 0; s.PC = 0; s.S = S; s.t = 0;
  for (int i = 0; i < C.nM; i++) s.M[i] = 0;
  for (int k = 0; k < C.nins; k++) { unsigned char c = (unsigned char)((pb >> (k * C.I)) & ((1u << C.I) - 1)); s.code[k] = c; s.M[k] = c; s.M[C.nins + k] = (c + 1) & C.mask; }
  if (have_y) s.M[C.nins] = y & C.mask;
  if (S) { S->best = S->final = S->first_full = S->intact = S->ever_mod = S->final_mod = S->walker_writes = 0; }
  int halted = 0;
  for (int t = 0; t < MAX_STEPS && !halted; t++) {
    s.t = t;
    unsigned ins = s.M[s.PC & C.pmask], opc = ISA[ins >> (C.I - C.o)], op = ins & C.opmask;
    s.PC = (s.PC + 1) & C.pmask; unsigned v, cy;
    switch (opc) {
    case P_NOP: break;
    case P_HALT: halted = 1; break;
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
    case P_ADD: v = s.A + rd(s, op); setA(s, v); s.Cf = v > C.mask; break;
    case P_ADC: v = s.A + rd(s, op) + s.Cf; setA(s, v); s.Cf = v > C.mask; break;
    case P_SUB: v = s.A - rd(s, op); cy = (int)v < 0; setA(s, v); s.Cf = cy; break;
    case P_INC: v = s.A + 1; setA(s, v); s.Cf = v > C.mask; break;
    case P_DEC: v = s.A - 1; cy = (int)v < 0; setA(s, v); s.Cf = cy; break;
    case P_NEG: cy = s.A != 0; setA(s, -s.A); s.Cf = cy; break;
    case P_SHL: cy = (s.A >> (C.W - 1)) & 1; setA(s, s.A << 1); s.Cf = cy; break;
    case P_SHR: cy = s.A & 1; setA(s, s.A >> 1); s.Cf = cy; break;
    case P_ROL: setA(s, (s.A << 1) | (s.A >> (C.W - 1))); break;
    case P_ROR: setA(s, (s.A >> 1) | ((s.A & 1) << (C.W - 1))); break;
    case P_RCL: cy = (s.A >> (C.W - 1)) & 1; setA(s, (s.A << 1) | s.Cf); s.Cf = cy; break;
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
  }
  if (S) { S->final = score(s); int same = 1; for (int k = 0; k < C.nins; k++) same &= s.M[k] == s.code[k]; S->final_mod = !same; }
  return s.A;
}

__device__ void table_key(const unsigned char *tbl, ull &lo, ull &hi) {
  int n = C.nin, W = C.W; ull l = 0, h = 0;
  for (int i = 0; i < n; i++) { int sh = i * W; if (sh < 64) { l |= (ull)tbl[i] << sh; if (sh + W > 64) h |= (ull)tbl[i] >> (64 - sh); } else h |= (ull)tbl[i] << (sh - 64); }
  lo = l; hi = h;
}

// counters: cnt[0..15] final-score histogram, cnt[16..31] best-score histogram, cnt[32] ever_mod, cnt[33] final_mod, cnt[34] walkers,
// cnt[35] full copiers ever, cnt[36] full copiers at the end, cnt[37] intact copiers, cnt[64..320] first-full-copy step histogram;
// cmin[0..15] min program per final score, cmin[16..31] per best score, cmin[32] min intact copier.
// copiers[]: (program, first_full | intact << 9 | persists << 10) pairs for full copiers (ever), up to max_copiers. misc: sentinel key + overflow + copier count.
__global__ void sweep(ull lo, ull count, ull *keys, ull *his, unsigned *progs, unsigned cap_log2, unsigned *misc, unsigned *cnt, unsigned *cmin, unsigned *copiers, unsigned max_copiers) {
  ull i = blockIdx.x * (ull)blockDim.x + threadIdx.x;
  if (i >= count) return;
  ull pb = lo + i; unsigned prog = (unsigned)pb;
  unsigned char tbl[16]; Stats S;
  for (int x = 0; x < C.nin; x++) tbl[x] = run(pb, x, 0, 0, nullptr);
  run(pb, 0, 0, 0, &S);
  atomicAdd(&cnt[S.final], 1u); atomicMin(&cmin[S.final], prog); atomicAdd(&cnt[16 + S.best], 1u); atomicMin(&cmin[16 + S.best], prog);
  if (S.ever_mod) atomicAdd(&cnt[32], 1u); if (S.final_mod) atomicAdd(&cnt[33], 1u); if (S.walker_writes >= 4) atomicAdd(&cnt[34], 1u);
  if (S.best == C.nins) {
    atomicAdd(&cnt[35], 1u); atomicAdd(&cnt[64 + S.first_full], 1u);
    if (S.final == C.nins) atomicAdd(&cnt[36], 1u);
    if (S.intact) { atomicAdd(&cnt[37], 1u); atomicMin(&cmin[32], prog); }
    unsigned slot = atomicAdd(&misc[3], 1u); if (slot < max_copiers) { copiers[2 * slot] = prog; copiers[2 * slot + 1] = (unsigned)S.first_full | ((unsigned)S.intact << 9) | ((unsigned)(S.final == C.nins) << 10); }
  }
  ull klo, khi; table_key(tbl, klo, khi);
  if (klo == EMPTY) { atomicMin(&misc[0], prog); misc[1] = 1; return; }
  ull mask = (1ull << cap_log2) - 1, h = mix(klo ^ mix(khi)) & mask;
  for (unsigned probe = 0; probe < 4096; probe++) {
    ull old = atomicCAS(&keys[h], EMPTY, klo);
    if (old == EMPTY || old == klo) { if (old == EMPTY) his[h] = khi; atomicMin(&progs[h], prog); return; }
    h = (h + 1) & mask;
  }
  atomicAdd(&misc[2], 1u);
}

int main(int argc, char **argv) {
  Cfg c; memset(&c, 0, sizeof c); c.W = 4; c.a = 4; c.p = 3; c.I = 4;
  const char *isa_s = nullptr, *out = nullptr; int gpu = 0; ull lo = 0, hi = 0; int have = 0; unsigned cap_log2 = 22, max_copiers = 100000;
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--W")) c.W = atoi(argv[++i]); else if (ARG("--a")) c.a = atoi(argv[++i]); else if (ARG("--p")) c.p = atoi(argv[++i]); else if (ARG("--I")) c.I = atoi(argv[++i]);
    else if (ARG("--isa")) isa_s = argv[++i]; else if (ARG("--out")) out = argv[++i]; else if (ARG("--gpu")) gpu = atoi(argv[++i]);
    else if (ARG("--cap-log2")) cap_log2 = atoi(argv[++i]); else if (ARG("--max-copiers")) max_copiers = atoi(argv[++i]);
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have = 1; } else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have = 1; }
    else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  if (!isa_s || !out) { fprintf(stderr, "need --isa and --out\n"); return 2; }
  c.mask = (1u << c.W) - 1; c.amask = (1u << c.a) - 1; c.pmask = (1u << c.p) - 1; c.nins = 1 << c.p; c.nM = 1 << c.a; c.nin = 1 << c.W;
  if (c.nM > MAXM || 2 * c.nins > c.nM || c.nins > 8 || c.I != c.W || c.nin * c.W > 128) { fprintf(stderr, "limits: a<=4, 2*2^p <= 2^a, 2^p <= 8, I == W <= 4\n"); return 2; }
  unsigned char isa[256]; int nisa = 0; char buf[2048]; strncpy(buf, isa_s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
  for (char *t = strtok(buf, ","); t; t = strtok(nullptr, ",")) { int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(t, PNAME[k])) id = k;
    if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa++] = id; }
  if (nisa & (nisa - 1)) { fprintf(stderr, "ISA length must be power of two\n"); return 2; }
  c.o = 0; while ((1 << c.o) < nisa) c.o++; if (c.o == 0) c.o = 1;
  if (c.o > c.I) { fprintf(stderr, "opcode bits > I\n"); return 2; }
  c.opmask = (1u << (c.I - c.o)) - 1;
  int pbits = c.nins * c.I; ull total = pbits >= 64 ? UINT64_MAX : (1ull << pbits); if (!have) { lo = 0; hi = total; }

  cudaSetDevice(gpu); cudaDeviceProp prop; cudaGetDeviceProperties(&prop, gpu);
  cudaMemcpyToSymbol(C, &c, sizeof c); cudaMemcpyToSymbol(ISA, isa, 256);
  const int NCNT = 64 + MAX_STEPS + 2, NMIN = 40;
  ull cap = 1ull << cap_log2; ull *d_keys, *d_his; unsigned *d_progs, *d_misc, *d_cnt, *d_cmin, *d_cop;
  cudaMalloc(&d_keys, cap * 8); cudaMalloc(&d_his, cap * 8); cudaMalloc(&d_progs, cap * 4); cudaMalloc(&d_misc, 16);
  cudaMalloc(&d_cnt, NCNT * 4); cudaMalloc(&d_cmin, NMIN * 4); cudaMalloc(&d_cop, (size_t)max_copiers * 8);
  cudaMemset(d_keys, 0xFF, cap * 8); cudaMemset(d_progs, 0xFF, cap * 4); cudaMemset(d_misc, 0xFF, 4); cudaMemset(d_misc + 1, 0, 12);
  cudaMemset(d_cnt, 0, NCNT * 4); cudaMemset(d_cmin, 0xFF, NMIN * 4);
  auto t0 = std::chrono::steady_clock::now();
  const ull SUB = 1ull << 26;
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
#ifdef EMU_LAUNCH
    EMU_LAUNCH(sweep, (unsigned)((n + 127) / 128), 128, off, n, d_keys, d_his, d_progs, cap_log2, d_misc, d_cnt, d_cmin, d_cop, max_copiers);
#else
    sweep<<<(unsigned)((n + 127) / 128), 128>>>(off, n, d_keys, d_his, d_progs, cap_log2, d_misc, d_cnt, d_cmin, d_cop, max_copiers);
#endif
    cudaError_t e = cudaDeviceSynchronize(); if (e != cudaSuccess) { fprintf(stderr, "ERROR %s\n", cudaGetErrorString(e)); return 1; }
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::vector<ull> keys(cap), his(cap); std::vector<unsigned> progs(cap), cnt(NCNT), cmin(NMIN); unsigned misc[4];
  cudaMemcpy(keys.data(), d_keys, cap * 8, cudaMemcpyDeviceToHost); cudaMemcpy(his.data(), d_his, cap * 8, cudaMemcpyDeviceToHost);
  cudaMemcpy(progs.data(), d_progs, cap * 4, cudaMemcpyDeviceToHost); cudaMemcpy(misc, d_misc, 16, cudaMemcpyDeviceToHost);
  cudaMemcpy(cnt.data(), d_cnt, NCNT * 4, cudaMemcpyDeviceToHost); cudaMemcpy(cmin.data(), d_cmin, NMIN * 4, cudaMemcpyDeviceToHost);
  unsigned ncop = misc[3] < max_copiers ? misc[3] : max_copiers; std::vector<unsigned> cop(2 * (size_t)ncop); if (ncop) cudaMemcpy(cop.data(), d_cop, (size_t)ncop * 8, cudaMemcpyDeviceToHost);
  if (misc[2]) { fprintf(stderr, "ERROR hash table overflow (%u programs dropped); rerun with --cap-log2 %u or a smaller range\n", misc[2], cap_log2 + 1); return 1; }
  ull n = misc[1] ? 1 : 0; for (ull i = 0; i < cap; i++) n += keys[i] != EMPTY;
  FILE *f = fopen(out, "wb"); if (!f) { perror(out); return 1; }
  unsigned hdr[8] = { 0x55314231u, (unsigned)c.W, (unsigned)c.a, (unsigned)c.p, (unsigned)c.I, (unsigned)c.o, 0u, (unsigned)nisa };
  fwrite(hdr, 4, 8, f); fwrite(&lo, 8, 1, f); fwrite(&hi, 8, 1, f); fwrite(&n, 8, 1, f); fwrite(isa, 1, nisa, f);
  for (ull i = 0; i < cap; i++) if (keys[i] != EMPTY) { fwrite(&keys[i], 8, 1, f); fwrite(&his[i], 8, 1, f); fwrite(&progs[i], 4, 1, f); }
  if (misc[1]) { ull k = EMPTY, h = 0; fwrite(&k, 8, 1, f); fwrite(&h, 8, 1, f); fwrite(&misc[0], 4, 1, f); }
  fclose(f);
  std::string cp = std::string(out) + ".copy"; FILE *g = fopen(cp.c_str(), "w"); if (!g) { perror(cp.c_str()); return 1; }
  fprintf(g, "layout L2 isa %s programs [%llu,%llu) copy window M[%d..%d] stats run x=0\n", isa_s, lo, hi, c.nins, 2 * c.nins - 1);
  for (int sc = 0; sc <= c.nins; sc++) fprintf(g, "final %d count %u min_program 0x%08x\n", sc, cnt[sc], cmin[sc]);
  for (int sc = 0; sc <= c.nins; sc++) fprintf(g, "best %d count %u min_program 0x%08x\n", sc, cnt[16 + sc], cmin[16 + sc]);
  fprintf(g, "ever_mod %u final_mod %u walkers %u copiers_ever %u copiers_final %u copiers_intact %u min_intact_copier 0x%08x\n", cnt[32], cnt[33], cnt[34], cnt[35], cnt[36], cnt[37], cmin[32]);
  fprintf(g, "first_full_hist"); for (int t = 0; t <= MAX_STEPS; t++) if (cnt[64 + t]) fprintf(g, " %d:%u", t, cnt[64 + t]); fprintf(g, "\n");
  fprintf(g, "listed %u\n", ncop); for (unsigned i = 0; i < ncop; i++) fprintf(g, "copier 0x%08x first %u intact %u persists %u\n", cop[2 * i], cop[2 * i + 1] & 511, (cop[2 * i + 1] >> 9) & 1, (cop[2 * i + 1] >> 10) & 1);
  fclose(g);
  fprintf(stderr, "L2 W=%d a=%d p=%d I=%d o=%d isa=%s programs=[%llu,%llu) distinct=%llu copiers_ever=%u intact=%u %.2fs (%.1f Mprog/s) %s\n", c.W, c.a, c.p, c.I, c.o, isa_s, lo, hi, n, cnt[35], cnt[37], secs, (hi - lo) / secs / 1e6, prop.name);
  printf("%llu\n", n);
  return 0;
}
