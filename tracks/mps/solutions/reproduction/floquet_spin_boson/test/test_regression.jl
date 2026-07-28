using Test

@testset "strict Zenodo reference curves" begin
    mktempdir() do dir
        expected_times = [0.0, 0.1, 0.2]

        wrong_length = joinpath(dir, "wrong_length.csv")
        write(wrong_length, "1.0\n0.9\n")
        @test_throws ArgumentError load_reference_curve(wrong_length, expected_times)

        wrong_grid = joinpath(dir, "wrong_grid.csv")
        write(wrong_grid, "0.0,1.0\n0.11,0.9\n0.22,0.8\n")
        @test_throws ArgumentError load_reference_curve(wrong_grid, expected_times)

        valid = joinpath(dir, "valid.csv")
        write(valid, "0.0,1.0\n0.1,0.9\n0.2,0.8\n")
        curve = load_reference_curve(valid, expected_times)
        @test curve.times == expected_times
        @test curve.values == [1.0, 0.9, 0.8]
    end
end

@testset "Redfield-Magnus reuses one step propagator" begin
    model = SpinBosonModel(alpha=0.0)
    values = zeros(3)
    redfield_magnus!(values, model, 0.1)
    @test values ≈ cos.([0.0, 0.1, 0.2]) atol=1e-12

    paper_values = redfield_magnus_paper_formula(model, 0.1, 3)
    @test paper_values ≈ values atol=1e-12
end

@testset "period-resolved Redfield drive distinguishes Fig. 2 frequencies" begin
    model = SpinBosonModel()
    low_frequency = zeros(49)
    high_frequency = zeros(49)
    redfield_magnus!(low_frequency, model, 2.5, π / 60)
    redfield_magnus!(high_frequency, model, 10.0, π / 60)
    @test maximum(abs.(low_frequency .- high_frequency)) > 1e-4

    oracle = redfield_magnus_paper_formula(model, 2.5, π / 60, length(low_frequency))
    @test low_frequency ≈ oracle atol=1e-12
end

@testset "quick Fig. 2 baseline records strict error metrics" begin
    mktempdir() do dir
        grid = period_grid(2.5, π / 60)
        times = collect(0:4) .* grid.dt
        values = redfield_magnus_paper_formula(SpinBosonModel(), 2.5, grid.dt, length(times))
        path = joinpath(dir, "redfield.csv")
        open(path, "w") do io
            for (t, value) in zip(times, values)
                println(io, "$t,$value")
            end
        end

        result = run_fig2(RunConfig(frequencies=[2.5], steps=4), Dict(2.5 => path))
        @test result[2.5].max_error < 1e-12
        @test result[2.5].rmse < 1e-12
    end
end

@testset "Fig. 2 keeps exact and Redfield references separate" begin
    mktempdir() do dir
        grid = period_grid(2.5, π / 60)
        times = collect(0:2) .* grid.dt
        values = [1.0, 0.9, 0.8]
        path = joinpath(dir, "exact.csv")
        open(path, "w") do io
            for (t, value) in zip(times, values)
                println(io, "$t,$value")
            end
        end
        solver = (model, ωd, dt, steps, tolerance) ->
            (; values, if_build_seconds=0.0, propagation_seconds=0.0, bond_dimension=1)
        result = run_fig2(RunConfig(frequencies=[2.5], steps=2),
                          Dict(2.5 => (; exact=path, redfield=path));
                          exact_solver=solver)
        @test result[2.5].exact.max_error == 0.0
        @test result[2.5].redfield.max_error > 1e-3
    end
end
