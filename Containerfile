ARG BASE_IMAGE=registry.access.redhat.com/ubi8/ubi:8.10
FROM ${BASE_IMAGE}

RUN dnf install -y --nodocs \
    python3.11 \
    clang cmake gcc gcc-c++ libedit-devel libffi-devel ncurses-devel ninja-build python3-devel zlib-devel \
    && dnf clean all

COPY build_llvm_triton.py /usr/local/bin/build_llvm_triton.py
