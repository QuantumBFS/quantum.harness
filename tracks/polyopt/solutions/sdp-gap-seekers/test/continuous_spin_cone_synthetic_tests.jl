using Test

const SOURCE_ROOT = normpath(joinpath(@__DIR__, "..", "src"))

for source_file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "SpinAxisInvolutionReduction.jl",
    "FullSpinPermutationReduction.jl",
    "FullSpinConeReduction.jl",
    "FullSpinIsotypicReduction.jl",
    "ContinuousSpinMomentReduction.jl",
    "ContinuousSpinConeReduction.jl",
)
    include(joinpath(SOURCE_ROOT, source_file))
end

using .SquareJ1J2Prototype
using .ExactSymmetryReduction
using .ReducedPrimalGapAssembly
using .FullSpinIsotypicReduction

const C = ContinuousSpinConeReduction

function word(left_axis::UInt8, right_axis::UInt8)
    return PauliWord([
        (1, left_axis),
        (2, right_axis),
    ])
end

@testset "continuous-spin l=2 row correspondence" begin
    diagonal_source = ReducedPSDBlock(
        :positive,
        :centered,
        V4Character(false, false),
        ReducedPSDRow[
            ReducedPSDRow(:centered, word(0x01, 0x01)),
            ReducedPSDRow(:centered, word(0x03, 0x03)),
        ],
    )
    diagonal = FullSpinIsotypicPSDBlock(
        diagonal_source,
        :s3_standard_representative,
        FullSpinIsotypicCombinationRow[
            FullSpinIsotypicCombinationRow([1, 2], [1, -1]),
        ],
    )

    offdiagonal_source = ReducedPSDBlock(
        :positive,
        :centered,
        V4Character(true, false),
        ReducedPSDRow[
            ReducedPSDRow(:centered, word(0x01, 0x03)),
            ReducedPSDRow(:centered, word(0x03, 0x01)),
        ],
    )
    offdiagonal = FullSpinIsotypicPSDBlock(
        offdiagonal_source,
        :eigen_plus,
        FullSpinIsotypicCombinationRow[
            FullSpinIsotypicCombinationRow([1, 2], [1, 1]),
        ],
    )

    diagonal_row = only(diagonal.rows)
    offdiagonal_row = only(offdiagonal.rows)
    @test C.row_site_signature(diagonal, diagonal_row) == (1, 2)
    @test C.row_site_signature(offdiagonal, offdiagonal_row) == (1, 2)

    diagonal_axes = C.row_axis_signature(diagonal, diagonal_row)
    offdiagonal_axes =
        C.row_axis_signature(offdiagonal, offdiagonal_row)
    @test C.diagonal_l2_orientation(diagonal_axes) == 1
    @test C.offdiagonal_l2_orientation(offdiagonal_axes) == 1
    @test C.component_squared_norm(diagonal_axes) == 2
    @test C.component_squared_norm(offdiagonal_axes) == 2

    reversed_diagonal = FullSpinIsotypicCombinationRow(
        [1, 2],
        [-1, 1],
    )
    reversed_axes =
        C.row_axis_signature(diagonal, reversed_diagonal)
    @test C.diagonal_l2_orientation(reversed_axes) == -1

    @test C.exact_permutation_rank(
        C.rows_by_site_signature(diagonal),
        C.rows_by_site_signature(offdiagonal),
    ) == 1
end
