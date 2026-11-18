#!/bin/bash
# Round-2 review of A11: run as `taskset -c 12-15 nice -n 19 ionice -c 3 r2_p.sh <cmd>`; sets one BLAS thread,
# hides CUDA, limits the address space to 1.5 GiB and execs the command.
ulimit -v 1572864
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
exec "$@"
