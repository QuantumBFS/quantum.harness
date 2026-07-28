#pragma once

// ============================================================
// Serial SSE QMC for the pure ferromagnetic transverse-field Ising model
//
//     H = -J sum_<ij> sigma^z_i sigma^z_j - h sum_i sigma^x_i ,   J>0, h>0.
//
// Stage 3 redesign (graph-agnostic Swendsen-Wang cluster update).
//
// Standard non-negative Sandvik (2003) decomposition, H = -sum_a H_a + C:
//   - CONST_SITE : diagonal identity on a site,   weight h
//   - FLIP_SITE  : off-diagonal sigma^x on a site, weight h
//   - BOND       : diagonal Ising on a bond,       weight J(1 + s_i s_j)
//                  = 2J on an aligned bond, 0 on an anti-aligned bond
//   C = J*Nb + h*N   (energy offset).
//
// The FM weight landscape (aligned bond = 2J, anti-aligned = 0) means bond
// operators only ever sit on aligned pairs and bind those two world lines.
// A single-world-line ("line") update cannot flip through such a bond without
// hitting weight 0; the Stage 2 code sidestepped this with an inverted
// energy-shift convention that destroyed ferromagnetic order (m^2 ~20x too
// small).  The cluster update instead flips *both* bound world lines together,
// so every bond stays aligned and the flip is rejection-free.  This restores
// the correct m^2 / m^4 / Q_L and works on any graph (no bipartite / 1D
// assumption), replacing the Stage 2 A/B line update.
//
// Off-diagonal update (Sandvik 2003 TFIM cluster update, rejection-free):
//   - Cut each site's imaginary-time world line at every site operator
//     (CONST or FLIP); the stretches between cuts are "segments".
//   - Fuse the two segments touched by each BOND operator (union-find):
//     they must flip together to keep the bond aligned.
//   - Flip each resulting cluster with probability 1/2.  A site operator whose
//     two neighbouring segments disagree on the flip toggles CONST<->FLIP
//     (both weight h, so the move is weight-preserving).
//
// Energy estimator:  E/N = -<n>/(beta N) + h + J*Nb/N.
// ============================================================

#include "lattice.hpp"
#include <cstdint>
#include <random>
#include <vector>

namespace cm {

enum class Op : std::int8_t { NONE = -1, FLIP_SITE = 0, CONST_SITE = 1, BOND = 2 };

struct SSEParams {
    int n_thermal = 2000;
    int n_bins = 200;
    int sweeps_per_bin = 20;
    std::uint64_t seed = 42;
    // Per-sweep validation/diagnostics.  Both are O(M) per sweep, so production
    // scans turn them off; the test suite leaves them on.
    bool check_config = true;   // verify world-line closure and bond alignment
    bool census = true;         // tally operator types (<n_const> identity)
    bool stage4_estimators = false; // opt-in propagation/time-averaged observables
    bool measure_rotated_bond_diagonal = false;
    double rotation_theta = 0.0;
};

struct SSEResult {
    double energy = 0.0;   // <H>/N
    double Cv = 0.0;       // heat capacity / N
    double m = 0.0;        // <|m|>,        m = (1/N) sum sigma^z
    double m2 = 0.0;       // <m^2>
    double m4 = 0.0;       // <m^4>
    double Q = 0.0;        // <m^2>^2 / <m^4>   (Blote-Deng Binder ratio)
    double Sq0 = 0.0;      // structure factor S(0)  (= m2)
    double Sqmin = 0.0;    // structure factor S(q_min)
    double xi_over_L = 0.0;// second-moment correlation length / L
    double spacetime_m2 = 0.0; // moments of beta^{-1} integral m(tau) d tau
    double spacetime_m4 = 0.0;
    double spacetime_Q = 0.0;  // Blote-Deng space-time Binder ratio
    double n_op_avg = 0.0; // <n> / N
    double sign_avg = 1.0; // always 1 (sign-problem free)
    int n_measure = 0;
    int n_thermal = 0;
    // diagnostics (operator-type census; <n_const> must equal beta*h*N exactly)
    double n_const_avg = 0.0, n_bond_avg = 0.0, n_flip_avg = 0.0;
    bool config_checked = false;
    int consistency_failures = -1; // -1 means the O(M) check was not performed

    // H0-ensemble diagnostic: J sin(2θ) × ⟨Σ_bonds ZZ⟩_{H0} / N.
    // Kept under its historical name for source compatibility.
    double dthetah_diagonal = 0.0;

    // Raw bin-level data.  Nonlinear estimators (Q_L, xi_L/L) must be
    // recomputed inside a jackknife/bootstrap over these bins rather than
    // propagated from the scalar means above (Stage 0 protocol 4.2).
    std::vector<double> bin_E, bin_m2, bin_m4, bin_S0, bin_Sq;
    std::vector<double> bin_spacetime_m2, bin_spacetime_m4;
};

class SSE {
public:
    SSE(const Lattice& lattice, double J, double h, double beta,
        const SSEParams& params = SSEParams{});
    SSEResult run();

    // BOND weight in the standard non-negative FM decomposition:
    //   2J if the two spins are aligned, 0 if anti-aligned.  s in {+1,-1}.
    double bondWeight(int si, int sj) const { return J_ * (1 + si * sj); }

    int operatorNum() const { return n_; }
    const std::vector<std::int8_t>& spin() const { return spin_; }

private:
    const Lattice& lat_;
    double J_, h_, beta_;
    int N_, Nb_, nCand_;          // nCand_ = N_ + Nb_ diagonal candidates
    SSEParams params_;

    int M_;                        // operator-string cutoff (length)
    int n_;                        // current number of non-identity operators
    std::vector<Op> opType_;       // per-slot operator type
    std::vector<int> opIdx_;       // per-slot site (SITE ops) or bond (BOND) index
    std::vector<std::int8_t> spin_;// +/-1, stored state |alpha(0)>

    std::mt19937_64 rng_;
    std::uniform_real_distribution<double> u01_{0.0, 1.0};

    // cluster-update scratch (reused across sweeps)
    std::vector<std::vector<int>> sitePos_; // per-site sorted site-operator positions
    std::vector<int> segBase_;              // per-site global id of its first segment
    std::vector<int> parent_;               // union-find over segments
    std::vector<std::uint8_t> flip_;        // per-segment flip decision

    void ensureCutoff();
    void diagonalUpdate();
    void clusterUpdate();

    int ufFind(int x);
    void ufUnion(int a, int b);
    int localSegment(int site, int pos) const;

    // debug: propagate |alpha(0)> through the string; return true iff it closes
    // on itself and every BOND operator sits on an aligned pair.
    bool verifyConfig();
};

} // namespace cm
