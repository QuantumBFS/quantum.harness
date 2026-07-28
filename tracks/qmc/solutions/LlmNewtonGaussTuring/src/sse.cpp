#include "sse.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace cm {

SSE::SSE(const Lattice& lattice, double J, double h, double beta,
         const SSEParams& params)
    : lat_(lattice), J_(J), h_(h), beta_(beta),
      N_(static_cast<int>(lattice.N)), Nb_(static_cast<int>(lattice.Nb)),
      nCand_(N_ + Nb_), params_(params),
      M_(20), n_(0),
      rng_(static_cast<std::uint64_t>(params.seed)) {
    if (J_ < 0) throw std::runtime_error("J must be >= 0");
    if (h_ <= 0) throw std::runtime_error("h must be > 0");

    opType_.assign(M_, Op::NONE);
    opIdx_.assign(M_, -1);

    // random initial state |alpha(0)>
    spin_.resize(N_);
    std::uniform_int_distribution<int> coin(0, 1);
    for (int i = 0; i < N_; ++i) spin_[i] = coin(rng_) ? 1 : -1;

    sitePos_.assign(N_, {});
    segBase_.assign(N_, 0);
}

// Grow the operator string when the expansion order approaches the cutoff.
// Only grows (never truncates a sampled configuration); ~1/3 head-room keeps
// the fixed-length truncation error unobservable.
void SSE::ensureCutoff() {
    int need = n_ + n_ / 3 + 4;
    if (need > M_) {
        opType_.resize(need, Op::NONE);
        opIdx_.resize(need, -1);
        M_ = need;
    }
}

// ------------------------------------------------------------
// Diagonal update: insert / remove CONST_SITE and BOND operators,
// propagating the spin state through FLIP_SITE operators.
// ------------------------------------------------------------
void SSE::diagonalUpdate() {
    ensureCutoff();
    std::uniform_int_distribution<int> pickCand(0, nCand_ - 1);

    for (int p = 0; p < M_; ++p) {
        switch (opType_[p]) {
            case Op::NONE: {
                int c = pickCand(rng_);
                if (c < N_) {                    // propose CONST_SITE, weight h
                    double Pacc = nCand_ * beta_ * h_ / (M_ - n_);
                    if (Pacc >= 1.0 || u01_(rng_) < Pacc) {
                        opType_[p] = Op::CONST_SITE; opIdx_[p] = c; ++n_;
                    }
                } else {                         // propose BOND, weight 2J if aligned
                    int b = c - N_;
                    double w = bondWeight(spin_[lat_.bonds[b].i], spin_[lat_.bonds[b].j]);
                    if (w > 0.0) {
                        double Pacc = nCand_ * beta_ * w / (M_ - n_);
                        if (Pacc >= 1.0 || u01_(rng_) < Pacc) {
                            opType_[p] = Op::BOND; opIdx_[p] = b; ++n_;
                        }
                    }
                }
                break;
            }
            case Op::CONST_SITE: {
                double Pacc = (M_ - n_ + 1) / (nCand_ * beta_ * h_);
                if (Pacc >= 1.0 || u01_(rng_) < Pacc) { opType_[p] = Op::NONE; opIdx_[p] = -1; --n_; }
                break;
            }
            case Op::BOND: {
                int b = opIdx_[p];
                double w = bondWeight(spin_[lat_.bonds[b].i], spin_[lat_.bonds[b].j]); // = 2J
                double Pacc = (M_ - n_ + 1) / (nCand_ * beta_ * w);
                if (Pacc >= 1.0 || u01_(rng_) < Pacc) { opType_[p] = Op::NONE; opIdx_[p] = -1; --n_; }
                break;
            }
            case Op::FLIP_SITE:
                spin_[opIdx_[p]] = -spin_[opIdx_[p]]; // propagate the world line
                break;
        }
    }
}

// ------------------------------------------------------------
// Union-find over segments
// ------------------------------------------------------------
int SSE::ufFind(int x) {
    while (parent_[x] != x) { parent_[x] = parent_[parent_[x]]; x = parent_[x]; }
    return x;
}
void SSE::ufUnion(int a, int b) {
    int ra = ufFind(a), rb = ufFind(b);
    if (ra != rb) parent_[ra] = rb;
}

// Local segment index on `site` that contains string position `pos`.
// sitePos_[site] is the sorted list of that site's site-operator positions,
// dividing the (periodic) world line into k = max(size,1) segments.  Segment
// k-1 is the wrap-around segment straddling propagation index 0.
int SSE::localSegment(int site, int pos) const {
    const auto& sp = sitePos_[site];
    int k = static_cast<int>(sp.size());
    if (k == 0) return 0;
    int c = static_cast<int>(std::lower_bound(sp.begin(), sp.end(), pos) - sp.begin());
    return (c == 0 || c == k) ? (k - 1) : (c - 1);
}

// ------------------------------------------------------------
// Cluster update (Sandvik 2003 TFIM Swendsen-Wang, rejection-free)
// ------------------------------------------------------------
void SSE::clusterUpdate() {
    // 1. Collect each site's site-operator positions (string scanned in order,
    //    so positions come out already sorted) and lay out global segment ids.
    for (int i = 0; i < N_; ++i) sitePos_[i].clear();
    for (int p = 0; p < M_; ++p) {
        Op t = opType_[p];
        if (t == Op::CONST_SITE || t == Op::FLIP_SITE) sitePos_[opIdx_[p]].push_back(p);
    }
    int nSeg = 0;
    for (int i = 0; i < N_; ++i) {
        segBase_[i] = nSeg;
        nSeg += std::max<int>(1, static_cast<int>(sitePos_[i].size()));
    }

    // 2. Union the two segments bound by every BOND operator.
    parent_.resize(nSeg);
    for (int s = 0; s < nSeg; ++s) parent_[s] = s;
    for (int p = 0; p < M_; ++p) {
        if (opType_[p] != Op::BOND) continue;
        int b = opIdx_[p];
        int i = static_cast<int>(lat_.bonds[b].i), j = static_cast<int>(lat_.bonds[b].j);
        ufUnion(segBase_[i] + localSegment(i, p), segBase_[j] + localSegment(j, p));
    }

    // 3. Flip each cluster with probability 1/2 (decision taken on the root).
    flip_.assign(nSeg, 2); // 2 = undecided
    for (int s = 0; s < nSeg; ++s) {
        int r = ufFind(s);
        if (flip_[r] == 2) flip_[r] = (u01_(rng_) < 0.5) ? 1 : 0;
        flip_[s] = flip_[r];
    }

    // 4a. Update the stored state |alpha(0)>: site i lives in its wrap-around
    //     segment (local index k-1, or 0 when the world line has no site ops).
    for (int i = 0; i < N_; ++i) {
        int k = static_cast<int>(sitePos_[i].size());
        int wrap = segBase_[i] + (k > 0 ? k - 1 : 0);
        if (flip_[wrap]) spin_[i] = -spin_[i];
    }

    // 4b. Toggle each site operator whose two neighbouring segments disagree on
    //     the flip decision (CONST <-> FLIP; both weight h, so weight-preserving).
    for (int i = 0; i < N_; ++i) {
        const auto& sp = sitePos_[i];
        int k = static_cast<int>(sp.size());
        for (int s = 0; s < k; ++s) {
            int below = segBase_[i] + (s - 1 + k) % k; // segment ending at this op
            int above = segBase_[i] + s;               // segment starting at this op
            if (flip_[below] != flip_[above]) {
                Op& t = opType_[sp[s]];
                t = (t == Op::FLIP_SITE) ? Op::CONST_SITE : Op::FLIP_SITE;
            }
        }
    }
}

// ------------------------------------------------------------
// Debug: configuration consistency
// ------------------------------------------------------------
bool SSE::verifyConfig() {
    std::vector<std::int8_t> s = spin_;
    for (int p = 0; p < M_; ++p) {
        if (opType_[p] == Op::BOND) {
            int b = opIdx_[p];
            if (s[lat_.bonds[b].i] != s[lat_.bonds[b].j]) return false; // anti-aligned bond
        } else if (opType_[p] == Op::FLIP_SITE) {
            s[opIdx_[p]] = -s[opIdx_[p]];
        }
    }
    for (int i = 0; i < N_; ++i)
        if (s[i] != spin_[i]) return false; // world line does not close
    return true;
}

// ------------------------------------------------------------
// Driver
// ------------------------------------------------------------
SSEResult SSE::run() {
    const double qmin = lat_.smallest_momentum();
    const std::array<double, 3> qvec = {qmin, 0.0, 0.0};

    // precompute the q_min phase factors
    std::vector<double> cosq(N_), sinq(N_);
    for (int i = 0; i < N_; ++i) {
        double qr = qvec[0] * lat_.site_coords[i][0]
                  + qvec[1] * lat_.site_coords[i][1]
                  + qvec[2] * lat_.site_coords[i][2];
        cosq[i] = std::cos(qr);
        sinq[i] = std::sin(qr);
    }

    SSEResult res;
    res.bin_E.reserve(params_.n_bins);
    res.bin_m2.reserve(params_.n_bins);
    res.bin_m4.reserve(params_.n_bins);
    res.bin_S0.reserve(params_.n_bins);
    res.bin_Sq.reserve(params_.n_bins);

    double sE = 0, sn = 0, sn2 = 0, sm = 0, sm2 = 0, sm4 = 0, sS0 = 0, sSq = 0;
    double sDtH = 0;
    double sNc = 0, sNb = 0, sNf = 0;
    int nm = 0, nbad = 0;

    for (int sw = 0; sw < params_.n_thermal; ++sw) {
        diagonalUpdate();
        clusterUpdate();
    }

    const double invBin = 1.0 / std::max(params_.sweeps_per_bin, 1);
    for (int bin = 0; bin < params_.n_bins; ++bin) {
        double bE = 0, bm2 = 0, bm4 = 0, bS0 = 0, bSq = 0;

        for (int s = 0; s < params_.sweeps_per_bin; ++s) {
            diagonalUpdate();
            clusterUpdate();
            ++nm;

            if (params_.check_config && !verifyConfig()) ++nbad;
            if (params_.census) {
                int nc = 0, nb = 0, nf = 0;
                for (int p = 0; p < M_; ++p) {
                    if (opType_[p] == Op::CONST_SITE) ++nc;
                    else if (opType_[p] == Op::BOND) ++nb;
                    else if (opType_[p] == Op::FLIP_SITE) ++nf;
                }
                sNc += nc; sNb += nb; sNf += nf;
            }

            // energy from the expansion order n
            double E = (-static_cast<double>(n_) / beta_ + h_ * N_ + J_ * Nb_) / N_;
            sn += n_; sn2 += static_cast<double>(n_) * n_;

            // magnetisation moments and structure factors on |alpha(0)>
            double Mz = 0.0, re = 0.0, im = 0.0;
            for (int i = 0; i < N_; ++i) {
                Mz += spin_[i];
                re += spin_[i] * cosq[i];
                im += spin_[i] * sinq[i];
            }
            double mm = Mz / N_, mm2 = mm * mm;
            double S0 = mm2;
            double Sq = (re * re + im * im) / (static_cast<double>(N_) * N_);

            sE += E; sm += std::abs(mm); sm2 += mm2; sm4 += mm2 * mm2;
            sS0 += S0; sSq += Sq;

            if (params_.measure_dthetah) {
                double sum_zz = 0;
                for (int b = 0; b < Nb_; ++b) {
                    int i = static_cast<int>(lat_.bonds[b].i);
                    int j = static_cast<int>(lat_.bonds[b].j);
                    sum_zz += spin_[i] * spin_[j];
                }
                sDtH += J_ * std::sin(2 * params_.theta_berry) * sum_zz / N_;
            }

            bE += E; bm2 += mm2; bm4 += mm2 * mm2; bS0 += S0; bSq += Sq;
        }

        res.bin_E.push_back(bE * invBin);
        res.bin_m2.push_back(bm2 * invBin);
        res.bin_m4.push_back(bm4 * invBin);
        res.bin_S0.push_back(bS0 * invBin);
        res.bin_Sq.push_back(bSq * invBin);
    }

    double inv = 1.0 / std::max(nm, 1);
    res.energy = sE * inv;
    double navg = sn * inv, n2avg = sn2 * inv;
    res.Cv = (n2avg - navg * navg - navg) / N_;   // (<n^2>-<n>^2-<n>)/N
    res.m = sm * inv; res.m2 = sm2 * inv; res.m4 = sm4 * inv;
    res.Q = (res.m2 > 1e-30) ? res.m2 * res.m2 / res.m4 : 0.0;
    res.Sq0 = sS0 * inv; res.Sqmin = sSq * inv;
    res.dthetah_diag = sDtH * inv;

    // second-moment correlation length, same convention as the ED oracle
    if (qmin > 1e-12 && res.Sqmin > 1e-30) {
        double denom = 4.0 * std::pow(std::sin(qmin / 2.0), 2);
        double xi2 = (res.Sq0 / res.Sqmin - 1.0) / denom;
        int Lmax = std::max({lat_.L[0], lat_.L[1], lat_.L[2]});
        if (xi2 > 0 && Lmax > 0) res.xi_over_L = std::sqrt(xi2) / Lmax;
    }

    res.n_op_avg = navg / N_;
    if (params_.census) {
        res.n_const_avg = sNc * inv;
        res.n_bond_avg = sNb * inv;
        res.n_flip_avg = sNf * inv;
    }
    res.consistency_failures = nbad;
    res.sign_avg = 1.0;
    res.n_measure = nm;
    res.n_thermal = params_.n_thermal;
    return res;
}

} // namespace cm
