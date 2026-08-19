using Test

module IsotypicRunnerUnderTest
include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "solve_shastry_sutherland_full_spin_isotypic_reduced_mof.jl",
))
end

const R = IsotypicRunnerUnderTest

@testset "runner string boundaries accept views and regex captures" begin
    gamma_view = SubString("x3//4", 2)
    @test gamma_view isa SubString{String}
    @test R.B.canonical_gamma(gamma_view) == "3//4"

    integer_view = SubString("x16", 2)
    float_view = SubString("x1e-7", 2)
    flag_view = SubString("x--threads", 2)
    @test R.B.parse_positive_int(integer_view, flag_view) == 16
    @test R.B.parse_positive_float(float_view, flag_view) == 1e-7

    canonical = R.B.canonical_gamma(gamma_view)
    fields = split(canonical, "//")
    @test all(field -> field isa SubString{String}, fields)
    metadata = Dict(
        "numerator" => "3",
        "denominator" => "4",
        "canonical" => "3//4",
        "float64" => 0.75,
    )
    label_capture = only(match(r"^(gamma)$", "gamma").captures)
    @test label_capture isa SubString{String}
    @test R.B.require_rational_metadata(
        metadata,
        fields[1],
        fields[2],
        gamma_view,
        0.75,
        label_capture,
    ) === nothing

    setup = Dict(
        "model" => "shastry-sutherland",
        "patch_level" => 1,
        "degree_d" => 2,
        "state_class" => "unrestricted",
        "physical_boundary_condition" =>
            "none-local-consistency-window",
        "g_square_over_dimer" => Dict(
            "numerator" => "4",
            "denominator" => "5",
            "canonical" => "4//5",
            "float64" => 0.8,
        ),
        "gamma" => metadata,
    )
    @test R.validate_setup(setup, gamma_view) === nothing

    withenv("SS_SCAN_DYNAMIC_INPUT" => SubString("x1", 2)) do
        @test R.dynamic_scan_input_enabled()
    end

    @test_throws ArgumentError R.B.canonical_gamma(
        SubString("x-1/2", 2),
    )
    @test_throws ArgumentError R.B.canonical_gamma(
        SubString("x1/0", 2),
    )
end
