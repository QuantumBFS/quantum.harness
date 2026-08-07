module PurificationSmoke

using ITensors
using ITensorMPS

export identity_pair_mps, impurity_observables, thermal_impurity_purification

const ELECTRON_STATES = ("Emp", "Up", "Dn", "UpDn")

"""
Construct the normalized local identity purification
`sum_s |s>_physical |s>_ancilla / 2`.
"""
function identity_pair_mps()
    sites = siteinds("Electron", 2; conserve_qns = false)
    pair = ITensor(sites[1], sites[2])
    for label in ELECTRON_STATES
        pair += state(label, sites[1]) * state(label, sites[2])
    end
    pair /= 2

    left, singular_values, right = svd(pair, sites[1])
    psi = MPS([left, singular_values * right])
    normalize!(psi)
    return sites, psi
end

"""
Apply `exp(-beta * H_impurity / 2)` to the physical half of an identity pair.

The impurity is particle-hole symmetric:
`epsilon_d = -interaction / 2`.
"""
function thermal_impurity_purification(beta::Real, interaction::Real)
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))
    interaction >= 0 || throw(ArgumentError("interaction must be nonnegative"))

    sites, psi = identity_pair_mps()
    epsilon_d = -interaction / 2
    h_impurity =
        epsilon_d * op("Ntot", sites[1]) +
        interaction * op("Nupdn", sites[1])
    imaginary_time_gate = exp((-beta / 2) * h_impurity)
    psi = apply(imaginary_time_gate, psi; cutoff = 0.0)
    normalize!(psi)
    return sites, psi
end

"""Measure physical impurity occupancy and double occupancy."""
function impurity_observables(psi::MPS)
    occupancy = real(expect(psi, "Ntot")[1])
    double_occupancy = real(expect(psi, "Nupdn")[1])
    return (; occupancy, double_occupancy)
end

end
