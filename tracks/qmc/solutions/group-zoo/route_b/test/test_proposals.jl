using JSON

@testset "published Huang acceptance log ratios" begin
    parameters = WormParameters(0.25, 0.25, 0.25, 2.0, 3.0, 4.0)
    @test parameters.A_annihilate + parameters.A_move + 2parameters.A_kink == 1.0
    @test create_logratio(
        parameters;
        beta=8.0,
        nsites=12,
        omega_g=96.0,
        logF_ratio=log(3.0),
    ) ≈ log(0.25 * 2.0 * 3.0) atol=2eps(Float64) rtol=0
    @test annihilate_logratio(
        parameters;
        beta=8.0,
        nsites=12,
        omega_g=96.0,
        logF_ratio=-log(3.0),
    ) ≈ -log(0.25 * 2.0 * 3.0) atol=2eps(Float64) rtol=0
    @test move_logratio(logF_ratio=0.7) == 0.7
    @test insert_logratio(parameters; nk=2, logF_ratio=0.4) ≈
          log(4.0 / 3.0) + 0.4 atol=2eps(Float64) rtol=0
    @test delete_logratio(parameters; nk=3, logF_ratio=-0.4) ≈
          log(3.0 / 4.0) - 0.4 atol=2eps(Float64) rtol=0
end

function fixture_logratio(family::String, logF::Float64, parameters::WormParameters)
    family == "create" && return create_logratio(
        parameters;
        beta=8.0,
        nsites=12,
        omega_g=96.0,
        logF_ratio=logF,
    )
    family == "annihilate" && return annihilate_logratio(
        parameters;
        beta=8.0,
        nsites=12,
        omega_g=96.0,
        logF_ratio=logF,
    )
    family == "move" && return move_logratio(logF_ratio=logF)
    family == "insert" && return insert_logratio(
        parameters;
        nk=2,
        logF_ratio=logF,
    )
    family == "delete" && return delete_logratio(
        parameters;
        nk=3,
        logF_ratio=logF,
    )
    error("unsupported fixture family: $family")
end

@testset "local forward and reverse Metropolis flows balance" begin
    parameters = WormParameters(0.25, 0.25, 0.25, 2.0, 3.0, 4.0)
    fixture_path = joinpath(@__DIR__, "fixtures", "local_balance_cases.json")
    for case in JSON.parsefile(fixture_path)
        forward = fixture_logratio(
            case["forward_family"],
            case["forward_logF"],
            parameters,
        )
        reverse = fixture_logratio(
            case["reverse_family"],
            case["reverse_logF"],
            parameters,
        )
        @test forward ≈ case["expected_forward"] atol=2e-15 rtol=0
        @test reverse ≈ case["expected_reverse"] atol=2e-15 rtol=0
        @test forward + reverse ≈ 0.0 atol=2e-15 rtol=0
        @test log_metropolis_acceptance(forward) -
              (forward + log_metropolis_acceptance(reverse)) ≈ 0.0 atol=2e-15 rtol=0
    end
end

@testset "proposal audit records density and acceptance" begin
    accepted = ProposalRecord(
        CreateDefects;
        direction=1,
        directed_bond=0,
        log_forward_density=log(2.0),
        log_reverse_density=0.0,
        log_jacobian=0.0,
        log_weight_ratio=0.0,
        uniform=0.4,
    )
    rejected = ProposalRecord(
        CreateDefects;
        direction=1,
        directed_bond=0,
        log_forward_density=log(2.0),
        log_reverse_density=0.0,
        log_jacobian=0.0,
        log_weight_ratio=0.0,
        uniform=0.6,
    )
    @test accepted.log_acceptance_ratio == -log(2.0)
    @test accepted.accepted
    @test !rejected.accepted
    @test_throws ArgumentError ProposalRecord(
        MoveDefect;
        direction=0,
        directed_bond=0,
        log_forward_density=0.0,
        log_reverse_density=0.0,
        log_jacobian=0.0,
        log_weight_ratio=0.0,
        uniform=1.0,
    )
end

@testset "invalid worm parameters and proposal inputs fail closed" begin
    @test_throws ArgumentError WormParameters(0.2, 0.25, 0.25, 2.0, 3.0, 4.0)
    @test_throws ArgumentError WormParameters(0.25, 0.25, 0.25, 0.0, 3.0, 4.0)
    parameters = WormParameters(0.25, 0.25, 0.25, 2.0, 3.0, 4.0)
    @test_throws ArgumentError create_logratio(
        parameters;
        beta=8.0,
        nsites=12,
        omega_g=95.0,
        logF_ratio=0.0,
    )
    @test_throws ArgumentError insert_logratio(parameters; nk=-1, logF_ratio=0.0)
    @test_throws ArgumentError delete_logratio(parameters; nk=0, logF_ratio=0.0)
end
