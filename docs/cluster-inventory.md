# SSH cluster inventory for Fable

Verified directly over SSH on **7 October 2026, approximately 14:36–14:38
Europe/Berlin (CEST)**. All four configured LAN nodes were reachable as `ender`.
This is a hardware and availability inventory, not a reservation or a Fable
runtime installation. Availability changes as other workloads start and stop.

## CPUs and system RAM

| SSH alias | LAN address | CPU | Physical cores | Logical CPUs | Installed RAM | OS-visible RAM | Available RAM at check |
|---|---|---|---:|---:|---:|---:|---:|
| adler40 | 192.168.178.171 | Intel Core i9-12900K | 16 (8 P + 8 E) | 24 | 64 GiB | 61.56 GiB | 57.77 GiB |
| specht32 | 192.168.178.187 | Intel Core i7-8700K | 6 | 12 | 48 GiB | 44.74 GiB | 42.72 GiB |
| knecht24 | 192.168.178.200 | AMD Ryzen Threadripper 1920X | 12 | 24 | 64 GiB | 60.51 GiB | 47.09 GiB |
| falke64 | 192.168.178.188 | AMD Ryzen 5 7600X | 6 | 12 | 64 GiB | 60.94 GiB | 58.69 GiB |
| **Total** | | **4 CPU packages** | **40** | **72** | **240 GiB** | **227.76 GiB** | **206.27 GiB** |

Installed RAM is the sum of populated DIMMs reported by `dmidecode`.
OS-visible and available RAM come from `free -b`; available includes reclaimable
cache. These are separate machines, so their RAM is not a single shared pool.
One-minute load averages at the first check were 0.00, 0.00, 0.02, and 0.16
respectively; logical CPU counts are capacity, not reserved free CPU slots.

## Discrete GPUs

| Node | Device identifier | GPU | Nominal VRAM | Free VRAM at check | Verified interface |
|---|---|---|---:|---:|---|
| adler40 | NVIDIA index 0 | GeForce RTX 4090 | 24 GiB | 23.52 GiB | NVIDIA driver / Vulkan |
| adler40 | NVIDIA index 1 | GeForce RTX 4080 | 16 GiB | 14.30 GiB | NVIDIA driver / Vulkan |
| specht32 | PCI 0000:03:00.0, DRM card0 | Radeon RX 9060 XT | 16 GiB | 15.87 GiB | Mesa RADV / Vulkan |
| specht32 | PCI 0000:06:00.0, DRM card2 | Radeon RX 9070 XT | 16 GiB | 15.87 GiB | Mesa RADV / Vulkan |
| knecht24 | NVIDIA index 0 | GeForce RTX 3060 | 12 GiB | 11.63 GiB | NVIDIA driver / Vulkan |
| knecht24 | NVIDIA index 1 | GeForce RTX 3060 | 12 GiB | 11.63 GiB | NVIDIA driver / Vulkan |
| knecht24 | NVIDIA index 2 | GeForce RTX 3060 | 12 GiB | 11.63 GiB | NVIDIA driver / Vulkan |
| falke64 | PCI 0000:03:00.0, DRM card1 | Radeon AI PRO R9700 | 32 GiB | 31.80 GiB | Mesa RADV / Vulkan |
| falke64 | PCI 0000:09:00.0, DRM card2 | Radeon AI PRO R9700 | 32 GiB | 31.79 GiB | Mesa RADV / Vulkan |

**Total: 9 discrete GPUs, 172 GiB nominal VRAM, approximately 168.04 GiB free
at the check.** Five NVIDIA GPUs provide 76 GiB nominal VRAM; four AMD GPUs
provide 96 GiB. Knecht currently has **three** RTX 3060s despite its hostname
and older documentation describing two.

NVIDIA free memory comes from `nvidia-smi`; AMD free memory is the difference
between the driver's `mem_info_vram_total` and `mem_info_vram_used`. Driver
reservations mean usable totals can be below nominal capacity. All discrete
GPUs reported 0% utilization when sampled, but this does not mean unallocated:
Adler's RTX 4080 had an `ender`-owned `homunculi` process, PID 1830863,
holding 1292 MiB. No NVIDIA compute processes were listed on Knecht.
No existing workloads were stopped or modified for this inventory.

NVIDIA driver version was 595.91.07; AMD Vulkan used Mesa RADV 26.0.8.
CUDA application/toolkit compatibility and ROCm support were not tested.
Fable's application dependencies and GPU backend still need to be matched to
these devices before scheduling jobs. VRAM across cards and nodes is not
automatically pooled; applications must explicitly support splitting work.

### Integrated GPUs

These are also present, but are excluded from the discrete compute totals:

- adler40: Intel UHD Graphics 770, shared system memory.
- specht32: Intel UHD Graphics 630, shared system memory.
- falke64: AMD Raphael integrated Radeon graphics, with 512 MiB reported
  by the driver's VRAM counter; additional shared memory is not dedicated VRAM.

Vulkan also lists `llvmpipe`, a CPU software renderer, which is not an extra GPU.
Integrated GPUs were enumerated but not validated for Fable workloads.

## SSH access and working constraints

The existing workstation SSH configuration already defines these aliases:

```powershell
ssh adler40
ssh specht32
ssh knecht24
ssh falke64
```

Each alias uses account `ender` and the workstation's existing
`~/.ssh/id_ed25519_ender` identity. Keys and credentials are not stored in this
repository. Access requires LAN reachability and an authorized SSH key;
cloning this repository alone does not grant cluster access.

Keep services bound to localhost or the node's LAN address. Before assigning
GPUs, refresh occupancy and identify existing workloads. Check `df -h` before
large downloads; free root space at this check was approximately 205 GiB on
Adler, 237 GiB on Specht, 63 GiB on Knecht, and 1.5 TiB on Falke.

## Refresh the measurements

Run the following on each node over SSH:

```bash
hostname
date -Is
lscpu
free -b
cat /proc/loadavg
sudo -n dmidecode --type 17
lspci -Dnn | grep -Ei 'VGA|3D|Display'
vulkaninfo --summary
df -h /
```

On NVIDIA nodes (`adler40`, `knecht24`):

```bash
nvidia-smi --query-gpu=index,name,uuid,memory.total,memory.free,utilization.gpu --format=csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv
```

On AMD nodes (`specht32`, `falke64`):

```bash
for card in /sys/class/drm/card[0-9]*; do
  dev="$card/device"
  [ -r "$dev/mem_info_vram_total" ] || continue
  echo "$card $(readlink -f "$dev")"
  echo "VRAM total / used (bytes):"
  cat "$dev/mem_info_vram_total" "$dev/mem_info_vram_used"
  echo "GPU utilization (%):"
  cat "$dev/gpu_busy_percent"
done
```

Match AMD cards by PCI address rather than assuming DRM and Vulkan device
indices are the same. The numbers can change across boots or environments.
