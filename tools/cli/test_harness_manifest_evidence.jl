using Test

include(joinpath(@__DIR__, "harness_manifest_evidence.jl"))

@testset "generic manifest evidence validation" begin
    evidence = Any[
        Dict("id"=>"abs-target", "value"=>0.9999, "expected_abs"=>1.0,
             "tolerance"=>1e-3, "status"=>"pass"),
        Dict("id"=>"signed-target", "value"=>2.01, "expected"=>2.0,
             "tolerance"=>0.02, "status"=>"pass"),
    ]
    @test harness_validate_evidence(evidence; required_ids=["abs-target", "signed-target"])

    bad_value = Any[
        Dict("id"=>"bad", "value"=>0.5, "expected_abs"=>1.0,
             "tolerance"=>1e-3, "status"=>"pass"),
    ]
    @test_throws ErrorException harness_validate_evidence(bad_value)

    bad_status = Any[
        Dict("id"=>"bad-status", "value"=>1.0, "expected_abs"=>1.0,
             "tolerance"=>1e-3, "status"=>"fail"),
    ]
    @test_throws ErrorException harness_validate_evidence(bad_status)

    missing = Any[
        Dict("id"=>"present", "value"=>1.0, "expected_abs"=>1.0,
             "tolerance"=>1e-3, "status"=>"pass"),
    ]
    @test_throws ErrorException harness_validate_evidence(missing; required_ids=["present", "missing"])

    declarations = Any[
        Dict("id"=>"declared-constraint", "kind"=>"fixture_check",
             "target"=>"primary", "check_code"=>3, "expected_abs"=>1.0, "tolerance"=>1e-6),
    ]
    bound = Any[
        Dict("id"=>"declared-constraint", "kind"=>"fixture_check",
             "target"=>"primary", "check_code"=>3, "value"=>0.9999999,
             "expected_abs"=>1.0, "tolerance"=>1e-6, "status"=>"pass"),
    ]
    @test harness_validate_evidence_against_declarations(bound, declarations)

    wrong_binding = Any[
        Dict("id"=>"declared-constraint", "kind"=>"fixture_check",
             "target"=>"secondary", "check_code"=>3, "value"=>0.9999999,
             "expected_abs"=>1.0, "tolerance"=>1e-6, "status"=>"pass"),
    ]
    @test_throws ErrorException harness_validate_evidence_against_declarations(wrong_binding, declarations)

    forged_target = Any[
        Dict("id"=>"declared-constraint", "kind"=>"fixture_check",
             "target"=>"primary", "check_code"=>3, "value"=>0.5,
             "expected_abs"=>0.5, "tolerance"=>1e-6, "status"=>"pass"),
    ]
    @test_throws ErrorException harness_validate_evidence_against_declarations(forged_target, declarations)

    measured_only = Any[
        Dict("id"=>"declared-constraint", "kind"=>"fixture_check",
             "target"=>"primary", "check_code"=>3, "value"=>0.9999999,
             "status"=>"pass"),
    ]
    @test harness_validate_evidence_against_declarations(measured_only, declarations)

    manifest = Dict(
        "status"=>"success",
        "script_hash"=>"abc123",
        "sources"=>["paper"],
        "claims"=>["figure"],
        "deviations"=>["alternate route"],
        "result"=>Dict("value"=>1.02, "se"=>0.05, "budget"=>0.10),
        "checks"=>declarations,
        "evidence"=>bound,
    )
    contract = Dict(
        "required_fields"=>["status", "script_hash", "result.value"],
        "nonempty_fields"=>["sources", "claims"],
        "equals"=>Any[Dict("field"=>"status", "value"=>"success")],
        "list_contains"=>Any[Dict("field"=>"deviations", "value"=>"alternate route")],
        "numeric_fields"=>["result.value", "result.se"],
        "optional_numeric_fields"=>["mean_R"],
        "numeric_bounds"=>Any[
            Dict("id"=>"error budget", "lhs_field"=>"result.se", "op"=>"<=", "rhs_field"=>"result.budget"),
        ],
        "evidence_sets"=>Any[
            Dict("evidence_field"=>"evidence", "declarations_field"=>"checks", "required"=>true),
        ],
    )
    @test harness_validate_manifest_contract(manifest, contract; path="manifest.json")

    generic_contract = Dict(
        "numeric_bounds"=>Any[
            Dict("id"=>"optional absent bound", "lhs_field"=>"result.se", "op"=>"<=",
                 "rhs_field"=>"missing.budget", "when_present"=>"missing.budget"),
        ],
    )
    @test harness_validate_manifest_contract(manifest, generic_contract; path="manifest.json")

    bad_contract = Dict(
        "numeric_bounds"=>Any[
            Dict("id"=>"too strict", "lhs_field"=>"result.se", "op"=>"<=", "rhs"=>0.01),
        ],
    )
    @test_throws ErrorException harness_validate_manifest_contract(manifest, bad_contract; path="manifest.json")
end
