function dense_hamiltonian(geometry::LatticeGeometry; J::Real = 1.0, h::Real)
    geometry.nsites <= 20 ||
        throw(ArgumentError("dense ED is restricted to at most 20 sites"))
    dimension = 1 << geometry.nsites
    H = zeros(Float64, dimension, dimension)

    for state in 0:dimension-1
        diagonal = 0.0
        for (i, j) in geometry.bonds
            zi = iszero((state >> (i - 1)) & 1) ? 1.0 : -1.0
            zj = iszero((state >> (j - 1)) & 1) ? 1.0 : -1.0
            diagonal -= float(J) * zi * zj
        end
        H[state+1, state+1] = diagonal

        for site in 1:geometry.nsites
            flipped = xor(state, 1 << (site - 1))
            H[state+1, flipped+1] = -float(h)
        end
    end

    return Symmetric(H)
end

function ed_thermal_observables(
    geometry::LatticeGeometry;
    J::Real = 1.0,
    h::Real,
    beta::Real,
)
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))
    decomposition = eigen(dense_hamiltonian(geometry; J, h))
    energies = decomposition.values
    vectors = decomposition.vectors
    weights = exp.(-float(beta) .* (energies .- minimum(energies)))
    weights ./= sum(weights)

    dimension = length(energies)
    magnetization = zeros(Float64, dimension)
    for state in 0:dimension-1
        up_minus_down = geometry.nsites - 2count_ones(UInt(state))
        magnetization[state+1] = up_minus_down / geometry.nsites
    end

    function thermal_diagonal_moment(power::Integer)
        diagonal = magnetization .^ power
        eigenstate_values = vec(sum(abs2.(vectors) .* diagonal, dims = 1))
        return dot(weights, eigenstate_values)
    end

    m2 = thermal_diagonal_moment(2)
    m4 = thermal_diagonal_moment(4)
    return (
        energy_per_site = dot(weights, energies) / geometry.nsites,
        m2 = m2,
        m4 = m4,
        binder_ratio = m2^2 / m4,
    )
end
