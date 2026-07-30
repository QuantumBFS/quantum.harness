const I2 = Matrix{Float64}(I, 2, 2)
const X = [0.0 1.0; 1.0 0.0]
const Z = [1.0 0.0; 0.0 -1.0]
const PZ_UP = [1.0 0.0; 0.0 0.0]
const PZ_DOWN = [0.0 0.0; 0.0 1.0]
const PX_PLUS = 0.5 .* (I2 + X)
const PX_MINUS = 0.5 .* (I2 - X)

function collapse_projectors(basis::Symbol)
    basis === :Z && return (PZ_UP, PZ_DOWN)
    basis === :X && return (PX_PLUS, PX_MINUS)
    throw(ArgumentError("collapse basis must be :Z or :X"))
end

function site_degree(Lx::Integer, Ly::Integer, x::Integer, y::Integer)
    return (x > 1) + (x < Lx) + (y > 1) + (y < Ly)
end

function bond_sites(x::Integer, y::Integer, direction::Symbol)
    direction === :right && return (x, y), (x + 1, y)
    direction === :down && return (x, y), (x, y + 1)
    throw(ArgumentError("direction must be :right or :down"))
end

function bond_hamiltonian(
    Lx::Integer,
    Ly::Integer,
    x::Integer,
    y::Integer,
    direction::Symbol,
    para::AbstractDict,
)
    (site1, site2) = bond_sites(x, y, direction)
    x1, y1 = site1
    x2, y2 = site2
    1 <= x1 <= Lx && 1 <= y1 <= Ly || throw(BoundsError())
    1 <= x2 <= Lx && 1 <= y2 <= Ly || throw(BoundsError())
    degree1 = site_degree(Lx, Ly, x1, y1)
    degree2 = site_degree(Lx, Ly, x2, y2)
    return -para[:J] * kron(Z, Z) -
           (para[:h] / degree1) * kron(X, I2) -
           (para[:h] / degree2) * kron(I2, X)
end

function trotter_gate(
    Lx::Integer,
    Ly::Integer,
    x::Integer,
    y::Integer,
    direction::Symbol,
    delta::Real,
    para::AbstractDict,
)
    matrix = exp(-delta * bond_hamiltonian(Lx, Ly, x, y, direction, para))
    return permutedims(reshape(matrix, 2, 2, 2, 2), (2, 1, 4, 3))
end

function exact_thermal_observables(
    Lx::Integer,
    Ly::Integer,
    beta::Real;
    J::Real=1.0,
    h::Real=2.9,
)
    site_count = Lx * Ly
    1 <= site_count <= 10 || throw(ArgumentError("exact diagonalization supports 1 to 10 sites"))
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))
    hilbert_dimension = 1 << site_count
    hamiltonian = zeros(Float64, hilbert_dimension, hilbert_dimension)
    site_index(x, y) = x + (y - 1) * Lx
    spin_z(basis, site) = ((basis >> (site - 1)) & 1) == 0 ? 1.0 : -1.0

    for basis in 0:(hilbert_dimension - 1)
        diagonal_energy = 0.0
        for y in 1:Ly, x in 1:(Lx - 1)
            diagonal_energy -= J * spin_z(basis, site_index(x, y)) *
                spin_z(basis, site_index(x + 1, y))
        end
        for x in 1:Lx, y in 1:(Ly - 1)
            diagonal_energy -= J * spin_z(basis, site_index(x, y)) *
                spin_z(basis, site_index(x, y + 1))
        end
        hamiltonian[basis + 1, basis + 1] = diagonal_energy
        for site in 1:site_count
            flipped = basis ⊻ (1 << (site - 1))
            hamiltonian[flipped + 1, basis + 1] -= h
        end
    end

    eigensystem = eigen(Hermitian(hamiltonian))
    shifted_weights = exp.(-beta .* (eigensystem.values .- minimum(eigensystem.values)))
    probabilities = shifted_weights / sum(shifted_weights)
    density_matrix = eigensystem.vectors * Diagonal(probabilities) * eigensystem.vectors'
    energy = dot(probabilities, eigensystem.values)

    x_sum = 0.0
    z_sum = 0.0
    zz_sum = 0.0
    bond_count = (Lx - 1) * Ly + Lx * (Ly - 1)
    for basis in 0:(hilbert_dimension - 1)
        probability = real(density_matrix[basis + 1, basis + 1])
        for site in 1:site_count
            z_sum += probability * spin_z(basis, site)
            flipped = basis ⊻ (1 << (site - 1))
            x_sum += real(density_matrix[basis + 1, flipped + 1])
        end
        for y in 1:Ly, x in 1:(Lx - 1)
            zz_sum += probability * spin_z(basis, site_index(x, y)) *
                spin_z(basis, site_index(x + 1, y))
        end
        for x in 1:Lx, y in 1:(Ly - 1)
            zz_sum += probability * spin_z(basis, site_index(x, y)) *
                spin_z(basis, site_index(x, y + 1))
        end
    end
    return (;
        energy,
        energy_per_site=energy / site_count,
        x_magnetization=x_sum / site_count,
        z_magnetization=z_sum / site_count,
        zz_nearest_neighbor=bond_count == 0 ? NaN : zz_sum / bond_count,
    )
end
