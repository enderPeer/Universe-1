# NVIDIA nodes (adler40, knecht24):  make -C gpu u1_cuda
# AMD nodes (specht32, falke64):     make -C gpu u1_vk      (needs glslc, libvulkan-dev)
# Any machine, logic check only:     make -C gpu u1_cuda_emu
NVCC ?= nvcc
all: u1_cuda u1_vk
# exp09/exp10 every-step kernel (CUDA) and exp06b layout-L2 engines (CUDA, emulation, Vulkan)
u1_multi: u1_multi.cu
	$(NVCC) -O3 -arch=native -o u1_multi u1_multi.cu
u1_l2: u1_l2.cu
	$(NVCC) -O3 -arch=native -o u1_l2 u1_l2.cu
u1_l2_emu: u1_l2.cu cuda_shim.h
	g++ -O2 -x c++ -include cuda_shim.h -o u1_l2_emu u1_l2.cu
u1_l2.spv: u1_l2.comp
	glslc --target-env=vulkan1.2 u1_l2.comp -o u1_l2.spv
u1_l2_vk: u1_l2_vk.c u1_l2.spv
	gcc -O2 -Wall -o u1_l2_vk u1_l2_vk.c -lvulkan
u1_cuda: u1_cuda.cu
	$(NVCC) -O3 -arch=native -o u1_cuda u1_cuda.cu
u1.spv: u1.comp
	glslc --target-env=vulkan1.2 u1.comp -o u1.spv
u1_vk: u1_vk.c u1.spv
	gcc -O2 -Wall -o u1_vk u1_vk.c -lvulkan
u1_cuda_emu: u1_cuda.cu cuda_shim.h
	g++ -O2 -x c++ -include cuda_shim.h -o u1_cuda_emu u1_cuda.cu
clean:
	rm -f u1_cuda u1_vk u1.spv u1_cuda_emu u1_multi u1_l2 u1_l2_emu u1_l2.spv u1_l2_vk
