using Test
using LinearAlgebra

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
)
    include(joinpath(SOURCE_ROOT, source_file))
end

using .PrimalGapSymbolics
using .ContinuousSpinMomentReduction

const C = ContinuousSpinMomentReduction

function rank_four_representatives(
    words::Vector{Vector{Int}},
    all_same::MomentKey,
    pair_12_34::MomentKey,
    pair_13_24::MomentKey,
    pair_14_23::MomentKey,
)
    representatives = Dict{MomentKey,MomentKey}()
    for axes in C.axis_assignments(4)
        C.even_axis_parities(axes) || continue
        counts = [
            count(==(axis), axes)
            for axis in UInt8(1):UInt8(3)
        ]
        representative = if maximum(counts) == 4
            all_same
        elseif axes[1] == axes[2]
            pair_12_34
        elseif axes[1] == axes[3]
            pair_13_24
        else
            pair_14_23
        end
        representatives[C.assigned_moment(words, axes)] =
            representative
    end
    return representatives
end

@testset "continuous-spin exact tensor parameterization" begin
    @test transpose(C.RATIONAL_ROTATION) * C.RATIONAL_ROTATION ==
          Matrix{ExactRational}(I, 3, 3)
    @test det(C.RATIONAL_ROTATION) == 1

    rank_two_words = [[1, 2]]
    xx = C.assigned_moment(rank_two_words, UInt8[1, 1])
    yy = C.assigned_moment(rank_two_words, UInt8[2, 2])
    zz = C.assigned_moment(rank_two_words, UInt8[3, 3])
    rank_two_representatives = Dict(
        xx => xx,
        yy => xx,
        zz => xx,
    )
    rank_two_substitutions, rank_two_pivots =
        C.skeleton_substitutions(
            [xx],
            rank_two_representatives,
            rank_two_words,
        )
    @test rank_two_pivots == [xx]
    @test rank_two_substitutions[xx] ==
          ExactLinearPolynomial(Dict(
              xx => Complex{ExactRational}(1, 0),
          ))

    distinct_words = [[1, 2, 3, 4]]
    xxxx = C.assigned_moment(
        distinct_words,
        UInt8[1, 1, 1, 1],
    )
    xxyy = C.assigned_moment(
        distinct_words,
        UInt8[1, 1, 2, 2],
    )
    xyxy = C.assigned_moment(
        distinct_words,
        UInt8[1, 2, 1, 2],
    )
    xyyx = C.assigned_moment(
        distinct_words,
        UInt8[1, 2, 2, 1],
    )
    distinct_representatives = rank_four_representatives(
        distinct_words,
        xxxx,
        xxyy,
        xyxy,
        xyyx,
    )
    distinct_substitutions, distinct_pivots =
        C.skeleton_substitutions(
            [xxxx, xxyy, xyxy, xyyx],
            distinct_representatives,
            distinct_words,
        )
    @test length(distinct_pivots) == 3
    @test distinct_substitutions[xyyx] ==
          distinct_substitutions[xxxx] -
          distinct_substitutions[xxyy] -
          distinct_substitutions[xyxy]

    repeated_words = [[1], [1], [1], [1]]
    repeated_xxxx = C.assigned_moment(
        repeated_words,
        UInt8[1, 1, 1, 1],
    )
    repeated_xxyy = C.assigned_moment(
        repeated_words,
        UInt8[1, 1, 2, 2],
    )
    repeated_representatives = rank_four_representatives(
        repeated_words,
        repeated_xxxx,
        repeated_xxyy,
        repeated_xxyy,
        repeated_xxyy,
    )
    repeated_substitutions, repeated_pivots =
        C.skeleton_substitutions(
            [repeated_xxxx, repeated_xxyy],
            repeated_representatives,
            repeated_words,
        )
    @test length(repeated_pivots) == 1
    @test repeated_substitutions[repeated_xxyy] ==
          (1//3) * repeated_substitutions[repeated_xxxx]
end
