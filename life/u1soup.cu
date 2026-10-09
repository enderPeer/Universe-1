// Design C soup (docs/12_design_c_soup.md), GPU implementation of sim/soup.py (normative; bit-identical outputs, fast/check_soup.py).
// usage: u1soup_cuda --gpu g [--N 4096 --P 256 --W 5 --a 5 --p 3 --isa LDIND,STIND,INCM,JNZ --S 32 --ticks 1000 --seed 1
//        --fill random|zero|pattern --ancestors 0x..[,0x..]|@file --n-ancestors 1 --spontaneous 1 --mu 0 --rays 0 --max-age 1024
//        --report-every 10 --census-every 100 --shadow 1 --out-dir dir --dump-final]   (defaults as sim/soup.py)
// One thread per processor slot. A step is two kernels: k_exec (the watcher for the previous step's write, then one instruction with
// the write only claimed: 64-bit atomicMax on a (step, slot) stamp per word, so the highest slot wins and the stamp's low bits are the
// word's last writer) and k_apply (winners write). The tick end: k_watch, compaction of parents and free slots (thrust), the reaper
// (sort by seq, kill the oldest), mutations (atomicXor, commutative), births, deaths by age, placements, rays; the shadow population
// and the statistics live on the host. Build: nvcc -O3 -arch=native -o u1soup_cuda u1soup.cu
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <string>
#include <vector>
#include <algorithm>
#include <unordered_map>
#include <cmath>
#include <thrust/device_ptr.h>
#include <thrust/copy.h>
#include <thrust/sort.h>
#include <thrust/count.h>
#include <thrust/iterator/counting_iterator.h>
typedef unsigned long long ull;

enum { P_NOP, P_HALT, P_LD, P_ST, P_LDI, P_CLR, P_SET, P_NOT, P_AND, P_OR, P_XOR, P_NAND, P_NOR, P_XNOR, P_ADD, P_ADC, P_SUB, P_INC, P_DEC,
       P_NEG, P_SHL, P_SHR, P_ROL, P_ROR, P_RCL, P_MUL, P_SWAP, P_JMP, P_JZ, P_JNZ, P_JC, P_SKZ, P_SKNZ, P_INCM, P_DECM, P_LDIND, P_STIND, P_COUNT };
static const char *PNAME[P_COUNT] = { "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR","ADD","ADC","SUB","INC","DEC",
  "NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP","JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND" };

struct Cfg { unsigned N, P, W, a, p, L, R, o, sh, mask, amask, opmask, max_age; ull seed, mu_thr; };
__constant__ Cfg C; __constant__ unsigned char ISA[256];
#define SHADOW_SEED 0x5AD0ull

__device__ __host__ __forceinline__ ull mix(ull x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }
__device__ __host__ __forceinline__ ull hsh(ull seed, ull tick, ull cell, ull k) { return mix(seed ^ mix(tick * 0x9E3779B97F4A7C15ULL + cell) ^ (k * 0xD1B54A32D192ED03ULL)); }

struct Soup {   // device arrays
  unsigned char *M; ull *claim; int *owner;
  unsigned char *alive, *A, *PC, *ext, *outr, *wflag, *wval; unsigned *B, *age, *wmask, *children, *waddr; int *pending; ull *genome, *seq;
  unsigned *parents, *pk, *pB, *pg_alive, *freel; ull *pg, *placed, *sortkey; unsigned *sortval; ull *cnt;   // cnt: births, faithful, mutant, deaths_age, deaths_reaper, placements, rays
};
__device__ __forceinline__ ull read_genome(const unsigned char *M, unsigned B) { ull g = 0; for (unsigned j = 0; j < C.L; j++) g |= (ull)M[(B + j) % C.N] << (j * C.W); return g; }
__device__ __forceinline__ void attach(Soup s, unsigned slot, unsigned B, ull g, ull seq) {
  s.alive[slot] = 1; s.B[slot] = B % C.N; s.A[slot] = 0; s.PC[slot] = 0; s.age[slot] = 0; s.wmask[slot] = 0; s.genome[slot] = g; s.pending[slot] = -1;
  s.children[slot] = 0; s.ext[slot] = 0; s.outr[slot] = 0; s.seq[slot] = seq; s.wflag[slot] = 0;
  for (unsigned j = 0; j < C.L; j++) atomicMax(&s.owner[(B + j) % C.N], (int)slot);
}
__device__ __forceinline__ void kill(Soup s, unsigned slot) {
  s.alive[slot] = 0;
  for (unsigned j = 0; j < C.L; j++) { unsigned x = (s.B[slot] + j) % C.N; if (s.owner[x] == (int)slot) s.owner[x] = -1; }
}
__device__ __forceinline__ void watch(Soup s, unsigned slot) {   // the watcher after a write: window written by me, last writer me, equal to my genome
  if (!s.wflag[slot]) return; s.wflag[slot] = 0;
  if (s.pending[slot] >= 0) return;
  unsigned m = s.wmask[slot], B = s.B[slot], full = (1u << C.L) - 1; ull g = s.genome[slot];
  for (unsigned k = C.L; k + C.L <= C.R; k++) {
    if (((m >> k) & full) != full) continue;
    int ok = 1; for (unsigned j = 0; j < C.L && ok; j++) ok = (unsigned)(s.claim[(B + k + j) % C.N] & 0xFFFFFFFFu) == slot + 1;
    if (ok && read_genome(s.M, B + k) == g) { s.pending[slot] = (int)k; s.wmask[slot] = 0; return; }
  }
}

__global__ void k_exec(Soup s, ull gstep) {
  unsigned slot = blockIdx.x * blockDim.x + threadIdx.x; if (slot >= C.P || !s.alive[slot]) return;
  watch(s, slot);
  unsigned B = s.B[slot], N = C.N, L = C.L, amask = C.amask, mask = C.mask;
  unsigned ins = s.M[(B + s.PC[slot]) % N], opc = ISA[ins >> C.sh], op = ins & C.opmask; unsigned PC = (s.PC[slot] + 1) % L, A = s.A[slot];
  unsigned waddr = 0, wval = 0; int wr = 0;
  #define RD(addr) s.M[(B + ((addr) & amask)) % N]
  #define WR(addr, v) do { waddr = (B + ((addr) & amask)) % N; wval = (v) & mask; wr = 1; s.wmask[slot] |= 1u << ((addr) & amask); } while (0)
  switch (opc) {
  case P_LDIND: { unsigned p = RD(op) & amask, x = (B + p) % N; A = s.M[x]; if (p >= L) s.outr[slot] = 1; int o = s.owner[x]; if (o != -1 && o != (int)slot) s.ext[slot] = 1; } break;
  case P_STIND: WR(RD(op), A); break;
  case P_INCM: WR(op, RD(op) + 1); break;
  case P_DECM: WR(op, RD(op) - 1); break;
  case P_JNZ: if (A != 0) PC = op % L; break;
  case P_JZ: if (A == 0) PC = op % L; break;
  case P_JMP: PC = op % L; break;
  case P_NOP: break;
  case P_LD: A = RD(op); break;
  case P_ST: WR(op, A); break;
  case P_LDI: A = op & mask; break;
  case P_NAND: A = (~(A & RD(op))) & mask; break;
  case P_ADD: A = (A + RD(op)) & mask; break;
  case P_SWAP: { unsigned t = RD(op); WR(op, A); A = t; } break;
  case P_SKZ: if (A == 0) PC = (PC + 1) % L; break;
  case P_SKNZ: if (A != 0) PC = (PC + 1) % L; break;
  case P_HALT: PC = (PC + L - 1) % L; break;
  default: break;
  }
  s.A[slot] = A; s.PC[slot] = PC; s.age[slot]++;
  if (wr) { s.waddr[slot] = waddr; s.wval[slot] = wval; s.wflag[slot] = 1; atomicMax(&s.claim[waddr], ((gstep + 1) << 32) | (slot + 1)); }
}
__global__ void k_apply(Soup s, ull gstep) {
  unsigned slot = blockIdx.x * blockDim.x + threadIdx.x; if (slot >= C.P || !s.alive[slot] || !s.wflag[slot]) return;
  unsigned x = s.waddr[slot]; if (s.claim[x] == (((gstep + 1) << 32) | (slot + 1))) s.M[x] = s.wval[slot];
}
__global__ void k_watch(Soup s) { unsigned slot = blockIdx.x * blockDim.x + threadIdx.x; if (slot < C.P && s.alive[slot]) watch(s, slot); }
__global__ void k_snapshot(Soup s, unsigned nb) {   // parents' B, offset, genome before any slot changes
  unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= nb) return; unsigned p = s.parents[i];
  s.pk[i] = s.pending[p]; s.pB[i] = (s.B[p] + s.pending[p]) % C.N; s.pg[i] = s.genome[p]; s.pending[p] = -1;
}
__global__ void k_kill(Soup s, unsigned nv) { unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i < nv) kill(s, s.sortval[i]); }
__global__ void k_palive(Soup s, unsigned nb) { unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i < nb) s.pg_alive[i] = s.alive[s.parents[i]]; }
__global__ void k_mutate(Soup s, unsigned nb, ull tick) {
  unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= nb) return;
  for (unsigned j = 0; j < C.L; j++) { ull r = hsh(C.seed, tick, 1, (ull)i * C.L + j);
    if ((r & 0xFFFFFFFFull) < C.mu_thr) { unsigned x = (s.pB[i] + j) % C.N; unsigned bit = (unsigned)((r >> 32) % C.W); atomicXor((unsigned *)(s.M + (x & ~3u)), (1u << bit) << (8 * (x & 3))); } }
}
__global__ void k_birth(Soup s, unsigned nb, ull seq0) {
  unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= nb) return;
  unsigned p = s.parents[i], c = s.freel[i]; ull g = read_genome(s.M, s.pB[i]);
  if (s.pg_alive[i]) s.children[p]++;
  attach(s, c, s.pB[i], g, seq0 + i); atomicAdd(&s.cnt[0], 1ull); atomicAdd(&s.cnt[g == s.pg[i] ? 1 : 2], 1ull);
}
__global__ void k_age(Soup s) { unsigned slot = blockIdx.x * blockDim.x + threadIdx.x; if (slot < C.P && s.alive[slot] && s.age[slot] >= C.max_age) { kill(s, slot); atomicAdd(&s.cnt[3], 1ull); } }
__global__ void k_place(Soup s, unsigned nf, ull tick, ull seq0) {
  unsigned j = blockIdx.x * blockDim.x + threadIdx.x; if (j >= nf) return;
  unsigned B = (unsigned)(hsh(C.seed, tick, 2, j) % C.N); ull g = read_genome(s.M, B); attach(s, s.freel[j], B, g, seq0 + j); s.placed[j] = g; atomicAdd(&s.cnt[5], 1ull);
}
__global__ void k_rays(Soup s, unsigned nr, ull tick) {
  unsigned i = blockIdx.x * blockDim.x + threadIdx.x; if (i >= nr) return; ull r = hsh(C.seed, tick, 3, 1 + i); unsigned x = (unsigned)(r % C.N), bit = (unsigned)((r >> 40) % C.W);
  atomicXor((unsigned *)(s.M + (x & ~3u)), (1u << bit) << (8 * (x & 3))); atomicAdd(&s.cnt[6], 1ull);
}
__global__ void k_sortkeys(Soup s) { unsigned slot = blockIdx.x * blockDim.x + threadIdx.x; if (slot < C.P) { s.sortkey[slot] = s.alive[slot] ? s.seq[slot] : ~0ull; s.sortval[slot] = slot; } }

struct IsParent { const unsigned char *alive; const int *pending; __host__ __device__ bool operator()(unsigned i) const { return alive[i] && pending[i] >= 0; } };
struct IsFree { const unsigned char *alive; __host__ __device__ bool operator()(unsigned i) const { return !alive[i]; } };

struct Activity {   // Bedau component activity over census ticks, bounded: a genome enters with >= 2 copies at a census
  struct Rec { ull first, last, act, peak; }; std::unordered_map<ull, Rec> m; ull singletons = 0, nnew = 0;
  void census(const std::unordered_map<ull, unsigned> &cnt, ull tick) {
    singletons = nnew = 0;
    for (auto &kv : cnt) { auto it = m.find(kv.first);
      if (it == m.end()) { if (kv.second < 2) { singletons++; continue; } it = m.emplace(kv.first, Rec{tick, tick, 0, 0}).first; nnew++; }
      it->second.act += kv.second; it->second.last = tick; it->second.peak = std::max(it->second.peak, (ull)kv.second); }
  }
  void write(const std::string &path, int width) {
    std::vector<std::pair<ull, Rec>> v(m.begin(), m.end()); std::sort(v.begin(), v.end(), [](const std::pair<ull, Rec> &x, const std::pair<ull, Rec> &y) { return x.second.act != y.second.act ? x.second.act > y.second.act : x.first < y.first; });
    FILE *f = fopen(path.c_str(), "w"); fprintf(f, "genome\tfirst_seen\tlast_seen\tactivity\tpeak\n");
    for (auto &x : v) fprintf(f, "0x%0*llx\t%llu\t%llu\t%llu\t%llu\n", width, x.first, x.second.first, x.second.last, x.second.act, x.second.peak); fclose(f);
  }
};
static double entropy(const std::unordered_map<ull, unsigned> &cnt, ull n) { double H = 0; if (n) for (auto &kv : cnt) { double p = (double)kv.second / n; H -= p * log2(p); } return H + 0.0; }

int main(int argc, char **argv) {
  Cfg c; memset(&c, 0, sizeof c); c.N = 4096; c.P = 256; c.W = 5; c.a = 5; c.p = 3; c.max_age = 1024; c.seed = 1;
  std::string isa_s = "LDIND,STIND,INCM,JNZ", fill = "random", ancestors, out_dir = "results/soup/run"; int gpu = 0, S = 32, n_anc = 1, spontaneous = 1, shadow = 1, dump_final = 0;
  double mu = 0, rays = 0; ull ticks = 1000, report_every = 10, census_every = 100;   // defaults as sim/soup.py
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--N")) c.N = strtoul(argv[++i], 0, 0); else if (ARG("--P")) c.P = strtoul(argv[++i], 0, 0);
    else if (ARG("--W")) c.W = atoi(argv[++i]); else if (ARG("--a")) c.a = atoi(argv[++i]); else if (ARG("--p")) c.p = atoi(argv[++i]); else if (ARG("--isa")) isa_s = argv[++i];
    else if (ARG("--S")) S = atoi(argv[++i]); else if (ARG("--ticks")) ticks = strtoull(argv[++i], 0, 0); else if (ARG("--seed")) c.seed = strtoull(argv[++i], 0, 0);
    else if (ARG("--fill")) fill = argv[++i]; else if (ARG("--ancestors")) ancestors = argv[++i]; else if (ARG("--n-ancestors")) n_anc = atoi(argv[++i]);
    else if (ARG("--spontaneous")) spontaneous = atoi(argv[++i]); else if (ARG("--mu")) mu = atof(argv[++i]); else if (ARG("--rays")) rays = atof(argv[++i]); else if (ARG("--max-age")) c.max_age = strtoul(argv[++i], 0, 0);
    else if (ARG("--report-every")) report_every = strtoull(argv[++i], 0, 0); else if (ARG("--census-every")) census_every = strtoull(argv[++i], 0, 0); else if (ARG("--shadow")) shadow = atoi(argv[++i]);
    else if (ARG("--out-dir")) out_dir = argv[++i]; else if (!strcmp(argv[i], "--dump-final")) dump_final = 1; else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  c.L = 1u << c.p; c.R = 1u << c.a; c.mask = (1u << c.W) - 1; c.amask = c.R - 1; c.mu_thr = (ull)(mu * 4294967296.0);
  unsigned char isa[256]; int nisa = 0; { char buf[1024]; strncpy(buf, isa_s.c_str(), sizeof buf - 1); buf[sizeof buf - 1] = 0;
    for (char *t = strtok(buf, ","); t; t = strtok(nullptr, ",")) { int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(t, PNAME[k])) id = k; if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa++] = id; } }
  c.o = 0; while ((1 << c.o) < nisa) c.o++; if (c.o == 0) c.o = 1; c.sh = c.W - c.o; c.opmask = (1u << c.sh) - 1;
  if (c.L * 2 > c.R || c.L * c.W > 64 || c.R > 32 || c.P > (1u << 24)) { fprintf(stderr, "limits: 2L <= reach <= 32, genome <= 64 bits, P <= 2^24\n"); return 2; }
  int width = (c.L * c.W + 3) / 4; std::vector<ull> anc;
  if (!ancestors.empty() && ancestors[0] == '@') { FILE *f = fopen(ancestors.c_str() + 1, "r"); if (!f) { perror(ancestors.c_str() + 1); return 2; } char line[256];   // @file: one program per line
    while (fgets(line, sizeof line, f)) { if (line[0] == '#' || line[0] == '\n') continue; anc.push_back(strtoull(line, 0, 16)); } fclose(f); }
  else { std::vector<char> buf(ancestors.begin(), ancestors.end()); buf.push_back(0); for (char *t = strtok(buf.data(), ","); t; t = strtok(nullptr, ",")) anc.push_back(strtoull(t, 0, 16)); }
  unsigned n = anc.empty() ? 0 : (unsigned)n_anc; if (n > c.P) { fprintf(stderr, "more ancestors than slots\n"); return 2; }
  cudaSetDevice(gpu); cudaDeviceProp prop; cudaGetDeviceProperties(&prop, gpu); cudaMemcpyToSymbol(C, &c, sizeof c); cudaMemcpyToSymbol(ISA, isa, 256);
  unsigned N = c.N, P = c.P, L = c.L;
  Soup s; cudaMalloc(&s.M, N + 4); cudaMalloc(&s.claim, (size_t)N * 8); cudaMalloc(&s.owner, (size_t)N * 4);
  cudaMalloc(&s.alive, P); cudaMalloc(&s.A, P); cudaMalloc(&s.PC, P); cudaMalloc(&s.ext, P); cudaMalloc(&s.outr, P); cudaMalloc(&s.wflag, P); cudaMalloc(&s.wval, P);
  cudaMalloc(&s.B, P * 4); cudaMalloc(&s.age, P * 4); cudaMalloc(&s.wmask, P * 4); cudaMalloc(&s.children, P * 4); cudaMalloc(&s.waddr, P * 4); cudaMalloc(&s.pending, P * 4);
  cudaMalloc(&s.genome, P * 8); cudaMalloc(&s.seq, P * 8); cudaMalloc(&s.parents, P * 4); cudaMalloc(&s.pk, P * 4); cudaMalloc(&s.pB, P * 4); cudaMalloc(&s.pg_alive, P * 4); cudaMalloc(&s.freel, P * 4);
  cudaMalloc(&s.pg, P * 8); cudaMalloc(&s.placed, P * 8); cudaMalloc(&s.sortkey, P * 8); cudaMalloc(&s.sortval, P * 4); cudaMalloc(&s.cnt, 8 * 8);
  cudaMemset(s.claim, 0, (size_t)N * 8); cudaMemset(s.owner, 0xFF, (size_t)N * 4); cudaMemset(s.alive, 0, P); cudaMemset(s.wflag, 0, P); cudaMemset(s.cnt, 0, 64);
  // ---- initial memory and ancestors (host side, as the reference)
  std::vector<unsigned char> M(N, 0);
  if (fill == "random") for (unsigned i = 0; i < N; i++) M[i] = hsh(c.seed, 0, i, 0) & c.mask;
  else if (fill == "pattern") { if (anc.empty()) { fprintf(stderr, "pattern fill needs an ancestor\n"); return 2; } for (unsigned i = 0; i < N; i++) M[i] = (((anc[0] >> ((i % L) * c.W)) & c.mask) + 1) & c.mask; }
  else if (fill != "zero") { fprintf(stderr, "bad fill\n"); return 2; }
  for (unsigned i = 0; i < n; i++) { unsigned B = (unsigned)(((ull)i * N) / n); ull pr = anc[i % anc.size()]; for (unsigned j = 0; j < L; j++) M[(B + j) % N] = (pr >> (j * c.W)) & c.mask; }
  cudaMemcpy(s.M, M.data(), N, cudaMemcpyHostToDevice);
  std::vector<unsigned> h_free(P); for (unsigned i = 0; i < P; i++) h_free[i] = i;
  thrust::device_ptr<unsigned char> d_alive(s.alive); thrust::device_ptr<unsigned> d_parents(s.parents), d_freel(s.freel), d_sortval(s.sortval); thrust::device_ptr<ull> d_sortkey(s.sortkey);
  ull nseq = 0, live = 0, final_tick = ticks;
  // Shadow and statistics on the host
  std::vector<ull> sh_g; std::vector<unsigned> sh_live; Activity act, sact; ull c_births = 0, c_faithful = 0, c_mutant = 0, c_dage = 0, c_dreap = 0, c_place = 0, c_rays = 0;
  std::vector<unsigned char> h_alive(P), h_ext(P), h_outr(P); std::vector<ull> h_genome(P); std::vector<unsigned> h_children(P); std::vector<ull> h_placed(P);
  if (n) {   // ancestors: k_birth with pg_alive = 0 and pg = genome (counts as a faithful birth; corrected below)
    std::vector<unsigned> slots(n), Bs(n); std::vector<ull> gs(n); for (unsigned i = 0; i < n; i++) { slots[i] = i; Bs[i] = (unsigned)(((ull)i * N) / n); ull g = 0; for (unsigned j = 0; j < L; j++) g |= (ull)M[(Bs[i] + j) % N] << (j * c.W); gs[i] = g; }
    cudaMemcpy(s.freel, slots.data(), n * 4, cudaMemcpyHostToDevice); cudaMemcpy(s.pB, Bs.data(), n * 4, cudaMemcpyHostToDevice); cudaMemcpy(s.pg, gs.data(), n * 8, cudaMemcpyHostToDevice);
    cudaMemset(s.pg_alive, 0, n * 4); cudaMemcpy(s.parents, slots.data(), n * 4, cudaMemcpyHostToDevice);
    k_birth<<<(n + 127) / 128, 128>>>(s, n, 0); cudaDeviceSynchronize(); cudaMemset(s.cnt, 0, 64); nseq = n; live = n;
    if (shadow) for (unsigned i = 0; i < n; i++) { sh_g.push_back(gs[i]); sh_live.push_back((unsigned)sh_g.size() - 1); }
  }
  auto do_place = [&](ull tick) {   // every free slot gets a processor at a random position
    if (!spontaneous) return;
    unsigned nf = thrust::copy_if(thrust::counting_iterator<unsigned>(0), thrust::counting_iterator<unsigned>(P), d_freel, IsFree{s.alive}) - d_freel;
    if (!nf) return;
    k_place<<<(nf + 127) / 128, 128>>>(s, nf, tick, nseq); cudaDeviceSynchronize(); nseq += nf; live += nf; c_place += nf;
    if (shadow) { cudaMemcpy(h_placed.data(), s.placed, nf * 8, cudaMemcpyDeviceToHost); for (unsigned j = 0; j < nf; j++) { sh_g.push_back(h_placed[j]); sh_live.push_back((unsigned)sh_g.size() - 1); } }
  };
  do_place(0);
  // ---- output
  std::string cmd; for (int i = 0; i < argc; i++) { cmd += argv[i]; cmd += ' '; }
  std::string mk = "mkdir -p " + out_dir; if (system(mk.c_str())) {}
  FILE *csv = fopen((out_dir + "/stats.csv").c_str(), "w"); if (!csv) { perror(out_dir.c_str()); return 1; }
  fprintf(csv, "tick,live,births,faithful,mutant,deaths_age,deaths_reaper,placements,rays,distinct_genomes,entropy,singletons,top_count,top_genome,parasites,out_readers,fertile,new_genomes,genomes_ever,shadow_distinct,shadow_entropy,shadow_singletons,shadow_new,shadow_ever\n");
  FILE *logf = fopen((out_dir + "/run.log").c_str(), "a"); fprintf(logf, "%s\n", cmd.c_str()); fflush(logf);
  auto t0 = std::chrono::steady_clock::now();
  auto report = [&](ull tick, int census) {
    cudaMemcpy(h_alive.data(), s.alive, P, cudaMemcpyDeviceToHost); cudaMemcpy(h_genome.data(), s.genome, P * 8, cudaMemcpyDeviceToHost); cudaMemcpy(h_ext.data(), s.ext, P, cudaMemcpyDeviceToHost);
    cudaMemcpy(h_outr.data(), s.outr, P, cudaMemcpyDeviceToHost); cudaMemcpy(h_children.data(), s.children, P * 4, cudaMemcpyDeviceToHost);
    std::unordered_map<ull, unsigned> cnt; ull nl = 0, par = 0, outr = 0, fert = 0;
    for (unsigned i = 0; i < P; i++) if (h_alive[i]) { cnt[h_genome[i]]++; nl++; par += h_ext[i]; outr += h_outr[i]; fert += h_children[i] > 0; }
    act.census(cnt, tick); ull topc = 0, topg = 0; for (auto &kv : cnt) if (kv.second > topc || (kv.second == topc && kv.first < topg && topc)) { topc = kv.second; topg = kv.first; }
    // python's most_common(1) returns the first-inserted among ties (insertion order = slot order); replicate: first slot's genome among the max
    if (topc) { for (unsigned i = 0; i < P; i++) if (h_alive[i] && cnt[h_genome[i]] == topc) { topg = h_genome[i]; break; } }
    fprintf(csv, "%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%zu,%.4f,%llu,%llu,0x%0*llx,%llu,%llu,%llu,%llu,%zu", tick, nl, c_births, c_faithful, c_mutant, c_dage, c_dreap, c_place, c_rays, cnt.size(), entropy(cnt, nl), act.singletons, topc, width, topg, par, outr, fert, act.nnew, act.m.size());
    if (shadow) { std::unordered_map<ull, unsigned> sc; for (unsigned i : sh_live) sc[sh_g[i]]++; sact.census(sc, tick); fprintf(csv, ",%zu,%.4f,%llu,%llu,%zu\n", sc.size(), entropy(sc, sh_live.size()), sact.singletons, sact.nnew, sact.m.size()); }
    else fprintf(csv, ",,,,,\n");
    fflush(csv);
    if (census) { std::vector<std::pair<ull, unsigned>> v; std::unordered_map<ull, unsigned> order; unsigned k = 0;
      for (unsigned i = 0; i < P; i++) if (h_alive[i] && !order.count(h_genome[i])) order[h_genome[i]] = k++;
      for (auto &kv : cnt) v.push_back(kv); std::sort(v.begin(), v.end(), [&](const std::pair<ull, unsigned> &x, const std::pair<ull, unsigned> &y) { return x.second != y.second ? x.second > y.second : order[x.first] < order[y.first]; });
      char nm[64]; snprintf(nm, sizeof nm, "/census_%08llu.tsv", tick); FILE *f = fopen((out_dir + nm).c_str(), "w"); fprintf(f, "genome\tcount\tfirst_seen\tdisassembly\n");
      for (size_t i = 0; i < v.size() && i < 50; i++) { auto it = act.m.find(v[i].first); fprintf(f, "0x%0*llx\t%u\t%llu\t", width, v[i].first, v[i].second, it == act.m.end() ? tick : it->second.first);
        for (unsigned j = 0; j < L; j++) { unsigned w = (v[i].first >> (j * c.W)) & c.mask; fprintf(f, "%s%s %u", j ? "; " : "", PNAME[isa[w >> c.sh]], w & c.opmask); } fprintf(f, "\n"); }
      fclose(f); }
    fprintf(stderr, "tick %9llu live %7llu births %10llu (faithful %llu mutant %llu) deaths age %llu reaper %llu placements %llu genomes %zu top %llu parasites %llu (%.0fs) %s\n", tick, nl, c_births, c_faithful, c_mutant, c_dage, c_dreap, c_place, cnt.size(), topc, par, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(), prop.name);
    fprintf(logf, "tick %llu live %llu births %llu genomes %zu\n", tick, nl, c_births, cnt.size()); fflush(logf);
  };
  unsigned grid = (P + 127) / 128; ull gstep = 0; ull hcnt[8];
  for (ull t = 0; t <= ticks; t++) {
    if (t % report_every == 0) report(t, t % census_every == 0);
    if (t == ticks) break;
    for (int i = 0; i < S; i++) { k_exec<<<grid, 128>>>(s, gstep); k_apply<<<grid, 128>>>(s, gstep); gstep++; }
    k_watch<<<grid, 128>>>(s);
    // ---- tick end
    unsigned nb = thrust::copy_if(thrust::counting_iterator<unsigned>(0), thrust::counting_iterator<unsigned>(P), d_parents, IsParent{s.alive, s.pending}) - d_parents;
    unsigned nf = (unsigned)thrust::count(d_alive, d_alive + P, (unsigned char)0); ull deaths = 0;
    if (nb) k_snapshot<<<(nb + 127) / 128, 128>>>(s, nb);
    if (nb > nf) { k_sortkeys<<<grid, 128>>>(s); thrust::sort_by_key(d_sortkey, d_sortkey + P, d_sortval); unsigned nv = nb - nf; k_kill<<<(nv + 127) / 128, 128>>>(s, nv); c_dreap += nv; deaths += nv; live -= nv; }
    if (nb) {
      thrust::copy_if(thrust::counting_iterator<unsigned>(0), thrust::counting_iterator<unsigned>(P), d_freel, IsFree{s.alive});
      k_palive<<<(nb + 127) / 128, 128>>>(s, nb); k_mutate<<<(nb + 127) / 128, 128>>>(s, nb, t); k_birth<<<(nb + 127) / 128, 128>>>(s, nb, nseq); nseq += nb; live += nb;
    }
    k_age<<<grid, 128>>>(s); cudaMemcpy(hcnt, s.cnt, 64, cudaMemcpyDeviceToHost);
    ull dage = hcnt[3] - c_dage; c_dage = hcnt[3]; deaths += dage; live -= dage; c_births = hcnt[0]; c_faithful = hcnt[1]; c_mutant = hcnt[2];
    if (shadow) {   // births first, then deaths
      for (unsigned i = 0; i < nb; i++) { ull p = sh_g[sh_live[hsh(c.seed ^ SHADOW_SEED, t, 3, i) % sh_live.size()]];
        for (unsigned j = 0; j < L; j++) { ull r = hsh(c.seed ^ SHADOW_SEED, t, 1, (ull)i * L + j); if ((r & 0xFFFFFFFFull) < c.mu_thr) p ^= 1ull << (j * c.W + (r >> 32) % c.W); }
        sh_g.push_back(p); sh_live.push_back((unsigned)sh_g.size() - 1); }
      for (ull i = 0; i < deaths; i++) { size_t k = hsh(c.seed ^ SHADOW_SEED, t, 2, i) % sh_live.size(); sh_live[k] = sh_live.back(); sh_live.pop_back(); }
    }
    do_place(t);
    { ull r = hsh(c.seed, t, 3, 0); unsigned nr = (unsigned)rays + (((r & 0xFFFFFFFFull) < (ull)((rays - (unsigned)rays) * 4294967296.0)) ? 1 : 0);
      if (nr) { k_rays<<<(nr + 127) / 128, 128>>>(s, nr, t); c_rays += nr; } }
    cudaError_t e = cudaDeviceSynchronize(); if (e != cudaSuccess) { fprintf(stderr, "ERROR %s\n", cudaGetErrorString(e)); return 1; }
    if (shadow && sh_live.size() != live) { fprintf(stderr, "shadow size %zu != live %llu at tick %llu\n", sh_live.size(), live, t); return 1; }
    if (!live) { final_tick = t + 1; report(t + 1, 1); fprintf(stderr, "extinct at tick %llu\n", t + 1); fprintf(logf, "extinct at tick %llu\n", t + 1); break; }
  }
  fclose(csv); act.write(out_dir + "/activity.tsv", width); if (shadow) sact.write(out_dir + "/shadow_activity.tsv", width);
  if (dump_final) {   // same format as sim/soup.py dump()
    cudaMemcpy(M.data(), s.M, N, cudaMemcpyDeviceToHost); std::vector<unsigned char> hA(P), hPC(P); std::vector<unsigned> hB(P), hage(P), hw(P); std::vector<ull> hseq(P);
    cudaMemcpy(h_alive.data(), s.alive, P, cudaMemcpyDeviceToHost); cudaMemcpy(hA.data(), s.A, P, cudaMemcpyDeviceToHost); cudaMemcpy(hPC.data(), s.PC, P, cudaMemcpyDeviceToHost); cudaMemcpy(hB.data(), s.B, P * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(hage.data(), s.age, P * 4, cudaMemcpyDeviceToHost); cudaMemcpy(hw.data(), s.wmask, P * 4, cudaMemcpyDeviceToHost); cudaMemcpy(h_genome.data(), s.genome, P * 8, cudaMemcpyDeviceToHost); cudaMemcpy(h_children.data(), s.children, P * 4, cudaMemcpyDeviceToHost);
    cudaMemcpy(h_ext.data(), s.ext, P, cudaMemcpyDeviceToHost); cudaMemcpy(h_outr.data(), s.outr, P, cudaMemcpyDeviceToHost); cudaMemcpy(hseq.data(), s.seq, P * 8, cudaMemcpyDeviceToHost);
    FILE *f = fopen((out_dir + "/final.txt").c_str(), "w"); ull last_tick = final_tick;
    fprintf(f, "soup N %u P %u W %u a %u p %u tick %llu\n", N, P, c.W, c.a, c.p, last_tick);
    for (unsigned i = 0; i < N; i++) fprintf(f, "%02x", M[i]); fprintf(f, "\n");
    for (unsigned i = 0; i < P; i++) if (h_alive[i]) fprintf(f, "%u B %u A %u PC %u age %u wmask %08x genome %llx children %u ext %u out %u seq %llu\n", i, hB[i], hA[i], hPC[i], hage[i], hw[i], h_genome[i], h_children[i], h_ext[i], h_outr[i], hseq[i]);
    fprintf(f, "counters {\"births\": %llu, \"deaths_age\": %llu, \"deaths_reaper\": %llu, \"faithful\": %llu, \"mutant\": %llu, \"placements\": %llu, \"rays\": %llu}\n", c_births, c_dage, c_dreap, c_faithful, c_mutant, c_place, c_rays);
    fclose(f);
  }
  fprintf(stderr, "done in %.1fs\n", std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count()); fprintf(logf, "done\n"); fclose(logf);
  return 0;
}
