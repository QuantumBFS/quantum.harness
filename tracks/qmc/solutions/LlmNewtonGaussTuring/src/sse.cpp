#include "sse.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace cm {

namespace {

int checked_sse_count(std::size_t value, const char* label) {
    if (value > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::length_error(std::string(label) + " exceeds SSE integer range");
    return static_cast<int>(value);
}

int checked_candidate_count(const Lattice& lattice) {
    const auto maximum = static_cast<std::size_t>(std::numeric_limits<int>::max());
    if (lattice.N > maximum || lattice.Nb > maximum || lattice.N > maximum - lattice.Nb)
        throw std::length_error("diagonal candidate count exceeds SSE integer range");
    return static_cast<int>(lattice.N + lattice.Nb);
}

} // namespace

SSE::SSE(const Lattice& lattice, double J, double h, double beta,
         const SSEParams& params)
    : lat_(lattice), J_(J), h_(h), beta_(beta),
      N_(checked_sse_count(lattice.N, "site count")),
      Nb_(checked_sse_count(lattice.Nb, "bond count")),
      nCand_(checked_candidate_count(lattice)), params_(params),
      M_(20), n_(0),
      rng_(params.seed) {
    if (!std::isfinite(J_) || J_ < 0) throw std::invalid_argument("J must be finite and >= 0");
    if (!std::isfinite(h_) || h_ <= 0) throw std::invalid_argument("h must be finite and > 0");
    if (!std::isfinite(beta_) || beta_ <= 0) throw std::invalid_argument("beta must be finite and > 0");
    if (params_.n_thermal < 0 || params_.n_bins <= 0 || params_.sweeps_per_bin <= 0)
        throw std::invalid_argument("SSE sweep counts require thermal >= 0, bins > 0, sweeps/bin > 0");
    if (params_.n_bins > std::numeric_limits<int>::max() / params_.sweeps_per_bin)
        throw std::length_error("SSE measurement sweep count exceeds integer range");
    if (params_.progress_every_bins < 0)
        throw std::invalid_argument("progress_every_bins must be >= 0");
    if (params_.measure_rotated_bond_diagonal
        && !std::isfinite(params_.rotation_theta))
        throw std::invalid_argument("rotation_theta must be finite when its diagnostic is enabled");
    std::string diagnostic;
    if (!lattice.verify(&diagnostic))
        throw std::invalid_argument("invalid lattice: " + diagnostic);
    if (lattice.site_coords.size() != lattice.N)
        throw std::invalid_argument("SSE requires one coordinate per lattice site");

    opType_.assign(M_, Op::NONE);
    opIdx_.assign(M_, -1);

    // Explicit hot/cold starts support the production thermalization gate.
    spin_.resize(N_);
    if (params_.initial_state == InitialState::ORDERED_UP) {
        std::fill(spin_.begin(), spin_.end(), 1);
    } else {
        std::uniform_int_distribution<int> coin(0, 1);
        for (int i = 0; i < N_; ++i) spin_[i] = coin(rng_) ? 1 : -1;
    }

    sitePos_.assign(N_, {});
    segBase_.assign(N_, 0);
    segmentCursor_.assign(N_, 0);
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
    std::fill(segmentCursor_.begin(), segmentCursor_.end(), 0);
    for (int p = 0; p < M_; ++p) {
        if (opType_[p] != Op::BOND) continue;
        int b = opIdx_[p];
        int i = static_cast<int>(lat_.bonds[b].i), j = static_cast<int>(lat_.bonds[b].j);
        auto segment_at = [this, p](int site) {
            const auto& positions = sitePos_[site];
            const int k = static_cast<int>(positions.size());
            if (k == 0) return segBase_[site];
            int& cursor = segmentCursor_[site];
            while (cursor < k && positions[cursor] < p) ++cursor;
            const int local = (cursor == 0 || cursor == k) ? (k - 1) : (cursor - 1);
            return segBase_[site] + local;
        };
        ufUnion(segment_at(i), segment_at(j));
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
    const std::vector<std::array<double, 3>> qvecs = lat_.smallest_momentum_vectors();
    if (qvecs.empty()) throw std::runtime_error("SSE requires a non-zero torus momentum");
    const auto& first_q = qvecs.front();
    const double qmin = std::sqrt(first_q[0] * first_q[0] + first_q[1] * first_q[1]
                                + first_q[2] * first_q[2]);

    // precompute the q_min phase factors
    std::vector<std::vector<double>> cosq(qvecs.size(), std::vector<double>(N_));
    std::vector<std::vector<double>> sinq(qvecs.size(), std::vector<double>(N_));
    for (std::size_t q = 0; q < qvecs.size(); ++q) {
        for (int i = 0; i < N_; ++i) {
            double qr = qvecs[q][0] * lat_.site_coords[i][0]
                      + qvecs[q][1] * lat_.site_coords[i][1]
                      + qvecs[q][2] * lat_.site_coords[i][2];
            cosq[q][i] = std::cos(qr);
            sinq[q][i] = std::sin(qr);
        }
    }

    // Stage 4 visits the same propagated state for every diagonal operator.
    // Keep these buffers outside the sweep loop so allocation is not part of
    // the production hot path.
    std::vector<std::int8_t> propagated;
    std::vector<double> q_re, q_im;
    if (params_.stage4_estimators) {
        propagated.resize(N_);
        q_re.resize(qvecs.size());
        q_im.resize(qvecs.size());
    }

    SSEResult res;
    res.bin_E.reserve(params_.n_bins);
    res.bin_m2.reserve(params_.n_bins);
    res.bin_m4.reserve(params_.n_bins);
    res.bin_S0.reserve(params_.n_bins);
    res.bin_Sq.reserve(params_.n_bins);
    res.bin_spacetime_m2.reserve(params_.n_bins);
    res.bin_spacetime_m4.reserve(params_.n_bins);
    if (params_.census) {
        res.bin_exchange_energy.reserve(params_.n_bins);
        res.bin_field_energy.reserve(params_.n_bins);
    }

    double sE = 0, sn = 0, sn2 = 0, sm = 0, sm2 = 0, sm4 = 0, sS0 = 0, sSq = 0;
    double sTm2 = 0, sTm4 = 0;
    double sDtH = 0;
    double sNc = 0, sNb = 0, sNf = 0;
    int nm = 0, nbad = 0;

    for (int sw = 0; sw < params_.n_thermal; ++sw) {
        diagonalUpdate();
        clusterUpdate();
    }

    const double invBin = 1.0 / std::max(params_.sweeps_per_bin, 1);
    for (int bin = 0; bin < params_.n_bins; ++bin) {
        double bE = 0, bm2 = 0, bm4 = 0, bS0 = 0, bSq = 0, bTm2 = 0, bTm4 = 0;
        double bExchange = 0, bField = 0;

        for (int s = 0; s < params_.sweeps_per_bin; ++s) {
            diagonalUpdate();
            clusterUpdate();
            ++nm;

            if (params_.check_config && !verifyConfig()) ++nbad;
            int nc = 0, nb = 0, nf = 0;
            if (params_.census) {
                for (int p = 0; p < M_; ++p) {
                    if (opType_[p] == Op::CONST_SITE) ++nc;
                    else if (opType_[p] == Op::BOND) ++nb;
                    else if (opType_[p] == Op::FLIP_SITE) ++nf;
                }
                sNc += nc; sNb += nb; sNf += nf;
            }

            // energy from the expansion order n
            double E = (-static_cast<double>(n_) / beta_ + h_ * N_ + J_ * Nb_) / N_;
            if (params_.census) {
                bExchange += (-static_cast<double>(nb) / beta_ + J_ * Nb_) / N_;
                bField += (-static_cast<double>(nf) / beta_) / N_;
            }
            sn += n_; sn2 += static_cast<double>(n_) * n_;

            // Legacy path measures on |alpha(0)>.  Stage 4 instead averages
            // equal-time observables over propagated states and separately
            // samples the continuous imaginary-time magnetisation.
            double Mz = 0.0;
            for (int i = 0; i < N_; ++i) {
                Mz += spin_[i];
            }
            double mm = Mz / N_, mm2 = 0.0, mm4 = 0.0, S0 = 0.0, Sq = 0.0;
            double tm2 = mm * mm, tm4 = tm2 * tm2;

            if (params_.stage4_estimators) {
                std::copy(spin_.begin(), spin_.end(), propagated.begin());
                double current_Mz = Mz;
                double equal_m2 = 0.0, equal_m4 = 0.0, equal_Sq = 0.0;
                int propagated_count = 0;
                double current_m = current_Mz / N_;
                double p1 = current_m;
                double p2 = current_m * current_m;
                double p3 = p2 * current_m;
                double p4 = p2 * p2;
                std::size_t interval_count = 1;
                std::fill(q_re.begin(), q_re.end(), 0.0);
                std::fill(q_im.begin(), q_im.end(), 0.0);
                for (std::size_t q = 0; q < qvecs.size(); ++q) {
                    for (int i = 0; i < N_; ++i) {
                        q_re[q] += propagated[i] * cosq[q][i];
                        q_im[q] += propagated[i] * sinq[q][i];
                    }
                }
                double qsum = 0.0;
                for (std::size_t q = 0; q < qvecs.size(); ++q) {
                    qsum += (q_re[q] * q_re[q] + q_im[q] * q_im[q])
                          / (static_cast<double>(N_) * N_);
                }
                qsum /= static_cast<double>(qvecs.size());
                for (int pidx = 0; pidx < M_; ++pidx) {
                    if (opType_[pidx] == Op::NONE) continue;

                    current_m = current_Mz / N_;
                    const double current_m_squared = current_m * current_m;
                    equal_m2 += current_m_squared;
                    equal_m4 += current_m_squared * current_m_squared;
                    equal_Sq += qsum;
                    ++propagated_count;

                    if (opType_[pidx] == Op::FLIP_SITE) {
                        const int site = opIdx_[pidx];
                        const double delta = -2.0 * propagated[site];
                        current_Mz += delta;
                        for (std::size_t q = 0; q < qvecs.size(); ++q) {
                            q_re[q] += delta * cosq[q][site];
                            q_im[q] += delta * sinq[q][site];
                        }
                        propagated[site] = -propagated[site];
                        qsum = 0.0;
                        for (std::size_t q = 0; q < qvecs.size(); ++q) {
                            qsum += (q_re[q] * q_re[q] + q_im[q] * q_im[q])
                                  / (static_cast<double>(N_) * N_);
                        }
                        qsum /= static_cast<double>(qvecs.size());
                    }
                    current_m = current_Mz / N_;
                    const double current_m_squared_after = current_m * current_m;
                    p1 += current_m;
                    p2 += current_m_squared_after;
                    p3 += current_m_squared_after * current_m;
                    p4 += current_m_squared_after * current_m_squared_after;
                    ++interval_count;
                }

                // Conditional on the operator sequence, its n ordered times
                // have Dirichlet(1,...,1) spacings.  These closed forms are
                // the exact spacing averages of mbar^2 and mbar^4.
                const double K = static_cast<double>(interval_count);
                tm2 = (p1 * p1 + p2) / (K * (K + 1.0));
                tm4 = (std::pow(p1, 4) + 6.0 * p1 * p1 * p2 + 3.0 * p2 * p2
                     + 8.0 * p1 * p3 + 6.0 * p4)
                    / (K * (K + 1.0) * (K + 2.0) * (K + 3.0));

                if (propagated_count == 0) {
                    equal_m2 = mm * mm;
                    equal_m4 = equal_m2 * equal_m2;
                    equal_Sq = qsum;
                    propagated_count = 1;
                }
                mm2 = equal_m2 / propagated_count;
                mm4 = equal_m4 / propagated_count;
                S0 = mm2;
                Sq = equal_Sq / propagated_count;
            } else {
                double qsum = 0.0;
                for (std::size_t q = 0; q < qvecs.size(); ++q) {
                    double re = 0.0, im = 0.0;
                    for (int i = 0; i < N_; ++i) {
                        re += spin_[i] * cosq[q][i];
                        im += spin_[i] * sinq[q][i];
                    }
                    qsum += (re * re + im * im) / (static_cast<double>(N_) * N_);
                }
                mm2 = mm * mm;
                mm4 = mm2 * mm2;
                S0 = mm2;
                Sq = qsum / std::max<std::size_t>(qvecs.size(), 1);
            }

            sE += E; sm += std::abs(mm); sm2 += mm2; sm4 += mm4;
            sS0 += S0; sSq += Sq;
            sTm2 += tm2; sTm4 += tm4;

            // Prefactor-weighted H0-ensemble ZZ diagnostic. It is not the
            // rotated-state diagonal expectation or the generalized force.
            if (params_.measure_rotated_bond_diagonal) {
                double sum_zz = 0;
                for (int b = 0; b < Nb_; ++b) {
                    int i = static_cast<int>(lat_.bonds[b].i);
                    int j = static_cast<int>(lat_.bonds[b].j);
                    sum_zz += spin_[i] * spin_[j];
                }
                sDtH += J_ * std::sin(2 * params_.rotation_theta) * sum_zz / N_;
            }

            bE += E; bm2 += mm2; bm4 += mm4; bS0 += S0; bSq += Sq;
            bTm2 += tm2; bTm4 += tm4;
        }

        res.bin_E.push_back(bE * invBin);
        res.bin_m2.push_back(bm2 * invBin);
        res.bin_m4.push_back(bm4 * invBin);
        res.bin_S0.push_back(bS0 * invBin);
        res.bin_Sq.push_back(bSq * invBin);
        res.bin_spacetime_m2.push_back(bTm2 * invBin);
        res.bin_spacetime_m4.push_back(bTm4 * invBin);
        if (params_.census) {
            res.bin_exchange_energy.push_back(bExchange * invBin);
            res.bin_field_energy.push_back(bField * invBin);
        }

        if (params_.progress_every_bins > 0
            && ((bin + 1) % params_.progress_every_bins == 0
                || bin + 1 == params_.n_bins)) {
            const double measured = static_cast<double>((bin + 1) * params_.sweeps_per_bin);
            const double partial_m2 = sTm2 / measured;
            const double partial_m4 = sTm4 / measured;
            const double partial_q = partial_m2 * partial_m2
                                   / std::max(partial_m4, 1e-30);
            std::cerr << "progress bins=" << (bin + 1) << '/' << params_.n_bins
                      << " E=" << (sE / measured)
                      << " Q_spacetime=" << partial_q << std::endl;
        }
    }

    double inv = 1.0 / std::max(nm, 1);
    res.energy = sE * inv;
    double navg = sn * inv, n2avg = sn2 * inv;
    res.Cv = (n2avg - navg * navg - navg) / N_;   // (<n^2>-<n>^2-<n>)/N
    res.m = sm * inv; res.m2 = sm2 * inv; res.m4 = sm4 * inv;
    res.Q = (res.m4 > 1e-30) ? res.m2 * res.m2 / res.m4 : 0.0;
    res.Sq0 = sS0 * inv; res.Sqmin = sSq * inv;
    res.spacetime_m2 = sTm2 * inv;
    res.spacetime_m4 = sTm4 * inv;
    res.spacetime_Q = res.spacetime_m2 * res.spacetime_m2
                    / std::max(res.spacetime_m4, 1e-30);
    res.dthetah_diagonal = sDtH * inv;

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
        res.exchange_energy = (-res.n_bond_avg / beta_ + J_ * Nb_) / N_;
        res.field_energy = (-res.n_flip_avg / beta_) / N_;
    }
    res.config_checked = params_.check_config;
    res.consistency_failures = params_.check_config ? nbad : -1;
    res.sign_avg = 1.0;
    res.n_measure = nm;
    res.n_thermal = params_.n_thermal;
    return res;
}

} // namespace cm
