using TOML

@testset "production mode requires immutable convergence evidence" begin
    required = Dict(
        "eigensolver" => 1e-10,
        "tail_norm" => 1e-4,
        "energy_balance" => 1e-3,
    )

    @test isnothing(require_convergence_evidence(:quick, "missing.toml", required))
    @test_throws ArgumentError require_convergence_evidence(:production, "missing.toml", required)

    mktempdir() do dir
        path = joinpath(dir, "evidence.toml")
        open(path, "w") do io
            TOML.print(io, Dict(
                "complete" => true,
                "axes" => Dict(axis => true for axis in REQUIRED_CONVERGENCE_AXES),
                "thresholds" => required,
                "results" => Dict(
                    "eigensolver" => 5e-11,
                    "tail_norm" => 5e-5,
                    "energy_balance" => 5e-4,
                ),
            ))
        end
        evidence = require_convergence_evidence(:production, path, required)
        @test evidence["thresholds"] == required

        relaxed = copy(required)
        relaxed["eigensolver"] = 1e-8
        open(path, "w") do io
            TOML.print(io, Dict(
                "complete" => true,
                "axes" => Dict(axis => true for axis in REQUIRED_CONVERGENCE_AXES),
                "thresholds" => relaxed,
                "results" => Dict(key => 0.0 for key in keys(required)),
            ))
        end
        @test_throws ArgumentError require_convergence_evidence(:production, path, required)
    end
end

@testset "resource estimate chooses local only below declared limits" begin
    small = estimate_resources(; bond_dimension=4, period_steps=10,
                               correlation_lag_steps=20, frequency_points=3)
    @test small.augmented_dimension == 16
    @test small.dense_floquet_bytes == 16^2 * sizeof(ComplexF64)
    @test small.execution == :local

    production = estimate_resources(; bond_dimension=235, period_steps=120,
                                    correlation_lag_steps=4096,
                                    frequency_points=191)
    @test production.augmented_dimension == 940
    @test production.execution == :remote
    @test production.estimated_wall_seconds > 600
end
