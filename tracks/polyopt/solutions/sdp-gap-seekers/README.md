# SDP Gap Seekers

## Team

| | |
|---|---|
| **Team name** | sdp-gap-seekers |
| **Members** | Xiansheng Cai (蔡贤盛), Sihan Hu (胡思寒) |

## Challenge

Certified bulk spectral-gap bounds for frustrated spin-1/2 models — compute provable upper bounds on the spectral gap of the square-lattice J1-J2 and Shastry-Sutherland models via semidefinite programming, going beyond the track's pinned energy-certification target.

Addresses #88 — released by Jie Wang (王杰), polyopt track.

## Approach

Extend `wangjie212/SpectralGap` to frustrated Heisenberg models:

1. **Reproduce baseline**: 1D transverse-field Ising gap certification (validated — Δ ≤ 0.258 at d=2 for N=9 via SpectralGap + Mosek 11).
2. **Fix kagome/Heisenberg compatibility**: the existing kagome function has a Mosek 11 zero-dim PSD cone bug. Work with Jie Wang to patch.
3. **Square J1-J2**: certify gap bounds at g=0 (unfrustrated, known gap) and g=0.5 (maximally frustrated, contested).
4. **Shastry-Sutherland**: benchmark at g=0 (Δ=1 exact singlet product) and g≈0.8 (contested spin-liquid region).

Fallback within the same toolchain: if gap SDP proves intractable, pivot to #124 (kagome energy bracket) or #49 (energy certification at scale) using the same QMBCertify/NCTSSoS stack.

## Environment

- Julia 1.11.5 + NCTSSoS v0.1.0 + Clarabel v0.11.1 + JuMP
- Mosek 11.2.2 (academic license)
- SpectralGap v0.3.0 (cloned, patched for Clarabel fallback)
- QMBCertify v0.3.5

## Division of labor

TBD after Day-1 team meeting.
