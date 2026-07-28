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
