#!/usr/bin/env julia

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))

for source in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "PrimalGapJuMP.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "FullStateSymmetryReduction.jl",
    "ShastryFullStateSpatialReduction.jl",
    "ShastryFullStateSpinSpatialReduction.jl",
    "ShastryFullStateSpinIsotypicReduction.jl",
    "ShastryFullStateSpinIsotypicPrimalGapMosek.jl",
)
    include(joinpath(TRACK_ROOT, "src", source))
end

using Mosek
using .SquareJ1J2Prototype
using .GenericGapModel
using .PrimalGapAssembly
using .FullStateSymmetryReduction
using .ShastryFullStateSpatialReduction
using .ShastryFullStateSpinSpatialReduction
using .ShastryFullStateSpinIsotypicReduction
using .ShastryFullStateSpinIsotypicPrimalGapMosek

const EXPECTED_COEFFICIENT_SHA256 =
    "2a6753a6ea7c57fa43bd33e09339046206fae5217ac3ae47c0cf9cc3b2dc2679"

function native_progress(message::AbstractString)
    println("[native-primal-truth] ", message)
    flush(stdout)
end

for dimension in 1:8
    indices = sort([
        ShastryFullStateSpinIsotypicPrimalGapMosek.mosek_svec_index(
            dimension,
            row,
            column,
        )
        for row in 1:dimension
        for column in row:dimension
    ])
    indices == collect(1:(dimension * (dimension + 1) ÷ 2)) ||
        error("native svec map is not a permutation at dimension $dimension")
end

problem = GapProblem(
    square_patch_geometry(1),
    shastry_sutherland_model(4 // 5),
    2 // 1,
    2;
    basis_mode=:structured,
    basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
)
primal = assemble_primal_gap(
    problem;
    stationarity_spec=StationaritySpec(:full_inner_state, 1),
    materialize_coefficients=false,
    structural_moment_filter=:v4_conjugation_even,
    materialize_moment_inventory=false,
)
v4 = assemble_full_state_v4_reduced_primal(
    primal;
    verify_truth=false,
    materialize_coefficients=false,
)
real_reduced = assemble_full_state_real_reduced_primal(
    v4;
    verify_truth=false,
    materialize_coefficients=false,
)
spatial = assemble_shastry_full_state_spatial_reduced_primal(
    real_reduced;
    verify_truth=false,
    materialize_coefficients=false,
)
spin_spatial = assemble_shastry_full_state_spin_spatial_reduced_primal(
    spatial;
    verify_truth=false,
    verify_source_covariance=false,
    materialize_coefficients=false,
)
isotypic = assemble_shastry_full_state_spin_isotypic_reduced_primal(
    spin_spatial;
    verify_truth=false,
    materialize_coefficients=false,
)
report = shastry_full_state_spin_isotypic_reduced_assembly_report(isotypic)

measurement = @timed build_shastry_full_state_spin_isotypic_mosek_primal(
    isotypic;
    threads=Threads.nthreads(),
    log_level=0,
    progress_callback=native_progress,
    fingerprint_coefficients=true,
)
native = measurement.value
native.coefficient_map_sha256 == EXPECTED_COEFFICIENT_SHA256 ||
    error("native coefficient fingerprint differs from the exact regression")
length(native.moment_variables) == 7_231 ||
    error("native primal changed the L=1 moment count")
expected_block_count =
    length(isotypic.positive_blocks) + length(isotypic.gap_blocks)
expected_block_count == 23 ||
    error("exact L=1 structural cone count changed")
native.native_psd_blocks == expected_block_count ||
    error("native primal changed the L=1 cone count")
Int(Mosek.getnumvar(native.task)) == 7_231 ||
    error("native Mosek task changed the scalar-variable count")
Int(Mosek.getnumacc(native.task)) == expected_block_count ||
    error("native Mosek task changed the affine-cone count")
Int(Mosek.getnumafe(native.task)) == report.psd_triangle_entries ||
    error("native Mosek task changed the PSD triangle inventory")

println(
    "native_primal_truth=true",
    " threads=", Threads.nthreads(),
    " wall_seconds=", measurement.time,
    " moments=", length(native.moment_variables),
    " affine_cones=", Mosek.getnumacc(native.task),
    " affine_entries=", Mosek.getnumafe(native.task),
    " scalar_terms=", native.scalar_coefficient_terms,
    " coefficient_map_sha256=", native.coefficient_map_sha256,
)
flush(stdout)
