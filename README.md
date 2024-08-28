# LLVM for Triton

[Triton](https://github.com/triton-lang/triton/) needs a special build of
LLVM:

- [MLIR](https://mlir.llvm.org/) (Multi-Level Intermediate Representation)
- targets `AMDGPU` and `NVPTX`
- static builds, so `libtriton.so` does not have a runtime dependency on
  `libLLVM*.so`
- no `_GLIBCXX_ASSERTIONS`

This build also disables tools and utils to reduce the size of the package.
Triton only uses `mlir-tblgen` at build time.
