/* Universe-1 Life, Vulkan host for life/u1life.comp (AMD GPUs). Same CLI and outputs as life/u1life.cu.
 * usage: u1life_vk --gpu g [same options as u1life_cuda]. Build: make -C life u1life_vk */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vulkan/vulkan.h>
#define CK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { fprintf(stderr, "ERROR %s failed: %d\n", #x, r_); exit(1); } } while (0)
typedef unsigned long long ull;
typedef struct { uint32_t mode, n, W, a, p, I, o, income, trigger, repro_cost, max_energy, max_age, start_energy, thr_hi, pad0, pad1, seed_lo, seed_hi, tick_lo, tick_hi, mu_lo, mu_hi, dr_lo, dr_hi; } Push;
static const char *PNAME[] = { "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR","ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP","JMP","JZ","JNZ","JC","SKZ","SKNZ","INCM","DECM","LDIND","STIND" };
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static uint64_t mix(uint64_t x) { x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x; }
static VkPhysicalDevice phys; static VkDevice dev;
static VkBuffer make_buffer(VkDeviceSize size, void **map) {
  VkBuffer buf; VkDeviceMemory mem;
  VkBufferCreateInfo bi = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, VK_SHARING_MODE_EXCLUSIVE, 0, NULL };
  CK(vkCreateBuffer(dev, &bi, NULL, &buf)); VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev, buf, &mr);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(phys, &mp);
  VkMemoryPropertyFlags want[2] = { VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT };
  uint32_t type = UINT32_MAX; for (int w = 0; w < 2 && type == UINT32_MAX; w++) for (uint32_t i = 0; i < mp.memoryTypeCount; i++) if ((mr.memoryTypeBits & (1u << i)) && (mp.memoryTypes[i].propertyFlags & want[w]) == want[w]) { type = i; break; }
  VkMemoryAllocateInfo ai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, mr.size, type };
  CK(vkAllocateMemory(dev, &ai, NULL, &mem)); CK(vkBindBufferMemory(dev, buf, mem, 0)); CK(vkMapMemory(dev, mem, 0, VK_WHOLE_SIZE, 0, map)); return buf;
}
int main(int argc, char **argv) {
  Push P; memset(&P, 0, sizeof P); P.n = 256; P.W = 4; P.a = 2; P.p = 3; P.I = 4; P.income = 20; P.trigger = 15; P.repro_cost = 128; P.max_energy = 255; P.max_age = 1024; P.start_energy = 64;
  uint64_t seed = 1, mu = 128, dr = 512, ticks = 10000, report = 100; double density = 0.05; const char *isa_s = "SWAP,ADD,NAND,SKZ", *out_dir = ".", *load = NULL; int gpu = 0, dump_final = 0;
  for (int i = 1; i < argc; i++) {
    #define ARG(nm) (!strcmp(argv[i], nm) && i + 1 < argc)
    if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--N")) P.n = atoi(argv[++i]); else if (ARG("--seed")) seed = strtoull(argv[++i], 0, 0);
    else if (ARG("--density")) density = atof(argv[++i]); else if (ARG("--ticks")) ticks = strtoull(argv[++i], 0, 0); else if (ARG("--report-every")) report = strtoull(argv[++i], 0, 0);
    else if (ARG("--isa")) isa_s = argv[++i]; else if (ARG("--a")) P.a = atoi(argv[++i]); else if (ARG("--p")) P.p = atoi(argv[++i]); else if (ARG("--I")) P.I = atoi(argv[++i]);
    else if (ARG("--income")) P.income = atoi(argv[++i]); else if (ARG("--trigger")) P.trigger = atoi(argv[++i]); else if (ARG("--repro-cost")) P.repro_cost = atoi(argv[++i]);
    else if (ARG("--max-energy")) P.max_energy = atoi(argv[++i]); else if (ARG("--mu-bits")) mu = strtoull(argv[++i], 0, 0); else if (ARG("--max-age")) P.max_age = atoi(argv[++i]);
    else if (ARG("--death-rate")) dr = strtoull(argv[++i], 0, 0); else if (ARG("--start-energy")) P.start_energy = atoi(argv[++i]); else if (ARG("--out-dir")) out_dir = argv[++i];
    else if (ARG("--load")) load = argv[++i]; else if (!strcmp(argv[i], "--dump-final")) dump_final = 1; else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  uint32_t isa[256]; int nisa = 0; char buf[1024]; strncpy(buf, isa_s, 1023); buf[1023] = 0;
  for (char *t = strtok(buf, ","); t; t = strtok(NULL, ",")) { int id = -1; for (int k = 0; k < 37; k++) if (!strcmp(t, PNAME[k])) id = k; if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa++] = id; }
  P.o = 0; while ((1 << P.o) < nisa) P.o++; if (P.o == 0) P.o = 1;
  if ((1u << P.p) > 8 || (1u << P.a) > 16) { fprintf(stderr, "shader compiled for <= 8 instructions, a <= 4\n"); return 2; }
  P.seed_lo = (uint32_t)seed; P.seed_hi = seed >> 32; P.mu_lo = (uint32_t)mu; P.mu_hi = mu >> 32; P.dr_lo = (uint32_t)dr; P.dr_hi = dr >> 32; P.thr_hi = (uint32_t)(density * 4294967296.0);
  ull nn = (ull)P.n * P.n;
  FILE *f = fopen("life/u1life.spv", "rb"); if (!f) f = fopen("u1life.spv", "rb"); if (!f) { fprintf(stderr, "u1life.spv not found\n"); return 1; }
  fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET); uint32_t *spv = malloc(len); if (fread(spv, 1, len, f) != (size_t)len) return 1; fclose(f);
  VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "u1life", 1, "none", 1, VK_API_VERSION_1_2 };
  VkInstanceCreateInfo ici = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, NULL, 0, &app, 0, NULL, 0, NULL }; VkInstance inst; CK(vkCreateInstance(&ici, NULL, &inst));
  uint32_t np = 0; vkEnumeratePhysicalDevices(inst, &np, NULL); VkPhysicalDevice *all = malloc(np * sizeof *all); vkEnumeratePhysicalDevices(inst, &np, all);
  VkPhysicalDeviceProperties props; int seen = -1;
  for (uint32_t i = 0; i < np; i++) { vkGetPhysicalDeviceProperties(all[i], &props); if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU && ++seen == gpu) { phys = all[i]; break; } }
  if (!phys) { fprintf(stderr, "discrete GPU %d not found\n", gpu); return 1; } vkGetPhysicalDeviceProperties(phys, &props);
  uint32_t nq = 0; vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, NULL); VkQueueFamilyProperties *qf = malloc(nq * sizeof *qf); vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, qf); uint32_t qfi = UINT32_MAX;
  for (uint32_t i = 0; i < nq; i++) if ((qf[i].queueFlags & VK_QUEUE_COMPUTE_BIT) && !(qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) { qfi = i; break; }
  if (qfi == UINT32_MAX) for (uint32_t i = 0; i < nq; i++) if (qf[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qfi = i; break; }
  float prio = 1.0f; VkDeviceQueueCreateInfo qci = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, NULL, 0, qfi, 1, &prio };
  VkPhysicalDeviceFeatures feat = {0}; feat.shaderInt64 = VK_TRUE;
  VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, NULL, 0, 1, &qci, 0, NULL, 0, NULL, &feat }; CK(vkCreateDevice(phys, &dci, NULL, &dev)); VkQueue queue; vkGetDeviceQueue(dev, qfi, 0, &queue);
  void *maps[7]; VkBuffer bufs[7]; VkDeviceSize sizes[7] = { nn * 4, nn * 4, nn * 4, nn * 4, nn * 4, 64, 1024 };
  for (int i = 0; i < 7; i++) bufs[i] = make_buffer(sizes[i], &maps[i]);
  memcpy(maps[6], isa, nisa * 4);
  VkDescriptorSetLayoutBinding binds[7]; for (int i = 0; i < 7; i++) binds[i] = (VkDescriptorSetLayoutBinding){ i, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL };
  VkDescriptorSetLayoutCreateInfo dli = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, 7, binds }; VkDescriptorSetLayout dsl; CK(vkCreateDescriptorSetLayout(dev, &dli, NULL, &dsl));
  VkPushConstantRange pcr = { VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(Push) }; VkPipelineLayoutCreateInfo pli = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1, &dsl, 1, &pcr }; VkPipelineLayout pl; CK(vkCreatePipelineLayout(dev, &pli, NULL, &pl));
  VkShaderModuleCreateInfo smi = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, (size_t)len, spv }; VkShaderModule sm; CK(vkCreateShaderModule(dev, &smi, NULL, &sm));
  VkComputePipelineCreateInfo cpi = { VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0, { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, sm, "main", NULL }, pl, VK_NULL_HANDLE, 0 };
  VkPipeline pipe; CK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpi, NULL, &pipe));
  VkDescriptorPoolSize ps = { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 7 }; VkDescriptorPoolCreateInfo dpi = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1, 1, &ps }; VkDescriptorPool dp; CK(vkCreateDescriptorPool(dev, &dpi, NULL, &dp));
  VkDescriptorSetAllocateInfo dai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, dp, 1, &dsl }; VkDescriptorSet ds; CK(vkAllocateDescriptorSets(dev, &dai, &ds));
  VkDescriptorBufferInfo dbi[7]; VkWriteDescriptorSet wds[7];
  for (int i = 0; i < 7; i++) { dbi[i] = (VkDescriptorBufferInfo){ bufs[i], 0, VK_WHOLE_SIZE }; wds[i] = (VkWriteDescriptorSet){ VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, i, 0, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &dbi[i], NULL }; }
  vkUpdateDescriptorSets(dev, 7, wds, 0, NULL);
  VkCommandPoolCreateInfo cpci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, NULL, VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, qfi }; VkCommandPool cp; CK(vkCreateCommandPool(dev, &cpci, NULL, &cp));
  VkCommandBufferAllocateInfo cbai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL, cp, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 }; VkCommandBuffer cb; CK(vkAllocateCommandBuffers(dev, &cbai, &cb));
  VkFenceCreateInfo fci = { VK_STRUCTURE_TYPE_FENCE_CREATE_INFO, NULL, 0 }; VkFence fence; CK(vkCreateFence(dev, &fci, NULL, &fence));
  uint32_t *g = maps[0], *m = maps[1], *ng = maps[2], *nm = maps[3], *cnt = maps[5]; uint32_t groups = (uint32_t)((nn + 255) / 256);
  VkMemoryBarrier bar = { VK_STRUCTURE_TYPE_MEMORY_BARRIER, NULL, VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT };
  #define DISPATCH(MODE, TICK) do { P.mode = (MODE); P.tick_lo = (uint32_t)(TICK); P.tick_hi = (uint32_t)((TICK) >> 32); \
    VkCommandBufferBeginInfo bi_ = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL, VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL }; CK(vkResetCommandBuffer(cb, 0)); CK(vkBeginCommandBuffer(cb, &bi_)); \
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe); vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL); \
    vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof P, &P); vkCmdDispatch(cb, groups, 1, 1); \
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &bar, 0, NULL, 0, NULL); CK(vkEndCommandBuffer(cb)); \
    VkSubmitInfo si_ = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &cb, 0, NULL }; CK(vkQueueSubmit(queue, 1, &si_, fence)); CK(vkWaitForFences(dev, 1, &fence, VK_TRUE, UINT64_MAX)); CK(vkResetFences(dev, 1, &fence)); } while (0)
  if (load) { FILE *lf = fopen(load, "rb"); if (!lf || fread(g, 4, nn, lf) != nn || fread(m, 4, nn, lf) != nn) { fprintf(stderr, "bad dump\n"); return 1; } fclose(lf); } else DISPATCH(0, 0);
  char path[1024]; snprintf(path, sizeof path, "mkdir -p %s", out_dir); if (system(path)) {}
  snprintf(path, sizeof path, "%s/stats.csv", out_dir); FILE *csv = fopen(path, "w"); fprintf(csv, "tick,alive,distinct_genomes,mean_energy,births,deaths\n");
  double t0 = now(); ull births = 0, deaths = 0;
  for (ull t = 0; t <= ticks; t++) {
    if (t % report == 0 || t == ticks) {
      ull alive = 0; double es = 0; uint32_t *gs = malloc(nn * 4); ull k = 0; for (ull i = 0; i < nn; i++) if ((m[i] >> 4) & 1) { alive++; es += m[i] >> 16; gs[k++] = g[i]; }
      // distinct genomes via sort
      int cmpu(const void *a, const void *b); ull dg = 0; if (k) { qsort(gs, k, 4, cmpu); dg = 1; for (ull i = 1; i < k; i++) dg += gs[i] != gs[i - 1]; } free(gs);
      fprintf(csv, "%llu,%llu,%llu,%.2f,%llu,%llu\n", t, alive, dg, alive ? es / alive : 0.0, births, deaths); fflush(csv);
      fprintf(stderr, "tick %7llu alive %8llu genomes %7llu energy %7.1f births %llu deaths %llu (%.1fs) %s\n", t, alive, dg, alive ? es / alive : 0.0, births, deaths, now() - t0, props.deviceName);
      births = deaths = 0; if (alive == 0) { fprintf(stderr, "extinct at tick %llu\n", t); break; }
    }
    if (t == ticks) break;
    cnt[0] = cnt[1] = 0; DISPATCH(1, t); DISPATCH(2, t); births += cnt[0]; deaths += cnt[1];
    memcpy(g, ng, nn * 4); memcpy(m, nm, nn * 4);   // host-visible buffers: swap by copy (simple, exact)
  }
  if (dump_final) { snprintf(path, sizeof path, "%s/final.bin", out_dir); FILE *df = fopen(path, "wb"); fwrite(g, 4, nn, df); fwrite(m, 4, nn, df); fclose(df); }
  snprintf(path, sizeof path, "%s/final.ppm", out_dir); FILE *pf = fopen(path, "wb"); fprintf(pf, "P6\n%u %u\n255\n", P.n, P.n);
  for (ull i = 0; i < nn; i++) { unsigned char px[3] = {0, 0, 0}; if ((m[i] >> 4) & 1) { uint64_t h = mix(g[i]); uint64_t b = 96 + (m[i] & 15) * 10; px[0] = (h & 255) * b / 255; px[1] = ((h >> 8) & 255) * b / 255; px[2] = ((h >> 16) & 255) * b / 255; } fwrite(px, 1, 3, pf); }
  fclose(pf); fclose(csv); fprintf(stderr, "done %llu ticks in %.1fs\n", ticks, now() - t0); return 0;
}
int cmpu(const void *a, const void *b) { uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b; return x < y ? -1 : x > y; }
