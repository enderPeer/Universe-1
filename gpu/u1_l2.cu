// Universe-1 exp06b kernel (CUDA): layout L2 (von Neumann). Code and data share one memory of 2^a words; the 2^p program words are
// loaded at M[0..2^p-1], fetch reads M[PC], so programs can rewrite themselves. Semantics = sim/machine_l2.py.
// Per program (unary): the truth table A(x) at step 256 (or HALT) for x = 0..15 -> same shard format as u1_cuda (distinct keys,
// min program); plus the self-copy test with x = 0: how many of the 2^p code words reappear position-wise at M[2^p..2^(p+1)-1]
// after the run (0..2^p). Output: <out> (function shard) and <out>.copy (text: histogram of copy scores with the minimum program id
// per score, and up to --max-copiers program ids with a full copy).
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

struct St { unsigned A, Z, Cf, PC; unsigned char M[MAXM]; };
__device__ __forceinline__ unsigned rd(St &s, unsigned addr) { return s.M[addr & C.amask]; }
__device__ __forceinline__ void wr(St &s, unsigned addr, unsigned v) { s.M[addr & C.amask] = v & C.mask; }
__device__ __forceinline__ void setA(St &s, unsigned v) { s.A = v & C.mask; s.Z = (s.A == 0); }

// runs program pb with A = x (y into M[nins] if have_y); returns final A, fills mem with the final memory, steps with the step count
__device__ unsigned run(ull pb, unsigned x, unsigned y, int have_y, unsigned char *mem, unsigned *steps) {
  St s; s.A = x & C.mask; s.Z = (s.A == 0); s.Cf = 0; s.PC = 0;
  for (int i = 0; i < C.nM; i++) s.M[i] = 0;
  for (int k = 0; k < C.nins; k++) { unsigned char c = (unsigned char)((pb >> (k * C.I)) & ((1u << C.I) - 1)); s.M[k] = c; s.M[C.nins + k] = (c + 1) & C.mask; }  // copy window pre-filled so that it differs from the code at every word: a match needs a write
  if (have_y) s.M[C.nins] = y & C.mask;
  for (int t = 0; t < MAX_STEPS; t++) {
    unsigned ins = s.M[s.PC & C.pmask], opc = ISA[ins >> (C.I - C.o)], op = ins & C.opmask;
    s.PC = (s.PC + 1) & C.pmask; unsigned v, cy;
    switch (opc) {
    case P_NOP: break;
    case P_HALT: *steps = t + 1; for (int i = 0; i < C.nM; i++) mem[i] = s.M[i]; return s.A;
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
  *steps = MAX_STEPS; for (int i = 0; i < C.nM; i++) mem[i] = s.M[i]; return s.A;
}

__device__ void table_key(const unsigned char *tbl, ull &lo, ull &hi) {
  int n = C.nin, W = C.W; ull l = 0, h = 0;
  for (int i = 0; i < n; i++) { int sh = i * W; if (sh < 64) { l |= (ull)tbl[i] << sh; if (sh + W > 64) h |= (ull)tbl[i] >> (64 - sh); } else h |= (ull)tbl[i] << (sh - 64); }
  lo = l; hi = h;
}

// keys/his/progs: function hash table; copy_min[score] = min program with that copy score (atomicMin), copy_cnt[score] = count;
// copiers[]: program ids with a full copy (up to max_copiers); misc[0..2] sentinel-key bookkeeping, misc[3] = copier count
__global__ void sweep(ull lo, ull count, ull *keys, ull *his, unsigned *progs, unsigned cap_log2, unsigned *misc,
                      unsigned *copy_min, unsigned *copy_cnt, unsigned *copiers, unsigned max_copiers) {
  ull i = blockIdx.x * (ull)blockDim.x + threadIdx.x;
  if (i >= count) return;
  ull pb = lo + i; unsigned prog = (unsigned)pb;
  unsigned char tbl[16], mem[MAXM]; unsigned steps;
  for (int x = 0; x < C.nin; x++) tbl[x] = run(pb, x, 0, 0, mem, &steps);
  // self-copy test with x = 0: compare M[nins .. 2*nins-1] with the initial code (mem holds the final memory of the x = 15 run; rerun x = 0)
  run(pb, 0, 0, 0, mem, &steps);
  int score = 0; for (int k = 0; k < C.nins; k++) { unsigned char c = (unsigned char)((pb >> (k * C.I)) & ((1u << C.I) - 1)); score += mem[C.nins + k] == c; }
  atomicMin(&copy_min[score], prog); atomicAdd(&copy_cnt[score], 1u);
  if (score == C.nins) { unsigned slot = atomicAdd(&misc[3], 1u); if (slot < max_copiers) copiers[slot] = prog; }
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
  if (c.nM > MAXM || 2 * c.nins > c.nM || c.nin > 16 || c.nin * c.W > 128) { fprintf(stderr, "limits: a<=4, 2*2^p <= 2^a, W<=4\n"); return 2; }
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
  ull cap = 1ull << cap_log2; ull *d_keys, *d_his; unsigned *d_progs, *d_misc, *d_cmin, *d_ccnt, *d_cop;
  cudaMalloc(&d_keys, cap * 8); cudaMalloc(&d_his, cap * 8); cudaMalloc(&d_progs, cap * 4); cudaMalloc(&d_misc, 16);
  cudaMalloc(&d_cmin, 64 * 4); cudaMalloc(&d_ccnt, 64 * 4); cudaMalloc(&d_cop, (size_t)max_copiers * 4);
  cudaMemset(d_keys, 0xFF, cap * 8); cudaMemset(d_progs, 0xFF, cap * 4); cudaMemset(d_misc, 0xFF, 4); cudaMemset(d_misc + 1, 0, 12);
  cudaMemset(d_cmin, 0xFF, 64 * 4); cudaMemset(d_ccnt, 0, 64 * 4);
  auto t0 = std::chrono::steady_clock::now();
  const ull SUB = 1ull << 26;
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
#ifdef EMU_LAUNCH
    EMU_LAUNCH(sweep, (unsigned)((n + 127) / 128), 128, off, n, d_keys, d_his, d_progs, cap_log2, d_misc, d_cmin, d_ccnt, d_cop, max_copiers);
#else
    sweep<<<(unsigned)((n + 127) / 128), 128>>>(off, n, d_keys, d_his, d_progs, cap_log2, d_misc, d_cmin, d_ccnt, d_cop, max_copiers);
#endif
    cudaError_t e = cudaDeviceSynchronize(); if (e != cudaSuccess) { fprintf(stderr, "ERROR %s\n", cudaGetErrorString(e)); return 1; }
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::vector<ull> keys(cap), his(cap); std::vector<unsigned> progs(cap), cmin(64), ccnt(64); unsigned misc[4];
  cudaMemcpy(keys.data(), d_keys, cap * 8, cudaMemcpyDeviceToHost); cudaMemcpy(his.data(), d_his, cap * 8, cudaMemcpyDeviceToHost);
  cudaMemcpy(progs.data(), d_progs, cap * 4, cudaMemcpyDeviceToHost); cudaMemcpy(misc, d_misc, 16, cudaMemcpyDeviceToHost);
  cudaMemcpy(cmin.data(), d_cmin, 64 * 4, cudaMemcpyDeviceToHost); cudaMemcpy(ccnt.data(), d_ccnt, 64 * 4, cudaMemcpyDeviceToHost);
  unsigned ncop = misc[3] < max_copiers ? misc[3] : max_copiers; std::vector<unsigned> cop(ncop); if (ncop) cudaMemcpy(cop.data(), d_cop, ncop * 4, cudaMemcpyDeviceToHost);
  if (misc[2]) { fprintf(stderr, "ERROR hash table overflow (%u programs dropped); rerun with --cap-log2 %u or a smaller range\n", misc[2], cap_log2 + 1); return 1; }
  ull n = misc[1] ? 1 : 0; for (ull i = 0; i < cap; i++) n += keys[i] != EMPTY;
  FILE *f = fopen(out, "wb"); if (!f) { perror(out); return 1; }
  unsigned hdr[8] = { 0x55314231u, (unsigned)c.W, (unsigned)c.a, (unsigned)c.p, (unsigned)c.I, (unsigned)c.o, 0u, (unsigned)nisa };
  fwrite(hdr, 4, 8, f); fwrite(&lo, 8, 1, f); fwrite(&hi, 8, 1, f); fwrite(&n, 8, 1, f); fwrite(isa, 1, nisa, f);
  for (ull i = 0; i < cap; i++) if (keys[i] != EMPTY) { fwrite(&keys[i], 8, 1, f); fwrite(&his[i], 8, 1, f); fwrite(&progs[i], 4, 1, f); }
  if (misc[1]) { ull k = EMPTY, h = 0; fwrite(&k, 8, 1, f); fwrite(&h, 8, 1, f); fwrite(&misc[0], 4, 1, f); }
  fclose(f);
  std::string cp = std::string(out) + ".copy"; FILE *g = fopen(cp.c_str(), "w"); if (!g) { perror(cp.c_str()); return 1; }
  fprintf(g, "layout L2 isa %s programs [%llu,%llu) copy window M[%d..%d] test input x=0\n", isa_s, lo, hi, c.nins, 2 * c.nins - 1);
  for (int sc = 0; sc <= c.nins; sc++) fprintf(g, "score %d count %u min_program 0x%08x\n", sc, ccnt[sc], cmin[sc]);
  fprintf(g, "full_copiers %u listed %u\n", misc[3], ncop); for (unsigned i = 0; i < ncop; i++) fprintf(g, "copier 0x%08x\n", cop[i]);
  fclose(g);
  fprintf(stderr, "L2 W=%d a=%d p=%d I=%d o=%d isa=%s programs=[%llu,%llu) distinct=%llu full_copiers=%u %.2fs (%.1f Mprog/s) %s\n", c.W, c.a, c.p, c.I, c.o, isa_s, lo, hi, n, misc[3], secs, (hi - lo) / secs / 1e6, prop.name);
  printf("%llu\n", n);
  return 0;
}
