#!/bin/bash
# Run one command under the constraint prefix (CPUs 12-15, nice 19, idle I/O, one BLAS thread, CUDA hidden).
exec taskset -c 12-15 nice -n 19 ionice -c 3 env CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 "$@"
