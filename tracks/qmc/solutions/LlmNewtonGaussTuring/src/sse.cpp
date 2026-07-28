#include "sse.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace cm {

// ============================================================
// Constructor
// ============================================================
SSE::SSE(const Lattice& lattice, double J, double h, double beta,
         const SSEParams& params)
    : lat_(lattice), J_(J), h_(h), beta_(beta),
      N_(static_cast<int>(lattice.N)), Nb_(static_cast<int>(lattice.Nb)),
      possibleOperatorNumber_(Nb_ + N_),
      params_(params),
      cutoff_(20),  // start small, adjustCutoff() will grow as needed
      operatorNum_(0),
      rng_(static_cast<unsigned>(params.seed)),
      halfLinkNum_(N_ / 2)
{
    if (J_ < 0) throw std::runtime_error("J must be >= 0");
    if (h_ <= 0) throw std::runtime_error("h must be > 0 for SSE dynamics");
    if (N_ % 2 != 0) throw std::runtime_error("N must be even");

    operatorList_.assign(static_cast<std::size_t>(cutoff_),
                         std::make_pair(OpType::NO_OPERATOR, -1));
    std::uniform_int_distribution<int> coin(0, 1);
    for (int i = 0; i < N_; ++i)
        spin_.push_back(coin(rng_) ? SpinDir::Up : SpinDir::Down);
}

// ============================================================
// Diagonal update — faithful port of sse_new SingleCpu::Run()
//
// possibleOperatorNumber = Nb + N
// CONST (0..N-1):  weight = h
// BOND (N..N+Nb-1): weight = bondWeight(spin_i, spin_j)
// ============================================================
void SSE::adjustCutoff() {
    if (cutoff_ * 0.9 < operatorNum_) {
        int adj = std::max(1, static_cast<int>(0.1 * cutoff_));
        cutoff_ += adj;
        operatorList_.insert(operatorList_.end(),
                             static_cast<std::size_t>(adj),
                             std::make_pair(OpType::NO_OPERATOR, -1));
    }
}

void SSE::diagonalUpdate() {
    adjustCutoff();
    std::uniform_int_distribution<int> randChoice(0, possibleOperatorNumber_ - 1);
    std::uniform_real_distribution<double> u01(0.0, 1.0);
    auto ifChoose = [&](double p) { return p >= 1.0 || (p > 0.0 && u01(rng_) < p); };

    for (auto& op : operatorList_) {
        auto& [opType, opIndex] = op;
        double P = -1.0;

        if (opType != OpType::NO_OPERATOR) {
            switch (opType) {
                case OpType::CONST_OPERATOR:
                    P = (cutoff_ - operatorNum_ + 1) /
                        (static_cast<double>(possibleOperatorNumber_) * beta_ * h_);
                    break;
                case OpType::BOND_OPERATOR: {
                    int bi = static_cast<int>(lat_.bonds[opIndex].i);
                    int bj = static_cast<int>(lat_.bonds[opIndex].j);
                    double w = bondWeight(spin_[bi], spin_[bj]);
                    P = (cutoff_ - operatorNum_ + 1) /
                        (static_cast<double>(possibleOperatorNumber_) * beta_ * w);
                    break;
                }
                case OpType::OFFDIAG_OPERATOR:
                    flip(spin_[opIndex]);
                    break;
                default: break;
            }
            if (opType != OpType::OFFDIAG_OPERATOR && ifChoose(P)) {
                op = std::make_pair(OpType::NO_OPERATOR, -1);
                --operatorNum_;
            }
        } else {
            int c = randChoice(rng_);
            if (c < N_) {
                P = static_cast<double>(possibleOperatorNumber_) * beta_ * h_ /
                    (cutoff_ - operatorNum_);
                if (ifChoose(P)) { opType = OpType::CONST_OPERATOR; opIndex = c; ++operatorNum_; }
            } else {
                int b = c - N_;
                int bi = static_cast<int>(lat_.bonds[b].i);
                int bj = static_cast<int>(lat_.bonds[b].j);
                double w = bondWeight(spin_[bi], spin_[bj]);
                P = static_cast<double>(possibleOperatorNumber_) * beta_ * w /
                    (cutoff_ - operatorNum_);
                if (ifChoose(P)) { opType = OpType::BOND_OPERATOR; opIndex = b; ++operatorNum_; }
            }
        }
    }
}

// ============================================================
// Line update — faithful port of sse_new LineUpdate
// ============================================================
void SSE::lineUpdate() {
    linkA_.assign(static_cast<std::size_t>(halfLinkNum_), {});
    linkB_.assign(static_cast<std::size_t>(halfLinkNum_), {});
    singleSiteList_.assign(static_cast<std::size_t>(N_), {});
    link_.assign(static_cast<std::size_t>(N_), {});

    constructLink();
    updateLattice<true>(linkA_, linkB_);
    updateLattice<false>(linkB_, linkA_);
    writeBack();

    linkA_.clear(); linkB_.clear(); singleSiteList_.clear(); link_.clear();
}

void SSE::constructLink() {
    for (std::size_t oi = 0; oi < operatorList_.size(); ++oi) {
        auto [opType, opIndex] = operatorList_[oi];
        switch (opType) {
            case OpType::NO_OPERATOR: continue;

            case OpType::BOND_OPERATOR: {
                int i = static_cast<int>(lat_.bonds[opIndex].i);
                int j = static_cast<int>(lat_.bonds[opIndex].j);
                SpinDir si = spin_[i], sj = spin_[j];
                if (i % 2 == 0) {
                    linkA_[i>>1].push_back({opType, opIndex, (int)oi, si, sj, 0});
                    linkB_[j>>1].push_back({opType, opIndex, (int)oi, si, sj, 0});
                    linkA_[i>>1].back().imageIndex = linkB_[j>>1].size() - 1;
                    linkB_[j>>1].back().imageIndex = linkA_[i>>1].size() - 1;
                } else {
                    linkA_[j>>1].push_back({opType, opIndex, (int)oi, si, sj, 0});
                    linkB_[i>>1].push_back({opType, opIndex, (int)oi, si, sj, 0});
                    linkA_[j>>1].back().imageIndex = linkB_[i>>1].size() - 1;
                    linkB_[i>>1].back().imageIndex = linkA_[j>>1].size() - 1;
                }
                break;
            }

            case OpType::CONST_OPERATOR:
                if (opIndex % 2 == 0) {
                    linkA_[opIndex>>1].push_back({opType, opIndex, (int)oi, spin_[opIndex], spin_[opIndex], 0});
                    singleSiteList_[opIndex].push_back({oi, linkA_[opIndex>>1].size() - 1});
                } else {
                    linkB_[opIndex>>1].push_back({opType, opIndex, (int)oi, spin_[opIndex], spin_[opIndex], 0});
                    singleSiteList_[opIndex].push_back({oi, linkB_[opIndex>>1].size() - 1});
                }
                break;

            case OpType::OFFDIAG_OPERATOR:
                if (opIndex % 2 == 0) {
                    linkA_[opIndex>>1].push_back({opType, opIndex, (int)oi, spin_[opIndex], -spin_[opIndex], 0});
                    singleSiteList_[opIndex].push_back({oi, linkA_[opIndex>>1].size() - 1});
                } else {
                    linkB_[opIndex>>1].push_back({opType, opIndex, (int)oi, spin_[opIndex], -spin_[opIndex], 0});
                    singleSiteList_[opIndex].push_back({oi, linkB_[opIndex>>1].size() - 1});
                }
                flip(spin_[opIndex]);
                break;
        }
    }
}

template<bool IsA>
void SSE::updateLattice(std::vector<std::vector<OpLink>>& link,
                         std::vector<std::vector<OpLink>>& linkOther) {
    const int offset = IsA ? 0 : 1;
    std::uniform_real_distribution<double> u01(0.0, 1.0);

    for (int site = 0; site < halfLinkNum_; ++site) {
        auto& sSL = singleSiteList_[(site << 1) + offset];
        if (sSL.empty()) continue;

        for (const auto& soi : sSL) {
            std::size_t li = soi.linkIndex;
            double metropolisP = 0.0;

            while (true) {
                li = (li + 1) % link[site].size();
                auto& [opType, opIndex, _, cfgi, cfgj, image] = link[site][li];
                (void)_; (void)image;
                if (opType == OpType::BOND_OPERATOR) {
                    int bond_i = static_cast<int>(lat_.bonds[opIndex].i);
                    bool csite = (bond_i == ((site << 1) | offset));
                    if (csite)
                        metropolisP += std::log(bondWeight(-cfgi, cfgj) / bondWeight(cfgi, cfgj));
                    else
                        metropolisP += std::log(bondWeight(cfgi, -cfgj) / bondWeight(cfgi, cfgj));
                } else break;
            }

            if (u01(rng_) < std::exp(metropolisP)) {
                { auto& [opType, opIndex, _, cfgi, cfgj, image] = link[site][li];
                  (void)_; (void)opIndex; (void)cfgj; (void)image;
                  flip(cfgi);
                  opType = (opType == OpType::OFFDIAG_OPERATOR) ? OpType::CONST_OPERATOR : OpType::OFFDIAG_OPERATOR; }
                while (true) {
                    li = (li + link[site].size() - 1) % link[site].size();
                    auto& [opType, opIndex, _, cfgi, cfgj, image] = link[site][li];
                    (void)_; (void)opIndex;
                    if (opType == OpType::BOND_OPERATOR) {
                        int bond_i = static_cast<int>(lat_.bonds[opIndex].i);
                        bool csite = (bond_i == ((site << 1) | offset));
                        if (csite) {
                            flip(cfgi);
                            flip(IsA ? linkOther[site][image].cfgi
                                     : linkOther[(site+1)%halfLinkNum_][image].cfgi);
                        } else {
                            flip(cfgj);
                            flip(IsA ? linkOther[(site-1+halfLinkNum_)%halfLinkNum_][image].cfgj
                                     : linkOther[site][image].cfgj);
                        }
                    } else {
                        flip(cfgj);
                        opType = (opType == OpType::OFFDIAG_OPERATOR) ? OpType::CONST_OPERATOR : OpType::OFFDIAG_OPERATOR;
                        break;
                    }
                }
            }
        }
    }
}

template void SSE::updateLattice<true>(std::vector<std::vector<OpLink>>&, std::vector<std::vector<OpLink>>&);
template void SSE::updateLattice<false>(std::vector<std::vector<OpLink>>&, std::vector<std::vector<OpLink>>&);

void SSE::writeBack() {
    for (int i = 0; i < N_; ++i)
        link_[i] = (i % 2 == 0) ? linkA_[i >> 1] : linkB_[i >> 1];
    for (int i = 0; i < N_; ++i) {
        if (link_[i].empty()) continue;
        const auto& first = link_[i][0];
        int bj = static_cast<int>(lat_.bonds[first.opIndex].j);
        spin_[i] = (first.opType == OpType::BOND_OPERATOR && i == bj) ? first.cfgj : first.cfgi;
    }
    for (int i = 0; i < N_; ++i)
        for (const auto& ref : singleSiteList_[i])
            operatorList_[ref.listIndex].first = link_[i][ref.linkIndex].opType;
}

// ============================================================
// Observables
// ============================================================
double SSE::magnetization() const {
    double sum = 0.0;
    for (auto s : spin_) sum += static_cast<double>(to_int(s));
    return sum / static_cast<double>(N_);
}

double SSE::computeEnergy() const {
    // E = J·Nb + h·N - ⟨n⟩/β
    return (J_ * static_cast<double>(Nb_) +
            h_ * static_cast<double>(N_) -
            static_cast<double>(operatorNum_) / beta_) / static_cast<double>(N_);
}

// ============================================================
// Full run
// ============================================================
SSEResult SSE::run() {
    SSEResult res;
    int tot = params_.n_thermal + params_.n_bins * params_.sweeps_per_bin;
    double sum_E = 0.0, sum_E2 = 0.0, sum_m = 0.0, sum_m2 = 0.0, sum_m4 = 0.0, sum_n = 0.0;
    int n_meas = 0;

    for (int sw = 0; sw < tot; ++sw) {
        diagonalUpdate();
        lineUpdate();

        if (sw >= params_.n_thermal && (sw - params_.n_thermal) % params_.sweeps_per_bin == 0) {
            ++n_meas;
            double E = computeEnergy();
            sum_E += E; sum_E2 += E * E;
            double m = magnetization();
            double m2 = m * m;
            sum_m += std::abs(m); sum_m2 += m2; sum_m4 += m2 * m2;
            sum_n += static_cast<double>(operatorNum_);
        }
    }

    double inv = 1.0 / std::max(n_meas, 1);
    res.energy = sum_E * inv;
    double E_avg = res.energy;
    res.Cv = (sum_E2 * inv - E_avg * E_avg) * beta_ * beta_ * static_cast<double>(N_);
    res.m = sum_m * inv; res.m2 = sum_m2 * inv; res.m4 = sum_m4 * inv;
    res.Q = (res.m2 > 1e-30) ? (res.m2 * res.m2 / res.m4) : 0.0;
    res.n_op_avg = sum_n * inv / static_cast<double>(N_);
    res.n_measure = n_meas; res.n_thermal = params_.n_thermal;
    res.susceptibility = res.m2 * beta_ * static_cast<double>(N_);
    return res;
}

} // namespace cm
