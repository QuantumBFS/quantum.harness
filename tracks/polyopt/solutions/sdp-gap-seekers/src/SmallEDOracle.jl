module SmallEDOracle

using LinearAlgebra
using ..SquareJ1J2Prototype: square_patch
using ..GenericGapModel:
    GapProblem,
    NoStateSymmetry,
    instantiate_terms,
    square_j1j2_model,
    square_patch_geometry

export dense_from_pauli_terms,
       dense_from_spin_bonds,
       compare_hamiltonian_builders,
       run_small_ed_oracle

"""
Build a dense finite-patch matrix directly from canonical Pauli terms.

This finite matrix is only an implementation oracle. It is not the
infinite-volume bulk-gap relaxation.
"""
function dense_from_pauli_terms(problem::GapProblem)
    terms = instantiate_terms(problem.model, problem.patch)
    nsites = length(problem.patch.sites)
    dimension = 1 << nsites
    hamiltonian = zeros(ComplexF64, dimension, dimension)

    for state in 0:(dimension - 1), term in terms
        target = state
        phase = ComplexF64(term.coefficient)
        for (site, axis) in term.word.ops
            bit = (state >> (site - 1)) & 1
            if axis == 1 # X
                target ⊻= 1 << (site - 1)
            elseif axis == 2 # Y
                phase *= bit == 0 ? im : -im
                target ⊻= 1 << (site - 1)
            else # Z
                phase *= bit == 0 ? 1 : -1
            end
        end
        hamiltonian[target + 1, state + 1] += phase
    end
    return hamiltonian
end

"""
Independent spin-basis construction using

    S_i·S_j = S_i^z S_j^z + 1/2(S_i^+S_j^- + S_i^-S_j^+).
"""
function dense_from_spin_bonds(L::Int; g::T=1//2) where {T<:Real}
    patch = square_patch(L; g)
    nsites = length(patch.sites)
    dimension = 1 << nsites
    hamiltonian = zeros(ComplexF64, dimension, dimension)

    for state in 0:(dimension - 1), bond in patch.bonds
        bit_i = (state >> (bond.i - 1)) & 1
        bit_j = (state >> (bond.j - 1)) & 1
        coupling = Float64(bond.coupling)
        hamiltonian[state + 1, state + 1] +=
            coupling * (bit_i == bit_j ? 1//4 : -1//4)
        if bit_i != bit_j
            target = state ⊻ (1 << (bond.i - 1)) ⊻ (1 << (bond.j - 1))
            hamiltonian[target + 1, state + 1] += coupling / 2
        end
    end
    return hamiltonian
end

function comparison_problem(L::Int, g::T) where {T<:Real}
    patch = square_patch_geometry(L)
    model = square_j1j2_model(g)
    return GapProblem(
        patch,
        model,
        zero(T),
        2;
        basis_mode=:one_symbol,
        symmetry=NoStateSymmetry(),
    )
end

function compare_hamiltonian_builders(L::Int=1; g::T=1//2) where {T<:Real}
    problem = comparison_problem(L, g)
    pauli_hamiltonian = dense_from_pauli_terms(problem)
    bond_hamiltonian = dense_from_spin_bonds(L; g)
    return (
        max_builder_difference=maximum(abs, pauli_hamiltonian - bond_hamiltonian),
        hermiticity_error=maximum(abs, pauli_hamiltonian - pauli_hamiltonian'),
        trace=tr(pauli_hamiltonian),
        hamiltonian=pauli_hamiltonian,
    )
end

function total_sz_diagonal(nsites::Int)
    dimension = 1 << nsites
    diagonal = zeros(Float64, dimension)
    for state in 0:(dimension - 1)
        diagonal[state + 1] = sum(
            ((state >> (site - 1)) & 1) == 0 ? 0.5 : -0.5
            for site in 1:nsites
        )
    end
    return Diagonal(diagonal)
end

function run_small_ed_oracle(L::Int=1; g::T=1//2, degeneracy_tol=1e-10) where {T<:Real}
    comparison = compare_hamiltonian_builders(L; g)
    hamiltonian = comparison.hamiltonian
    nsites = Int(round(log2(size(hamiltonian, 1))))
    sz = total_sz_diagonal(nsites)
    sz_commutator_error = maximum(abs, hamiltonian * sz - sz * hamiltonian)

    eigensystem = eigen(Hermitian(hamiltonian))
    eigenvalues = eigensystem.values
    ground_energy = first(eigenvalues)
    ground_vector = eigensystem.vectors[:, 1]
    ground_residual =
        norm(hamiltonian * ground_vector - ground_energy * ground_vector)
    ground_multiplicity = count(
        energy -> abs(energy - ground_energy) <= degeneracy_tol,
        eigenvalues,
    )
    first_distinct_index = findfirst(
        energy -> energy > ground_energy + degeneracy_tol,
        eigenvalues,
    )
    first_distinct_energy =
        first_distinct_index === nothing ? NaN : eigenvalues[first_distinct_index]

    return (
        L=L,
        g=g,
        sites=nsites,
        dimension=size(hamiltonian, 1),
        max_builder_difference=comparison.max_builder_difference,
        hermiticity_error=comparison.hermiticity_error,
        trace=comparison.trace,
        sz_commutator_error=sz_commutator_error,
        ground_energy=ground_energy,
        ground_residual=ground_residual,
        ground_multiplicity=ground_multiplicity,
        first_distinct_energy=first_distinct_energy,
        first_distinct_gap=first_distinct_energy - ground_energy,
    )
end

end
