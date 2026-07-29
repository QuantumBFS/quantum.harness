using Test
using LinearAlgebra
using ITensors
using ITensorMPS

include(joinpath(@__DIR__, "validated_chain_fixture.jl"))
using .FiniteBathPurification:
    FiniteBathParameters,
    identity_purification,
    interleaved_sites,
    non_qn_purification,
    physical_hamiltonian_mpo,
    probe_qn_purification_capability,
    qn_dual_purification

function qn_occupation_basis(sites, n_up::Int, n_down::Int)
    n_orbitals = length(sites) ÷ 2
    up_basis = [
        state for state in 0:((1 << n_orbitals) - 1) if
        count_ones(state) == n_up
    ]
    down_basis = [
        state for state in 0:((1 << n_orbitals) - 1) if
        count_ones(state) == n_down
    ]
    return [
        begin
            labels = fill("Emp", length(sites))
            for orbital in 1:n_orbitals
                mask = 1 << (orbital - 1)
                up = !iszero(up_state & mask)
                down = !iszero(down_state & mask)
                labels[2 * orbital - 1] =
                    up ? (down ? "UpDn" : "Up") : (down ? "Dn" : "Emp")
            end
            MPS(sites, labels)
        end for up_state in up_basis, down_state in down_basis
    ][:]
end

function qn_mpo_sector_matrix(parameters, purification, n_up, n_down)
    sites = interleaved_sites(parameters; purification)
    hamiltonian =
        physical_hamiltonian_mpo(sites, parameters; purification)
    basis = qn_occupation_basis(sites, n_up, n_down)
    return [
        inner(target', hamiltonian, source) for
        target in basis, source in basis
    ]
end

function compare_qn_and_non_qn_sector(
    parameters, purification, n_up, n_down
)
    qn_matrix =
        qn_mpo_sector_matrix(parameters, purification, n_up, n_down)
    non_qn_matrix = qn_mpo_sector_matrix(
        parameters, non_qn_purification(), n_up, n_down
    )
    @test ishermitian(qn_matrix)
    @test qn_matrix ≈ non_qn_matrix atol = 1.0e-13
    @test eigvals(Hermitian(qn_matrix)) ≈
          eigvals(Hermitian(non_qn_matrix)) atol = 1.0e-12
end

@testset "probe requires validated runner capability and fails closed" begin
    validated, result = mktempdir() do empty_path
        withenv("PATH" => empty_path) do
            offline_validated = validated_chain_fixture(; n_bath = 1)
            offline_result =
                probe_qn_purification_capability(offline_validated)
            return offline_validated, offline_result
        end
    end
    @test !hasmethod(probe_qn_purification_capability, Tuple{})
    @test result.supported
    @test result.failure === nothing

    bath_artifact = _fixture_bath_artifact(1, 0.1, 1.0)
    mapping_artifact, mapping_json =
        _fixture_chain_mapping_artifact(bath_artifact)
    @test bath_artifact["sha256"] ==
          bytes2hex(
              sha256(
                  codeunits(
                      canonical_artifact_json(bath_artifact["payload"])
                  ),
              ),
          )
    @test mapping_artifact["sha256"] ==
          bytes2hex(
              sha256(
                  codeunits(
                      canonical_artifact_json(mapping_artifact["payload"])
                  ),
              ),
          )
    @test mapping_artifact["payload"]["source_bath_sha256"] ==
          bath_artifact["sha256"]
    corrupted = deepcopy(mapping_artifact)
    corrupted["payload"]["Q"][1][1] = 0.0
    @test_throws ArgumentError validate_chain_mapping_artifact(
        corrupted, mapping_json, bath_artifact
    )

    mandatory = (
        :site_labels_valid,
        :identity_sector_valid,
        :mpo_zero_flux_valid,
        :operator_sectors_valid,
        :tdvp_step_valid,
        :hdf5_roundtrip_valid,
    )
    all_true = NamedTuple{mandatory}(ntuple(_ -> true, length(mandatory)))
    for field in mandatory
        invalid = merge(all_true, NamedTuple{(field,)}((1,)))
        failed = FiniteBathPurification._probe_qn_purification_capability(
            validated, _ -> invalid
        )
        @test !failed.supported
        @test failed.failure isa String
    end
    errored = FiniteBathPurification._probe_qn_purification_capability(
        validated, _ -> error("injected probe error")
    )
    @test !errored.supported
    @test occursin("injected probe error", errored.failure)
end

const QN_MPO_TEST_MAX_BATH =
    parse(Int, get(ENV, "QN_MPO_TEST_MAX_BATH", "2"))
QN_MPO_TEST_MAX_BATH in 1:6 ||
    error("QN_MPO_TEST_MAX_BATH must be between 1 and 6")

@testset "QN MPO dense matrices and spectra" begin
    for n_bath in 1:QN_MPO_TEST_MAX_BATH, interaction in (0.0, 0.8)
        validated = validated_chain_fixture(
            ; n_bath, gamma = 0.13, bandwidth = 1.2
        )
        parameters = FiniteBathParameters(
            validated;
            U = interaction,
            epsilon_d = -0.31,
            mu = 0.07,
        )
        purification = qn_dual_purification(parameters, validated)
        compare_qn_and_non_qn_sector(parameters, purification, 1, 1)
        if n_bath <= 3
            n_orbitals = n_bath + 1
            for n_up in 0:n_orbitals, n_down in 0:n_orbitals
                (n_up, n_down) == (1, 1) && continue
                compare_qn_and_non_qn_sector(
                    parameters, purification, n_up, n_down
                )
            end
        end
    end
end

@testset "QN MPO preserves Jordan-Wigner signs across ancillas" begin
    validated = validated_chain_fixture(
        ; n_bath = 2, gamma = 0.13, bandwidth = 1.2
    )
    parameters = FiniteBathParameters(validated)
    purification = qn_dual_purification(parameters, validated)
    sites = interleaved_sites(parameters; purification)
    hamiltonian =
        physical_hamiltonian_mpo(sites, parameters; purification)
    links = (
        (1, 3, parameters.lambda),
        (3, 5, parameters.chain_hopping[1]),
    )
    for (left, right, coefficient) in links
        for (spin, state) in (("up", "Up"), ("dn", "Dn"))
            for (parity_state, expected) in
                (("Emp", coefficient), ("Up", -coefficient))
                elements = ComplexF64[]
                for (source_site, target_site) in
                    ((right, left), (left, right))
                    source = fill("Emp", length(sites))
                    target = fill("Emp", length(sites))
                    source[source_site] = state
                    target[target_site] = state
                    source[left + 1] = parity_state
                    target[left + 1] = parity_state
                    element = inner(
                        MPS(sites, target)',
                        hamiltonian,
                        MPS(sites, source),
                    )
                    push!(elements, element)
                    @test element ≈ expected atol = 1.0e-14
                end
                @test elements[1] ≈ conj(elements[2]) atol = 1.0e-14
            end
        end
    end
end
