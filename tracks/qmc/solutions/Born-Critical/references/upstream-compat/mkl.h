#pragma once

// The pinned code uses only the LAPACKE routines declared below.  Eigen's
// optional MKL dispatch is disabled so the compatibility build remains
// independent of MKL's proprietary headers; LAPACKE symbols still come from
// the node-local libmkl_rt runtime.

using lapack_int = int;
inline constexpr int LAPACK_COL_MAJOR = 102;

extern "C" {
lapack_int LAPACKE_zgetrf(int, lapack_int, lapack_int, void *, lapack_int, lapack_int *);
lapack_int LAPACKE_zgetri(int, lapack_int, void *, lapack_int, const lapack_int *);
lapack_int LAPACKE_dgetrf(int, lapack_int, lapack_int, double *, lapack_int, lapack_int *);
lapack_int LAPACKE_dgetri(int, lapack_int, double *, lapack_int, const lapack_int *);
lapack_int LAPACKE_dgeqp3_work(
    int, lapack_int, lapack_int, double *, lapack_int, lapack_int *,
    double *, double *, lapack_int
);
lapack_int LAPACKE_dgeqrf(
    int, lapack_int, lapack_int, double *, lapack_int, double *
);
lapack_int LAPACKE_dorgqr(
    int, lapack_int, lapack_int, lapack_int, double *, lapack_int,
    const double *
);
}

#undef EIGEN_USE_MKL_ALL
