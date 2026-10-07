/* Universe-1 Vulkan host for gpu/u1.comp (AMD GPUs). Same CLI and shard format as gpu/u1_cuda.cu.
 * usage: u1_vk --gpu g --W w --a a --p p --I i --isa ... [--binary] --lo L --hi H --out file
 * Adapted from enderPeer/Dimension42 explorer/nano_search3_vk.c. Build: see gpu/Makefile. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <vulkan/vulkan.h>
#define CK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { fprintf(stderr, "ERROR %s failed: %d\n", #x, r_); exit(1); } } while (0)
typedef unsigned long long ull;
typedef struct { uint32_t W, a, p, I, o, bin, nins, nM, nin, ntab, cap_log2, lo_lo, lo_hi, count; } Push;
#define SUB (1ull << 25)
#define EMPTY 0xFFFFFFFFFFFFFFFFull
static const char *PNAME[] = { "NOP","HALT","LD","ST","LDI","CLR","SET","NOT","AND","OR","XOR","NAND","NOR","XNOR",
  "ADD","ADC","SUB","INC","DEC","NEG","SHL","SHR","ROL","ROR","RCL","MUL","SWAP","JMP","JZ","JNZ","JC","SKZ","SKNZ",
  "INCM","DECM","LDIND","STIND" };
#define P_COUNT 37
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
int main(int argc, char **argv) {
  Push P; memset(&P, 0, sizeof P); P.W = 4; P.a = 2; P.p = 3; int I = -1; P.cap_log2 = 26;
  const char *isa_s = NULL, *out = NULL; int gpu = 0; ull lo = 0, hi = 0; int have = 0;
  for (int i = 1; i < argc; i++) {
    #define ARG(n) (!strcmp(argv[i], n) && i + 1 < argc)
    if (ARG("--W")) P.W = atoi(argv[++i]); else if (ARG("--a")) P.a = atoi(argv[++i]); else if (ARG("--p")) P.p = atoi(argv[++i]);
    else if (ARG("--I")) I = atoi(argv[++i]); else if (ARG("--isa")) isa_s = argv[++i]; else if (ARG("--out")) out = argv[++i];
    else if (ARG("--gpu")) gpu = atoi(argv[++i]); else if (ARG("--cap-log2")) P.cap_log2 = atoi(argv[++i]);
    else if (ARG("--lo")) { lo = strtoull(argv[++i], 0, 0); have = 1; } else if (ARG("--hi")) { hi = strtoull(argv[++i], 0, 0); have = 1; }
    else if (!strcmp(argv[i], "--binary")) P.bin = 1; else { fprintf(stderr, "bad arg %s\n", argv[i]); return 2; }
  }
  if (!isa_s || !out) { fprintf(stderr, "need --isa and --out\n"); return 2; }
  P.I = I < 0 ? P.W : I; P.nins = 1u << P.p; P.nM = 1u << P.a; P.nin = 1u << P.W; P.ntab = P.bin ? P.nin * P.nin : P.nin;
  if (P.nM > 16 || P.ntab > 256 || P.nins > 256) { fprintf(stderr, "config exceeds shader limits (a<=4, table<=256, instr<=256)\n"); return 2; }
  uint32_t isa[256]; unsigned char isa8[256]; int nisa = 0; char buf[2048]; strncpy(buf, isa_s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
  for (char *t = strtok(buf, ","); t; t = strtok(NULL, ",")) { int id = -1; for (int k = 0; k < P_COUNT; k++) if (!strcmp(t, PNAME[k])) id = k;
    if (id < 0) { fprintf(stderr, "unknown primitive %s\n", t); return 2; } isa[nisa] = id; isa8[nisa++] = id; }
  if (nisa & (nisa - 1)) { fprintf(stderr, "ISA length must be power of two\n"); return 2; }
  P.o = 0; while ((1 << P.o) < nisa) P.o++; if (P.o == 0) P.o = 1;
  if (P.o > P.I) { fprintf(stderr, "opcode bits > I\n"); return 2; }
  int pbits = P.nins * P.I; if (pbits > 64) { fprintf(stderr, "program bits > 64\n"); return 2; }
  ull total = pbits == 64 ? UINT64_MAX : (1ull << pbits); if (!have) { lo = 0; hi = total; }

  FILE *f = fopen("gpu/u1.spv", "rb"); if (!f) f = fopen("u1.spv", "rb");
  if (!f) { fprintf(stderr, "ERROR u1.spv not found (glslc --target-env=vulkan1.2 gpu/u1.comp -o gpu/u1.spv)\n"); return 1; }
  fseek(f, 0, SEEK_END); long len = ftell(f); fseek(f, 0, SEEK_SET); uint32_t *spv = malloc(len);
  if (fread(spv, 1, len, f) != (size_t)len) return 1; fclose(f);
  VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO, NULL, "u1", 1, "none", 1, VK_API_VERSION_1_2 };
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
  VkPhysicalDeviceShaderAtomicInt64Features at64 = { VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_ATOMIC_INT64_FEATURES, NULL, VK_TRUE, VK_FALSE };
  VkPhysicalDeviceFeatures feat = {0}; feat.shaderInt64 = VK_TRUE;
  VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, &at64, 0, 1, &qci, 0, NULL, 0, NULL, &feat };
  CK(vkCreateDevice(phys, &dci, NULL, &dev)); VkQueue queue; vkGetDeviceQueue(dev, qfi, 0, &queue);

  ull cap = 1ull << P.cap_log2; void *maps[5];
  VkBuffer bufs[5] = { make_buffer(cap * 8, &maps[0]), make_buffer(cap * 8, &maps[1]), make_buffer(cap * 4, &maps[2]), make_buffer(64, &maps[3]), make_buffer(1024, &maps[4]) };
  memset(maps[0], 0xFF, cap * 8); memset(maps[2], 0xFF, cap * 4); memset(maps[3], 0, 64); ((uint32_t *)maps[3])[0] = UINT32_MAX; memcpy(maps[4], isa, nisa * 4);
  VkDescriptorSetLayoutBinding binds[5]; for (int i = 0; i < 5; i++) binds[i] = (VkDescriptorSetLayoutBinding){ i, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1, VK_SHADER_STAGE_COMPUTE_BIT, NULL };
  VkDescriptorSetLayoutCreateInfo dli = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, 5, binds }; VkDescriptorSetLayout dsl; CK(vkCreateDescriptorSetLayout(dev, &dli, NULL, &dsl));
  VkPushConstantRange pcr = { VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(Push) };
  VkPipelineLayoutCreateInfo pli = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1, &dsl, 1, &pcr }; VkPipelineLayout pl; CK(vkCreatePipelineLayout(dev, &pli, NULL, &pl));
  VkShaderModuleCreateInfo smi = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, (size_t)len, spv }; VkShaderModule sm; CK(vkCreateShaderModule(dev, &smi, NULL, &sm));
  VkComputePipelineCreateInfo cpi = { VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO, NULL, 0,
    { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_COMPUTE_BIT, sm, "main", NULL }, pl, VK_NULL_HANDLE, 0 };
  VkPipeline pipe; CK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpi, NULL, &pipe));
  VkDescriptorPoolSize ps = { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 5 }; VkDescriptorPoolCreateInfo dpi = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1, 1, &ps };
  VkDescriptorPool dp; CK(vkCreateDescriptorPool(dev, &dpi, NULL, &dp));
  VkDescriptorSetAllocateInfo dai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, dp, 1, &dsl }; VkDescriptorSet ds; CK(vkAllocateDescriptorSets(dev, &dai, &ds));
  VkDescriptorBufferInfo dbi[5]; VkWriteDescriptorSet wds[5];
  for (int i = 0; i < 5; i++) { dbi[i] = (VkDescriptorBufferInfo){ bufs[i], 0, VK_WHOLE_SIZE };
    wds[i] = (VkWriteDescriptorSet){ VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds, i, 0, 1, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &dbi[i], NULL }; }
  vkUpdateDescriptorSets(dev, 5, wds, 0, NULL);
  VkCommandPoolCreateInfo cpci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, NULL, VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, qfi }; VkCommandPool cp; CK(vkCreateCommandPool(dev, &cpci, NULL, &cp));
  VkCommandBufferAllocateInfo cbai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, NULL, cp, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1 }; VkCommandBuffer cb; CK(vkAllocateCommandBuffers(dev, &cbai, &cb));
  VkFenceCreateInfo fci = { VK_STRUCTURE_TYPE_FENCE_CREATE_INFO, NULL, 0 }; VkFence fence; CK(vkCreateFence(dev, &fci, NULL, &fence));

  double t0 = now();
  for (ull off = lo; off < hi; off += SUB) {
    ull n = hi - off < SUB ? hi - off : SUB;
    P.lo_lo = (uint32_t)off; P.lo_hi = (uint32_t)(off >> 32); P.count = (uint32_t)n;
    VkCommandBufferBeginInfo bi = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, NULL, VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT, NULL };
    CK(vkResetCommandBuffer(cb, 0)); CK(vkBeginCommandBuffer(cb, &bi));
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe); vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
    vkCmdPushConstants(cb, pl, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof P, &P); vkCmdDispatch(cb, (uint32_t)((n + 255) / 256), 1, 1);
    CK(vkEndCommandBuffer(cb));
    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO, NULL, 0, NULL, NULL, 1, &cb, 0, NULL };
    CK(vkQueueSubmit(queue, 1, &si, fence)); CK(vkWaitForFences(dev, 1, &fence, VK_TRUE, UINT64_MAX)); CK(vkResetFences(dev, 1, &fence));
  }
  double secs = now() - t0;
  uint64_t *keys = maps[0], *his = maps[1]; uint32_t *progs = maps[2], *misc = maps[3];
  if (misc[2]) { fprintf(stderr, "ERROR hash table overflow (%u dropped); rerun with --cap-log2 %u\n", misc[2], P.cap_log2 + 1); return 1; }
  ull n = misc[1] ? 1 : 0; for (ull i = 0; i < cap; i++) n += keys[i] != EMPTY;
  FILE *fo = fopen(out, "wb"); if (!fo) { perror(out); return 1; }
  uint32_t hdr[8] = { 0x55314231u, P.W, P.a, P.p, P.I, P.o, P.bin, (uint32_t)nisa };
  fwrite(hdr, 4, 8, fo); fwrite(&lo, 8, 1, fo); fwrite(&hi, 8, 1, fo); fwrite(&n, 8, 1, fo); fwrite(isa8, 1, nisa, fo);
  for (ull i = 0; i < cap; i++) if (keys[i] != EMPTY) { fwrite(&keys[i], 8, 1, fo); fwrite(&his[i], 8, 1, fo); fwrite(&progs[i], 4, 1, fo); }
  if (misc[1]) { ull k = EMPTY, h = 0; fwrite(&k, 8, 1, fo); fwrite(&h, 8, 1, fo); fwrite(&misc[0], 4, 1, fo); }
  fclose(fo);
  fprintf(stderr, "W=%u a=%u p=%u I=%u o=%u isa=%s %s programs=[%llu,%llu) distinct=%llu %.2fs (%.1f Mprog/s) %s\n", P.W, P.a, P.p, P.I, P.o, isa_s,
          P.bin ? "binary" : "unary", lo, hi, n, secs, (hi - lo) / secs / 1e6, props.deviceName);
  printf("%llu\n", n);
  return 0;
}
