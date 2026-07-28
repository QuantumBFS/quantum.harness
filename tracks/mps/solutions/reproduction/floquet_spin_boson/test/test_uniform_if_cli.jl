using Test
using UniformTEMPO

include(joinpath(@__DIR__, "..", "scripts", "cache_uniform_if.jl"))

@testset "Uniform IF cache CLI honors config and --rebuild-cache" begin
    mktempdir() do directory
        config_path = joinpath(directory, "quick.toml")
        write(config_path, """
            mode = "quick"
            dt_target = 0.1
            frequencies = [2.5]
            steps = 1
            compression_tolerance = 1.0e-7
            run_exact = false
            cache_dir = "ignored-by-test"
            rebuild_cache = false
            """)
        builds = Ref(0)
        builder = function (_model, dt, _tolerance, _settings)
            builds[] += 1
            return UniformPTMPO(2, dt), Dict("builder_calls" => builds[])
        end
        first = cache_cli_main([config_path, directory]; pt_builder=builder)
        reused = cache_cli_main([config_path, directory]; pt_builder=builder)
        rebuilt = cache_cli_main(["--rebuild-cache", config_path, directory]; pt_builder=builder)
        @test builds[] == 2
        @test first.q == reused.q == rebuilt.q
        @test rebuilt.convergence_metadata["builder_calls"] == 2
    end
end

@testset "Default UniformTEMPO builder records auditable completion metadata" begin
    settings = UniformIFBuildSettings(n_c=17, cap_rank=23, max_rank=29)
    fake_unitempo = function (_operator, dt, _bcf, _tolerance; kwargs...)
        @test kwargs[:n_c] == 17
        return UniformPTMPO(2, dt)
    end
    pt, convergence = default_uniform_pt_builder(SpinBosonModel(), 0.1, 1.0e-7, settings;
                                                   unitempo=fake_unitempo)
    @test pt isa UniformPTMPO
    @test convergence["builder_identity"] == "UniformTEMPO.uniTEMPO"
    @test convergence["status"] == "completed"
    @test convergence["achieved_chi"] == 1
    @test convergence["build_settings"]["n_c"] == 17
    @test !isempty(convergence)
    @test !haskey(convergence, "residual")
    @test !haskey(convergence, "iterations")
end
