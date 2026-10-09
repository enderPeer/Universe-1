/* Universe-1 exp11 Vulkan host for gpu/u1_avida.comp (AMD GPUs). Same CLI and output format as gpu/u1_avida.cu.
 * usage: u1_avida_vk --gpu g --len L [--lo A --hi B | --genomes FILE] --out FILE [--gens 3] [--max-list 1000000] [--sub-log2 20]
 * Build: glslc --target-env=vulkan1.2 gpu/u1_avida.comp -o gpu/u1_avida.spv; gcc -O2 -o gpu/u1_avida_vk gpu/u1_avida_vk.c -lvulkan */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vulkan/vulkan.h>
#define CK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { fprintf(stderr, "ERROR %s failed: %d\n", #x, r_); exit(1); } } while (0)
typedef unsigned long long ull;
typedef struct { uint32_t L, budget, gens, list_mode, max_list, lo_lo, lo_hi, count; } Push;
#define SUB_LOG2_DEFAULT 20   /* invocations per submit: below the amdgpu compute watchdog */
#define NCNT 1024
#define NBUF 5
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static VkPhysicalDevice phys; static VkDevice dev;
static VkBuffer make_buffer(VkDeviceSize size, void **map) {
  VkBuffer buf; VkDeviceMemory mem;
  VkBufferCreateInfo bi = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, size, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, VK_SHARING_MODE_EXCLUSIVE, 0, NULL };
  CK(vkCreateBuffer(dev, &bi, NULL, &buf));
  VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev, buf, &mr);
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(phys, &mp);
  VkMemoryPropertyFlags want[2] = { VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_CACHED_BIT,
                                    VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT };
  uint32_t type = UINT32_MAX;
  for (int w = 0; w < 2 && type == UINT32_MAX; w++) for (uint32_t i = 0; i < mp.memoryTypeCount; i++)
    if ((mr.memoryTypeBits & (1u << i)) && (mp.memoryTypes[i].propertyFlags & want[w]) == want[w]) { type = i; break; }
  VkMemoryAllocateInfo ai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, mr.size, type };
  CK(vkAllocateMemory(dev, &ai, NULL, &mem)); CK(vkBindBufferMemory(dev, buf, mem, 0)); CK(vkMapMemory(dev, mem, 0, VK_WHOLE_SIZE, 0, map));
  return buf;
}
static ull pow26(int n) { ull p = 1; for (int i = 0; i < n; i++) p *= 26; return p; }
int main(int argc, char **argv) {
  Push P; memset(&P, 0, sizeof P); P.L = 8; P.gens = 3; P.max_list = 1000000;
  const char *out = NULL, *genomes = NULL; int gpu = 0; ull lo = 0, hi = 0; int have = 0; int sub_log2 = SUB_LOG2_DEFAULT;
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--sub-log2")) sub_log2 = atoi(argv[++i]); else if (ARG("--len")) P.L = atoi(argv[++i]); else if (ARG("--gens")) P.gens = atoi(argv[++i]);
    else if (ARG("--out")) out = argv[++i]; else if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--max-list")) P.max_list = (uint32_t)strtoul(argv[++i], 0, 0);
    else if (ARG("--genomes")) genomes = argv[++i];
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have = 1; } else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have = 1; }
    else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  if (!out || P.L < 1 || P.L > 10 || P.gens < 1 || P.gens > 3) { fprintf(stderr, "need --out; 1 <= --len <= 10; 1 <= --gens <= 3\n"); return 2; }
  P.budget = 20 * P.L; ull total = pow26(P.L); if (!have) { lo = 0; hi = total; } if (hi > total) hi = total;
  ull *idx = NULL; size_t nidx = 0;
  if (genomes) {
    P.list_mode = 1; FILE *f = fopen(genomes, "r"); if (!f) { perror(genomes); return 1; } char buf[256]; size_t cap = 1024; idx = malloc(cap * 8);
    while (fgets(buf, sizeof buf, f)) { char s[64]; int n = 0; for (char *p = buf; *p && n < 60; p++) if (*p >= 'a' && *p <= 'z') s[n++] = *p; if (n != (int)P.L) continue;
      ull g = 0; for (int k = P.L - 1; k >= 0; k--) g = g * 26 + (s[k] - 'a'); if (nidx == cap) { cap *= 2; idx = realloc(idx, cap * 8); } idx[nidx++] = g; }
    fclose(f); lo = 0; hi = nidx; if (P.max_list < nidx) P.max_list = (uint32_t)nidx;
  }

  FILE *f = fopen("gpu/u1_avida.spv", "rb"); if (!f) f = fopen("u1_avida.spv", "rb");
  if (!f) { fprintf(stderr, "ERROR u1_avida.spv not found (glslc --target-env=vulkan1.2 gpu/u1_avida.comp -o gpu/u1_avida.spv)\n"); return 1; }
  fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET); uint32_t *spv = malloc(len);
  if (fread(spv, 1, len, f) != (size_t)len) return 1; fclose(f);
  VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "u1avida", 1, "none", 1, VK_API_VERSION_1_2 };
  VkInstanceCreateInfo ici = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, NULL, 0, &app, 0, NULL, 0, NULL };
  VkInstance inst; CK(vkCreateInstance(&ici, NULL, &inst));
  uint32_t np = 0; vkEnumeratePhysicalDevices(inst, &np, NULL); VkPhysicalDevice *all = malloc(np * sizeof *all); vkEnumeratePhysicalDevices(inst, &np, all);
  VkPhysicalDeviceProperties props; int seen = -1;
  for (uint32_t i = 0; i < np; i++) { vkGetPhysicalDeviceProperties(all[i], &props);
    if (props.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU && ++seen == gpu) { phys = all[i]; break; } }
  if (!phys) { fprintf(stderr, "ERROR discrete GPU %d not found\n", gpu); return 1; }
  vkGetPhysicalDeviceProperties(phys, &props);
  uint32_t nq = 0; vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, NULL); VkQueueFamilyProperties *qf = malloc(nq * sizeof *qf);
  vkGetPhysicalDeviceQueueFamilyProperties(phys, &nq, qf); uint32_t qfi = UINT32_MAX;
  for (uint32_t i = 0; i < nq; i++) if ((qf[i].queueFlags & VK_QUEUE_COMPUTE_BIT) && !(qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) { qfi = i; break; }
  if (qfi == UINT32_MAX) for (uint32_t i = 0; i < nq; i++) if (qf[i].queueFlags & VK_QUEUE_COMPUTE_BIT) { qfi = i; break; }
  float prio = 1.0f; VkDeviceQueueCreateInfo qci = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, NULL, 0, qfi, 1, &prio };
  VkPhysicalDeviceFeatures feat = {0}; feat.shaderInt64 = VK_TRUE;
  VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, NULL, 0, 1, &qci, 0, NULL, 0, NULL, &feat };
  CK(vkCreateDevice(phys, &dci, NULL, &dev)); VkQueue queue; vkGetDeviceQueue(dev, qfi, 0, &queue);

  void *maps[NBUF];
  VkBuffer bufs[NBUF] = { make_buffer(NCNT * 4, &maps[0]), make_buffer((VkDeviceSize)P.max_list * 8, &maps[1]), make_buffer((VkDeviceSize)P.max_list * 4, &maps[2]),
                          make_buffer(64, &maps[3]), make_buffer(nidx ? nidx * 8 : 8, &maps[4]) };
  memset(maps[0], 0, NCNT * 4); memset(maps[3], 0, 64); if (nidx) memcpy(maps[4], idx, nidx * 8);
  VkDescriptorSetLayoutBinding binds[NBUF]; for (int i = 0; i < NBUF; i++) binds[i] = (VkDescriptorSetLayoutBinding){ i, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL };
  VkDescriptorSetLayoutCreateInfo dli = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, NBUF, binds }; VkDescriptorSetLayout dsl; CK(vkCreateDescriptorSetLayout(dev, &dli, NULL, &dsl));
  VkPushConstantRange pcr = { VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(Push) };
  VkPipelineLayoutCreateInfo pli = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1, &dsl, 1, &pcr }; VkPipelineLayout pl; CK(vkCreatePipelineLayout(dev, &pli, NULL, &pl));
  VkShaderModuleCreateInfo smi = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, (size_t)len, spv }; VkShaderModule sm; CK(vkCreateShaderModule(dev, &smi, NULL, &sm));
  VkComputePipelineCreateInfo cpi = { VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0,
    { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, sm, "main", NULL }, pl, VK_NULL_HANDLE, 0 };
  VkPipeline pipe; CK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpi, NULL, &pipe));
  VkDescriptorPoolSize ps = { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NBUF }; VkDescriptorPoolCreateInfo dpi = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1, 1, &ps };
  VkDescriptorPool dp; CK(vkCreateDescriptorPool(dev, &dpi, NULL, &dp));
  VkDescriptorSetAllocateInfo dai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, dp, 1, &dsl }; VkDescriptorSet ds; CK(vkAllocateDescriptorSets(dev, &dai, &ds));
  VkDescriptorBufferInfo dbi[NBUF]; VkWriteDescriptorSet wds[NBUF];
  for (int i = 0; i < NBUF; i++) { dbi[i] = (VkDescriptorBufferInfo){ bufs[i], 0, VK_WHOLE_SIZE };
    wds[i] = (VkWriteDescriptorSet){ VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, i, 0, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &dbi[i], NULL }; }
  vkUpdateDescriptorSets(dev, NBUF, wds, 0, NULL);
  VkCommandPoolCreateInfo cpci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, NULL, VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, qfi }; VkCommandPool cp; CK(vkCreateCommandPool(dev, &cpci, NULL, &cp));
  VkCommandBufferAllocateInfo cbai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL, cp, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 }; VkCommandBuffer cb; CK(vkAllocateCommandBuffers(dev, &cbai, &cb));
  VkFenceCreateInfo fci = { VK_STRUCTURE_TYPE_FENCE_CREATE_INFO, NULL, 0 }; VkFence fence; CK(vkCreateFence(dev, &fci, NULL, &fence));

  double t0 = now();
  const ull SUB = 1ull << sub_log2;
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
    /* list mode: the shader indexes idx_list by the global invocation id, so submit the whole list at once (lo = 0) */
    P.lo_lo = (uint32_t)off; P.lo_hi = (uint32_t)(off >> 32); P.count = (uint32_t)n;
    if (P.list_mode) { n = hi - lo; P.count = (uint32_t)n; }
    VkCommandBufferBeginInfo bi = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL, VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
    CK(vkResetCommandBuffer(cb, 0)); CK(vkBeginCommandBuffer(cb, &bi));
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe); vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
    vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof P, &P); vkCmdDispatch(cb, (uint32_t)((n + 127) / 128), 1, 1);
    VkMemoryBarrier barrier = { VK_STRUCTURE_TYPE_MEMORY_BARRIER, NULL, VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_HOST_READ_BIT };
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &barrier, 0, NULL, 0, NULL);
    CK(vkEndCommandBuffer(cb));
    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &cb, 0, NULL };
    CK(vkQueueSubmit(queue, 1, &si, fence)); CK(vkWaitForFences(dev, 1, &fence, VK_TRUE, UINT64_MAX)); CK(vkResetFences(dev, 1, &fence));
    if (P.list_mode) break;
  }
  double secs = now() - t0;
  uint32_t *cnt = maps[0], *misc = maps[3], *lval = maps[2]; uint64_t *lidx = maps[1];
  if (cnt[7] != hi - lo) { fprintf(stderr, "ERROR %u of %llu genomes accounted for (dropped GPU work?)\n", cnt[7], hi - lo); return 1; }
  uint32_t nlist = misc[0], nl = nlist < P.max_list ? nlist : P.max_list;
  FILE *g = fopen(out, "w"); if (!g) { perror(out); return 1; }
  fprintf(g, "avida len %u genomes [%llu,%llu) budget %u gens %u%s\n", P.L, lo, hi, P.budget, P.gens, P.list_mode ? " list-mode" : "");
  fprintf(g, "viable %u depth0 %u depth1 %u depth2 %u divides0 %u intact %u copy_true0 %u processed %u\n", cnt[0], cnt[1], cnt[2], cnt[3], cnt[4], cnt[5], cnt[6], cnt[7]);
  fprintf(g, "first_divide_hist"); for (uint32_t t = 0; t <= P.budget; t++) if (cnt[64 + t]) fprintf(g, " %u:%u", t, cnt[64 + t]); fprintf(g, "\n");
  fprintf(g, "fecundity_hist"); for (int t = 0; t < 256; t++) if (cnt[512 + t]) fprintf(g, " %d:%u", t, cnt[512 + t]); fprintf(g, "\n");
  fprintf(g, "fecundity_true_hist"); for (int t = 0; t < 256; t++) if (cnt[768 + t]) fprintf(g, " %d:%u", t, cnt[768 + t]); fprintf(g, "\n");
  fprintf(g, "listed %u of %u\n", nl, nlist);
  for (uint32_t i = 0; i < nl; i++) {
    ull t = lidx[i]; char s[16]; for (uint32_t k = 0; k < P.L; k++) { s[k] = 'a' + (char)(t % 26); t /= 26; } s[P.L] = 0; uint32_t v = lval[i];
    fprintf(g, "genome %s index %llu viable %u depth %d first %u intact %u copy_true %u fecundity %u fecundity_true %u\n", s, (ull)lidx[i], v >> 31, (int)(v & 3) == 3 ? -1 : (int)(v & 3), (v >> 2) & 511, (v >> 11) & 1, (v >> 12) & 1, (v >> 13) & 511, (v >> 22) & 511);
  }
  fclose(g);
  fprintf(stderr, "avida L=%u genomes=[%llu,%llu) viable=%u (depth 0/1/2 %u/%u/%u) divides0=%u %.2fs (%.2f Mgen/s) %s\n", P.L, lo, hi, cnt[0], cnt[1], cnt[2], cnt[3], cnt[4], secs, (hi - lo) / secs / 1e6, props.deviceName);
  printf("%u\n", cnt[0]);
  return 0;
}
