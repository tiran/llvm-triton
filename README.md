# LLVM for Triton

## Why

The [Triton](https://github.com/triton-lang/triton/) Python package requires a special build of LLVM to compile. The build system of upstream Triton downloads community binaries at build time. For obvious reasons, we cannot trust these binaries and have to compile our own LLVM. The regular LLVM builds in RHEL do not work for us.

* Triton is not compatible with regular releases of LLVM. Instead it needs an LLVM version from a specific git commit.
* Almost every version of Triton needs a different version of LLVM. The commit is recorded in [`cmake/llvm-hash.txt`](https://github.com/triton-lang/triton/blob/main/cmake/llvm-hash.txt).
* LLVM must be built with [MLIR](https://mlir.llvm.org/) support and LLVM targets "AMDGU", "NVPTX" (NVIDIA), and the current CPU architecture. It must not be built with any additional CPU architecture, otherwise Triton fails with missing symbols.
* Dylib (dynamic, shared library) builds of LLVM are not supported. Normally, a full static build of LLVM is very large, because all tools are linked statically as well. Triton does not depend on LLVM tools, which allows us to exclude tools.
* LLVM must be compiled without `_GLIBCXX_ASSERTIONS` define.

## What

The `build_llvm_triton.py` command

1. download `llvm-project` tar ball from GitHub at a specific commit
2. unpacks the sources
3. builds LLVM for Triton
4. installs LLVM to `usr/lib64/llvm-triton-{shortcommit}` into a local `destdir`
5. packs and imports the build into a new, empty container image with name `llvm-triton-{shortcommit}-{os_id}{os_version_id}`

The container image is not runnable. It is designed to be used as a container-first artifact that can be copied into another container

```docker
COPY --from=.../llvm-triton-{shortcommit}-{os_id}{os_version_id} \
    /usr/lib64/llvm-triton-{shortcommit} /usr/lib64/llvm-triton-{shortcommit}
```

> **NOTE:** `shortcommit` are the first 8 characters of the full SHA-1 commit hash

## How to build

You need an API token with write permission to push the image.

```shell
$ ./build_llvm_triton.py a66376b0dc3b2ea8a84fda26faca287980986f78
$ podman login your.registry -u token -p <token>
$ podman push your.registry/llvm-triton-a66376b0-ubi9.4-x86_64:latest
```

### Create image index (manifest with multiple architectures)

```shell
$ podman manifest create your.registry/llvm-triton-a66376b0-ubi9.4:latest
$ podman manifest add your.registry/llvm-triton-a66376b0-ubi9.4:latest docker://your.registry/llvm-triton-a66376b0-ubi9.4-aarch64:latest
$ podman manifest add your.registry/llvm-triton-a66376b0-ubi9.4:latest docker://your.registry/llvm-triton-a66376b0-ubi9.4-x86_64:latest
$ podman manifest push --all your.registry/llvm-triton-a66376b0-ubi9.4:latest
```

## LLVM commits

- [`49af6502c6dcb4a7f7520178bd14df396f78240c`](https://github.com/llvm/llvm-project/commit/49af6502c6dcb4a7f7520178bd14df396f78240c) for Triton [2.1.0](https://github.com/triton-lang/triton/tree/v2.1.0) / aotriton 0.4.1b
- [`5e5a22caf88ac1ccfa8dc5720295fdeba0ad9372`](https://github.com/llvm/llvm-project/commit/5e5a22caf88ac1ccfa8dc5720295fdeba0ad9372) for Triton [2.3.1](https://github.com/triton-lang/triton/tree/release/2.3.x)
- [`10dc3a8e916d73291269e5e2b82dd22681489aa1`](https://github.com/llvm/llvm-project/commit/10dc3a8e916d73291269e5e2b82dd22681489aa1) for Triton [3.0.0](https://github.com/triton-lang/triton/tree/release/3.0.x) and [3.1.0](https://github.com/triton-lang/triton/tree/release/3.1.x)
- [`86b69c31642e98f8357df62c09d118ad1da4e16a`](https://github.com/llvm/llvm-project/commit/86b69c31642e98f8357df62c09d118ad1da4e16a) for Triton [3.2.0](https://github.com/triton-lang/triton/tree/release/3.2.x)
- [`a66376b0dc3b2ea8a84fda26faca287980986f78`](https://github.com/llvm/llvm-project/commit/a66376b0dc3b2ea8a84fda26faca287980986f78) for Triton [3.3.0](https://github.com/triton-lang/triton/blob/release/3.3.x)

- [`657ec7320d8a28171755ba0dd5afc570a5a16791`](https://github.com/llvm/llvm-project/commit/657ec7320d8a28171755ba0dd5afc570a5a16791) for AOTriton [0.7b](https://github.com/ROCm/aotriton/tree/0.7b)
- [`bd9145c8c21334e099d51b3e66f49d51d24931ee`](https://github.com/llvm/llvm-project/commit/bd9145c8c21334e099d51b3e66f49d51d24931ee) for AOTriton [0.8b](https://github.com/ROCm/aotriton/tree/0.8b)
