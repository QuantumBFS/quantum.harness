using Test

include("RunBootstrapRG.jl")

function synthetic_point(; depth=3, raw=-0.45, corrected=-0.451,
        upper=-0.42, fingerprint="fixed-map", clean=true,
        interval=false, classification="residual-corrected-floating-coefficients")
    Dict{String,Any}(
        "depth" => depth,
        "solver" => Dict{String,Any}(
            "lower_bound_candidate" => raw,
            "vumps_upper_endpoint" => upper,
            "map_fingerprint" => fingerprint,
            "clean" => clean),
        "dual" => Dict{String,Any}(
            "corrected_lower_bound" => corrected,
            "map_fingerprint" => fingerprint,
            "coefficient_policy" => Dict("complete_interval_enclosure" => interval)),
        "certification_classification" => classification,
        "accepted" => true)
end

@testset "Bootstrap-RG pure result validation" begin
    valid = synthetic_point()
    checks, accepted = validate_point_record(valid)
    @test accepted
    @test all(values(checks))

    falsely_interval = synthetic_point(classification="interval-certified")
    checks, accepted = validate_point_record(falsely_interval)
    @test !accepted
    @test !checks["floating_not_interval_certified"]

    above_exact = synthetic_point(raw=-0.44, corrected=-0.45)
    checks, accepted = validate_point_record(above_exact)
    @test !accepted
    @test !checks["raw_le_exact"]

    nonmonotonic = synthetic_point(raw=-0.46, corrected=-0.47)
    checks, accepted = validate_point_record(nonmonotonic; monotonic_predecessor=-0.45)
    @test !accepted
    @test !checks["depth_monotonic"]

    points = [synthetic_point(depth=3, raw=-0.46, corrected=-0.47),
        synthetic_point(depth=4, raw=-0.455, corrected=-0.465)]
    @test all(values(validate_run_records(points)))
    points[2]["solver"]["map_fingerprint"] = "changed-map"
    @test !validate_run_records(points)["fixed_fingerprint"]
    @test_throws ArgumentError run_formal_local(output_directory=tempname(), D=3)
    @test_throws ArgumentError run_formal_local(output_directory=tempname(), k0=2)
    @test_throws ArgumentError run_formal_local(output_directory=tempname(), depths=[3])
end

@testset "Bootstrap-RG map-quality comparison" begin
    product = bond_product_frozen_mps(ComplexF64[1, 0], 2)
    @test product.bond_dimensions == [(2, 2)]
    @test product.canonical_residual < 1e-14
    comparison = compare_map_quality(random_canonical_frozen_mps(2, 2; seed=991), -0.42;
        depth=3, D=2, k0=3)
    @test comparison["same_solver_budget"]
    @test comparison["all_sound"]
    @test Set(item["map"] for item in comparison["comparisons"]) ==
        Set(["product", "random_canonical", "vumps"])
    @test all(item["clean"] for item in comparison["comparisons"])
    @test all(item["D"] == 2 && item["depth"] == 3 && item["k0"] == 3
        for item in comparison["comparisons"])
end

@testset "QMBCertify integration disposition" begin
    assessment = qmbcertify_integration_assessment()
    @test assessment["qmbcertify_runtime_dependency"] === false
    @test assessment["decision"] == "do-not-integrate-current-oracle"
    @test assessment["structured_npa_augmentation"]["status"] ==
        "deferred-follow-up-milestone"
    @test assessment["structured_npa_augmentation"]["coarse_blocks"] ==
        "retain independent omega variables"
end
