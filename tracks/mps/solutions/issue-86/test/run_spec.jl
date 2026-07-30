using JSON
using Test
using TOML

if !isdefined(Main, :Issue86TrackB)
    include(joinpath(@__DIR__, "..", "src", "Issue86TrackB.jl"))
end
using .Issue86TrackB

@testset "Run spec expansion and resource classes" begin
    config = Dict(
        "sweeps" => Any[
            Dict(
                "model" => "nn",
                "lengths" => [16],
                "gammas" => [0.99, 1.0],
                "chis" => [64, 128],
                "excited" => false,
            ),
            Dict(
                "model" => "long_range",
                "sigmas" => [1.75],
                "lengths" => [128],
                "gammas" => [1.5609],
                "chis" => [128, 256],
                "poles" => [16],
            ),
        ],
    )

    spec = build_run_spec(config; run_id = "unit-run", stage = "stage-test")
    @test spec["metadata"]["run_id"] == "unit-run"
    @test spec["metadata"]["stage"] == "stage-test"
    @test length(spec["cells"]) == 6
    @test length(unique(cell["cell_id"] for cell in spec["cells"])) == 6
    @test all(
        !isnothing(match(r"^stage-test-[0-9a-f]{32}$", cell["cell_id"]))
        for cell in spec["cells"]
    )
    @test [cell["cell_id"] for cell in spec["cells"]] ==
        [cell["cell_id"] for cell in build_run_spec(
            config; run_id = "another-run", stage = "stage-test"
        )["cells"]]
    @test [cell["resource_class"] for cell in spec["cells"]] ==
        ["A", "B", "A", "B", "C", "D"]
    @test all(cell["params"]["tolerance"] == 1.0e-8 for cell in spec["cells"])

    changed = deepcopy(config)
    changed["sweeps"][1]["gammas"] = [1.01, 1.0]
    changed_spec = build_run_spec(changed; run_id = "changed", stage = "stage-test")
    @test changed_spec["cells"][1]["cell_id"] != spec["cells"][1]["cell_id"]
end

@testset "Production stage configurations have the planned cells" begin
    config_directory = joinpath(@__DIR__, "..", "configs")
    expectations = Dict(
        "calibration.toml" => (1, Dict("A" => 1)),
        "stage1.toml" => (75, Dict("A" => 70, "B" => 5)),
        "stage2-baseline.toml" => (60, Dict("A" => 60)),
        "stage2-systematics.toml" => (32, Dict("A" => 20, "B" => 12)),
        "stage2-contingency.toml" => (6, Dict("C" => 6)),
        "stage2-chi256.toml" => (6, Dict("D" => 6)),
    )

    for (filename, (expected_total, expected_classes)) in expectations
        config = TOML.parsefile(joinpath(config_directory, filename))
        spec = build_run_spec(config; run_id = filename, stage = splitext(filename)[1])
        counts = Dict{String, Int}()
        for cell in spec["cells"]
            counts[cell["resource_class"]] =
                get(counts, cell["resource_class"], 0) + 1
        end
        @test length(spec["cells"]) == expected_total
        @test counts == expected_classes
    end
end

@testset "Stage 2 first pass reuses Stage 1 baseline cells" begin
    config_path = joinpath(
        @__DIR__, "..", "configs", "stage2-first-pass.toml"
    )
    @test isfile(config_path)
    if isfile(config_path)
        config = TOML.parsefile(config_path)
        spec = build_run_spec(
            config; run_id = "stage2-first-pass", stage = "stage2-first-pass"
        )
        cells = spec["cells"]

        @test length(cells) == 67
        @test count(cell -> cell["resource_class"] == "A", cells) == 54
        @test count(cell -> cell["resource_class"] == "B", cells) == 13
        @test count(cells) do cell
            params = cell["params"]
            params["model"] == "long_range" &&
                params["poles"] == 16 &&
                params["chi"] == 64 &&
                params["L"] in (8, 24, 48)
        end == 30
        @test count(cells) do cell
            params = cell["params"]
            params["model"] == "long_range" &&
                params["poles"] == 12 &&
                params["chi"] == 64
        end == 20
        @test count(cells) do cell
            params = cell["params"]
            params["model"] == "long_range" &&
                params["poles"] == 16 &&
                params["chi"] == 128
        end == 12
        @test count(cells) do cell
            params = cell["params"]
            params["model"] == "long_range" &&
                params["poles"] == 16 &&
                params["chi"] == 64 &&
                params["L"] in (32, 64) &&
                params["gamma"] in (1.57, 1.43)
        end == 4

        nn_diagnostics = filter(
            cell -> cell["params"]["model"] == "nn", cells
        )
        @test length(nn_diagnostics) == 1
        @test only(nn_diagnostics)["params"]["L"] == 16
        @test only(nn_diagnostics)["params"]["chi"] == 128
        @test only(nn_diagnostics)["params"]["tolerance"] == 1.0e-11
        @test only(nn_diagnostics)["params"]["maxiter"] == 80
    end
end

@testset "Completed cells are excluded from resume" begin
    config = Dict(
        "sweeps" => Any[
            Dict(
                "model" => "nn",
                "lengths" => [8],
                "gammas" => [0.99, 1.0, 1.01],
                "chis" => [64],
            ),
        ],
    )
    spec = build_run_spec(config; run_id = "resume-run", stage = "stage1")

    mktempdir() do directory
        first_id = spec["cells"][1]["cell_id"]
        second_id = spec["cells"][2]["cell_id"]
        first_manifest = joinpath(directory, "cells", first_id, "manifest.json")
        mkpath(dirname(first_manifest))
        open(first_manifest, "w") do io
            JSON.print(io, Dict(
                "status" => "success",
                "cell_id" => first_id,
                "stage" => spec["cells"][1]["stage"],
                "resource_class" => spec["cells"][1]["resource_class"],
                "params" => spec["cells"][1]["params"],
                "result" => Dict("E0" => -1.0),
            ))
        end

        failed_manifest = joinpath(directory, "cells", second_id, "manifest.json")
        mkpath(dirname(failed_manifest))
        open(failed_manifest, "w") do io
            JSON.print(io, Dict("status" => "failed", "error" => "test failure"))
        end

        third_cell = spec["cells"][3]
        stale_params = deepcopy(third_cell["params"])
        stale_params["gamma"] = 9.99
        stale_manifest = joinpath(
            directory, "cells", third_cell["cell_id"], "manifest.json"
        )
        mkpath(dirname(stale_manifest))
        open(stale_manifest, "w") do io
            JSON.print(io, Dict(
                "status" => "success",
                "cell_id" => third_cell["cell_id"],
                "stage" => third_cell["stage"],
                "resource_class" => third_cell["resource_class"],
                "params" => stale_params,
                "result" => Dict("E0" => -9.99),
            ))
        end

        @test pending_cell_indices(spec, directory) == [2, 3]
        @test pending_cell_indices(spec, directory; resource_class = "B") == Int[]

        collected = collect_cell_results(spec, directory)
        @test length(collected) == 1
        @test collected[1]["E0"] == -1.0
        @test collected[1]["cell_id"] == first_id
    end
end

@testset "Malformed success manifests remain pending" begin
    config = Dict(
        "sweeps" => Any[
            Dict(
                "model" => "nn",
                "lengths" => [8],
                "gammas" => [1.0],
                "chis" => [64],
            ),
        ],
    )
    spec = build_run_spec(config; run_id = "malformed-run", stage = "stage1")
    cell = only(spec["cells"])

    mktempdir() do directory
        manifest_path = joinpath(
            directory, "cells", cell["cell_id"], "manifest.json"
        )
        mkpath(dirname(manifest_path))
        open(manifest_path, "w") do io
            JSON.print(io, Dict(
                "status" => "success",
                "cell_id" => cell["cell_id"],
                "stage" => cell["stage"],
                "resource_class" => cell["resource_class"],
                "params" => cell["params"],
                "result" => nothing,
            ))
        end

        @test pending_cell_indices(spec, directory) == [1]
        @test isempty(collect_cell_results(spec, directory))
    end
end

@testset "Cell execution writes an atomic resumable manifest" begin
    config = Dict(
        "sweeps" => Any[
            Dict(
                "model" => "nn",
                "lengths" => [8],
                "gammas" => [1.0],
                "chis" => [64],
            ),
        ],
    )
    spec = build_run_spec(config; run_id = "cell-run", stage = "stage1")
    calls = Ref(0)
    fake_solver = function (; kwargs...)
        calls[] += 1
        return Dict{String, Any}("E0" => -8.0, "runtime" => 0.01)
    end

    mktempdir() do directory
        first = execute_cell(spec, 1, directory; solver = fake_solver)
        second = execute_cell(spec, 1, directory; solver = fake_solver)
        cell_id = spec["cells"][1]["cell_id"]
        manifest_path = joinpath(directory, "cells", cell_id, "manifest.json")
        manifest = JSON.parsefile(manifest_path)

        @test calls[] == 1
        @test first["E0"] == second["E0"] == -8.0
        @test manifest["status"] == "success"
        @test manifest["cell_id"] == cell_id
        @test manifest["resource_class"] == "A"
        @test manifest["runtime"]["julia_threads"] >= 1
        @test isempty(filter(name -> occursin(".tmp-", name), readdir(dirname(manifest_path))))
    end
end
