using Carlo
using Test

include(joinpath(@__DIR__, "..", "src", "DedicatedTFIMSSE.jl"))
using .DedicatedTFIMSSE

@testset "dedicated TFIM SSE structure" begin
    for (name, L, sites, bonds, coordination) in (
        ("honeycomb", 2, 8, 12, 3),
        ("triangular", 3, 9, 27, 6),
    )
        observed_sites, edges, observed_coordination =
            DedicatedTFIMSSE.lattice_edges(name, L)
        @test observed_sites == sites
        @test length(edges) == bonds
        @test observed_coordination == coordination
        degree = zeros(Int, sites)
        for (first, second) in edges
            degree[first] += 1
            degree[second] += 1
        end
        @test degree == fill(coordination, sites)
    end

    params = Dict{Symbol,Any}(
        :lattice_name => "honeycomb",
        :L => 2,
        :T => 1 / 0.85,
        :J => 0.73,
        :h => 1.17,
        :string_length => 256,
    )
    mc = DedicatedTFIMSSE.MC(params)
    @test DedicatedTFIMSSE.candidate_weight(mc) ≈
          mc.n_sites * mc.h + 2 * mc.J * length(mc.edges)
    @test all(==(DedicatedTFIMSSE.OP_IDENTITY), mc.kinds)
    @test mc.expansion_order == 0

    m2, m4 = DedicatedTFIMSSE.dirichlet_time_average_moments([1.0, -1.0])
    @test m2 ≈ 1 / 3
    @test m4 ≈ 1 / 5
    asymmetric_m2, asymmetric_m4 =
        DedicatedTFIMSSE.dirichlet_time_average_moments([1.0, 2.0, 0.0])
    @test asymmetric_m2 ≈ 7 / 6
    @test asymmetric_m4 ≈ 31 / 15
    constant_m2, constant_m4 =
        DedicatedTFIMSSE.dirichlet_time_average_moments(fill(0.37, 100_000))
    @test constant_m2 ≈ 0.37^2
    @test constant_m4 ≈ 0.37^4

    no_flip_m2, no_flip_m4 = DedicatedTFIMSSE.spacetime_moments(mc)
    @test no_flip_m2 ≈ 1.0
    @test no_flip_m4 ≈ 1.0

    mc.kinds[1] = DedicatedTFIMSSE.OP_FIELD_FLIP
    mc.indices[1] = 1
    mc.kinds[2] = DedicatedTFIMSSE.OP_FIELD_FLIP
    mc.indices[2] = 1
    mc.expansion_order = 2
    artificial_m2, artificial_m4 = DedicatedTFIMSSE.spacetime_moments(mc)
    expected_m2, expected_m4 =
        DedicatedTFIMSSE.dirichlet_time_average_moments([1.0, 0.75, 1.0])
    @test artificial_m2 ≈ expected_m2
    @test artificial_m4 ≈ expected_m4

    mc.kinds[2] = DedicatedTFIMSSE.OP_FIELD_CONSTANT
    mc.indices[2] = 1
    mc.kinds[3] = DedicatedTFIMSSE.OP_FIELD_FLIP
    mc.indices[3] = 1
    mc.expansion_order = 3
    diagonal_split_m2, diagonal_split_m4 =
        DedicatedTFIMSSE.spacetime_moments(mc)
    split_expected_m2, split_expected_m4 =
        DedicatedTFIMSSE.dirichlet_time_average_moments(
            [1.0, 0.75, 0.75, 1.0],
        )
    @test diagonal_split_m2 ≈ split_expected_m2
    @test diagonal_split_m4 ≈ split_expected_m4
end

@testset "correlated Binder jackknife" begin
    m2_bins = [0.18, 0.24, 0.31, 0.27, 0.22, 0.29]
    m4_bins = [0.07, 0.10, 0.16, 0.12, 0.09, 0.14]
    binder(m2, m4) = m2^2 / m4
    count = length(m2_bins)
    complete = binder(sum(m2_bins) / count, sum(m4_bins) / count)
    leave_one_out = [
        binder(
            (sum(m2_bins) - m2_bins[index]) / (count - 1),
            (sum(m4_bins) - m4_bins[index]) / (count - 1),
        ) for index in eachindex(m2_bins)
    ]
    leave_one_out_mean = sum(leave_one_out) / count
    expected_mean =
        count * complete - (count - 1) * leave_one_out_mean
    expected_error = sqrt(
        (count - 1) / count *
        sum((value - leave_one_out_mean)^2 for value in leave_one_out),
    )

    observed_mean, observed_error, covariance =
        Carlo.jackknife(binder, (m2_bins, m4_bins), false)
    @test only(observed_mean) ≈ expected_mean
    @test only(observed_error) ≈ expected_error
    @test isnothing(covariance)
end
