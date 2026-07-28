#pragma once

#include "lattice.hpp"
#include <cstddef>
#include <random>
#include <vector>

namespace cm {

enum class OpType : int { NO_OPERATOR = -1, OFFDIAG_OPERATOR, BOND_OPERATOR, CONST_OPERATOR };

enum class SpinDir : int { Up = 1, Down = -1 };
inline SpinDir operator-(SpinDir s) { return static_cast<SpinDir>(-static_cast<int>(s)); }
inline void flip(SpinDir& s) { s = -s; }
inline int to_int(SpinDir s) { return static_cast<int>(s); }

using OpIndex = int;
using OpListType = std::pair<OpType, OpIndex>;

struct SSEParams { int n_thermal = 1000; int n_bins = 100; int sweeps_per_bin = 50; int seed = 42; };

struct SSEResult {
    double energy = 0.0, energy_sq = 0.0, Cv = 0.0, m = 0.0, m2 = 0.0, m4 = 0.0, Q = 0.0;
    double n_op_avg = 0.0, sign_avg = 1.0, susceptibility = 0.0;
    int n_measure = 0, n_thermal = 0;
};

// ============================================================
// SSE Markov chain — pure TFIM, Sandvik standard decomposition
//
// H = -J Σ σ^z_i σ^z_j - h Σ σ^x_i
//
// Decomposition:
//   BOND_OPERATOR:  weight = J(1 + σ_i σ_j) ∈ {0, 2J}
//   CONST_OPERATOR: weight = h  (h * identity)
//   OFFDIAG_OPERATOR: weight = h  (h * σ^x)
//
// possibleOperatorNumber = Nb + N  (Nb bond + N const)
// Energy: E = J·Nb + h·N - ⟨n⟩/β
// ============================================================
class SSE {
public:
    SSE(const Lattice& lattice, double J, double h, double beta,
        const SSEParams& params = SSEParams{});
    SSEResult run();

    int operatorNum() const { return operatorNum_; }
    const std::vector<SpinDir>& spin() const { return spin_; }

    double bondWeight(SpinDir a, SpinDir b) const {
        return J_ * (1.0 + static_cast<double>(to_int(a) * to_int(b)));
    }

    struct OpLink {
        OpType opType = OpType::NO_OPERATOR;
        OpIndex opIndex = 0;
        int listIndex = 0;
        SpinDir cfgi = SpinDir::Up, cfgj = SpinDir::Down;
        std::size_t imageIndex = 0;
    };
    struct SiteRef { std::size_t listIndex; std::size_t linkIndex; };

private:
    const Lattice& lat_;
    double J_, h_, beta_;
    int N_, Nb_, possibleOperatorNumber_;  // Nb + N
    SSEParams params_;

    int cutoff_, operatorNum_;
    std::vector<OpListType> operatorList_;
    std::vector<SpinDir> spin_;
    std::mt19937 rng_;

    void adjustCutoff();
    void diagonalUpdate();
    void lineUpdate();
    void constructLink();
    template<bool IsA> void updateLattice(std::vector<std::vector<OpLink>>& link,
                                           std::vector<std::vector<OpLink>>& linkOther);
    void writeBack();
    double magnetization() const;
    double computeEnergy() const;

    int halfLinkNum_;
    std::vector<std::vector<OpLink>> linkA_, linkB_, link_;
    std::vector<std::vector<SiteRef>> singleSiteList_;
};

} // namespace cm
