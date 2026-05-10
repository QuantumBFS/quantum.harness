using Test

include(joinpath(@__DIR__, "harness_cell_config.jl"))

@testset "generic run-spec cell settings" begin
    spec = Dict{String,Any}(
        "settings" => Dict{String,Any}(
            "sampler" => "exact",
            "budget" => 10,
            "nested" => Dict{String,Any}("mode" => "strict"),
        ),
        "provenance" => Dict{String,Any}(
            "protocol_hash" => "proto-a",
            "sources" => ["paper"],
            "claims" => ["figure"],
            "deviations" => ["declared-method-change"],
        ),
        "cells" => Any[
            Dict{String,Any}(
                "cell_id" => "cell-0001",
                "params" => Dict{String,Any}("axis" => 1),
            ),
            Dict{String,Any}(
                "cell_id" => "cell-0002",
                "params" => Dict{String,Any}("axis" => 2),
                "settings" => Dict{String,Any}("budget" => 20),
                "provenance" => Dict{String,Any}(
                    "claims" => ["figure", "cell-specific-check"],
                ),
            ),
        ],
    )

    expected = harness_expected_cell_settings(spec)
    @test expected["cell-0001"]["sampler"] == "exact"
    @test expected["cell-0001"]["budget"] == 10
    @test expected["cell-0002"]["sampler"] == "exact"
    @test expected["cell-0002"]["budget"] == 20

    expected_provenance = harness_expected_cell_provenance(spec)
    @test expected_provenance["cell-0001"]["protocol_hash"] == "proto-a"
    @test expected_provenance["cell-0001"]["claims"] == ["figure"]
    @test expected_provenance["cell-0002"]["protocol_hash"] == "proto-a"
    @test expected_provenance["cell-0002"]["claims"] == ["figure", "cell-specific-check"]

    manifests = Any[
        Dict{String,Any}(
            "cell_id" => "cell-0001",
            "params" => Dict{String,Any}("axis" => 1),
            "protocol_hash" => "proto-a",
            "sources" => ["paper"],
            "claims" => ["figure"],
            "deviations" => ["declared-method-change"],
            "settings" => Dict{String,Any}(
                "sampler" => "exact",
                "budget" => 10,
                "nested" => Dict{String,Any}("mode" => "strict"),
            ),
        ),
        Dict{String,Any}(
            "cell_id" => "cell-0002",
            "params" => Dict{String,Any}("axis" => 2),
            "protocol_hash" => "proto-a",
            "sources" => ["paper"],
            "claims" => ["figure", "cell-specific-check"],
            "deviations" => ["declared-method-change"],
            "settings" => Dict{String,Any}(
                "sampler" => "exact",
                "budget" => 20,
                "nested" => Dict{String,Any}("mode" => "strict"),
            ),
        ),
    ]

    @test harness_validate_manifest_settings(manifests[1], expected["cell-0001"]; path="cell-0001")
    @test harness_validate_manifest_settings(manifests[2], expected["cell-0002"]; path="cell-0002")
    @test harness_validate_manifest_provenance(manifests[1], expected_provenance["cell-0001"]; path="cell-0001")
    @test harness_validate_manifest_provenance(manifests[2], expected_provenance["cell-0002"]; path="cell-0002")

    summary = harness_summarize_manifest_settings(manifests)
    @test summary["constant"]["sampler"] == "exact"
    @test summary["constant"]["nested"] == Dict{String,Any}("mode" => "strict")
    @test !haskey(summary["constant"], "budget")
    @test length(summary["varying"]["budget"]) == 2
    @test summary["varying"]["budget"][1]["value"] == 10
    @test summary["varying"]["budget"][2]["value"] == 20

    provenance_summary = harness_summarize_manifest_fields(manifests, ["protocol_hash", "claims", "deviations"])
    @test provenance_summary["constant"]["protocol_hash"] == "proto-a"
    @test provenance_summary["constant"]["deviations"] == ["declared-method-change"]
    @test !haskey(provenance_summary["constant"], "claims")
    @test length(provenance_summary["varying"]["claims"]) == 2
    @test provenance_summary["varying"]["claims"][1]["value"] == ["figure"]
    @test provenance_summary["varying"]["claims"][2]["value"] == ["figure", "cell-specific-check"]

    bad = deepcopy(manifests[2])
    bad["settings"]["budget"] = 30
    @test_throws ErrorException harness_validate_manifest_settings(bad, expected["cell-0002"]; path="bad")

    bad_provenance = deepcopy(manifests[2])
    bad_provenance["deviations"] = String[]
    @test_throws ErrorException harness_validate_manifest_provenance(
        bad_provenance, expected_provenance["cell-0002"]; path="bad-provenance")

    symbol_key_manifests = Any[
        Dict{String,Any}(
            "cell_id" => "cell-a",
            "params" => Dict{String,Any}("axis" => 1),
            "settings" => Dict(:budget => 10),
        ),
        Dict{String,Any}(
            "cell_id" => "cell-b",
            "params" => Dict{String,Any}("axis" => 2),
            "settings" => Dict(:budget => 20),
        ),
    ]
    symbol_summary = harness_summarize_manifest_settings(symbol_key_manifests)
    @test !haskey(symbol_summary["constant"], "budget")
    @test length(symbol_summary["varying"]["budget"]) == 2
    @test symbol_summary["varying"]["budget"][1]["value"] == 10
    @test symbol_summary["varying"]["budget"][2]["value"] == 20
end
