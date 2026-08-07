using Test
using JSON

const implementation = joinpath(@__DIR__, "xy_ltrg_reproduction.jl")

if !isfile(implementation)
    @testset "XY LTRG implementation is present" begin
        @test isfile(implementation)
    end
else
    include(implementation)
    using .XYLTRGReproduction

    @testset "spin-half XY bond Hamiltonian uses S=sigma/2" begin
        h = bond_hamiltonian(1.0)
        @test size(h) == (4, 4)
        @test h[2, 3] == -0.5
        @test h[3, 2] == -0.5
        @test count(!iszero, h) == 2

        h_pauli = bond_hamiltonian(1.0; pauli_convention=true)
        @test h_pauli[2, 3] == -2.0
        @test h_pauli[3, 2] == -2.0
    end

    @testset "vectorized gate evolves bra and preserves ket" begin
        tau = 0.2
        gate = vectorized_gate(tau)
        @test size(gate) == (16, 16)

        # Local vectorized index p = bra + 2*(ket-1). The input has
        # (bra1,bra2)=(up,down), (ket1,ket2)=(up,down).
        input = 1 + (4 - 1) * 4
        unchanged = input
        swapped_bra = 2 + (3 - 1) * 4
        wrong_ket = 4 + (1 - 1) * 4

        @test isapprox(gate[unchanged, input], cosh(tau / 2); atol=1e-14)
        @test isapprox(gate[swapped_bra, input], sinh(tau / 2); atol=1e-14)
        @test gate[wrong_ket, input] == 0.0
    end

    @testset "Jordan-Wigner thermodynamics has independent analytic anchors" begin
        low_temperature = exact_thermo(200.0)
        @test isapprox(low_temperature.energy, -1 / pi; atol=2e-5)
        @test isapprox(200.0 * low_temperature.specific_heat, pi / 3; rtol=2e-4)

        high_temperature = exact_thermo(1e-6)
        @test isapprox(1e-6 * high_temperature.free_energy, -log(2); atol=1e-10)
        @test abs(high_temperature.energy) < 1e-6
        @test high_temperature.specific_heat >= 0.0
    end

    @testset "Gamma-lambda LTRG update preserves normalization bookkeeping" begin
        core_names = (
            :LTRGState,
            :identity_state,
            :log_partition_per_site,
            :step!,
        )
        core_is_defined = all(name -> isdefined(XYLTRGReproduction, name), core_names)
        @test core_is_defined

        if core_is_defined
            state = identity_state()
            @test isapprox(log_partition_per_site(state), log(2); atol=1e-14)

            diagnostic = step!(state, vectorized_gate(0.05), 0.05, 16; cutoff=0.0)
            @test state.beta == 0.05
            @test isfinite(diagnostic.log_norm_ab)
            @test isfinite(diagnostic.log_norm_ba)
            @test 0.0 <= diagnostic.truncerr_ab <= 1.0
            @test 0.0 <= diagnostic.truncerr_ba <= 1.0
            @test isapprox(maximum(state.lambda_ab), 1.0; atol=1e-14)
            @test isapprox(maximum(state.lambda_ba), 1.0; atol=1e-14)
            @test all(isfinite, state.lambda_ab)
            @test all(isfinite, state.lambda_ba)
        end
    end

    @testset "small-beta LTRG agrees with exact thermodynamics" begin
        core_is_defined = all(
            name -> isdefined(XYLTRGReproduction, name),
            (:identity_state, :log_partition_per_site, :step!),
        )
        @test core_is_defined

        if core_is_defined
            tau = 0.01
            state = identity_state()
            gate = vectorized_gate(tau)
            for _ in 1:20
                step!(state, gate, tau, 32; cutoff=0.0)
            end
            ltrg_free_energy = -log_partition_per_site(state) / state.beta
            exact_free_energy = exact_thermo(state.beta).free_energy
            relative_error = abs((ltrg_free_energy - exact_free_energy) / exact_free_energy)
            @test relative_error < 2e-4
        end
    end

    @testset "direct bond energy has physical and unit-cell anchors" begin
        estimator_is_defined = isdefined(
            XYLTRGReproduction,
            :direct_bond_energies,
        )
        @test estimator_is_defined

        if estimator_is_defined
            identity_energy = direct_bond_energies(identity_state())
            @test identity_energy.ab == 0.0
            @test identity_energy.ba == 0.0
            @test identity_energy.mean == 0.0

            state = identity_state()
            gate = vectorized_gate(0.01)
            for _ in 1:20
                step!(state, gate, 0.01, 32; cutoff=0.0)
            end
            energy = direct_bond_energies(state)
            swapped = LTRGState(
                copy(state.gamma_b),
                copy(state.gamma_a),
                copy(state.lambda_ba),
                copy(state.lambda_ab),
                state.log_scale,
                state.beta,
            )
            swapped_energy = direct_bond_energies(swapped)

            @test isapprox(energy.ab, swapped_energy.ba; atol=1e-10)
            @test isapprox(energy.ba, swapped_energy.ab; atol=1e-10)
            @test isapprox(energy.mean, -0.02493770759816712; atol=2e-4)
        end
    end

    @testset "bilayer purification energy is physical and translation covariant" begin
        estimator_is_defined = isdefined(
            XYLTRGReproduction,
            :purification_bond_energies,
        )
        @test estimator_is_defined

        if estimator_is_defined
            identity_energy = purification_bond_energies(identity_state())
            @test identity_energy.ab == 0.0
            @test identity_energy.ba == 0.0
            @test identity_energy.mean == 0.0

            state = identity_state()
            half_gate = vectorized_gate(0.005)
            for _ in 1:20
                step!(state, half_gate, 0.01, 32; cutoff=0.0)
            end
            energy = purification_bond_energies(state)
            swapped = LTRGState(
                copy(state.gamma_b),
                copy(state.gamma_a),
                copy(state.lambda_ba),
                copy(state.lambda_ab),
                state.log_scale,
                state.beta,
            )
            swapped_energy = purification_bond_energies(swapped)

            @test isapprox(energy.ab, swapped_energy.ba; atol=1e-10)
            @test isapprox(energy.ba, swapped_energy.ab; atol=1e-10)
            @test isapprox(energy.mean, -0.02493770759816712; atol=2e-4)
            @test energy.mean >= -1 / pi
        end
    end

    @testset "symmetric bilayer step suppresses ordered bond bias" begin
        step_is_defined = isdefined(XYLTRGReproduction, :bilayer_step!)
        @test step_is_defined

        if step_is_defined
            tau = 0.01
            ordered = identity_state()
            ordered_gate = vectorized_gate(0.5 * tau)
            symmetric = identity_state()
            quarter_gate = vectorized_gate(0.25 * tau)
            half_gate = vectorized_gate(0.5 * tau)
            for _ in 1:20
                step!(ordered, ordered_gate, tau, 32; cutoff=0.0)
                bilayer_step!(
                    symmetric,
                    quarter_gate,
                    half_gate,
                    tau,
                    32;
                    cutoff=0.0,
                )
            end
            ordered_energy = purification_bond_energies(ordered)
            symmetric_energy = purification_bond_energies(symmetric)

            @test isapprox(symmetric.beta, 0.2; atol=1e-14)
            @test abs(symmetric_energy.ab - symmetric_energy.ba) <
                  abs(ordered_energy.ab - ordered_energy.ba)
            @test isapprox(
                symmetric_energy.mean,
                -0.02493770759816712;
                atol=2e-4,
            )
        end
    end

    @testset "uniform-grid derivatives recover a cubic polynomial" begin
        derivative_is_defined = isdefined(
            XYLTRGReproduction,
            :finite_difference_uniform,
        )
        @test derivative_is_defined

        if derivative_is_defined
            beta = collect(0.0:0.1:1.0)
            values = beta .^ 3
            derivatives = finite_difference_uniform(beta, values)
            @test derivatives.first[3:end-2] ≈ 3 .* beta[3:end-2] .^ 2 atol = 1e-11
            @test derivatives.second[3:end-2] ≈ 6 .* beta[3:end-2] atol = 1e-11
        end
    end

    @testset "curve cell persists declared parameters and diagnostics" begin
        curve_names = (:run_curve, :run_cell!)
        curve_is_defined = all(name -> isdefined(XYLTRGReproduction, name), curve_names)
        @test curve_is_defined

        if curve_is_defined
            mktempdir() do run_dir
                curve_output = joinpath(run_dir, "direct-curve.json")
                curve = run_curve(
                    0.1,
                    8,
                    0.3;
                    progress_every = 10,
                    output = curve_output,
                )
                @test isfile(curve_output)
                @test curve["beta"] ≈ [0.1, 0.2, 0.3] atol = 1e-12
                @test all(isfinite, curve["free_energy"])
                @test all(value -> 0.0 <= value <= 1.0, curve["max_truncerr"])
                truncation_fields = (
                    "truncerr_ab",
                    "truncerr_ba",
                    "cumulative_truncerr",
                )
                @test all(haskey(curve, field) for field in truncation_fields)
                if all(haskey(curve, field) for field in truncation_fields)
                    @test all(value -> 0.0 <= value <= 1.0, curve["truncerr_ab"])
                    @test all(value -> 0.0 <= value <= 1.0, curve["truncerr_ba"])
                    @test issorted(curve["cumulative_truncerr"])
                    @test isapprox(
                        curve["cumulative_truncerr"][end],
                        sum(curve["truncerr_ab"]) + sum(curve["truncerr_ba"]);
                        rtol = 1e-12,
                    )
                end

                endpoint_curve = run_curve(
                    0.1,
                    8,
                    1.2;
                    progress_every = 12,
                )
                direct_fields = (
                    "direct_energy_beta",
                    "direct_energy_ab",
                    "direct_energy_ba",
                    "direct_energy",
                    "direct_specific_heat",
                    "exact_specific_heat_at_direct_beta",
                    "direct_specific_heat_relative_error",
                )
                @test all(haskey(endpoint_curve, field) for field in direct_fields)
                if all(haskey(endpoint_curve, field) for field in direct_fields)
                    @test length(endpoint_curve["direct_energy_beta"]) == 9
                    @test endpoint_curve["direct_energy_beta"] ≈ collect(0.4:0.1:1.2) atol = 1e-12
                    @test all(isfinite, endpoint_curve["direct_energy_ab"])
                    @test all(isfinite, endpoint_curve["direct_energy_ba"])
                    @test all(isfinite, endpoint_curve["direct_energy"])
                    @test all(isfinite, endpoint_curve["direct_specific_heat"])
                    @test all(isfinite, endpoint_curve["exact_specific_heat_at_direct_beta"])
                    @test all(isfinite, endpoint_curve["direct_specific_heat_relative_error"])
                end

                curve_spec = Dict(
                    "id" => "tiny",
                    "tau" => 0.1,
                    "Dc" => 8,
                    "beta_max" => 0.3,
                )
                settings = Dict("spin_convention" => "S=sigma/2", "J" => 1.0)
                provenance = Dict("paper" => "arXiv:1011.0155")
                run_spec = Dict(
                    "run_dir" => run_dir,
                    "settings" => settings,
                    "provenance" => provenance,
                )
                cell = Dict(
                    "cell_id" => "cell-0001",
                    "params" => Dict("curve" => curve_spec),
                )
                manifest = run_cell!(run_spec, cell; progress_every = 10)
                manifest_path = joinpath(run_dir, "cells", "cell-0001", "manifest.json")
                saved = JSON.parsefile(manifest_path)

                @test manifest["success"] === true
                @test saved["params"] == cell["params"]
                @test saved["settings"] == settings
                @test saved["provenance"] == provenance
                @test saved["metrics"]["samples"] == 3
                @test haskey(saved["metrics"], "cumulative_truncerr")
                @test haskey(saved["metrics"], "direct_specific_heat_endpoint")
                @test haskey(saved["metrics"], "direct_specific_heat_relative_error")
                @test isfile(joinpath(run_dir, "cells", "cell-0001", "data.json"))
            end
        end
    end

    @testset "bilayer curve persists physical endpoint diagnostics" begin
        runner_names = (:run_bilayer_curve, :run_bilayer_cell!)
        runners_are_defined = all(
            name -> isdefined(XYLTRGReproduction, name),
            runner_names,
        )
        @test runners_are_defined

        if runners_are_defined
            curve = run_bilayer_curve(
                0.1,
                8,
                1.2;
                progress_every = 12,
            )
            @test curve["method"] == "bilayer LTRG++ purification"
            @test curve["beta"] ≈ collect(0.4:0.1:1.2) atol = 1e-12
            for field in (
                "energy_ab",
                "energy_ba",
                "energy",
                "exact_energy",
                "specific_heat",
                "exact_specific_heat",
                "specific_heat_relative_error",
                "cumulative_truncerr",
            )
                @test length(curve[field]) == 9
                @test all(isfinite, curve[field])
            end
            @test curve["energy"][end] >= -1 / pi

            mktempdir() do run_dir
                settings = Dict(
                    "method" => "bilayer LTRG++ purification",
                    "spin_convention" => "S=sigma/2",
                    "J" => 1.0,
                    "svd_cutoff" => 0.0,
                )
                provenance = Dict("paper" => "arXiv:1612.01896")
                run_spec = Dict(
                    "run_dir" => run_dir,
                    "settings" => settings,
                    "provenance" => provenance,
                )
                cell = Dict(
                    "cell_id" => "cell-0001",
                    "params" => Dict(
                        "curve" => Dict(
                            "id" => "tiny-bilayer",
                            "tau" => 0.1,
                            "Dc" => 8,
                            "beta_max" => 0.3,
                        ),
                    ),
                )
                manifest = run_bilayer_cell!(run_spec, cell; progress_every=3)
                saved = JSON.parsefile(
                    joinpath(run_dir, "cells", "cell-0001", "manifest.json"),
                )

                @test manifest["success"] === true
                @test saved["settings"] == settings
                @test saved["provenance"] == provenance
                @test saved["metrics"]["method"] == "bilayer LTRG++ purification"
                @test isfinite(saved["metrics"]["specific_heat_endpoint"])
                @test isfinite(saved["metrics"]["specific_heat_relative_error"])
                @test isfile(joinpath(run_dir, "cells", "cell-0001", "data.json"))
            end
        end
    end

    @testset "Pauli-bilinear negative control is caught" begin
        control_names = (:run_negative_control, :main)
        control_is_defined = all(
            name -> isdefined(XYLTRGReproduction, name),
            control_names,
        )
        @test control_is_defined

        if control_is_defined
            control = run_negative_control(
                tau = 0.1,
                Dc = 20,
                beta_max = 2.0,
                progress_every = 20,
            )
            @test control["relative_free_energy_error"] > 0.05
            @test control["caught"] === true
            @test control["spin_convention"] == "Pauli bilinears"
        end
    end
end
