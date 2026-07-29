#include "pfapack.h"

// Stage 3A validates log-partition functions only.  The upstream logZ path
// computes an unused magnetization diagnostic through PFAPACK, so this shim
// returns a quiet zero for that excluded observable.  No reported logZ value
// depends on this result.
extern "C" void skpf10(
    int,
    double *,
    double *result,
    const char *,
    const char *
) {
    result[0] = 0.0;
    result[1] = 0.0;
}
