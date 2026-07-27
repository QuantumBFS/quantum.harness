module LocalSpinIdentities

using LinearAlgebra

export spin_dot,
       total_spin_squared,
       bond_projectors,
       local_identity_checks

const Q = Rational{Int}
const CQ = Complex{Q}

const I2 = CQ[1 0; 0 1]
const SX = CQ[0 1//2; 1//2 0]
const SY = CQ[0 -im//2; im//2 0]
const SZ = CQ[1//2 0; 0 -1//2]
const SPIN_COMPONENTS = (SX, SY, SZ)

identity_operator(nsites::Int) = Matrix{CQ}(I, 2^nsites, 2^nsites)

function operator_on_site(operator::Matrix{CQ}, nsites::Int, site::Int)
    1 <= site <= nsites || throw(ArgumentError("site outside local cluster"))
    result = CQ[1]
    for position in 1:nsites
        result = kron(result, position == site ? operator : I2)
    end
    return result
end

function spin_dot(nsites::Int, i::Int, j::Int)
    i == j && throw(ArgumentError("spin_dot requires two different sites"))
    result = zeros(CQ, 2^nsites, 2^nsites)
    for component in SPIN_COMPONENTS
        result += operator_on_site(component, nsites, i) *
                  operator_on_site(component, nsites, j)
    end
    return result
end

function total_spin_squared(nsites::Int)
    result = zeros(CQ, 2^nsites, 2^nsites)
    for component in SPIN_COMPONENTS
        total_component = zeros(CQ, 2^nsites, 2^nsites)
        for site in 1:nsites
            total_component += operator_on_site(component, nsites, site)
        end
        result += total_component * total_component
    end
    return result
end

function bond_projectors(nsites::Int, i::Int, j::Int)
    identity = identity_operator(nsites)
    bond = spin_dot(nsites, i, j)
    singlet = (1//4) * identity - bond
    triplet = (3//4) * identity + bond
    return singlet, triplet
end

is_zero(operator) = all(iszero, operator)

"""
Machine-check local identities over exact complex-rational matrices.

No floating-point eigensolver is used. The returned dictionary contains only
Boolean exact-equality checks and exact projector traces.
"""
function local_identity_checks(; g::Q=2//5)
    checks = Dict{String,Any}()

    # Two-site bond algebra.
    identity2 = identity_operator(2)
    bond = spin_dot(2, 1, 2)
    singlet, triplet = bond_projectors(2, 1, 2)
    checks["bond_minimal_polynomial"] =
        is_zero(bond * bond + (1//2) * bond - (3//16) * identity2)
    checks["bond_projector_sum"] = singlet + triplet == identity2
    checks["bond_projector_idempotence"] =
        singlet * singlet == singlet && triplet * triplet == triplet
    checks["bond_projector_orthogonality"] =
        is_zero(singlet * triplet) && is_zero(triplet * singlet)
    checks["bond_projector_traces"] = (tr(singlet), tr(triplet))

    # Three-site total-spin sectors, relevant to J1-J1-J2 triangles.
    identity3 = identity_operator(3)
    total3 = total_spin_squared(3)
    projector_half = ((15//4) * identity3 - total3) / 3
    projector_three_half = (total3 - (3//4) * identity3) / 3
    checks["triangle_casimir_polynomial"] =
        is_zero((total3 - (3//4) * identity3) *
                (total3 - (15//4) * identity3))
    checks["triangle_projector_sum"] =
        projector_half + projector_three_half == identity3
    checks["triangle_projector_idempotence"] =
        projector_half^2 == projector_half &&
        projector_three_half^2 == projector_three_half
    checks["triangle_projector_orthogonality"] =
        is_zero(projector_half * projector_three_half)
    checks["triangle_projector_traces"] =
        (tr(projector_half), tr(projector_three_half))

    # Four-site square plaquette.
    identity4 = identity_operator(4)
    total4 = total_spin_squared(4)
    projector0 = (total4 - 2identity4) * (total4 - 6identity4) / 12
    projector1 = total4 * (6identity4 - total4) / 8
    projector2 = total4 * (total4 - 2identity4) / 24

    edge_sum =
        spin_dot(4, 1, 2) + spin_dot(4, 2, 3) +
        spin_dot(4, 3, 4) + spin_dot(4, 4, 1)
    diagonal_sum = spin_dot(4, 1, 3) + spin_dot(4, 2, 4)

    checks["plaquette_total_spin_identity"] =
        total4 == 3identity4 + 2(edge_sum + diagonal_sum)
    checks["plaquette_casimir_polynomial"] =
        is_zero(total4 * (total4 - 2identity4) * (total4 - 6identity4))
    checks["plaquette_projector_sum"] =
        projector0 + projector1 + projector2 == identity4
    checks["plaquette_projector_idempotence"] =
        projector0^2 == projector0 &&
        projector1^2 == projector1 &&
        projector2^2 == projector2
    checks["plaquette_projector_orthogonality"] =
        is_zero(projector0 * projector1) &&
        is_zero(projector0 * projector2) &&
        is_zero(projector1 * projector2)
    checks["plaquette_projector_traces"] =
        (tr(projector0), tr(projector1), tr(projector2))
    checks["edge_diagonal_commutator"] =
        is_zero(edge_sum * diagonal_sum - diagonal_sum * edge_sum)

    # Resolve the plaquette simultaneously by the two diagonal-pair spins and
    # total spin. This is aligned with the J2 geometry.
    singlet13, triplet13 = bond_projectors(4, 1, 3)
    singlet24, triplet24 = bond_projectors(4, 2, 4)
    joint_projectors = [
        singlet13 * singlet24,
        singlet13 * triplet24,
        triplet13 * singlet24,
        triplet13 * triplet24 * projector0,
        triplet13 * triplet24 * projector1,
        triplet13 * triplet24 * projector2,
    ]
    joint_energies = Q[
        -3g/2,
        -g/2,
        -g/2,
        -2 + g/2,
        -1 + g/2,
        1 + g/2,
    ]
    plaquette_hamiltonian = edge_sum + g * diagonal_sum

    checks["joint_projector_sum"] = sum(joint_projectors) == identity4
    checks["joint_projector_idempotence"] =
        all(projector -> projector^2 == projector, joint_projectors)
    checks["joint_projector_orthogonality"] =
        all(
            (i == j || is_zero(joint_projectors[i] * joint_projectors[j]))
            for i in eachindex(joint_projectors)
            for j in eachindex(joint_projectors)
        )
    checks["joint_projector_traces"] = Tuple(tr.(joint_projectors))
    checks["plaquette_spectral_resolution"] =
        all(
            plaquette_hamiltonian * joint_projectors[i] ==
            joint_energies[i] * joint_projectors[i]
            for i in eachindex(joint_projectors)
        )

    return checks
end

end
