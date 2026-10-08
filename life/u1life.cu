// Universe-1 Life, GPU implementation of docs/06_life_spec.md (CUDA). Bit-identical to life/src/main.rs.
// usage: u1life_cuda --gpu g [--N 256 --seed 1 --density 0.05 --ticks 10000 --report-every 100 --isa SWAP,ADD,NAND,SKZ
//        --a 2 --p 3 --I 4 --income 20 --trigger 15 --repro-cost 128 --max-energy 255 --mu-bits 128 --max-age 1024
//        --death-rate 512 --start-energy 64 --out-dir dir --dump-final --load dump.bin --ppm-every 0]
// --ppm-every k writes out-dir/t%08llu.ppm every k ticks (same files as the CPU reference), e.g. for a video.
// Build: nvcc -O3 -arch=native -o u1life_cuda u1life.cu ; emulation: g++ -O2 -x c++ -include ../gpu/cuda_shim.h -o u1life_emu u1life.cu
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <string>
#include <vector>
#include <algorithm>
typedef unsigned long long ull;

enum { P_NOP, P_HALT, P_LD, P_ST, P_LDI, P_CLR, P_SET, P_NOT, P_AND, P_OR, P_XOR, P_NAND, P_NOR, P_XNOR, P_ADD, P_ADC, P_SUB, P_INC, P_DEC,
       P_NEG, P_SHL, P_SHR, P_ROL, P_ROR, P_RCL, P_MUL, P_SWAP, P_JMP, P_JZ, P_JNZ, P_JC, P_SKZ, P_SKNZ, P_INCM, P_DECM, P_LDIND, P_STIND, P_COUNT };
static const char *PNAME[P_COUNT] = { "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR","ADD","ADC","SUB","INC","DEC",
  "NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP","JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND" };

struct Cfg { int W, a, p, I, o, nins, nM; unsigned mask, amask, pmask, opmask; };
struct Par { unsigned n, income, trigger, repro_cost, max_energy, max_age, start_energy; ull seed, mu_bits, death_rate; };
__constant__ Cfg C; __constant__ Par PR; __constant__ unsigned char ISA[256];
#define MAX_STEPS 256
#define MAXM 16

__device__ __host__ __forceinline__ ull mix(ull x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }
__device__ __host__ __forceinline__ ull hsh(ull seed, ull tick, ull cell, ull k) { return mix(seed ^ mix(tick * 0x9E3779B97F4A7C15ULL + cell) ^ (k * 0xD1B54A32D192ED03ULL)); }

struct St { unsigned A, Z, Cf, PC; unsigned M[MAXM]; };
__device__ __forceinline__ unsigned rd(St &s, unsigned addr) { addr &= C.amask; return addr == 0 ? s.A : s.M[addr]; }
__device__ __forceinline__ void wr(St &s, unsigned addr, unsigned v) { addr &= C.amask; v &= C.mask; if (addr == 0) s.A = v; else s.M[addr] = v; }
__device__ __forceinline__ void setA(St &s, unsigned v) { s.A = v & C.mask; s.Z = (s.A == 0); }


// returns final A and writes steps (256 for non-halting). No cycle fast-forward: a periodic run simply executes all
// 256 steps, which yields the identical state at step 256 (the CPU engines only skip the work).
__device__ unsigned run(unsigned genome, unsigned x, unsigned y, unsigned *steps_out) {
  unsigned char opc[8], opnd[8];
  for (int k = 0; k < C.nins; k++) { unsigned ins = (genome >> (k * C.I)) & ((1u << C.I) - 1); opc[k] = ISA[ins >> (C.I - C.o)]; opnd[k] = ins & C.opmask; }
  St s; s.A = x & C.mask; s.Z = (s.A == 0); s.Cf = 0; s.PC = 0; for (int i = 0; i < C.nM; i++) s.M[i] = 0; s.M[1] = y & C.mask;
  for (int t = 0; t < MAX_STEPS; t++) {
    unsigned k = s.PC & C.pmask, op = opnd[k]; s.PC = (s.PC + 1) & C.pmask; unsigned v, cy;
    switch (opc[k]) {
    case P_NOP: break;
    case P_HALT: *steps_out = t + 1; return s.A;
    case P_LD: setA(s, rd(s, op)); break; case P_ST: wr(s, op, s.A); break; case P_LDI: setA(s, op); break;
    case P_CLR: setA(s, 0); break; case P_SET: setA(s, C.mask); break; case P_NOT: setA(s, ~s.A); break;
    case P_AND: setA(s, s.A & rd(s, op)); break; case P_OR: setA(s, s.A | rd(s, op)); break; case P_XOR: setA(s, s.A ^ rd(s, op)); break;
    case P_NAND: setA(s, ~(s.A & rd(s, op))); break; case P_NOR: setA(s, ~(s.A | rd(s, op))); break; case P_XNOR: setA(s, ~(s.A ^ rd(s, op))); break;
    case P_ADD: v = s.A + rd(s, op); setA(s, v); s.Cf = v > C.mask; break;
    case P_ADC: v = s.A + rd(s, op) + s.Cf; setA(s, v); s.Cf = v > C.mask; break;
    case P_SUB: v = s.A - rd(s, op); cy = (int)v < 0; setA(s, v); s.Cf = cy; break;
    case P_INC: v = s.A + 1; setA(s, v); s.Cf = v > C.mask; break;
    case P_DEC: v = s.A - 1; cy = (int)v < 0; setA(s, v); s.Cf = cy; break;
    case P_NEG: cy = s.A != 0; setA(s, -s.A); s.Cf = cy; break;
    case P_SHL: cy = (s.A >> (C.W - 1)) & 1; setA(s, s.A << 1); s.Cf = cy; break;
    case P_SHR: cy = s.A & 1; setA(s, s.A >> 1); s.Cf = cy; break;
    case P_ROL: setA(s, (s.A << 1) | (s.A >> (C.W - 1))); break; case P_ROR: setA(s, (s.A >> 1) | ((s.A & 1) << (C.W - 1))); break;
    case P_RCL: cy = (s.A >> (C.W - 1)) & 1; setA(s, (s.A << 1) | s.Cf); s.Cf = cy; break;
    case P_MUL: setA(s, s.A * rd(s, op)); break;
    case P_SWAP: { unsigned tA = s.A, tt = rd(s, op); wr(s, op, tA); setA(s, tt); } break;
    case P_JMP: s.PC = op & C.pmask; break; case P_JZ: if (s.Z) s.PC = op & C.pmask; break; case P_JNZ: if (!s.Z) s.PC = op & C.pmask; break;
    case P_JC: if (s.Cf) s.PC = op & C.pmask; break; case P_SKZ: if (s.Z) s.PC = (s.PC + 1) & C.pmask; break; case P_SKNZ: if (!s.Z) s.PC = (s.PC + 1) & C.pmask; break;
    case P_INCM: wr(s, op, rd(s, op) + 1); break; case P_DECM: wr(s, op, rd(s, op) - 1); break;
    case P_LDIND: setA(s, rd(s, rd(s, op))); break; case P_STIND: wr(s, rd(s, op), s.A); break;
    }
  }
  *steps_out = MAX_STEPS; return s.A;
}

__device__ __host__ __forceinline__ unsigned pk(unsigned state, unsigned alive, unsigned age, unsigned energy) { return (state & 15) | (alive << 4) | (min(age, 2047u) << 5) | (min(energy, 65535u) << 16); }
__device__ __host__ __forceinline__ unsigned alv(unsigned m) { return (m >> 4) & 1; }

__global__ void k_init(unsigned *genome, unsigned *meta, ull thr) {
  ull c = blockIdx.x * (ull)blockDim.x + threadIdx.x; ull nn = (ull)PR.n * PR.n; if (c >= nn) return;
  if ((hsh(PR.seed, 0, c, 0) >> 32) < thr) { genome[c] = (unsigned)hsh(PR.seed, 0, c, 1); meta[c] = pk((unsigned)(hsh(PR.seed, 0, c, 2) & 15), 1, 0, PR.start_energy); }
  else { genome[c] = 0; meta[c] = 0; }
}
__constant__ int DX[4] = {0, 1, 0, -1}; __constant__ int DY[4] = {0 - 1, 0, 1, 0};

__global__ void k_phase1(const unsigned *genome, const unsigned *meta, unsigned *p1, ull tick) {
  ull c = blockIdx.x * (ull)blockDim.x + threadIdx.x; ull nn = (ull)PR.n * PR.n; if (c >= nn) return;
  unsigned me = meta[c]; if (!alv(me)) { p1[c] = 0; return; }
  int n = PR.n, d = tick % 4, x = c % n, y = c / n;
  int nx = ((x + DX[d]) % n + n) % n, ny = ((y + DY[d]) % n + n) % n; unsigned nbm = meta[(ull)ny * n + nx];
  unsigned steps; unsigned a = run(genome[c], me & 15, alv(nbm) ? (nbm & 15) : 0, &steps);
  unsigned cost = (steps + 15) / 16; unsigned e = me >> 16; unsigned ea = min(e + PR.income, PR.max_energy); ea = ea > cost ? ea - cost : 0;
  p1[c] = (a & 15) | (cost << 4) | (ea << 16);
}
__global__ void k_phase2(const unsigned *genome, const unsigned *meta, const unsigned *p1, unsigned *ng, unsigned *nm, ull tick, unsigned *counts) {
  ull c = blockIdx.x * (ull)blockDim.x + threadIdx.x; ull nn = (ull)PR.n * PR.n; if (c >= nn) return;
  int n = PR.n, d = tick % 4, x = c % n, y = c / n;
  ull parent = (ull)(((y - DY[d]) % n + n) % n) * n + ((x - DX[d]) % n + n) % n;
  ull child = (ull)(((y + DY[d]) % n + n) % n) * n + ((x + DX[d]) % n + n) % n;
  #define NS(i) (p1[i] & 15)
  #define EA(i) (p1[i] >> 16)
  #define QUAL(i) (alv(meta[i]) && NS(i) == PR.trigger && EA(i) >= PR.repro_cost)
  #define COLON(ch, pa) (QUAL(pa) && !(alv(meta[ch]) && NS(ch) == PR.trigger && EA(ch) >= EA(pa)))
  if (COLON(c, parent)) {
    unsigned g = genome[parent]; for (ull k = 0; k < 32; k++) if (hsh(PR.seed, tick, c, 16 + k) % PR.mu_bits == 0) g ^= 1u << k;
    ng[c] = g; nm[c] = pk(0, 1, 0, PR.start_energy); atomicAdd(&counts[0], 1u); if (alv(meta[c])) atomicAdd(&counts[1], 1u);
  } else if (alv(meta[c])) {
    unsigned a = ((meta[c] >> 5) & 2047) + 1; unsigned e = EA(c); if (COLON(child, c)) e -= PR.repro_cost;
    if (e == 0 || a > PR.max_age || hsh(PR.seed, tick, c, 8) % PR.death_rate == 0) { ng[c] = 0; nm[c] = 0; atomicAdd(&counts[1], 1u); }
    else { ng[c] = genome[c]; nm[c] = pk(NS(c), 1, a, e); }
  } else { ng[c] = 0; nm[c] = 0; }
}

static void write_ppm(const std::string &path, const std::vector<unsigned> &g, const std::vector<unsigned> &m, unsigned n) {
  FILE *pf = fopen(path.c_str(), "wb"); if (!pf) { perror(path.c_str()); exit(1); } fprintf(pf, "P6\n%u %u\n255\n", n, n);
  std::vector<unsigned char> px((size_t)n * n * 3);
  for (size_t i = 0; i < (size_t)n * n; i++) { unsigned char *p = &px[i * 3]; p[0] = p[1] = p[2] = 0; if (alv(m[i])) { ull h = mix(g[i]); ull b = 96 + (m[i] & 15) * 10; p[0] = (h & 255) * b / 255; p[1] = ((h >> 8) & 255) * b / 255; p[2] = ((h >> 16) & 255) * b / 255; } }
  fwrite(px.data(), 1, px.size(), pf); fclose(pf);
}

int main(int argc, char **argv) {
  Cfg c; memset(&c, 0, sizeof c); c.W = 4; c.a = 2; c.p = 3; c.I = 4; Par pr; pr.n = 256; pr.income = 20; pr.trigger = 15; pr.repro_cost = 128; pr.max_energy = 255; pr.max_age = 1024; pr.start_energy = 64; pr.seed = 1; pr.mu_bits = 128; pr.death_rate = 512;
  double density = 0.05; ull ticks = 10000, report = 100; const char *isa_s = "SWAP,ADD,NAND,SKZ"; std::string out_dir = "."; const char *load = nullptr; int gpu = 0, dump_final = 0; ull ppm_every = 0;
  for (int i = 1; i < argc; i++) {
    #define ARG(nm) (!strcmp(argv[i], nm) && i + 1 < argc)
    if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--N")) pr.n = atoi(argv[++i]); else if (ARG("--seed")) pr.seed = strtoull(argv[++i], 0, 0);
    else if (ARG("--density")) density = atof(argv[++i]); else if (ARG("--ticks")) ticks = strtoull(argv[++i], 0, 0); else if (ARG("--report-every")) report = strtoull(argv[++i], 0, 0);
    else if (ARG("--isa")) isa_s = argv[++i]; else if (ARG("--a")) c.a = atoi(argv[++i]); else if (ARG("--p")) c.p = atoi(argv[++i]); else if (ARG("--I")) c.I = atoi(argv[++i]);
    else if (ARG("--income")) pr.income = atoi(argv[++i]); else if (ARG("--trigger")) pr.trigger = atoi(argv[++i]); else if (ARG("--repro-cost")) pr.repro_cost = atoi(argv[++i]);
    else if (ARG("--max-energy")) pr.max_energy = atoi(argv[++i]); else if (ARG("--mu-bits")) pr.mu_bits = strtoull(argv[++i], 0, 0); else if (ARG("--max-age")) pr.max_age = atoi(argv[++i]);
    else if (ARG("--death-rate")) pr.death_rate = strtoull(argv[++i], 0, 0); else if (ARG("--start-energy")) pr.start_energy = atoi(argv[++i]); else if (ARG("--out-dir")) out_dir = argv[++i];
    else if (ARG("--ppm-every")) ppm_every = strtoull(argv[++i], 0, 0); else if (ARG("--load")) load = argv[++i]; else if (!strcmp(argv[i], "--dump-final")) dump_final = 1; else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  unsigned char isa[256]; int nisa = 0; char buf[1024]; strncpy(buf, isa_s, 1023); buf[1023] = 0;
  for (char *t = strtok(buf, ","); t; t = strtok(nullptr, ",")) { int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(t, PNAME[k])) id = k; if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa++] = id; }
  c.o = 0; while ((1 << c.o) < nisa) c.o++; if (c.o == 0) c.o = 1; c.mask = (1u << c.W) - 1; c.amask = (1u << c.a) - 1; c.pmask = (1u << c.p) - 1; c.nins = 1 << c.p; c.nM = 1 << c.a; c.opmask = (1u << (c.I - c.o)) - 1;
  if (c.nins > 8 || c.nM > MAXM) { fprintf(stderr, "kernel compiled for <= 8 instructions and a <= 4\n"); return 2; }
  ull nn = (ull)pr.n * pr.n;
  cudaSetDevice(gpu); cudaDeviceProp prop; cudaGetDeviceProperties(&prop, gpu);
  cudaMemcpyToSymbol(C, &c, sizeof c); cudaMemcpyToSymbol(PR, &pr, sizeof pr); cudaMemcpyToSymbol(ISA, isa, 256);
  unsigned *d_g, *d_m, *d_ng, *d_nm, *d_p1, *d_cnt;
  cudaMalloc(&d_g, nn * 4); cudaMalloc(&d_m, nn * 4); cudaMalloc(&d_ng, nn * 4); cudaMalloc(&d_nm, nn * 4); cudaMalloc(&d_p1, nn * 4); cudaMalloc(&d_cnt, 8);
  unsigned grid = (unsigned)((nn + 255) / 256);
  std::vector<unsigned> g(nn), m(nn);
  if (load) { FILE *f = fopen(load, "rb"); if (!f || fread(g.data(), 4, nn, f) != nn || fread(m.data(), 4, nn, f) != nn) { fprintf(stderr, "bad dump\n"); return 1; } fclose(f); cudaMemcpy(d_g, g.data(), nn * 4, cudaMemcpyHostToDevice); cudaMemcpy(d_m, m.data(), nn * 4, cudaMemcpyHostToDevice); }
  else {
#ifdef EMU_LAUNCH
    EMU_LAUNCH(k_init, grid, 256, d_g, d_m, (ull)(density * 4294967296.0));
#else
    k_init<<<grid, 256>>>(d_g, d_m, (ull)(density * 4294967296.0));
#endif
  }
  std::string cmd = "mkdir -p " + out_dir; if (system(cmd.c_str())) {}
  FILE *csv = fopen((out_dir + "/stats.csv").c_str(), "w"); fprintf(csv, "tick,alive,distinct_genomes,mean_energy,births,deaths\n");
  auto t0 = std::chrono::steady_clock::now(); ull births = 0, deaths = 0;
  for (ull t = 0; t <= ticks; t++) {
    bool do_report = t % report == 0 || t == ticks, do_ppm = ppm_every && t % ppm_every == 0 && t != ticks;
    if (do_report || do_ppm) { cudaMemcpy(g.data(), d_g, nn * 4, cudaMemcpyDeviceToHost); cudaMemcpy(m.data(), d_m, nn * 4, cudaMemcpyDeviceToHost); }
    if (do_ppm) { char nm[32]; snprintf(nm, sizeof nm, "/t%08llu.ppm", t); write_ppm(out_dir + nm, g, m, pr.n); }
    if (do_report) {
      ull alive = 0; double es = 0; std::vector<unsigned> gs; for (ull i = 0; i < nn; i++) if (alv(m[i])) { alive++; es += m[i] >> 16; gs.push_back(g[i]); }
      std::sort(gs.begin(), gs.end()); ull dg = std::unique(gs.begin(), gs.end()) - gs.begin();
      fprintf(csv, "%llu,%llu,%llu,%.2f,%llu,%llu\n", t, alive, dg, alive ? es / alive : 0.0, births, deaths); fflush(csv);
      fprintf(stderr, "tick %7llu alive %8llu genomes %7llu energy %7.1f births %llu deaths %llu (%.1fs) %s\n", t, alive, dg, alive ? es / alive : 0.0, births, deaths, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count(), prop.name);
      births = deaths = 0; if (alive == 0) { fprintf(stderr, "extinct at tick %llu\n", t); break; }
    }
    if (t == ticks) break;
    cudaMemset(d_cnt, 0, 8);
#ifdef EMU_LAUNCH
    EMU_LAUNCH(k_phase1, grid, 256, d_g, d_m, d_p1, t);
    EMU_LAUNCH(k_phase2, grid, 256, d_g, d_m, d_p1, d_ng, d_nm, t, d_cnt);
#else
    k_phase1<<<grid, 256>>>(d_g, d_m, d_p1, t);
    k_phase2<<<grid, 256>>>(d_g, d_m, d_p1, d_ng, d_nm, t, d_cnt);
#endif
    unsigned cnt[2]; cudaMemcpy(cnt, d_cnt, 8, cudaMemcpyDeviceToHost); births += cnt[0]; deaths += cnt[1];
    std::swap(d_g, d_ng); std::swap(d_m, d_nm);
  }
  cudaMemcpy(g.data(), d_g, nn * 4, cudaMemcpyDeviceToHost); cudaMemcpy(m.data(), d_m, nn * 4, cudaMemcpyDeviceToHost);
  if (dump_final) { FILE *f = fopen((out_dir + "/final.bin").c_str(), "wb"); fwrite(g.data(), 4, nn, f); fwrite(m.data(), 4, nn, f); fclose(f); }
  write_ppm(out_dir + "/final.ppm", g, m, pr.n); fclose(csv);
  fprintf(stderr, "done %llu ticks in %.1fs\n", ticks, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
  return 0;
}
