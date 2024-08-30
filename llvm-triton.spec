# LLVM for Triton (https://github.com/triton-lang/triton)
#
# Triton needs a special build of LLVM with MLIR for AMD and NVIDIA GPUs.
# Triton 2.3.1 and 3.0.0 are incompatible with regular releases of LLVM. They
# need LLVM from a specific git commit.
#
# Spec file is based on https://src.fedoraproject.org/rpms/llvm17/blob/rawhide/f/llvm17.spec
# and Tom Rix's python-triton.spec
#
# TODO: Explore '-DLLVM_BUILD_LLVM_DYLIB=OFF -DLLVM_LINK_LLVM_DYLIB=OFF' to
# link Triton statically w/o dependency on 'libLLVM.so.18.git...'. It is
# currently failing with missing symbol 'std::__glibcxx_assert_fail'.
#

# for local testing
%bcond_with ccache
%bcond_without cleanup

# build statically so libtriton does not depend on libLLVM-*.so
%bcond_without static

# omit tools to reduce size, triton build does not need tools
%bcond_with tools

# We are building with clang for faster/lower memory LTO builds.
# See https://docs.fedoraproject.org/en-US/packaging-guidelines/#_compiler_macros
%global toolchain clang

# Opt out of https://fedoraproject.org/wiki/Changes/fno-omit-frame-pointer
# https://bugzilla.redhat.com/show_bug.cgi?id=2158587
%undefine _include_frame_pointers

# re-define without -Wp,-D_GLIBCXX_ASSERTIONS, assertions break Triton build
# undefined reference to `std::__glibcxx_assert_fail(char const*, int, char const*, char const*)'
%global _preprocessor_defines %(echo %{_preprocessor_defines} | sed 's/-D_GLIBCXX_ASSERTIONS/-U_GLIBCXX_ASSERTIONS/')

# Opt out of debuginfo and debugsource. This is an internal developer package
# just for Triton builds.
%global debug_package %{nil}

# build for Triton version, see cmake/llvm-hash.txt for LLVM commit hash.
%global triton_ver 2.3.1

%if "%{triton_ver}" == "2.1.0"
  # PyTorch 2.3.1 ROCm build with aotriton 0.4.1b
  %global triton_name aotriton
  %global llvm_commit 49af6502c6dcb4a7f7520178bd14df396f78240c
  %global maj_ver 18
  %global min_ver 0
  %global patch_ver 0
%elif "%{triton_ver}" == "2.3.1"
  %global triton_name triton
  %global llvm_commit 5e5a22caf88ac1ccfa8dc5720295fdeba0ad9372
  %global maj_ver 18
  %global min_ver 0
  %global patch_ver 0
%elif "%{triton_ver}" == "3.0.0"
  %global triton_name aotriton
  %global llvm_commit 10dc3a8e916d73291269e5e2b82dd22681489aa1
  %global maj_ver 19
  %global min_ver 0
  %global patch_ver 0
%else
  %{error:unsupport Triton version %{triton_ver}}
%endif

# traditional short commit has 7 chars, but Triton uses 8 chars
%global llvm_shortcommit %(c=%{llvm_commit}; echo ${c:0:8})

%global install_prefix %{_libdir}/%{name}
%global install_bindir %{install_prefix}/bin
%global install_includedir %{install_prefix}/include
%global install_libdir %{install_prefix}/lib
%global pkg_includedir %{_includedir}/%{name}
%global pkg_datadir %{install_prefix}/share

%global targets_to_build "AMDGPU;NVPTX;X86;PowerPC;SystemZ;AArch64"
%global enable_projects "mlir;llvm"

%global build_install_prefix %{buildroot}%{install_prefix}

%global llvm_triple %{_target_platform}


Name:		llvm-%{triton_name}
Version:	%{maj_ver}.%{min_ver}.%{patch_ver}.git%{llvm_shortcommit}
Release:	5%{?dist}
Summary:	LLVM with MLIR for Triton %{triton_ver}

License:	Apache-2.0 WITH LLVM-exception OR NCSA
URL:		http://llvm.org
Source0:	https://github.com/llvm/llvm-project/archive/%{llvm_commit}.tar.gz#/llvm-project-%{maj_ver}.%{min_ver}.%{patch_ver}-%{llvm_shortcommit}.tar.gz

# https://github.com/llvm/llvm-project/commit/4f3c9dabecc6074f8455ca23ba70020d5c556e63
Patch0001:	0001-mlir-exclude-capi-test.patch
# disable unused tools to reduce size
Patch0002:	0002-mlir-disable-tools.patch

ExclusiveArch:	x86_64 aarch64 ppc64 ppc64le s390x

BuildRequires:	gcc
BuildRequires:	gcc-c++
BuildRequires:	clang
BuildRequires:	cmake
BuildRequires:	ninja-build
BuildRequires:	zlib-devel
BuildRequires:	libffi-devel
BuildRequires:	ncurses-devel
%ifarch %{valgrind_arches}
# Enable extra functionality when run the LLVM JIT under valgrind.
BuildRequires:	valgrind-devel
%endif
# LLVM's LineEditor library will use libedit if it is available.
BuildRequires:	libedit-devel
# We need python3-devel for %%py3_shebang_fix
BuildRequires:	python3-devel
BuildRequires:	python3-setuptools

Requires:	%{name}-libs%{?_isa} = %{version}-%{release}

Provides:	%{name}(%{triton_name}) = %{triton_ver}
Provides:	%{name}(commit) = %{llvm_commit}
Provides:	%{name}(commit) = %{llvm_shortcommit}

%description
LLVM is a compiler infrastructure designed for compile-time, link-time,
runtime, and idle-time optimization of programs from arbitrary programming
languages. The compiler infrastructure includes mirror sets of programming
tools as well as libraries with equivalent functionality.

This package provides a special build for Triton with MLIR.


%package devel
Summary:	Libraries and header files for LLVM
Requires:	%{name}%{?_isa} = %{version}-%{release}
Requires:	%{name}-libs%{?_isa} = %{version}-%{release}
# The installed LLVM cmake files will add -ledit to the linker flags for any
# app that requires the libLLVMLineEditor, so we need to make sure
# libedit-devel is available.
Requires:	libedit-devel
Requires:	%{name}-static%{?_isa} = %{version}-%{release}

Provides:	%{name}-devel(%{triton_name}) = %{triton_ver}
Provides:	%{name}-devel(commit) = %{llvm_commit}
Provides:	%{name}-devel(commit) = %{llvm_shortcommit}

%description devel
This package contains library and header files needed to develop new native
programs that use the LLVM infrastructure.

%package libs
Summary:	LLVM shared libraries

Provides:	%{name}-libs(%{triton_name}) = %{triton_ver}
Provides:	%{name}-libs(commit) = %{llvm_commit}
Provides:	%{name}-libs(commit) = %{llvm_shortcommit}

%description libs
Shared libraries for the LLVM compiler infrastructure.

Requires(post): /sbin/ldconfig
Requires(postun): /sbin/ldconfig

%package static
Summary:	LLVM static libraries

Provides:	%{name}-static(%{triton_name}) = %{triton_ver}
Provides:	%{name}-static(commit) = %{llvm_commit}
Provides:	%{name}-static(commit) = %{llvm_shortcommit}

%description static
Static libraries for the LLVM compiler infrastructure.

# no cmake-utils, test and googletest packages


%prep
%autosetup -p1 -n llvm-project-%{llvm_commit}

# not needed, COPR does not have enough disk space
rm -rf bolt clang compiler-rt cross-project-tests flang libc libclc libcxx libcxxabi libunwind lld lldb llvm-libgcc openmp polly pstl runtimes

%py3_shebang_fix \
	llvm/test/BugPoint/compile-custom.ll.py \
	llvm/tools/opt-viewer/*.py \
	llvm/utils/update_cc_test_checks.py


%build

%global _lto_cflags %nil

# Copy CFLAGS into ASMFLAGS, so -fcf-protection is used when compiling assembly files.
export ASMFLAGS="%{build_cflags}"

cd llvm

%cmake	-G Ninja \
	-DBUILD_SHARED_LIBS:BOOL=OFF \
	-DLLVM_PARALLEL_LINK_JOBS=1 \
	-DCMAKE_BUILD_TYPE=Release \
	-DLLVM_LIBDIR_SUFFIX= \
%if %{with ccache}
	-DLLVM_CCACHE_BUILD=on \
%endif
	\
	-DLLVM_TARGETS_TO_BUILD=%{targets_to_build} \
	-DLLVM_ENABLE_PROJECTS=%{enable_projects} \
	-DLLVM_VERSION_SUFFIX=".git%{llvm_shortcommit}" \
	-DLLVM_DEFAULT_TARGET_TRIPLE=%{llvm_triple} \
	-DCMAKE_INSTALL_PREFIX=%{install_prefix} \
	\
	-DLLVM_ENABLE_LIBCXX:BOOL=OFF \
	-DLLVM_ENABLE_ZLIB:BOOL=ON \
	-DLLVM_ENABLE_FFI:BOOL=ON \
	-DLLVM_ENABLE_RTTI:BOOL=ON \
	\
	-DLLVM_BUILD_RUNTIME:BOOL=ON \
	\
%if %{with tools}
	-DLLVM_BUILD_TOOLS:BOOL=ON \
%else
	-DLLVM_BUILD_TOOLS:BOOL=OFF \
%endif
	-DLLVM_INCLUDE_TOOLS:BOOL=ON \
	-DLLVM_TOOLS_INSTALL_DIR:PATH=bin \
	\
	-DLLVM_INCLUDE_TESTS:BOOL=OFF \
	-DLLVM_BUILD_TESTS:BOOL=OFF \
	-DLLVM_INSTALL_GTEST:BOOL=OFF \
	-DLLVM_LIT_ARGS=-v \
	\
	-DLLVM_INCLUDE_EXAMPLES:BOOL=OFF \
	-DLLVM_BUILD_EXAMPLES:BOOL=OFF \
	\
	-DLLVM_INCLUDE_UTILS:BOOL=OFF \
	-DLLVM_INSTALL_UTILS:BOOL=OFF \
	-DLLVM_UTILS_INSTALL_DIR:PATH=bin \
	\
	-DLLVM_INCLUDE_DOCS:BOOL=OFF \
	-DLLVM_BUILD_DOCS:BOOL=OFF \
	-DLLVM_ENABLE_SPHINX:BOOL=OFF \
	-DLLVM_ENABLE_DOXYGEN:BOOL=OFF \
	\
	-DLLVM_UNREACHABLE_OPTIMIZE:BOOL=OFF \
%if %{with static}
	-DLLVM_BUILD_LLVM_DYLIB:BOOL=OFF \
	-DLLVM_LINK_LLVM_DYLIB:BOOL=OFF \
%else
	-DLLVM_BUILD_LLVM_DYLIB:BOOL=ON \
	-DLLVM_LINK_LLVM_DYLIB:BOOL=ON \
%endif
	-DLLVM_INSTALL_TOOLCHAIN_ONLY:BOOL=OFF \
	-DLLVM_INCLUDE_BENCHMARKS=OFF \
	\
	-DMLIR_ENABLE_EXECUTION_ENGINE:bool=OFF

# Build libLLVM.so first.  This ensures that when libLLVM.so is linking, there
# are no other compile jobs running.  This will help reduce OOM errors on the
# builders without having to artificially limit the number of concurrent jobs.
%if %{without static}
%cmake_build --target LLVM
%endif
%cmake_build


%install
cd llvm
%cmake_install

%if %{with cleanup}
# COPR does not have enough disk space
rm -rf %{__cmake_builddir}
%endif

# Create ld.so.conf.d entry
mkdir -p %{buildroot}/etc/ld.so.conf.d
cat >> %{buildroot}/etc/ld.so.conf.d/%{name}-%{_arch}.conf << EOF
%{install_libdir}
EOF

%check
# no checks


%files
%license LICENSE.TXT
%{pkg_datadir}/opt-viewer
%if %{with tools}
%{install_bindir}/*
%else
%{install_bindir}/llvm-tblgen
%{install_bindir}/mlir-pdll
%{install_bindir}/mlir-tblgen
%endif


%files libs
%license LICENSE.TXT
%if %{without static}
%{install_libdir}/libLLVM-%{maj_ver}*.git%{llvm_shortcommit}.so
%{install_libdir}/libLLVM-%{maj_ver}*.%{min_ver}*.so
%{install_libdir}/libMLIR.so.%{maj_ver}*.git%{llvm_shortcommit}
%endif
%{install_libdir}/libmlir*.so.%{maj_ver}*.git%{llvm_shortcommit}
%{install_libdir}/libLTO.so.%{maj_ver}*.git%{llvm_shortcommit}
%{install_libdir}/libRemarks.so.%{maj_ver}*.git%{llvm_shortcommit}
%config(noreplace) /etc/ld.so.conf.d/%{name}-%{_arch}.conf

%files devel
%license LICENSE.TXT
%{install_includedir}/mlir
%{install_includedir}/mlir-c
%{install_includedir}/llvm
%{install_includedir}/llvm-c
%if %{without static}
%{install_libdir}/libLLVM.so
%{install_libdir}/libMLIR.so
%endif
%{install_libdir}/libLTO.so
%{install_libdir}/libRemarks.so
%{install_libdir}/libmlir*.so
%{install_libdir}/cmake/llvm
%{install_libdir}/cmake/mlir
%if %{with tools}
%{install_bindir}/llvm-config
%endif
%{install_libdir}/objects-Release/obj.MLIR*/*

%files static
%license LICENSE.TXT
%{install_libdir}/*.a


%changelog
* Fri Aug 30 2024 Christian Heimes <cheimes@redhat.com> - 18.0.0.git5e5a22ca-5
- Include aarch64, ppc64le, and s390x

* Wed Aug 28 2024 Christian Heimes <cheimes@redhat.com> - 18.0.0.git5e5a22ca-4
- Use longer commit hash and name in provides

* Wed Aug 28 2024 Christian Heimes <cheimes@redhat.com> - 18.0.0.git5e5a22c-3
- Build without tools to reduce size

* Tue Aug 06 2024 Christian Heimes <cheimes@redhat.com> - 18.0.0.git5e5a22c-2
- Build without utils and clean up to address out of diskspace issue

* Mon Aug 05 2024 Christian Heimes <cheimes@redhat.com> - 18.0.0.git5e5a22c-1
- Initial build for Triton 2.3.1
- Build with MLIR
