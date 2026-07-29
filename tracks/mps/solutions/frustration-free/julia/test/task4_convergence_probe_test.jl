using Test

include("task4_convergence_probe.jl")
using .Task4ConvergenceProbe: parse_probe_config

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
