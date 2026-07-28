#include "sse.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace cm {

SSE::SSE(const Lattice& lattice, double J, double h, double beta,
         const SSEParams& params)
    : lat_(lattice), J_(J), h_(h), beta_(beta),
      N_(static_cast<int>(lattice.N)), Nb_(static_cast<int>(lattice.Nb)),
      possibleOperatorNumber_(Nb_ + N_),
      energyShift_(0.0), params_(params),
      cutoff_(20), operatorNum_(0),
      rng_(static_cast<unsigned>(params.seed)),
      halfLinkNum_(N_ / 2)
{
    if (J_ < 0) throw std::runtime_error("J must be >= 0");
    if (h_ <= 0) throw std::runtime_error("h must be > 0");
    if (N_ % 2 != 0) throw std::runtime_error("N must be even");
    setEnergyShift();
    operatorList_.assign(cutoff_, std::make_pair(OpType::NO_OPERATOR, -1));
    std::uniform_int_distribution<int> coin(0, 1);
    for (int i = 0; i < N_; ++i) spin_.push_back(coin(rng_) ? SpinDir::Up : SpinDir::Down);
}

void SSE::setEnergyShift() {
    const SpinDir s2[2] = {SpinDir::Up, SpinDir::Down};
    energyShift_ = 0.0; double maxE = 0.0;
    for (auto a : s2) for (auto b : s2) maxE = std::max(maxE, -bondWeight(a, b));
    energyShift_ = -maxE - 0.1;
}

void SSE::adjustCutoff() {
    if (cutoff_ * 0.9 < operatorNum_) {
        int adj = std::max(1, static_cast<int>(0.1 * cutoff_));
        cutoff_ += adj;
        operatorList_.insert(operatorList_.end(), adj, std::make_pair(OpType::NO_OPERATOR, -1));
    }
}

void SSE::diagonalUpdate() {
    adjustCutoff();
    int tot = possibleOperatorNumber_;
    std::uniform_int_distribution<int> rc(0, tot - 1);
    std::uniform_real_distribution<double> u01(0.0, 1.0);
    auto ifC = [&](double p) { return p >= 1.0 || (p > 0.0 && u01(rng_) < p); };

    for (auto& op : operatorList_) {
        auto& [t, idx] = op; double P = -1.0;
        if (t != OpType::NO_OPERATOR) {
            switch (t) {
                case OpType::BOND_OPERATOR: {
                    int bi = lat_.bonds[idx].i, bj = lat_.bonds[idx].j;
                    P = (cutoff_ - operatorNum_ + 1) / (tot * beta_ * bondWeight(spin_[bi], spin_[bj]));
                    break;
                }
                case OpType::CONST_OPERATOR:
                    P = (cutoff_ - operatorNum_ + 1) / (tot * beta_ * h_); break;
                case OpType::OFFDIAG_OPERATOR: flip(spin_[idx]); break;
                default: break;
            }
            if (t != OpType::OFFDIAG_OPERATOR && ifC(P)) { op = std::make_pair(OpType::NO_OPERATOR, -1); --operatorNum_; }
        } else {
            int c = rc(rng_);
            if (c < N_) {
                P = tot * beta_ * h_ / (cutoff_ - operatorNum_);
                if (ifC(P)) { t = OpType::CONST_OPERATOR; idx = c; ++operatorNum_; }
            } else {
                int b = c - N_, bi = lat_.bonds[b].i, bj = lat_.bonds[b].j;
                P = tot * beta_ * bondWeight(spin_[bi], spin_[bj]) / (cutoff_ - operatorNum_);
                if (ifC(P)) { t = OpType::BOND_OPERATOR; idx = b; ++operatorNum_; }
            }
        }
    }
}

void SSE::lineUpdate() {
    linkA_.assign(halfLinkNum_, {}); linkB_.assign(halfLinkNum_, {});
    singleSiteList_.assign(N_, {}); link_.assign(N_, {});
    constructLink(); updateLattice<true>(linkA_, linkB_); updateLattice<false>(linkB_, linkA_);
    writeBack(); linkA_.clear(); linkB_.clear(); singleSiteList_.clear(); link_.clear();
}

void SSE::constructLink() {
    for (std::size_t oi = 0; oi < operatorList_.size(); ++oi) {
        auto [t, idx] = operatorList_[oi];
        switch (t) {
            case OpType::NO_OPERATOR: continue;
            case OpType::BOND_OPERATOR: {
                int i = lat_.bonds[idx].i, j = lat_.bonds[idx].j;
                SpinDir si = spin_[i], sj = spin_[j];
                if (i % 2 == 0) {
                    linkA_[i>>1].push_back({t, idx, (int)oi, si, sj, 0});
                    linkB_[j>>1].push_back({t, idx, (int)oi, si, sj, 0});
                    linkA_[i>>1].back().imageIndex = linkB_[j>>1].size() - 1;
                    linkB_[j>>1].back().imageIndex = linkA_[i>>1].size() - 1;
                } else {
                    linkA_[j>>1].push_back({t, idx, (int)oi, si, sj, 0});
                    linkB_[i>>1].push_back({t, idx, (int)oi, si, sj, 0});
                    linkA_[j>>1].back().imageIndex = linkB_[i>>1].size() - 1;
                    linkB_[i>>1].back().imageIndex = linkA_[j>>1].size() - 1;
                } break;
            }
            case OpType::CONST_OPERATOR:
                if (idx % 2 == 0) {
                    linkA_[idx>>1].push_back({t, idx, (int)oi, spin_[idx], spin_[idx], 0});
                    singleSiteList_[idx].push_back({oi, linkA_[idx>>1].size() - 1});
                } else {
                    linkB_[idx>>1].push_back({t, idx, (int)oi, spin_[idx], spin_[idx], 0});
                    singleSiteList_[idx].push_back({oi, linkB_[idx>>1].size() - 1});
                } break;
            case OpType::OFFDIAG_OPERATOR:
                if (idx % 2 == 0) {
                    linkA_[idx>>1].push_back({t, idx, (int)oi, spin_[idx], -spin_[idx], 0});
                    singleSiteList_[idx].push_back({oi, linkA_[idx>>1].size() - 1});
                } else {
                    linkB_[idx>>1].push_back({t, idx, (int)oi, spin_[idx], -spin_[idx], 0});
                    singleSiteList_[idx].push_back({oi, linkB_[idx>>1].size() - 1});
                } flip(spin_[idx]); break;
        }
    }
}

template<bool IsA>
void SSE::updateLattice(std::vector<std::vector<OpLink>>& link,
                         std::vector<std::vector<OpLink>>& oth) {
    int off = IsA ? 0 : 1;
    std::uniform_real_distribution<double> u01(0.0, 1.0);
    for (int site = 0; site < halfLinkNum_; ++site) {
        auto& sSL = singleSiteList_[(site<<1)+off]; if (sSL.empty()) continue;
        for (const auto& soi : sSL) {
            std::size_t li = soi.linkIndex; double mp = 0.0;
            while (true) {
                li = (li + 1) % link[site].size();
                auto& [ot, oi, _, cfgi, cfgj, im] = link[site][li]; (void)_; (void)im;
                if (ot == OpType::BOND_OPERATOR) {
                    int bi = lat_.bonds[oi].i;
                    bool cs = (bi == ((site<<1)|off));
                    mp += cs ? std::log(bondWeight(-cfgi, cfgj)/bondWeight(cfgi, cfgj))
                             : std::log(bondWeight(cfgi, -cfgj)/bondWeight(cfgi, cfgj));
                } else break;
            }
            if (u01(rng_) < std::exp(mp)) {
                { auto& [ot, oi, _, cfgi, cfgj, im] = link[site][li]; (void)_; (void)oi; (void)cfgj; (void)im;
                  flip(cfgi); ot = (ot == OpType::OFFDIAG_OPERATOR) ? OpType::CONST_OPERATOR : OpType::OFFDIAG_OPERATOR; }
                while (true) {
                    li = (li + link[site].size() - 1) % link[site].size();
                    auto& [ot, oi, _, cfgi, cfgj, im] = link[site][li]; (void)_; (void)oi;
                    if (ot == OpType::BOND_OPERATOR) {
                        int bi = lat_.bonds[oi].i;
                        bool cs = (bi == ((site<<1)|off));
                        if (cs) { flip(cfgi); flip(IsA ? oth[site][im].cfgi : oth[(site+1)%halfLinkNum_][im].cfgi); }
                        else { flip(cfgj); flip(IsA ? oth[(site-1+halfLinkNum_)%halfLinkNum_][im].cfgj : oth[site][im].cfgj); }
                    } else { flip(cfgj); ot = (ot == OpType::OFFDIAG_OPERATOR) ? OpType::CONST_OPERATOR : OpType::OFFDIAG_OPERATOR; break; }
                }
            }
        }
    }
}
template void SSE::updateLattice<true>(std::vector<std::vector<OpLink>>&, std::vector<std::vector<OpLink>>&);
template void SSE::updateLattice<false>(std::vector<std::vector<OpLink>>&, std::vector<std::vector<OpLink>>&);

void SSE::writeBack() {
    for (int i = 0; i < N_; ++i) link_[i] = (i % 2 == 0) ? linkA_[i >> 1] : linkB_[i >> 1];
    for (int i = 0; i < N_; ++i) {
        if (link_[i].empty()) continue;
        const auto& f = link_[i][0]; int bj = lat_.bonds[f.opIndex].j;
        spin_[i] = (f.opType == OpType::BOND_OPERATOR && i == bj) ? f.cfgj : f.cfgi;
    }
    for (int i = 0; i < N_; ++i)
        for (const auto& r : singleSiteList_[i]) operatorList_[r.listIndex].first = link_[i][r.linkIndex].opType;
}

double SSE::magnetization() const {
    double s = 0.0; for (auto sp : spin_) s += to_int(sp); return s / N_;
}
double SSE::computeEnergy() const {
    return (-operatorNum_ / beta_ - energyShift_ * Nb_ + h_ * N_) / N_;
}

SSEResult SSE::run() {
    SSEResult res; int tot = params_.n_thermal + params_.n_bins * params_.sweeps_per_bin;
    double sE = 0, sE2 = 0, sm = 0, sm2 = 0, sm4 = 0, sn = 0; int nm = 0;
    for (int sw = 0; sw < tot; ++sw) {
        diagonalUpdate(); lineUpdate();
        if (sw >= params_.n_thermal && (sw - params_.n_thermal) % params_.sweeps_per_bin == 0) {
            ++nm; double E = computeEnergy(); sE += E; sE2 += E*E;
            double m = magnetization(), m2 = m*m; sm += std::abs(m); sm2 += m2; sm4 += m2*m2;
            sn += operatorNum_;
        }
    }
    double inv = 1.0 / std::max(nm, 1); res.energy = sE * inv;
    res.Cv = (sE2*inv - res.energy*res.energy) * beta_ * beta_ * N_;
    res.m = sm*inv; res.m2 = sm2*inv; res.m4 = sm4*inv;
    res.Q = (res.m2 > 1e-30) ? res.m2*res.m2/res.m4 : 0;
    res.n_op_avg = sn*inv/N_; res.n_measure=nm; res.n_thermal=params_.n_thermal;
    res.susceptibility = res.m2 * beta_ * N_; return res;
}

} // namespace cm
