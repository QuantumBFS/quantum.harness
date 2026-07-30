using Test

include("task4_convergence_probe.jl")
using .Task4ConvergenceProbe: parse_probe_config, run_probe

@testset "Task4 convergence probe config" begin
    config = parse_probe_config(
        Dict(
            "REP" => "chain",
            "MODE" => "qn",
            "INSERTION" => "creation",
            "DT" => "0.005",
            "CUTOFF" => "0",
            "MAXDIM" => "256",
            "KDIM" => "64",
        ),
    )
    @test config == (
        representation = :chain,
        mode = :qn,
        insertion = :creation,
        dt = 0.005,
        cutoff = 0.0,
        maxdim = 256,
        kdim = 64,
    )
    @test_throws ArgumentError parse_probe_config(
        Dict("REP" => "direct", "MODE" => "qn")
    )
    @test_throws ArgumentError parse_probe_config(Dict("DT" => "0"))
    @test_throws ArgumentError parse_probe_config(
        Dict("INSERTION" => "other")
    )
end

@testset "Task4 convergence probe executes a tiny configuration" begin
    config = parse_probe_config(
        Dict(
            "REP" => "direct",
            "MODE" => "non_qn",
            "INSERTION" => "creation",
            "DT" => "0.04",
            "CUTOFF" => "1e-8",
            "MAXDIM" => "16",
            "KDIM" => "4",
        ),
    )
    payload = run_probe(config)

    @test payload.settings == config
    @test payload.fixed_problem.n_bath == 3
    @test length(payload.solver.G_up) == 5
    @test length(payload.diagnostics.branches) == 12
end
