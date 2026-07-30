using Test

include("task5_qn_resource_benchmark.jl")
using .Task5QNResourceBenchmark:
    parse_benchmark_config,
    run_benchmark,
    validate_paired_benchmark

@testset "Task5 resource benchmark configuration" begin
    config = parse_benchmark_config(
        Dict(
            "MODE" => "qn",
            "N_BATH" => "12",
            "BETA" => "0.2",
            "DT" => "0.05",
            "CUTOFF" => "1e-12",
            "MAXDIM" => "256",
            "KDIM" => "0",
            "EXPECTED_GIT_COMMIT" => repeat("a", 40),
        ),
    )
    @test config.mode === :qn
    @test config.n_bath == 12
    @test config.beta == 0.2
    @test config.expected_git_commit == repeat("a", 40)
    @test_throws ArgumentError parse_benchmark_config(Dict("MODE" => "direct"))
    @test_throws ArgumentError parse_benchmark_config(Dict("N_BATH" => "0"))
    @test_throws ArgumentError parse_benchmark_config(
        Dict("EXPECTED_GIT_COMMIT" => "dirty")
    )
end

@testset "Task5 Slurm wrapper isolates benchmark writers" begin
    script = read(joinpath(@__DIR__, "task5_qn_resource_benchmark.sbatch"), String)
    @test occursin("#SBATCH --cpus-per-task=16", script)
    @test occursin(raw"${MODE:?Set MODE", script)
    @test occursin(raw"${OUTPUT:?Set OUTPUT", script)
    @test occursin("EXPECTED_GIT_COMMIT", script)
    @test occursin("BATH_ARTIFACT_PATH", script)
    @test occursin("MAPPING_ARTIFACT_PATH", script)
    @test occursin("mktemp", script)
    @test !occursin("CHECKPOINT", script)
end

@testset "Task5 resource benchmark executes bounded tiny work" begin
    common = Dict(
        "N_BATH" => "1",
        "BETA" => "0.02",
        "DT" => "0.02",
        "CUTOFF" => "1e-8",
        "MAXDIM" => "16",
        "KDIM" => "0",
        "EXPECTED_GIT_COMMIT" => repeat("b", 40),
    )
    non_qn = run_benchmark(parse_benchmark_config(merge(common, Dict("MODE" => "non_qn"))))
    qn = run_benchmark(parse_benchmark_config(merge(common, Dict("MODE" => "qn"))))

    @test non_qn.fixed_problem.n_bath == 1
    @test non_qn.resources.wall_seconds > 0
    @test non_qn.resources.peak_rss_bytes > 0
    @test !isempty(non_qn.diagnostics.mpo_link_dimensions)
    @test !isempty(non_qn.diagnostics.maximum_link_dimensions_by_bond)
    @test isfinite(non_qn.diagnostics.truncation_max_error)
    @test isfinite(non_qn.diagnostics.krylov_max_error_estimate)
    @test non_qn.diagnostics.krylov_all_converged
    @test haskey(non_qn.observables, :G_up)

    paired = validate_paired_benchmark(non_qn, qn)
    @test paired.scientific_validation_passed
    @test paired.observable_max_absolute_delta <= 1e-6
    @test paired.production_beta32_eligible === false
    @test paired.n_bath_48_eligible === false
end
