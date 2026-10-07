# CPU reference:            cargo build --release          (binary: target/release/u1life)
# NVIDIA (adler40,knecht24): make u1life_cuda
# AMD (specht32,falke64):    make u1life_vk                 (glslc + libvulkan-dev)
# Logic check without GPU:   make u1life_emu  (then compare final.bin with the CPU reference)
NVCC ?= nvcc
all: u1life_cuda u1life_vk
u1life_cuda: u1life.cu
	$(NVCC) -O3 -arch=native -o u1life_cuda u1life.cu
u1life.spv: u1life.comp
	glslc --target-env=vulkan1.2 u1life.comp -o u1life.spv
u1life_vk: u1life_vk.c u1life.spv
	gcc -O2 -Wall -o u1life_vk u1life_vk.c -lvulkan
u1life_emu: u1life.cu ../gpu/cuda_shim.h
	g++ -O2 -x c++ -include ../gpu/cuda_shim.h -o u1life_emu u1life.cu
clean:
	rm -f u1life_cuda u1life_vk u1life.spv u1life_emu
