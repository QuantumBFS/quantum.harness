# Deterministic smoke tests for the independent line-update FSS observables.
include(joinpath(@__DIR__, "..", "src", "TIM_lattice_observables.jl"))

using Test

function direct_fss_sums(s, phases)
    spins = 2 .* s.conf .- 1
    initial = copy(spins)
    magnetizations = Float64[sum(spins) / s.N]
    structure = Float64[]
    function structure_factor()
        q_re = phases.cosq * spins
        q_im = phases.sinq * spins
        return sum(q_re .^ 2 .+ q_im .^ 2) /
               (size(phases.cosq, 1) * s.N^2)
    end
    push!(structure, structure_factor())
    for position in 1:s.lm
        operator_type = s.opl[1, position]
        operator_type == 0 && continue
        if operator_type == 6 || operator_type == 7
            site = s.opl[2, position]
            spins[site] = -spins[site]
        end
        push!(magnetizations, sum(spins) / s.N)
        push!(structure, structure_factor())
    end
    @test spins == initial
    p1 = sum(magnetizations)
    p2 = sum(magnetizations .^ 2)
    p3 = sum(magnetizations .^ 3)
    p4 = sum(magnetizations .^ 4)
    K = Float64(length(magnetizations))
    return (
        spacetime_m2 = (p1^2 + p2) / (K * (K + 1)),
        spacetime_m4 = (p1^4 + 6p1^2 * p2 + 3p2^2 + 8p1 * p3 + 6p4) /
                       (K * (K + 1) * (K + 2) * (K + 3)),
        S0 = p2 / K, Sq = sum(structure) / K, equal_m4 = p4 / K,
    )
end

@testset "FSS phase tables" begin
    for lattice in (:triangular, :honeycomb)
        phases = build_fss_phases(lattice, 6, 6)
        @test size(phases.cosq) == (6, lattice == :triangular ? 36 : 72)
        @test all(isfinite, phases.cosq)
        @test all(isfinite, phases.sinq)
        @test phases.q_norm ≈ 2pi / (3sqrt(3))
    end
end

@testset "closed-worldline estimators" begin
    s = Sim(:triangular, 3, 3, -1.0, 0.0, 4.76811, 6.0, 20260730)
    fill!(s.conf, 1)
    fill!(s.opl, 0)
    s.lm = 2
    s.nh = 2
    s.opl[:, 1] .= (6, 1)  # site 1: 1 -> 0
    s.opl[:, 2] .= (7, 1)  # site 1: 0 -> 1
    @test check_config(s)

    phases = build_fss_phases(:triangular, 3, 3)
    observable = measure_fss(s, phases; check_periodicity = true)
    middle_m = 1 - 2 / s.N
    states = [1.0, middle_m, 1.0]
    @test observable.S0 ≈ sum(states .^ 2) / 3
    @test observable.equal_m4 ≈ sum(states .^ 4) / 3
    @test observable.Sq ≈ 4 / (3s.N^2) atol = 1e-14
    @test observable.spacetime_m2 <= observable.S0 + 1e-12
    @test observable.spacetime_m4 <= observable.equal_m4 + 1e-12
end

@testset "empty operator string" begin
    s = Sim(:honeycomb, 2, 2, -1.0, 0.0, 2.1325, 4.0, 20260731)
    fill!(s.conf, 1)
    fill!(s.opl, 0)
    s.lm = 1
    s.nh = 0
    observable = measure_fss(s, build_fss_phases(:honeycomb, 2, 2);
                             check_periodicity = true)
    @test observable.spacetime_m2 ≈ 1
    @test observable.spacetime_m4 ≈ 1
    @test observable.S0 ≈ 1
    @test observable.equal_m4 ≈ 1
    @test observable.Sq ≈ 0 atol = 1e-14
end

@testset "optimized estimator matches direct propagation" begin
    for (case_index, (lattice, field)) in enumerate(((:triangular, 4.76811),
                                                      (:honeycomb, 2.1325)))
        s = Sim(lattice, 3, 3, -1.0, 0.0, field, 6.0, 20260740 + case_index)
        set_bond_epsilon!(s, recommended_line_epsilon(lattice))
        _, classes = color_lattice(lattice, 3, 3, s.N, s.bond)
        scratch = LineScratch(s.N, 1, 20260740 + case_index)
        for _ in 1:50
            dupdate!(s)
            line_sweep!(s, scratch, classes)
            s.lm = max(s.lm, floor(Int, 1.25 * s.nh))
        end
        @test check_config(s)
        phases = build_fss_phases(lattice, 3, 3)
        optimized = measure_fss(s, phases; check_periodicity = true)
        direct = direct_fss_sums(s, phases)
        for name in (:spacetime_m2, :spacetime_m4, :S0, :Sq, :equal_m4)
            @test getproperty(optimized, name) ≈ getproperty(direct, name) rtol = 1e-12
        end
    end
end
