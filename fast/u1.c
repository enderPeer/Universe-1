/* Universe-1 fast brute-force core.
 * Mirrors sim/machine.py exactly (layout L3: address 0 aliases A).
 * Enumerates program ids [lo, hi) of a 2^p x I bit code image for a fixed
 * ISA, runs every input for <= 256 steps, collects distinct truth tables.
 *
 * build: make -C fast        run: fast/u1 --help
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define MAX_STEPS 256
#define MAXM 256

enum { P_NOP, P_HALT, P_LD, P_ST, P_LDI, P_CLR, P_SET, P_NOT, P_AND, P_OR, P_XOR,
       P_NAND, P_NOR, P_XNOR, P_ADD, P_ADC, P_SUB, P_INC, P_DEC, P_NEG, P_SHL, P_SHR,
       P_ROL, P_ROR, P_RCL, P_MUL, P_SWAP, P_JMP, P_JZ, P_JNZ, P_JC, P_SKZ, P_SKNZ,
       P_INCM, P_DECM, P_LDIND, P_STIND, P_COUNT };
static const char *PNAME[P_COUNT] = {
  "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR",
  "ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP",
  "JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND" };

typedef struct { int W, a, p, I, o, sbits; uint32_t mask, amask, pmask, opmask; int nins, nM; } Cfg;
typedef struct { uint32_t A, Z, C, PC, H, chg; uint32_t M[MAXM]; } St;

static inline uint32_t rd(const Cfg *c, St *s, uint32_t addr) {
  addr &= c->amask; return addr == 0 ? s->A : s->M[addr];
}
static inline void wr(const Cfg *c, St *s, uint32_t addr, uint32_t v) {
  addr &= c->amask; v &= c->mask;
  if (addr == 0) { if (s->A != v) s->chg = 1; s->A = v; }
  else { if (s->M[addr] != v) s->chg = 1; s->M[addr] = v; }
}
static inline void setA(const Cfg *c, St *s, uint32_t v) {
  v &= c->mask; if (s->A != v) s->chg = 1; s->A = v;
  uint32_t z = (v == 0); if (s->Z != z) s->chg = 1; s->Z = z;
}
static inline void setC(St *s, uint32_t cy) { if (s->C != cy) s->chg = 1; s->C = cy; }

/* packed full state, valid when c->sbits <= 30 */
static inline uint32_t pack(const Cfg *c, const St *s) {
  uint32_t k = s->A | (s->Z << c->W) | (s->C << (c->W + 1)) | (s->PC << (c->W + 2));
  int sh = c->W + 2 + c->p;
  for (int i = 1; i < c->nM; i++) { k |= s->M[i] << sh; sh += c->W; }
  return k;
}
static inline void unpack(const Cfg *c, St *s, uint32_t k) {
  s->A = k & c->mask; s->Z = (k >> c->W) & 1; s->C = (k >> (c->W + 1)) & 1; s->PC = (k >> (c->W + 2)) & c->pmask;
  int sh = c->W + 2 + c->p;
  for (int i = 1; i < c->nM; i++) { s->M[i] = (k >> sh) & c->mask; sh += c->W; }
}
typedef struct { uint32_t *stamp; uint32_t cur; uint32_t hist[MAX_STEPS + 1]; } Vis;

/* returns 0 = budget/loop, 1 = halt. On a repeated state the run is periodic
 * and the state at step MAX_STEPS is reconstructed from the history. */
static inline int run(const Cfg *c, const uint8_t *opc, const uint8_t *opnd,
                      uint32_t initA, uint32_t y, int have_y, St *s, Vis *vis) {
  s->A = initA & c->mask; s->Z = (s->A == 0); s->C = 0; s->PC = 0; s->H = 0;
  memset(s->M, 0, sizeof(uint32_t) * c->nM);
  if (have_y) s->M[1] = y;
  if (vis) { if (++vis->cur == 0) { memset(vis->stamp, 0, sizeof(uint32_t) << c->sbits); vis->cur = 1; }
             uint32_t k = pack(c, s); vis->stamp[k] = vis->cur; vis->hist[0] = k; }
  for (int t = 0; t < MAX_STEPS; t++) {
    uint32_t pc0 = s->PC;
    uint32_t k = s->PC & c->pmask, op = opnd[k];
    s->PC = (s->PC + 1) & c->pmask; s->chg = 0;
    uint32_t v, cy;
    switch (opc[k]) {
    case P_NOP: break;
    case P_HALT: s->H = 1; return 1;
    case P_LD: setA(c, s, rd(c, s, op)); break;
    case P_ST: wr(c, s, op, s->A); break;
    case P_LDI: setA(c, s, op); break;
    case P_CLR: setA(c, s, 0); break;
    case P_SET: setA(c, s, c->mask); break;
    case P_NOT: setA(c, s, ~s->A); break;
    case P_AND: setA(c, s, s->A & rd(c, s, op)); break;
    case P_OR: setA(c, s, s->A | rd(c, s, op)); break;
    case P_XOR: setA(c, s, s->A ^ rd(c, s, op)); break;
    case P_NAND: setA(c, s, ~(s->A & rd(c, s, op))); break;
    case P_NOR: setA(c, s, ~(s->A | rd(c, s, op))); break;
    case P_XNOR: setA(c, s, ~(s->A ^ rd(c, s, op))); break;
    case P_ADD: v = s->A + rd(c, s, op); setA(c, s, v); setC(s, v > c->mask); break;
    case P_ADC: v = s->A + rd(c, s, op) + s->C; setA(c, s, v); setC(s, v > c->mask); break;
    case P_SUB: v = s->A - rd(c, s, op); cy = (int32_t)v < 0; setA(c, s, v); setC(s, cy); break;
    case P_INC: v = s->A + 1; setA(c, s, v); setC(s, v > c->mask); break;
    case P_DEC: v = s->A - 1; cy = (int32_t)v < 0; setA(c, s, v); setC(s, cy); break;
    case P_NEG: cy = s->A != 0; setA(c, s, -s->A); setC(s, cy); break;
    case P_SHL: cy = (s->A >> (c->W - 1)) & 1; setA(c, s, s->A << 1); setC(s, cy); break;
    case P_SHR: cy = s->A & 1; setA(c, s, s->A >> 1); setC(s, cy); break;
    case P_ROL: setA(c, s, (s->A << 1) | (s->A >> (c->W - 1))); break;
    case P_ROR: setA(c, s, (s->A >> 1) | ((s->A & 1) << (c->W - 1))); break;
    case P_RCL: cy = (s->A >> (c->W - 1)) & 1; setA(c, s, (s->A << 1) | s->C); setC(s, cy); break;
    case P_MUL: setA(c, s, s->A * rd(c, s, op)); break;
    case P_SWAP: { uint32_t tA = s->A, t = rd(c, s, op); wr(c, s, op, tA); setA(c, s, t); } break;
    case P_JMP: s->PC = op & c->pmask; break;
    case P_JZ: if (s->Z) s->PC = op & c->pmask; break;
    case P_JNZ: if (!s->Z) s->PC = op & c->pmask; break;
    case P_JC: if (s->C) s->PC = op & c->pmask; break;
    case P_SKZ: if (s->Z) s->PC = (s->PC + 1) & c->pmask; break;
    case P_SKNZ: if (!s->Z) s->PC = (s->PC + 1) & c->pmask; break;
    case P_INCM: wr(c, s, op, rd(c, s, op) + 1); break;
    case P_DECM: wr(c, s, op, rd(c, s, op) - 1); break;
    case P_LDIND: setA(c, s, rd(c, s, rd(c, s, op))); break;
    case P_STIND: wr(c, s, rd(c, s, op), s->A); break;
    }
    if (vis) {
      uint32_t k = pack(c, s);
      if (vis->stamp[k] == vis->cur) {
        /* find start of cycle in history */
        int start = 0; while (vis->hist[start] != k) start++;
        int period = (t + 1) - start;
        int idx = start + (MAX_STEPS - start) % period;
        unpack(c, s, vis->hist[idx]);
        return 0;
      }
      vis->stamp[k] = vis->cur; vis->hist[t + 1] = k;
    } else if (!s->chg && s->PC == pc0) return 0; /* fixed point */
  }
  return 0;
}

/* ---- hash set of (lo,hi) -> prog --------------------------------------- */
typedef struct { uint64_t lo, hi; uint32_t prog; uint8_t used; } Rec;
typedef struct { Rec *t; uint64_t cap, n; } Set;
static uint64_t mix(uint64_t x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }
static void set_init(Set *s, uint64_t cap) { s->cap = cap; s->n = 0; s->t = calloc(cap, sizeof(Rec)); if (!s->t) { perror("calloc"); exit(1); } }
static void set_add(Set *s, uint64_t lo, uint64_t hi, uint32_t prog);
static void set_grow(Set *s) {
  Set n; set_init(&n, s->cap * 2);
  for (uint64_t i = 0; i < s->cap; i++) if (s->t[i].used) set_add(&n, s->t[i].lo, s->t[i].hi, s->t[i].prog);
  free(s->t); *s = n;
}
static void set_add(Set *s, uint64_t lo, uint64_t hi, uint32_t prog) {
  if (s->n * 10 >= s->cap * 7) set_grow(s);
  uint64_t i = mix(lo ^ mix(hi)) & (s->cap - 1);
  for (;;) {
    Rec *r = &s->t[i];
    if (!r->used) { r->used = 1; r->lo = lo; r->hi = hi; r->prog = prog; s->n++; return; }
    if (r->lo == lo && r->hi == hi) { if (prog < r->prog) r->prog = prog; return; }
    i = (i + 1) & (s->cap - 1);
  }
}

/* table -> key. exact when total bits <= 128, else 2x64-bit hash */
static void table_key(const uint8_t *tbl, int n, int W, uint64_t *lo, uint64_t *hi) {
  if (n * W <= 128) {
    uint64_t l = 0, h = 0;
    for (int i = 0; i < n; i++) {
      int sh = i * W;
      if (sh < 64) { l |= (uint64_t)tbl[i] << sh; if (sh + W > 64) h |= (uint64_t)tbl[i] >> (64 - sh); }
      else h |= (uint64_t)tbl[i] << (sh - 64);
    }
    *lo = l; *hi = h; return;
  }
  uint64_t a = 0x9E3779B97F4A7C15ULL, b = 0xD1B54A32D192ED03ULL;
  for (int i = 0; i < n; i++) { a = mix(a ^ tbl[i]); b = mix(b + tbl[i] * 0x100000001b3ULL); }
  *lo = a; *hi = b;
}

static void usage(void) {
  fprintf(stderr,
  "u1 --W w --a a --p p [--I i] --isa LD,ST,... [--binary] [--lo L --hi H]\n"
  "   [--shard i --nshards n] [--out file] [--threads t] [--novis]\n"
  "program bits = 2^p * I; program ids enumerate [lo,hi) (default whole space)\n"
  "ISA length must be a power of two <= 2^I; opcode uses the top log2(len) bits.\n");
  exit(2);
}

int main(int argc, char **argv) {
  Cfg c = {0}; c.W = 4; c.a = 2; c.p = 3; c.I = -1;
  const char *isa_s = NULL, *out = NULL; int binary = 0, threads = 0, novis = 0;
  uint64_t lo = 0, hi = 0; int have_range = 0; long shard = -1, nshards = 1;
  for (int i = 1; i < argc; i++) {
    #define ARG(name) (!strcmp(argv[i], name) && i + 1 < argc)
    if (ARG("--W")) c.W = atoi(argv[++i]);
    else if (ARG("--a")) c.a = atoi(argv[++i]);
    else if (ARG("--p")) c.p = atoi(argv[++i]);
    else if (ARG("--I")) c.I = atoi(argv[++i]);
    else if (ARG("--isa")) isa_s = argv[++i];
    else if (ARG("--out")) out = argv[++i];
    else if (ARG("--threads")) threads = atoi(argv[++i]);
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have_range = 1; }
    else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have_range = 1; }
    else if (ARG("--shard")) shard = atol(argv[++i]);
    else if (ARG("--nshards")) nshards = atol(argv[++i]);
    else if (!strcmp(argv[i], "--binary")) binary = 1;
    else if (!strcmp(argv[i], "--novis")) novis = 1;
    else usage();
  }
  if (!isa_s || c.W < 1 || c.W > 8 || c.a < 0 || c.a > 8 || c.p < 1 || c.p > 8) usage();
  if (c.I < 0) c.I = c.W;
  c.mask = (1u << c.W) - 1; c.amask = (1u << c.a) - 1; c.pmask = (1u << c.p) - 1;
  c.nins = 1 << c.p; c.nM = 1 << c.a;
  if (binary && c.a < 1) { fprintf(stderr, "--binary needs --a >= 1\n"); return 2; }

  uint8_t isa[256]; int nisa = 0;
  char buf[2048]; strncpy(buf, isa_s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
  for (char *tok = strtok(buf, ","); tok; tok = strtok(NULL, ",")) {
    int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(tok, PNAME[k])) id = k;
    if (id < 0) { fprintf(stderr, "unknown primitive %s\n", tok); return 2; }
    isa[nisa++] = (uint8_t)id;
  }
  if (nisa & (nisa - 1)) { fprintf(stderr, "ISA length must be power of two\n"); return 2; }
  c.o = 0; while ((1 << c.o) < nisa) c.o++; if (c.o == 0) c.o = 1;
  if (c.o > c.I) { fprintf(stderr, "opcode bits %d > I %d\n", c.o, c.I); return 2; }
  c.opmask = (1u << (c.I - c.o)) - 1;

  int pbits = c.nins * c.I;
  if (pbits > 64) { fprintf(stderr, "program bits %d > 64 unsupported\n", pbits); return 2; }
  uint64_t total = pbits == 64 ? UINT64_MAX : (1ULL << pbits);
  if (!have_range) { lo = 0; hi = total; }
  if (shard >= 0) { uint64_t span = hi - lo; lo = lo + span * shard / nshards; hi = lo + (span * (shard + 1) / nshards - span * shard / nshards); }
  if (pbits > 32) { fprintf(stderr, "note: program bits %d > 32; use --lo/--hi or shards\n", pbits); }

  c.sbits = c.W + 2 + c.p + (c.nM - 1) * c.W;
  int use_vis = !novis && c.sbits <= 26; /* 256 MB stamp table per thread at most */
  if (!use_vis) fprintf(stderr, "cycle detection off (state bits %d, novis=%d): fixed-point detection only\n", c.sbits, novis);
  int nin = 1 << c.W, ntab = binary ? nin * nin : nin;
#ifdef _OPENMP
  if (threads > 0) omp_set_num_threads(threads);
  int nthr = omp_get_max_threads();
#else
  int nthr = 1;
#endif
  Set *sets = calloc(nthr, sizeof(Set));
  for (int t = 0; t < nthr; t++) set_init(&sets[t], 1 << 16);
  uint64_t halts = 0, runs = 0;
  double t0 = (double)clock() / CLOCKS_PER_SEC;
#ifdef _OPENMP
  t0 = omp_get_wtime();
#endif
  #pragma omp parallel reduction(+:halts,runs)
  {
#ifdef _OPENMP
    int tid = omp_get_thread_num();
#else
    int tid = 0;
#endif
    St s; uint8_t opc[256], opnd[256], tbl[65536];
    Vis vis = {0}, *vp = NULL;
    if (use_vis) { vis.stamp = calloc(1u << c.sbits, sizeof(uint32_t)); if (!vis.stamp) { perror("calloc"); exit(1); } vp = &vis; }
    #pragma omp for schedule(dynamic, 8192)
    for (uint64_t pb = lo; pb < hi; pb++) {
      for (int k = 0; k < c.nins; k++) {
        uint32_t ins = (uint32_t)((pb >> (k * c.I)) & ((1u << c.I) - 1));
        opc[k] = isa[ins >> (c.I - c.o)]; opnd[k] = ins & c.opmask;
      }
      int idx = 0;
      if (!binary) {
        for (int x = 0; x < nin; x++) { halts += run(&c, opc, opnd, x, 0, 0, &s, vp); tbl[idx++] = (uint8_t)s.A; runs++; }
      } else {
        for (int x = 0; x < nin; x++) for (int y = 0; y < nin; y++) { halts += run(&c, opc, opnd, x, y, 1, &s, vp); tbl[idx++] = (uint8_t)s.A; runs++; }
      }
      uint64_t klo, khi; table_key(tbl, ntab, c.W, &klo, &khi);
      set_add(&sets[tid], klo, khi, (uint32_t)pb);
    }
    free(vis.stamp);
  }
  for (int t = 1; t < nthr; t++) { for (uint64_t i = 0; i < sets[t].cap; i++) if (sets[t].t[i].used) set_add(&sets[0], sets[t].t[i].lo, sets[t].t[i].hi, sets[t].t[i].prog); free(sets[t].t); }
  double t1 = (double)clock() / CLOCKS_PER_SEC;
#ifdef _OPENMP
  t1 = omp_get_wtime();
#endif
  if (out) {
    FILE *f = fopen(out, "wb"); if (!f) { perror(out); return 1; }
    /* header: magic, W,a,p,I,o,binary, lo, hi, count ; then records lo,hi,prog (little endian native) */
    uint32_t hdr[8] = { 0x55314231u, (uint32_t)c.W, (uint32_t)c.a, (uint32_t)c.p, (uint32_t)c.I, (uint32_t)c.o, (uint32_t)binary, (uint32_t)nisa };
    fwrite(hdr, 4, 8, f); fwrite(&lo, 8, 1, f); fwrite(&hi, 8, 1, f); fwrite(&sets[0].n, 8, 1, f);
    fwrite(isa, 1, nisa, f);
    for (uint64_t i = 0; i < sets[0].cap; i++) if (sets[0].t[i].used) { fwrite(&sets[0].t[i].lo, 8, 1, f); fwrite(&sets[0].t[i].hi, 8, 1, f); fwrite(&sets[0].t[i].prog, 4, 1, f); }
    fclose(f);
  }
  fprintf(stderr, "W=%d a=%d p=%d I=%d o=%d isa=%s %s programs=[%llu,%llu) n=%llu distinct=%llu halt_runs=%llu/%llu %.1fs (%.2f Mprog/s, %d thr)\n",
    c.W, c.a, c.p, c.I, c.o, isa_s, binary ? "binary" : "unary", (unsigned long long)lo, (unsigned long long)hi,
    (unsigned long long)(hi - lo), (unsigned long long)sets[0].n, (unsigned long long)halts, (unsigned long long)runs,
    t1 - t0, (hi - lo) / (t1 - t0) / 1e6, nthr);
  printf("%llu\n", (unsigned long long)sets[0].n);
  return 0;
}
