using JSON
using Test

include(joinpath(@__DIR__, "harness_validate_numeric.jl"))

function write_json(path, value)
    open(path, "w") do io
        JSON.print(io, value, 2)
    end
end

@testset "harness numeric validation" begin
    dir = mktempdir()
    actual_path = joinpath(dir, "actual.json")
    reference_path = joinpath(dir, "reference.json")
    spec_path = joinpath(dir, "check.json")

    write_json(actual_path, Dict("nested" => Dict("estimate" => 1.02, "stderr" => 0.02)))
    write_json(reference_path, Dict("target" => 1.00))
    write_json(spec_path, Dict(
        "check_id" => "generic-smoke",
        "checks" => Any[
            Dict(
                "name" => "nested field compare",
                "actual" => Dict("path" => actual_path, "field" => "nested.estimate"),
                "reference" => Dict("path" => reference_path, "field" => "target"),
                "uncertainty" => Dict("path" => actual_path, "field" => "nested.stderr"),
                "tolerance" => Dict("abs" => 0.05, "sigma" => 2.0, "mode" => "all"),
            ),
        ],
    ))

    pass_report = harness_validate_numeric(spec_path)
    @test pass_report["status"] == "pass"
    @test only(pass_report["checks"])["metrics"]["abs"] ≈ 0.02 atol=1e-12

    write_json(actual_path, Dict("nested" => Dict("estimate" => 1.20, "stderr" => 0.01)))
    fail_report = harness_validate_numeric(spec_path)
    @test fail_report["status"] == "fail"
    @test only(fail_report["checks"])["status"] == "fail"

    pointer_spec = joinpath(dir, "pointer-check.json")
    write_json(actual_path, Dict("series" => Any[Dict("value" => 3.0)]))
    write_json(reference_path, Dict("series" => Any[Dict("value" => 3.0)]))
    write_json(pointer_spec, Dict(
        "check_id" => "json-pointer-smoke",
        "checks" => Any[
            Dict(
                "name" => "json pointer compare",
                "actual" => Dict("path" => actual_path, "pointer" => "/series/0/value"),
                "reference" => Dict("path" => reference_path, "pointer" => "/series/0/value"),
                "tolerance" => Dict("abs" => 0.0),
            ),
        ],
    ))
    @test harness_validate_numeric(pointer_spec)["status"] == "pass"

    toml_spec = joinpath(dir, "check.toml")
    open(toml_spec, "w") do io
        println(io, "check_id = \"toml-smoke\"")
        println(io)
        println(io, "[[checks]]")
        println(io, "name = \"toml spec compare\"")
        println(io, "actual = { path = \"actual.json\", field = \"metrics.value\" }")
        println(io, "reference = { path = \"reference.json\", field = \"metrics.value\" }")
        println(io, "tolerance = { abs = 0.0 }")
    end
    write_json(actual_path, Dict("metrics" => Dict("value" => 5.0)))
    write_json(reference_path, Dict("metrics" => Dict("value" => 5.0)))
    @test harness_validate_numeric(toml_spec)["status"] == "pass"

    protocol_spec = joinpath(dir, "protocol.toml")
    open(protocol_spec, "w") do io
        println(io, "[[checks]]")
        println(io, "id = \"source_audit\"")
        println(io, "kind = \"source_audit\"")
        println(io)
        println(io, "[[checks]]")
        println(io, "id = \"reference_gate\"")
        println(io, "kind = \"numeric_compare\"")
        println(io, "gate = \"preflight\"")
        println(io)
        println(io, "  [[checks.compare]]")
        println(io, "  name = \"protocol nested compare\"")
        println(io, "  actual = { path = \"actual.json\", field = \"metrics.value\" }")
        println(io, "  reference = { path = \"reference.json\", field = \"metrics.value\" }")
        println(io, "  tolerance = { abs = 0.0 }")
    end
    @test harness_validate_numeric(protocol_spec; check_id="reference_gate")["status"] == "pass"

    single_check_spec = joinpath(dir, "single-check.json")
    write_json(single_check_spec, Dict(
        "name" => "single object compare",
        "actual" => Dict("path" => actual_path, "field" => "metrics.value"),
        "reference" => Dict("path" => reference_path, "field" => "metrics.value"),
        "tolerance" => Dict("abs" => 0.0),
    ))
    @test harness_validate_numeric(single_check_spec)["status"] == "pass"

    bool_spec = joinpath(dir, "bool-check.json")
    write_json(actual_path, Dict("metrics" => Dict("value" => true)))
    write_json(reference_path, Dict("metrics" => Dict("value" => 1.0)))
    write_json(bool_spec, Dict(
        "checks" => Any[
            Dict(
                "name" => "bool is not numeric",
                "actual" => Dict("path" => actual_path, "field" => "metrics.value"),
                "reference" => Dict("path" => reference_path, "field" => "metrics.value"),
                "tolerance" => Dict("abs" => 0.0),
            ),
        ],
    ))
    @test_throws ErrorException harness_validate_numeric(bool_spec)

    old_validation_spec = get(ENV, "HARNESS_VALIDATION_SPEC", nothing)
    try
        ENV["HARNESS_VALIDATION_SPEC"] = protocol_spec
        parsed = harness_parse_args(["--check-id", "reference_gate"])
        @test parsed.spec_path == protocol_spec
        @test parsed.check_id == "reference_gate"
    finally
        if old_validation_spec === nothing
            delete!(ENV, "HARNESS_VALIDATION_SPEC")
        else
            ENV["HARNESS_VALIDATION_SPEC"] = old_validation_spec
        end
    end
end
