using QuantumMCMethods
using Carlo
using HDF5
using Random
using Statistics
using Test

@testset "square-lattice geometry" begin
    @test nbonds(SquareLatticeTFIM(1, 1)) == 0
    @test nbonds(SquareLatticeTFIM(2, 2)) == 4
    @test nbonds(SquareLatticeTFIM(4, 4)) == 24
    @test nbonds(SquareLatticeTFIM(10, 10)) == 180
    @test SquareLatticeTFIM(2, 2).bonds ==
          [(1, 2), (3, 4), (1, 3), (2, 4)]
end

@testset "analytic spectra" begin
    h = 1.7
    one_spin = exact_spectrum(SquareLatticeTFIM(1, 1; J=0, h))
    @test one_spin ≈ [-h, h] atol=1e-12

    J = 0.9
    h = 1.3
    one_bond = exact_spectrum(SquareLatticeTFIM(2, 1; J, h))
    expected = sort([-sqrt(J^2 + 4h^2), -J, J, sqrt(J^2 + 4h^2)])
    @test one_bond ≈ expected atol=1e-12
end

@testset "independent-spin thermodynamics" begin
    model = SquareLatticeTFIM(2, 2; J=0, h=1.3)
    for beta in (0.0, 0.1, 0.7, 1.0)
        exact = exact_thermal_observables(model, beta)
        analytic = independent_spin_observables(nsites(model), model.h, beta)
        @test exact.logZ ≈ analytic.logZ atol=1e-11
        @test exact.u ≈ analytic.u atol=1e-11
        @test exact.c ≈ analytic.c atol=1e-11
        @test exact.mx ≈ analytic.mx atol=1e-11
        @test exact.mz2 ≈ analytic.mz2 atol=1e-11
    end
end

@testset "one-dimensional Jordan-Wigner thermodynamics" begin
    for L in 1:8, h in (0.4, 1.0, 1.7), beta in (0.0, 0.1, 0.7, 2.0)
        model = SquareLatticeTFIM(L, 1; J=0.9, h)
        dense = exact_thermal_observables(model, beta)
        fermion = exact_open_chain_observables(model, beta)
        @test fermion.logZ ≈ dense.logZ atol=2e-11
        @test fermion.u ≈ dense.u atol=2e-11
        @test fermion.c ≈ dense.c atol=2e-11
        @test fermion.mx ≈ dense.mx atol=2e-11
    end

    classical_chain = SquareLatticeTFIM(8, 1; J=0.9, h=0.0)
    for beta in (0.0, 0.7, 2.0)
        dense = exact_thermal_observables(classical_chain, beta)
        fermion = exact_open_chain_observables(classical_chain, beta)
        @test fermion.logZ ≈ dense.logZ atol=2e-11
        @test fermion.u ≈ dense.u atol=2e-11
        @test fermion.c ≈ dense.c atol=2e-11
        @test fermion.mx ≈ dense.mx atol=2e-11
    end

    @test_throws ArgumentError exact_open_chain_observables(
        SquareLatticeTFIM(2, 2; J=1.0, h=1.0),
        1.0,
    )

    # The thermodynamic-limit integral must recover independent spins and be
    # converged with respect to the quadrature order at the critical point.
    for beta in (0.0, 0.3, 2.0)
        infinite = exact_infinite_chain_observables(0.0, 1.3, beta)
        independent = independent_spin_observables(1, 1.3, beta)
        @test infinite.logZ_density ≈ independent.logZ atol=2e-13
        @test infinite.u ≈ independent.u atol=2e-13
        @test infinite.c ≈ independent.c atol=2e-13
        @test infinite.mx ≈ independent.mx atol=2e-13
    end
    critical_256 = exact_infinite_chain_observables(
        1.0, 1.0, 2.0; quadrature_order=256,
    )
    critical_512 = exact_infinite_chain_observables(
        1.0, 1.0, 2.0; quadrature_order=512,
    )
    for observable in (:logZ_density, :free_energy_density, :u, :c, :mx)
        @test getproperty(critical_256, observable) ≈
              getproperty(critical_512, observable) atol=2e-13
    end
end

@testset "classical enumeration" begin
    model = SquareLatticeTFIM(2, 2; J=1.0, h=0)
    for beta in (0.0, 0.1, 0.7, 1.0)
        exact = exact_thermal_observables(model, beta)
        classical = classical_enumeration(model, beta)
        @test exact.logZ ≈ classical.logZ atol=1e-11
        @test exact.u ≈ classical.u atol=1e-11
        @test exact.c ≈ classical.c atol=1e-11
        @test exact.mz2 ≈ classical.mz2 atol=1e-11
    end
end

@testset "SSE configuration invariants" begin
    model = SquareLatticeTFIM(2, 2; J=1.0, h=2.5)
    state = initialize_sse(model, 0.7, Xoshiro(1234); cutoff=96)
    rng = Xoshiro(5678)
    for _ in 1:1_000
        sweep!(state, model, 0.7, rng)
        @test validate_configuration(state, model)
    end
    @test state.n < length(state.operators)

    # Cutoff diagnostics must record a transient hit at the insertion event;
    # checking only at the end of a sweep can miss it after later removals.
    forced = initialize_sse(
        SquareLatticeTFIM(1, 1; J=0.0, h=1.0),
        10.0,
        Xoshiro(1);
        cutoff=1,
    )
    diagonal_update!(
        forced,
        SquareLatticeTFIM(1, 1; J=0.0, h=1.0),
        10.0,
        Xoshiro(2),
    )
    @test forced.n == 1
    @test forced.max_n_observed == 1
    @test forced.cutoff_touched

    old_cutoff = length(forced.operators)
    QuantumMCMethods._warmup_cutoff_guard!(forced)
    @test length(forced.operators) > old_cutoff
    @test !forced.cutoff_touched
end

@testset "constant-deflated expansion-order oracle" begin
    for (h, beta) in ((2.5, 0.5), (3.5, 1.0))
        model = SquareLatticeTFIM(2, 2; J=1.0, h)
        thermal = exact_thermal_observables(model, beta)
        standard = exact_expansion_order_moments(model, beta)
        deflated = exact_expansion_order_moments(
            model,
            beta;
            deflate_site_constant=true,
        )

        @test standard.energy_density ≈ thermal.u atol=1e-11
        @test deflated.energy_density ≈ thermal.u atol=1e-11
        @test standard.heat_capacity ≈ thermal.c atol=1e-11
        @test deflated.heat_capacity ≈ thermal.c atol=1e-11
        @test standard.mean - deflated.mean ≈
              beta * h * nsites(model) atol=1e-11
        @test deflated.heat_influence_variance <
              standard.heat_influence_variance
    end

    difficult = SquareLatticeTFIM(2, 2; J=1.0, h=3.5)
    standard = exact_expansion_order_moments(difficult, 1.0)
    deflated = exact_expansion_order_moments(
        difficult,
        1.0;
        deflate_site_constant=true,
    )
    @test deflated.heat_influence_variance /
          standard.heat_influence_variance < 0.4
end

@testset "autocorrelation diagnostics" begin
    rng = Xoshiro(20260728)
    iid = randn(rng, 50_000)
    iid_diagnostic = autocorrelation_estimate(iid)
    @test 0.5 <= iid_diagnostic.tau_int <= 0.75
    @test iid_diagnostic.effective_samples <= length(iid)
    @test iid_diagnostic.standard_error ≈
          sqrt(iid_diagnostic.asymptotic_variance / length(iid))

    phi = 0.8
    ar1 = zeros(Float64, 100_000)
    for sample in 2:length(ar1)
        ar1[sample] = phi * ar1[sample - 1] + randn(rng)
    end
    ar1_diagnostic = autocorrelation_estimate(view(ar1, 1_001:length(ar1)))
    theoretical_tau = (1 + phi) / (2(1 - phi))
    @test ar1_diagnostic.tau_int ≈ theoretical_tau rtol=0.25

    constant_diagnostic = autocorrelation_estimate(fill(2.0, 100))
    @test constant_diagnostic.tau_int == 0.5
    @test constant_diagnostic.standard_error == 0.0
    @test constant_diagnostic.effective_samples == 100
end

@testset "SSE trace and nonlinear influence series" begin
    model = SquareLatticeTFIM(2, 2; J=1.0, h=2.5)
    beta = 0.7
    trace = sample_sse_trace(
        model,
        beta;
        warmup=500,
        sweeps=4_096,
        seed=20260728,
        validate_every=256,
    )

    @test length(trace) == 4_096
    @test !trace.cutoff_touched
    @test trace.max_expansion_order < trace.cutoff
    @test all(
        trace.n .== trace.nJ .+ trace.n0 .+ trace.nflip,
    )
    @test trace.nh == trace.n0 + trace.nflip

    for observable in (:u, :c, :mx)
        value = observable_estimate(trace, model, beta, observable)
        influence = observable_influence(trace, model, beta, observable)
        diagnostic = autocorrelation_estimate(influence)
        curve = blocking_curve(trace, model, beta, observable; min_blocks=16)

        @test isfinite(value)
        @test length(influence) == length(trace)
        @test mean(influence) ≈ 0 atol=1e-11
        @test diagnostic.standard_error > 0
        @test !isempty(curve)
        @test all(point -> isfinite(point.standard_error), curve)
        @test all(point -> ispow2(point.block_size), curve)
        @test all(point -> point.blocks >= 16, curve)

        standard_observable = Symbol(observable, :_standard)
        standard_value = observable_estimate(
            trace,
            model,
            beta,
            standard_observable,
        )
        standard_diagnostic = autocorrelation_estimate(
            observable_influence(
                trace,
                model,
                beta,
                standard_observable,
            ),
        )
        @test abs(value - standard_value) <=
              5hypot(diagnostic.standard_error,
                     standard_diagnostic.standard_error)
    end

    constant_diagnostic = autocorrelation_estimate(
        trace.n0 .- beta * model.h * nsites(model),
    )
    @test abs(mean(trace.n0) - beta * model.h * nsites(model)) <=
          5constant_diagnostic.standard_error
end

@testset "Carlo adapter callbacks" begin
    params = Dict(
        :Lx => 2,
        :Ly => 2,
        :J => 1.0,
        :h => 2.5,
        :beta => 0.7,
        :thermalization => 100,
        :binsize => 20,
        :seed => 20260727,
        :cutoff => 96,
        :validate_every => 25,
    )
    context = Carlo.MCContext{Xoshiro}(params)
    mc = TFIMSSECarlo(params)
    Carlo.init!(mc, context, params)

    for _ in 1:500
        Carlo.sweep!(mc, context)
        context.sweeps += 1
        if Carlo.is_thermalized(context)
            Carlo.measure!(mc, context)
        end
    end

    @test validate_configuration(mc.state, mc.model)
    @test !isempty(context.measure)
    @test mc.state.n < length(mc.state.operators)

    mktempdir() do directory
        checkpoint = joinpath(directory, "scientific-state.h5")
        h5open(checkpoint, "w") do file
            Carlo.write_checkpoint(mc, create_group(file, "simulation"))
        end

        restored = TFIMSSECarlo(params)
        h5open(checkpoint, "r") do file
            Carlo.read_checkpoint!(restored, file["simulation"])
        end
        @test restored.state.spins == mc.state.spins
        @test restored.state.operators == mc.state.operators
        @test restored.state.n == mc.state.n
        @test validate_configuration(restored.state, restored.model)
    end
end
