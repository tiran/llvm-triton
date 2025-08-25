#!/usr/bin/env python3.11
# compatible with Python 3.11+ (needs platform.freedesktop_os_release)
"""Build LLVM for Triton"""

import argparse
import logging
import os
import pathlib
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

EnvDict = dict[str, str]

# mapping of /etc/os-release ID to tag extension
OS_RELEASE_ID_MAP: dict[str, str] = {
    "fedora": "fc",
    "rhel": "ubi",
}

ARCH = platform.machine()


class BuildLLVMTriton:
    download_url_template: str = (
        "https://github.com/llvm/llvm-project/archive/{}.tar.gz"
    )

    # build with MLIR and LLVM
    enable_projects: tuple[str, ...] = ("mlir", "llvm")

    # Build for AMD, NVIDIA, and the current arch
    targets_to_build: tuple[str, ...] = ("host", "AMDGPU", "NVPTX")

    # omit tools to reduce size, triton build does not need tools
    llvm_build_tools = "OFF"
    # static linking
    llvm_dylib = "OFF"

    def __init__(
        self,
        *,
        llvm_commit: str,
        buildroot: pathlib.Path,
        engine: str = "podman",
        container_registry: str = "localhost",
        image_tag: str = "latest",
    ) -> None:
        self.llvm_commit = llvm_commit
        self.engine = engine
        self.container_registry = container_registry
        self.image_tag = image_tag
        self.buildroot = buildroot
        self.buildroot.mkdir(exist_ok=True)

    @property
    def llvm_shortcommit(self) -> str:
        return self.llvm_commit[:8]

    @property
    def llvm_triton_name(self) -> str:
        """Name used in container tag, install prefix, and other places"""
        return f"llvm-triton-{self.llvm_shortcommit}"

    @property
    def install_prefix(self) -> pathlib.Path:
        """Installation path (absolute)"""
        return pathlib.Path("/usr/lib64") / self.llvm_triton_name

    @property
    def destdir(self) -> pathlib.Path:
        """destdir for cmake install"""
        return self.buildroot / self.llvm_triton_name

    @property
    def llvm_src_targz(self) -> pathlib.Path:
        """Path to LLVM sources tar bundle"""
        return self.buildroot / f"llvm-project-{self.llvm_commit}.tar.gz"

    @property
    def llvm_project_root(self) -> pathlib.Path:
        """Path to root directory of unpacked LLVM sources"""
        return self.buildroot / f"llvm-project-{self.llvm_commit}"

    @property
    def cmake_builddir(self) -> pathlib.Path:
        """cmake build directory"""
        return self.llvm_project_root / f"build-{ARCH}"

    def check_call(self, cmd: list[str], extra_env: EnvDict | None = None) -> None:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        logger.info("Running: %s (extra_env: %s)", shlex.join(cmd), extra_env)
        subprocess.check_call(cmd, env=env)

    def download(self) -> pathlib.Path:
        """Download tar.gz bundle"""
        targz = self.llvm_src_targz
        if targz.is_file():
            logger.info("%s already downloaded", targz)
            return targz

        url = self.download_url_template.format(self.llvm_commit)
        tmp = self.buildroot / f"{targz.name}.tmp"

        def reporthook(blocknum: int, bs: int, size: int) -> None:
            if (blocknum % 100) == 0:
                print(".", end="", flush=True)

        logger.info("Downloading %s", url)
        # write to tmp file
        urlretrieve(url, tmp, reporthook=reporthook)
        print("")
        # rename
        os.rename(tmp, targz)
        return targz

    def unpack(self, targz: pathlib.Path) -> None:
        llvm_project_root = self.llvm_project_root
        if llvm_project_root.is_dir():
            logger.info("Removing old build dir %s", llvm_project_root)
            shutil.rmtree(llvm_project_root)

        # we need license, cmake, and project dirs
        root = llvm_project_root.name
        parts = ["LICENSE.TXT", "cmake", *self.enable_projects]
        pattern = re.compile(f"^{root}/({'|'.join(parts)})(/.*)?$")

        def filter_cb(member: tarfile.TarInfo, dest: str) -> tarfile.TarInfo | None:
            member = tarfile.data_filter(member, dest)
            if member is None:
                return None
            # only extract members that start with a prefix or is root directory
            if pattern.match(member.name):
                return member
            return None

        logger.info("Unpacking %s (%s)", targz, pattern.pattern)

        with tarfile.TarFile.open(targz, mode="r:*") as t:
            t.extractall(self.buildroot, filter=filter_cb)

        if not llvm_project_root.is_dir():
            raise ValueError(f"{llvm_project_root} missing")

    def cmake_configure(self) -> None:
        """Configure with cmake"""
        # rpm --eval '%{_target_platform}'
        # {_target_cpu}-%{_vendor}-%{_target_os}%{?_gnu}
        llvm_triple = f"{ARCH}-redhat-linux-gnu"

        # ccache for local testing
        ccache = "ON" if shutil.which("ccache") else "OFF"

        cmd: list[str] = [
            "cmake",
            "-S",
            str(self.llvm_project_root / "llvm"),
            "-B",
            str(self.cmake_builddir),
            "-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON",
            # based on llvm-triton.spec
            "-G",
            "Ninja",
            "-DBUILD_SHARED_LIBS:BOOL=OFF",
            "-DLLVM_PARALLEL_LINK_JOBS=1",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DLLVM_LIBDIR_SUFFIX=",
            f"-DLLVM_CCACHE_BUILD={ccache}",
            f"-DLLVM_TARGETS_TO_BUILD={';'.join(self.targets_to_build)}",
            f"-DLLVM_ENABLE_PROJECTS={';'.join(self.enable_projects)}",
            # add short commit as version suffix
            f"-DLLVM_VERSION_SUFFIX=.git{self.llvm_shortcommit}",
            f"-DLLVM_DEFAULT_TARGET_TRIPLE={llvm_triple}",
            f"-DCMAKE_INSTALL_PREFIX={self.install_prefix}",
            "-DLLVM_ENABLE_LIBCXX:BOOL=OFF",
            "-DLLVM_ENABLE_ZLIB:BOOL=ON",
            "-DLLVM_ENABLE_FFI:BOOL=ON",
            "-DLLVM_ENABLE_RTTI:BOOL=ON",
            "-DLLVM_BUILD_RUNTIME:BOOL=ON",
            f"-DLLVM_BUILD_TOOLS:BOOL={self.llvm_build_tools}",
            "-DLLVM_INCLUDE_TOOLS:BOOL=ON",
            "-DLLVM_TOOLS_INSTALL_DIR:PATH=bin",
            "-DLLVM_INCLUDE_TESTS:BOOL=OFF",
            "-DLLVM_BUILD_TESTS:BOOL=OFF",
            "-DLLVM_INSTALL_GTEST:BOOL=OFF",
            "-DLLVM_LIT_ARGS=-v",
            "-DLLVM_INCLUDE_EXAMPLES:BOOL=OFF",
            "-DLLVM_BUILD_EXAMPLES:BOOL=OFF",
            "-DLLVM_INCLUDE_UTILS:BOOL=ON",
            "-DLLVM_INSTALL_UTILS:BOOL=ON",
            "-DLLVM_UTILS_INSTALL_DIR:PATH=bin",
            "-DLLVM_INCLUDE_DOCS:BOOL=OFF",
            "-DLLVM_BUILD_DOCS:BOOL=OFF",
            "-DLLVM_ENABLE_SPHINX:BOOL=OFF",
            "-DLLVM_ENABLE_DOXYGEN:BOOL=OFF",
            "-DLLVM_UNREACHABLE_OPTIMIZE:BOOL=OFF",
            f"-DLLVM_BUILD_LLVM_DYLIB:BOOL={self.llvm_dylib}",
            f"-DLLVM_LINK_LLVM_DYLIB:BOOL={self.llvm_dylib}",
            "-DLLVM_INSTALL_TOOLCHAIN_ONLY:BOOL=OFF",
            "-DLLVM_INCLUDE_BENCHMARKS=OFF",
            "-DMLIR_ENABLE_EXECUTION_ENGINE:bool=OFF",
        ]
        self.check_call(cmd)

    def cmake_build(self) -> None:
        """Build LLVM"""
        cmd: list[str] = [
            "cmake",
            "--build",
            str(self.cmake_builddir),
        ]
        self.check_call(cmd)

    def cmake_install(self) -> None:
        """Install into destdir"""
        cmd: list[str] = [
            "cmake",
            "--install",
            str(self.cmake_builddir),
        ]
        self.check_call(cmd, extra_env={"DESTDIR": str(self.destdir)})
        # install_prefix relative to destdir (strip leading '/')
        install_dir = self.destdir.joinpath(*self.install_prefix.parts[1:])
        # include license
        shutil.copy2(self.llvm_project_root / "LICENSE.TXT", install_dir)

    def pack_build(self) -> pathlib.Path:
        """Pack directory as uncompressed tar ball"""
        tarbundle = self.buildroot / f"llvm-triton-{self.llvm_shortcommit}-{ARCH}.tar"
        logger.info("Packing %s", tarbundle)
        tarbundle.unlink(missing_ok=True)
        with tarfile.open(tarbundle, mode="x:") as t:
            t.add(self.destdir, arcname=".", recursive=True)
        return tarbundle

    def container_import(self, tarbundle: pathlib.Path) -> str:
        """Import tar ball as a new container"""
        os_release = platform.freedesktop_os_release()
        os_id = OS_RELEASE_ID_MAP.get(os_release["ID"], os_release["ID"])
        os_version_id = os_release["VERSION_ID"]
        image_name = f"{self.container_registry}/{self.llvm_triton_name}-{os_id}{os_version_id}-{ARCH}:{self.image_tag}"

        # remove old container (not supported by buildah)
        cmd: list[str] = [
            self.engine,
            "rmi",
            "--ignore",
            image_name,
        ]
        self.check_call(cmd)

        logger.info("Importing %s into container %s", tarbundle, image_name)
        cmd = [
            self.engine,
            "import",
            str(tarbundle),
            image_name,
        ]
        # additional metadata
        labels = {
            "org.opencontainers.image.revision": self.llvm_commit,
            "org.opencontainers.image.title": self.llvm_triton_name,
            "org.opencontainers.image.description": f"LLVM for Triton with MLIR for {ARCH}",
            "org.freedesktop.os-release.id": os_release["ID"],
            "org.freedesktop.os-release.version_id": os_release["VERSION_ID"],
            "architecture": ARCH,
        }
        for name, value in labels.items():
            cmd.append("-c")
            cmd.append(f"LABEL {name}={value}")

        self.check_call(cmd)

        cmd = [self.engine, "inspect", image_name]
        self.check_call(cmd)

        return image_name

    def build(self) -> str:
        logger.info("Building LLVM %s", self.llvm_commit)

        targz = self.download()
        # TODO: verify checksum
        self.unpack(targz)
        self.cmake_configure()
        self.cmake_build()
        self.cmake_install()
        # TODO: check tarbundle size to detect bad builds
        # should be around 600 to 750 MiB
        tarbundle = self.pack_build()
        for directory in [self.llvm_project_root, self.destdir]:
            logger.info("rmtree %s", directory)
            shutil.rmtree(directory)
        return self.container_import(tarbundle)


def commit(commit: str) -> str:
    expected = 40
    if len(commit) != expected:
        raise argparse.ArgumentError(
            None, f"commit must have {expected} characters, got {len(commit)}"
        )
    return commit


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--container-engine",
    type=str,
    default="podman",
    # buildah is not supported
    choices=["podman", "docker"],
    dest="container_engine",
)
parser.add_argument(
    "--container-registry",
    type=str,
    default="localhost",
    dest="container_registry",
)
parser.add_argument(
    "--image-tag",
    type=str,
    default="latest",
    dest="image_tag",
)
parser.add_argument(
    "--buildroot",
    type=pathlib.Path,
    default=pathlib.Path(os.getcwd()).absolute() / "buildroot",
    dest="buildroot",
)

parser.add_argument(
    "--push",
    help="Push container to registry?",
    action="store_true",
    dest="push",
)
parser.add_argument(
    "llvm_commit",
    type=commit,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parser.parse_args()
    builder = BuildLLVMTriton(
        llvm_commit=args.llvm_commit,
        engine=args.container_engine,
        container_registry=args.container_registry,
        image_tag=args.image_tag,
        buildroot=args.buildroot.absolute(),
    )
    tag = builder.build()
    if args.push:
        builder.check_call([args.engine, "push", tag])


if __name__ == "__main__":
    main()
