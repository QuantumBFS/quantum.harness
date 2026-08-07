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

@testset "canonical QN fixtures are checked in" begin
    expected_bath_sha256 = (
        "7d894928d95481cff0c5a8f47592681db1e9bae8731f1a16bb1b83fc310a8b4f",
        "acada4ceb615f6f9ab020376e0ce1e2c529011c0606b6e5178251ce9e6753395",
        "01f498d95a6e22db27ff8992001edd896d48f3bbc4563a1477fa5371e2c46931",
        "fd790a29ad2c3fe5e840c7ee260dbcf96b50ec434b9ef01065f1bfa1ba231cdf",
        "818dc73dffeb851961e8cb6944df92a45423d9ee8893bd8b9b3d08e4135323ba",
        "57f6b6295f9cb0cba9fc5463a004cf1ed37a846d7229bd21343fff74292cbea4",
    )
    expected_mapping_sha256 = (
        "cb9fc9fbb83e7d6538e4f08f2dee0d218787946006f1aa4437bad23d55e8ba4a",
        "30ba94076c1a5828da8749bc79dc495b59db2ae1e49d99f2db928e8fd2a22c09",
        "8041184dd33c467d361218a157fafdb027290adf941312262d550f44a23318fb",
        "79139728b461f34bce98d6d3fb664cbebabd2f22090e06ad7ab8f3f38cc3f81c",
        "5e21d93e712fa611fe7bda482f19b6ddce0aea295770804ed27e3cfcaf74eb18",
        "9c27f3b20aa5891b3aa393e45ac012ca39eebba974f3e417268d7ef0c48a6ed3",
    )
    for n_bath in 1:6
        artifacts = validated_chain_fixture_artifacts(n_bath)
        @test artifacts.bath_artifact["sha256"] ==
              expected_bath_sha256[n_bath]
        @test artifacts.mapping_artifact["sha256"] ==
              expected_mapping_sha256[n_bath]
        @test artifacts.bath_artifact["payload"]["provenance"][
            "python_version"
        ] == "3.12.13"
        @test artifacts.mapping_artifact["payload"]["provenance"][
            "numpy_version"
        ] == "2.5.1"
        @test validated_chain_fixture(; n_bath).mapping_sha256 ==
              expected_mapping_sha256[n_bath]
    end
    @test_throws MethodError validated_chain_fixture(
        ; n_bath = 1, gamma = 0.2
    )
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

    artifacts = validated_chain_fixture_artifacts(1)
    corrupted_bath = deepcopy(artifacts.bath_artifact)
    corrupted_bath["payload"]["epsilon"][1] += 0.125
    corrupted_bath["sha256"] = bytes2hex(
        sha256(
            codeunits(canonical_artifact_json(corrupted_bath["payload"]))
        ),
    )
    corrupted_bath_json = canonical_artifact_json(corrupted_bath) * "\n"
    @test corrupted_bath["sha256"] != artifacts.bath_artifact["sha256"]
    @test_throws ArgumentError validate_bath_artifact(
        corrupted_bath,
        corrupted_bath_json,
        authoritative_model_definition(),
    )

    corrupted_mapping = deepcopy(artifacts.mapping_artifact)
    corrupted_mapping["payload"]["chain_onsite"][1] += 0.125
    corrupted_mapping_payload_json =
        canonical_artifact_json(corrupted_mapping["payload"])
    corrupted_mapping["sha256"] =
        bytes2hex(sha256(codeunits(corrupted_mapping_payload_json)))
    corrupted_mapping_json = canonical_chain_mapping_json(corrupted_mapping)
    @test corrupted_mapping["sha256"] !=
          artifacts.mapping_artifact["sha256"]
    @test_throws ArgumentError validate_chain_mapping_artifact(
        corrupted_mapping,
        corrupted_mapping_json,
        artifacts.bath_artifact,
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
        validated = validated_chain_fixture(; n_bath)
        parameters = FiniteBathParameters(
            validated;
            U = interaction,
            epsilon_d = -0.31,
            mu = 0.07,
        )
        purification = qn_dual_purification(parameters, validated)
        for sector in ((1, 0), (0, 1), (1, 1))
            compare_qn_and_non_qn_sector(
                parameters, purification, sector...
            )
        end
        if n_bath <= 3
            n_orbitals = n_bath + 1
            for n_up in 0:n_orbitals, n_down in 0:n_orbitals
                (n_up, n_down) in ((1, 0), (0, 1), (1, 1)) &&
                    continue
                compare_qn_and_non_qn_sector(
                    parameters, purification, n_up, n_down
                )
            end
        end
    end
end

@testset "QN MPO preserves Jordan-Wigner signs across ancillas" begin
    validated = validated_chain_fixture(; n_bath = 2)
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
