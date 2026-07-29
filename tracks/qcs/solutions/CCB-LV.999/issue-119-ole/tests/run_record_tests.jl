include(joinpath(@__DIR__, "..", "src", "RunRecords.jl"))
using .RunRecords
using TOML

@testset "per-seed TOML record round-trips without dropping layers" begin
    result = (
        seed_id = 3,
        sample_value = 0.8125,
        peak_rss_bytes = UInt64(123456),
        norm_defect = NaN,
        initial_bits = Dict(52 => 0, 59 => 1),
        layers = [
            (
                layer = 1,
                max_truncation_error = 1.0e-8,
                wall_seconds = 0.25,
            ),
        ],
    )

    mktempdir() do directory
        path = joinpath(directory, "seed-3.toml")
        write_run_record(
            path,
            result;
            run_metadata = Dict("qasm_sha256" => repeat("a", 64), "chi" => 64),
        )
        loaded = TOML.parsefile(path)
        @test loaded["result"]["seed_id"] == 3
        @test loaded["result"]["sample_value"] == 0.8125
        @test loaded["result"]["peak_rss_bytes"] == 123456
        @test isnan(loaded["result"]["norm_defect"])
        @test loaded["result"]["initial_bits"] == Dict("52" => 0, "59" => 1)
        @test only(loaded["result"]["layers"])["layer"] == 1
        @test loaded["run"]["chi"] == 64
    end
end
