#!/usr/bin/env julia

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))

for source in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "FullStateSymmetryReduction.jl",
    "ShastryFullStateSpatialReduction.jl",
    "ShastryFullStateSpinSpatialReduction.jl",
    "ShastryFullStateSpinIsotypicReduction.jl",
)
    include(joinpath(TRACK_ROOT, "src", source))
end

using .SquareJ1J2Prototype
using .GenericGapModel
using .PrimalGapAssembly
using .FullStateSymmetryReduction
using .ShastryFullStateSpatialReduction
using .ShastryFullStateSpinSpatialReduction
using .ShastryFullStateSpinIsotypicReduction

const EXPECTED_COEFFICIENT_SHA256 =
    "2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679"

function measured(callback, label)
    println("[structural-pipeline-truth] ", label)
    flush(stdout)
    measurement = @timed callback()
    println(
        "[structural-pipeline-truth] ",
        label,
        " wall_seconds=",
        measurement.time,
    )
    flush(stdout)
    return measurement.value
end

problem = GapProblem(
    square_patch_geometry(1),
    shastry_sutherland_model(4 // 5),
    2 // 1,
    2;
    basis_mode=:structured,
    basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
)
primal = measured("structural primal") do
    assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
        materialize_coefficients=false,
        structural_moment_filter=:v4_conjugation_even,
        materialize_moment_inventory=false,
    )
end
v4 = measured("structural V4") do
    assemble_full_state_v4_reduced_primal(
        primal;
        verify_truth=false,
        materialize_coefficients=false,
    )
end
real_reduced = measured("structural conjugation") do
    assemble_full_state_real_reduced_primal(
        v4;
        verify_truth=false,
        materialize_coefficients=false,
    )
end
spatial = measured("structural spatial") do
    assemble_shastry_full_state_spatial_reduced_primal(
        real_reduced;
        verify_truth=false,
        materialize_coefficients=false,
    )
end
spin_spatial = measured("structural spin quotient") do
    assemble_shastry_full_state_spin_spatial_reduced_primal(
        spatial;
        verify_truth=false,
        verify_source_covariance=false,
        materialize_coefficients=false,
    )
end
isotypic = measured("parallel exact isotypic truth and coefficients") do
    assemble_shastry_full_state_spin_isotypic_reduced_primal(spin_spatial)
end

isotypic.coefficient_map_sha256 == EXPECTED_COEFFICIENT_SHA256 ||
    error("parallel structural pipeline differs from materialized truth")
report =
    shastry_full_state_spin_isotypic_reduced_assembly_report(isotypic)
report.spin_isotypic_moments == 7_231 ||
    error("parallel structural pipeline changed the moment count")
report.psd_triangle_entries == 75_967 ||
    error("parallel structural pipeline changed the PSD inventory")

println(
    "structural_pipeline_truth=true",
    " threads=", Threads.nthreads(),
    " moments=", report.spin_isotypic_moments,
    " psd_triangle_entries=", report.psd_triangle_entries,
    " coefficient_map_sha256=", isotypic.coefficient_map_sha256,
)
flush(stdout)
