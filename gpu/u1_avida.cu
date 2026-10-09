// Universe-1 exp11 kernel (CUDA): Avida's heads CPU (cHardwareCPU, default 26-instruction heads set) and Avida's Analyze-Mode
// viability test (cTestCPU::TestGenome, 3 generations), one genome per thread. Semantics = sim/avida.py = docs/14_exp11_avida.md.
// Per genome of length L (index g = sum op_i * 26^i): run the organism for 20 L cycles (TEST_CPU_TIME_MOD = AGE_LIMIT = 20), record
// its first divide (cycle, copy-true, parent intact) and all its divides (fecundity; the parent continues after a divide as under
// DIVIDE_METHOD 1); if the first child is not a copy of the genome, test the child (and its child) for 20 x length cycles each,
// viable when some offspring equals its parent or an ancestor (cTestCPU::TestGenome_Body).
// Output (<out>, text): counts, histograms and the list of viable genomes; with --genomes FILE one line per listed genome
// (letters a..z, one genome per line) whether viable or not, for fast/check_avida.py.
// usage: u1_avida --gpu g --len L [--lo A --hi B | --genomes FILE] --out FILE [--gens 3] [--max-list 1000000]
// Build: nvcc -O3 -arch=native -o u1_avida u1_avida.cu;  CPU logic check: g++ -O2 -x c++ -include cuda_shim.h -o u1_avida_emu u1_avida.cu
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <chrono>
#include <string>
#include <vector>
typedef unsigned long long ull;

#define MAXMEM 128          // memory of one organism: 3 x genome; the depth-2 organism's genome is <= 4 L, so L <= 10
#define MAXGEN 40           // genome of the depth-2 organism (4 L)
#define MAXCHILD 80         // a child of the depth-2 organism (2 x 4 L), compared only
#define MAXBUDGET 256       // 20 L cycles, L <= 10
#define STACK_SIZE 10
#define MAX_LABEL 10
#define MIN_GENOME_LENGTH 8
#define MAX_GENOME_LENGTH 2048
#define NUM_NOPS 3
#define INST_ERROR 255
enum { NOP_A, NOP_B, NOP_C, IF_N_EQU, IF_LESS, IF_LABEL, MOV_HEAD, JMP_HEAD, GET_HEAD, SET_FLOW, SHIFT_R, SHIFT_L, INC, DEC, PUSH, POP,
       SWAP_STK, SWAP, ADD, SUB, NAND, H_COPY, H_ALLOC, H_DIVIDE, IO, H_SEARCH };
enum { HEAD_IP, HEAD_READ, HEAD_WRITE, HEAD_FLOW };
enum { REG_AX, REG_BX, REG_CX };
// counters: 0 viable, 1..3 viable found at depth 0/1/2, 4 genomes dividing at depth 0 (any divide), 5 viable with intact parent,
// 6 viable with copy-true at depth 0, 7 genomes processed; 64.. first-divide cycle histogram (viable), 512.. fecundity histogram
// (viable), 768.. copy-true fecundity histogram (viable)
#define NCNT 1024
#define C_VIABLE 0
#define C_DEPTH 1
#define C_DIVIDES0 4
#define C_INTACT 5
#define C_COPYTRUE0 6
#define C_PROCESSED 7
#define C_FIRST 64
#define C_FEC 512
#define C_FECT 768

struct Cfg { int L, budget, gens, list_mode; unsigned max_list; };
__constant__ Cfg C;
__constant__ int INPUTS[3];

struct Org {
  unsigned char mem[MAXMEM]; unsigned exe[4], cop[4]; int size;
  int reg[3]; int heads[4]; int lstack[STACK_SIZE], gstack[STACK_SIZE]; int lsp, gsp, cur_stack;
  unsigned char rlabel[MAX_LABEL], nlabel[MAX_LABEL]; int rlen, nlen;
  int mal_active, advance_ip, time_used, num_divides, input_ptr;
  const unsigned char *genome; int glen;
  // first-divide record and lifetime statistics
  int first_step, first_copy_true, first_intact, divides_true, child_len; unsigned char child[MAXCHILD];
};

__device__ __forceinline__ int is_nop(int inst) { return inst < NUM_NOPS; }
__device__ __forceinline__ int adjust(const Org &o, int pos) {            // cHeadCPU::fullAdjust
  int size = o.size;
  if (pos >= 0 && pos < size) return pos;
  if (size == 0 || pos < 0) return 0;
  return pos < 2 * size ? pos - size : pos % size;
}
__device__ __forceinline__ void advance(Org &o, int h) { o.heads[h] = adjust(o, o.heads[h] + 1); }
__device__ __forceinline__ int next_inst(const Org &o) { int p = o.heads[HEAD_IP]; return p + 1 == o.size ? INST_ERROR : o.mem[p + 1]; }
__device__ __forceinline__ void set_exe(Org &o, int pos) { if (pos >= 0 && pos < o.size) o.exe[pos >> 5] |= 1u << (pos & 31); }
__device__ __forceinline__ void set_cop(Org &o, int pos) { o.cop[pos >> 5] |= 1u << (pos & 31); }
__device__ __forceinline__ int get_exe(const Org &o, int pos) { return (o.exe[pos >> 5] >> (pos & 31)) & 1; }
__device__ __forceinline__ int get_cop(const Org &o, int pos) { return (o.cop[pos >> 5] >> (pos & 31)) & 1; }
__device__ __forceinline__ int find_modified(Org &o, int def) {           // FindModifiedRegister / FindModifiedHead
  if (is_nop(next_inst(o))) { advance(o, HEAD_IP); def = o.mem[o.heads[HEAD_IP]]; set_exe(o, o.heads[HEAD_IP]); }
  return def;
}
__device__ __forceinline__ void read_next_label(Org &o) {                 // ReadLabel(MAX_LENGTH), MAX_LABEL_EXE_SIZE 1
  o.nlen = 0;
  while (is_nop(next_inst(o)) && o.nlen < MAX_LABEL) {
    advance(o, HEAD_IP); o.nlabel[o.nlen++] = o.mem[o.heads[HEAD_IP]];
    if (o.nlen <= 1) set_exe(o, o.heads[HEAD_IP]);
  }
}
__device__ __forceinline__ void complement_label(Org &o) { for (int i = 0; i < o.nlen; i++) { o.nlabel[i] += 1; if (o.nlabel[i] >= NUM_NOPS) o.nlabel[i] -= NUM_NOPS; } }
__device__ int find_label_forward(const Org &o, int pos) {                // cHardwareCPU::FindLabel_Forward, literally
  int size = o.size, search_start = pos, ls = o.nlen, found = 0;
  pos += ls;
  while (pos < size) {
    if (is_nop(o.mem[pos])) {
      int start_pos = pos, end_pos = pos + 1;
      while (start_pos > search_start && is_nop(o.mem[start_pos - 1])) start_pos--;
      while (end_pos < size && is_nop(o.mem[end_pos])) end_pos++;
      int max_offset = end_pos - start_pos - ls + 1, offset = start_pos;
      for (offset = start_pos; offset < start_pos + max_offset; offset++) {
        int matches;
        for (matches = 0; matches < ls; matches++) if (o.nlabel[matches] != o.mem[offset + matches]) break;
        if (matches == ls) { found = 1; break; }
      }
      if (found) { pos = ls + offset; break; }
      pos = end_pos;
    }
    pos += ls;
  }
  return found ? pos : -1;
}
__device__ __forceinline__ int find_label(Org &o) {                        // FindLabel(0)
  if (o.nlen == 0) return o.heads[HEAD_IP];
  int f = find_label_forward(o, 0);
  return f >= 0 ? adjust(o, f - 1) : o.heads[HEAD_IP];
}
__device__ __forceinline__ void stack_push(Org &o, int v) {
  if (o.cur_stack == 0) { o.lsp = o.lsp == 0 ? STACK_SIZE - 1 : o.lsp - 1; o.lstack[o.lsp] = v; }
  else { o.gsp = o.gsp == 0 ? STACK_SIZE - 1 : o.gsp - 1; o.gstack[o.gsp] = v; }
}
__device__ __forceinline__ int stack_pop(Org &o) {
  int v;
  if (o.cur_stack == 0) { v = o.lstack[o.lsp]; o.lstack[o.lsp] = 0; if (++o.lsp == STACK_SIZE) o.lsp = 0; }
  else { v = o.gstack[o.gsp]; o.gstack[o.gsp] = 0; if (++o.gsp == STACK_SIZE) o.gsp = 0; }
  return v;
}
__device__ int allocate_main(Org &o, int allocated) {                     // Allocate_Main with REQUIRE_ALLOCATE 1, ALLOC_METHOD 0
  if (o.mal_active) return 0;
  if (allocated < 1) return 0;
  int old = o.size, nw = old + allocated;
  if (nw > MAX_GENOME_LENGTH || nw < MIN_GENOME_LENGTH) return 0;
  if (allocated > (int)(old * 2.0)) return 0;
  if (old > (int)(allocated * 2.0)) return 0;
  if (nw > MAXMEM) return 0;                                              // cannot happen for L <= 10 (3 x 4 L = 120)
  for (int i = old; i < nw; i++) { o.mem[i] = 0; o.exe[i >> 5] &= ~(1u << (i & 31)); o.cop[i >> 5] &= ~(1u << (i & 31)); }
  o.size = nw; o.mal_active = 1;
  return 1;
}
__device__ int divide_check_viable(const Org &o, int parent_size, int child_size) {   // cHardwareBase::Divide_CheckViable, defaults
  int g = o.glen;
  int min_size = (int)(g / 2.0); if (min_size < MIN_GENOME_LENGTH) min_size = MIN_GENOME_LENGTH;
  int max_size = (int)(g * 2.0); if (max_size > MAX_GENOME_LENGTH) max_size = MAX_GENOME_LENGTH;
  if (child_size < min_size || child_size > max_size) return 0;
  if (parent_size < min_size || parent_size > max_size) return 0;
  int executed = 0; for (int i = 0; i < parent_size; i++) executed += get_exe(o, i);
  if (executed < (int)(parent_size * 0.5)) return 0;
  int copied = 0; for (int i = parent_size; i < parent_size + child_size; i++) copied += get_cop(o, i);
  if (copied < (int)(child_size * 0.5)) return 0;
  return 1;
}
__device__ int divide_main(Org &o, int div_point, int extra_lines) {      // Divide_Main, DIVIDE_METHOD 1, no mutations
  int child_size = o.size - div_point - extra_lines;
  if (!divide_check_viable(o, div_point, child_size)) return 0;
  int copy_true = child_size == o.glen; for (int i = 0; copy_true && i < child_size; i++) copy_true = o.mem[div_point + i] == o.genome[i];
  o.num_divides++; o.divides_true += copy_true;
  if (o.num_divides == 1) {
    o.first_step = o.time_used; o.first_copy_true = copy_true;
    int intact = div_point == o.glen; for (int i = 0; intact && i < div_point; i++) intact = o.mem[i] == o.genome[i];
    o.first_intact = intact; o.child_len = child_size;
    for (int i = 0; i < child_size && i < MAXCHILD; i++) o.child[i] = o.mem[div_point + i];
  }
  o.size = div_point; o.mal_active = 0; o.advance_ip = 0;
  // parent alive: Reset (registers, heads, stacks, labels) and ClearFlags
  o.reg[0] = o.reg[1] = o.reg[2] = 0; o.heads[0] = o.heads[1] = o.heads[2] = o.heads[3] = 0;
  for (int i = 0; i < STACK_SIZE; i++) o.lstack[i] = o.gstack[i] = 0; o.lsp = o.gsp = 0; o.cur_stack = 0; o.rlen = o.nlen = 0;
  o.exe[0] = o.exe[1] = o.exe[2] = o.exe[3] = 0; o.cop[0] = o.cop[1] = o.cop[2] = o.cop[3] = 0;
  return 1;
}
__device__ void execute(Org &o, int inst) {
  int *reg = o.reg, *heads = o.heads;
  if (inst < NUM_NOPS) return;
  switch (inst) {
  case IF_N_EQU: { int op1 = find_modified(o, REG_BX), op2 = (op1 + 1) % 3; if (reg[op1] == reg[op2]) advance(o, HEAD_IP); } break;
  case IF_LESS: { int op1 = find_modified(o, REG_BX), op2 = (op1 + 1) % 3; if (reg[op1] >= reg[op2]) advance(o, HEAD_IP); } break;
  case IF_LABEL: { read_next_label(o); complement_label(o); int eq = o.nlen == o.rlen; for (int i = 0; eq && i < o.nlen; i++) eq = o.nlabel[i] == o.rlabel[i];
                   if (!eq) advance(o, HEAD_IP); } break;
  case MOV_HEAD: { int h = find_modified(o, HEAD_IP); heads[h] = heads[HEAD_FLOW]; if (h == HEAD_IP) o.advance_ip = 0; } break;
  case JMP_HEAD: { int h = find_modified(o, HEAD_IP); heads[h] = adjust(o, (int)((unsigned)heads[h] + (unsigned)reg[REG_CX])); } break;
  case GET_HEAD: { int h = find_modified(o, HEAD_IP); reg[REG_CX] = heads[h]; } break;
  case SET_FLOW: { int r = find_modified(o, REG_CX); heads[HEAD_FLOW] = adjust(o, reg[r]); } break;
  case SHIFT_R: { int r = find_modified(o, REG_BX); reg[r] = reg[r] >> 1; } break;
  case SHIFT_L: { int r = find_modified(o, REG_BX); reg[r] = (int)((unsigned)reg[r] << 1); } break;
  case INC: { int r = find_modified(o, REG_BX); reg[r] = (int)((unsigned)reg[r] + 1u); } break;
  case DEC: { int r = find_modified(o, REG_BX); reg[r] = (int)((unsigned)reg[r] - 1u); } break;
  case PUSH: { int r = find_modified(o, REG_BX); stack_push(o, reg[r]); } break;
  case POP: { int r = find_modified(o, REG_BX); reg[r] = stack_pop(o); } break;
  case SWAP_STK: o.cur_stack ^= 1; break;
  case SWAP: { int op1 = find_modified(o, REG_BX), op2 = (op1 + 1) % 3, t = reg[op1]; reg[op1] = reg[op2]; reg[op2] = t; } break;
  case ADD: { int d = find_modified(o, REG_BX); reg[d] = (int)((unsigned)reg[REG_BX] + (unsigned)reg[REG_CX]); } break;
  case SUB: { int d = find_modified(o, REG_BX); reg[d] = (int)((unsigned)reg[REG_BX] - (unsigned)reg[REG_CX]); } break;
  case NAND: { int d = find_modified(o, REG_BX); reg[d] = ~(reg[REG_BX] & reg[REG_CX]); } break;
  case H_COPY: {
    heads[HEAD_READ] = adjust(o, heads[HEAD_READ]); heads[HEAD_WRITE] = adjust(o, heads[HEAD_WRITE]);
    int r = o.mem[heads[HEAD_READ]];
    if (is_nop(r)) { if (o.rlen < MAX_LABEL) o.rlabel[o.rlen++] = r; } else o.rlen = 0;
    o.mem[heads[HEAD_WRITE]] = r; set_cop(o, heads[HEAD_WRITE]);
    advance(o, HEAD_READ); advance(o, HEAD_WRITE);
  } break;
  case H_ALLOC: { int cur = o.size, alloc = (int)(2.0 * cur); if (alloc > MAX_GENOME_LENGTH - cur) alloc = MAX_GENOME_LENGTH - cur;
                  if (allocate_main(o, alloc)) reg[REG_AX] = cur; } break;
  case H_DIVIDE: {
    for (int h = 0; h < 4; h++) heads[h] = adjust(o, heads[h]);
    int div_pos = heads[HEAD_READ], child_end = heads[HEAD_WRITE]; if (child_end == 0) child_end = o.size;
    divide_main(o, div_pos, o.size - child_end);
    for (int h = 0; h < 4; h++) heads[h] = adjust(o, heads[h]);
  } break;
  case IO: { int r = find_modified(o, REG_BX); if (o.input_ptr >= 3) o.input_ptr = 0; reg[r] = INPUTS[o.input_ptr++]; } break;
  case H_SEARCH: {
    read_next_label(o); complement_label(o); int found = find_label(o);
    reg[REG_BX] = found - heads[HEAD_IP]; reg[REG_CX] = o.nlen; heads[HEAD_FLOW] = found; advance(o, HEAD_FLOW);
  } break;
  }
}
// run one organism for `budget` cycles (stop at the first divide unless lifetime); returns the number of divides
__device__ int run_org(Org &o, const unsigned char *genome, int glen, int budget, int lifetime) {
  o.genome = genome; o.glen = glen; o.size = glen; for (int i = 0; i < glen; i++) o.mem[i] = genome[i];
  o.exe[0] = o.exe[1] = o.exe[2] = o.exe[3] = 0; o.cop[0] = o.cop[1] = o.cop[2] = o.cop[3] = 0;
  o.reg[0] = o.reg[1] = o.reg[2] = 0; o.heads[0] = o.heads[1] = o.heads[2] = o.heads[3] = 0;
  for (int i = 0; i < STACK_SIZE; i++) o.lstack[i] = o.gstack[i] = 0; o.lsp = o.gsp = 0; o.cur_stack = 0; o.rlen = o.nlen = 0;
  o.mal_active = 0; o.advance_ip = 1; o.time_used = 0; o.num_divides = 0; o.input_ptr = 0;
  o.first_step = 0; o.first_copy_true = 0; o.first_intact = 0; o.divides_true = 0; o.child_len = 0;
  while (o.time_used < budget && (lifetime || o.num_divides == 0)) {
    o.time_used++; o.advance_ip = 1;
    o.heads[HEAD_IP] = adjust(o, o.heads[HEAD_IP]); int ip = o.heads[HEAD_IP]; int inst = o.mem[ip];
    set_exe(o, ip);
    execute(o, inst);
    if (o.advance_ip) advance(o, HEAD_IP);
  }
  return o.num_divides;
}
__device__ __forceinline__ int same(const unsigned char *a, int na, const unsigned char *b, int nb) { if (na != nb) return 0; for (int i = 0; i < na; i++) if (a[i] != b[i]) return 0; return 1; }

struct Res { int viable, depth, divides0, first_step, copy_true0, intact, fecundity, fecundity_true; };
__device__ void test_genome(const unsigned char *g0, int L, Res &r) {
  Org o; unsigned char c0[MAXCHILD], c1[MAXCHILD]; int l0 = 0, l1 = 0;
  int n0 = run_org(o, g0, L, 20 * L, 1);
  r.viable = 0; r.depth = -1; r.divides0 = n0; r.first_step = o.first_step; r.copy_true0 = o.first_copy_true; r.intact = o.first_intact;
  r.fecundity = n0; r.fecundity_true = o.divides_true;
  if (n0 == 0) return;
  if (o.first_copy_true) { r.viable = 1; r.depth = 0; return; }
  if (C.gens < 2) return;
  l0 = o.child_len; for (int i = 0; i < l0; i++) c0[i] = o.child[i];
  if (l0 > MAXGEN) return;                                                 // cannot happen (child <= 2 L <= 20)
  int n1 = run_org(o, c0, l0, 20 * l0, 0);
  if (n1 == 0) return;
  if (o.first_copy_true || same(o.child, o.child_len, g0, L)) { r.viable = 1; r.depth = 1; return; }
  if (C.gens < 3) return;
  l1 = o.child_len; for (int i = 0; i < l1; i++) c1[i] = o.child[i];
  if (l1 > MAXGEN) return;                                                 // cannot happen (child <= 2 x 2 L <= 40)
  int n2 = run_org(o, c1, l1, 20 * l1, 0);
  if (n2 == 0) return;
  if (o.first_copy_true || same(o.child, o.child_len, g0, L) || same(o.child, o.child_len, c0, l0)) { r.viable = 1; r.depth = 2; }
}

// list entries: index (ull), packed fields: depth | first_step << 2 | intact << 11 | copy_true0 << 12 | fecundity << 13 | fecundity_true << 22 | viable << 31
#ifdef EMU_LAUNCH
#define SH_ADD(k) atomicAdd(&cnt[k], 1u)          // single-threaded emulation: no shared-memory aggregation
#else
#define SH_ADD(k) atomicAdd(&sh[k], 1u)
#endif
__global__ void sweep(ull lo, ull count, const ull *idx_list, unsigned *cnt, ull *list_idx, unsigned *list_val, unsigned *nlist) {
#ifndef EMU_LAUNCH
  __shared__ unsigned sh[8];
  if (threadIdx.x < 8) sh[threadIdx.x] = 0;
  __syncthreads();
#endif
  ull i = blockIdx.x * (ull)blockDim.x + threadIdx.x;
  if (i < count) {
    ull g = idx_list ? idx_list[i] : lo + i; ull t = g; unsigned char genome[MAXGEN];
    for (int k = 0; k < C.L; k++) { genome[k] = (unsigned char)(t % 26); t /= 26; }
    Res r; test_genome(genome, C.L, r);
    SH_ADD(C_PROCESSED);
    if (r.divides0) SH_ADD(C_DIVIDES0);
    if (r.viable) {
      SH_ADD(C_VIABLE); SH_ADD(C_DEPTH + r.depth);
      if (r.intact) SH_ADD(C_INTACT); if (r.copy_true0) SH_ADD(C_COPYTRUE0);
      atomicAdd(&cnt[C_FIRST + r.first_step], 1u); atomicAdd(&cnt[C_FEC + (r.fecundity < 255 ? r.fecundity : 255)], 1u); atomicAdd(&cnt[C_FECT + (r.fecundity_true < 255 ? r.fecundity_true : 255)], 1u);
    }
    if (r.viable || C.list_mode) {
      unsigned slot = atomicAdd(nlist, 1u);
      if (slot < C.max_list) { list_idx[slot] = g; list_val[slot] = (unsigned)(r.depth & 3) | ((unsigned)r.first_step << 2) | ((unsigned)r.intact << 11) | ((unsigned)r.copy_true0 << 12)
                               | ((unsigned)(r.fecundity < 511 ? r.fecundity : 511) << 13) | ((unsigned)(r.fecundity_true < 511 ? r.fecundity_true : 511) << 22) | ((unsigned)r.viable << 31); }
    }
  }
#ifndef EMU_LAUNCH
  __syncthreads();
  if (threadIdx.x < 8 && sh[threadIdx.x]) atomicAdd(&cnt[threadIdx.x], sh[threadIdx.x]);
#endif
}

static ull pow26(int n) { ull p = 1; for (int i = 0; i < n; i++) p *= 26; return p; }
int main(int argc, char **argv) {
  Cfg c; memset(&c, 0, sizeof c); c.L = 8; c.gens = 3; c.max_list = 1000000;
  const char *out = nullptr, *genomes = nullptr; int gpu = 0; ull lo = 0, hi = 0; int have = 0;
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--len")) c.L = atoi(argv[++i]); else if (ARG("--gens")) c.gens = atoi(argv[++i]); else if (ARG("--out")) out = argv[++i]; else if (ARG("--gpu")) gpu = atoi(argv[++i]);
    else if (ARG("--max-list")) c.max_list = (unsigned)strtoul(argv[++i], 0, 0); else if (ARG("--genomes")) genomes = argv[++i];
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have = 1; } else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have = 1; }
    else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  if (!out || c.L < 1 || c.L > 10 || c.gens < 1 || c.gens > 3) { fprintf(stderr, "need --out; 1 <= --len <= 10; 1 <= --gens <= 3\n"); return 2; }
  c.budget = 20 * c.L; ull total = pow26(c.L); if (!have) { lo = 0; hi = total; }
  if (hi > total) hi = total;
  std::vector<ull> idx; std::vector<std::string> names;
  if (genomes) {
    c.list_mode = 1; FILE *f = fopen(genomes, "r"); if (!f) { perror(genomes); return 1; } char buf[256];
    while (fgets(buf, sizeof buf, f)) { std::string s; for (char *p = buf; *p; p++) if (*p >= 'a' && *p <= 'z') s += *p; if ((int)s.size() != c.L) continue;
      ull g = 0; for (int k = c.L - 1; k >= 0; k--) g = g * 26 + (s[k] - 'a'); idx.push_back(g); names.push_back(s); }
    fclose(f); lo = 0; hi = idx.size(); if (c.max_list < idx.size()) c.max_list = (unsigned)idx.size();
  }
  int inputs[3] = { 0x0f13149f, 0x3308e53e, 0x556241eb };
  cudaSetDevice(gpu); cudaDeviceProp prop; cudaGetDeviceProperties(&prop, gpu);
  cudaMemcpyToSymbol(C, &c, sizeof c); cudaMemcpyToSymbol(INPUTS, inputs, sizeof inputs);
  unsigned *d_cnt, *d_lval, *d_nlist; ull *d_lidx, *d_idx = nullptr;
  cudaMalloc(&d_cnt, NCNT * 4); cudaMalloc(&d_lidx, (size_t)c.max_list * 8); cudaMalloc(&d_lval, (size_t)c.max_list * 4); cudaMalloc(&d_nlist, 4);
  cudaMemset(d_cnt, 0, NCNT * 4); cudaMemset(d_nlist, 0, 4);
  if (c.list_mode) { cudaMalloc(&d_idx, idx.size() * 8 + 8); cudaMemcpy(d_idx, idx.data(), idx.size() * 8, cudaMemcpyHostToDevice); }
  auto t0 = std::chrono::steady_clock::now();
  const ull SUB = 1ull << 24;
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
#ifdef EMU_LAUNCH
    EMU_LAUNCH(sweep, (unsigned)((n + 127) / 128), 128, off, n, d_idx ? d_idx + (off - lo) : nullptr, d_cnt, d_lidx, d_lval, d_nlist);
#else
    sweep<<<(unsigned)((n + 127) / 128), 128>>>(off, n, d_idx ? d_idx + (off - lo) : nullptr, d_cnt, d_lidx, d_lval, d_nlist);
#endif
    cudaError_t e = cudaDeviceSynchronize(); if (e != cudaSuccess) { fprintf(stderr, "ERROR %s\n", cudaGetErrorString(e)); return 1; }
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  std::vector<unsigned> cnt(NCNT); unsigned nlist;
  cudaMemcpy(cnt.data(), d_cnt, NCNT * 4, cudaMemcpyDeviceToHost); cudaMemcpy(&nlist, d_nlist, 4, cudaMemcpyDeviceToHost);
  unsigned nl = nlist < c.max_list ? nlist : c.max_list; std::vector<ull> lidx(nl); std::vector<unsigned> lval(nl);
  if (nl) { cudaMemcpy(lidx.data(), d_lidx, (size_t)nl * 8, cudaMemcpyDeviceToHost); cudaMemcpy(lval.data(), d_lval, (size_t)nl * 4, cudaMemcpyDeviceToHost); }
  if (cnt[C_PROCESSED] != hi - lo) { fprintf(stderr, "ERROR %u of %llu genomes accounted for\n", cnt[C_PROCESSED], hi - lo); return 1; }
  FILE *g = fopen(out, "w"); if (!g) { perror(out); return 1; }
  fprintf(g, "avida len %d genomes [%llu,%llu) budget %d gens %d%s\n", c.L, lo, hi, c.budget, c.gens, c.list_mode ? " list-mode" : "");
  fprintf(g, "viable %u depth0 %u depth1 %u depth2 %u divides0 %u intact %u copy_true0 %u processed %u\n", cnt[C_VIABLE], cnt[C_DEPTH], cnt[C_DEPTH + 1], cnt[C_DEPTH + 2], cnt[C_DIVIDES0], cnt[C_INTACT], cnt[C_COPYTRUE0], cnt[C_PROCESSED]);
  fprintf(g, "first_divide_hist"); for (int t = 0; t <= c.budget; t++) if (cnt[C_FIRST + t]) fprintf(g, " %d:%u", t, cnt[C_FIRST + t]); fprintf(g, "\n");
  fprintf(g, "fecundity_hist"); for (int t = 0; t < 256; t++) if (cnt[C_FEC + t]) fprintf(g, " %d:%u", t, cnt[C_FEC + t]); fprintf(g, "\n");
  fprintf(g, "fecundity_true_hist"); for (int t = 0; t < 256; t++) if (cnt[C_FECT + t]) fprintf(g, " %d:%u", t, cnt[C_FECT + t]); fprintf(g, "\n");
  fprintf(g, "listed %u of %u\n", nl, nlist);
  for (unsigned i = 0; i < nl; i++) {
    ull t = lidx[i]; char s[16]; for (int k = 0; k < c.L; k++) { s[k] = 'a' + (char)(t % 26); t /= 26; } s[c.L] = 0; unsigned v = lval[i];
    fprintf(g, "genome %s index %llu viable %u depth %d first %u intact %u copy_true %u fecundity %u fecundity_true %u\n", s, lidx[i], v >> 31, (int)(v & 3) == 3 ? -1 : (int)(v & 3), (v >> 2) & 511, (v >> 11) & 1, (v >> 12) & 1, (v >> 13) & 511, (v >> 22) & 511);
  }
  fclose(g);
  fprintf(stderr, "avida L=%d genomes=[%llu,%llu) viable=%u (depth 0/1/2 %u/%u/%u) divides0=%u %.2fs (%.2f Mgen/s) %s\n", c.L, lo, hi, cnt[C_VIABLE], cnt[C_DEPTH], cnt[C_DEPTH + 1], cnt[C_DEPTH + 2], cnt[C_DIVIDES0], secs, (hi - lo) / secs / 1e6, prop.name);
  printf("%u\n", cnt[C_VIABLE]);
  return 0;
}
