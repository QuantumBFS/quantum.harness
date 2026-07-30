# Diagnostic: where did the h_z=0.05 warm CTMRG branch diverge from fresh
# contractions during the series-pilot optimization? Re-contracts every saved
# step checkpoint of the pilot's h_z=0.05 point with a fresh deterministic and
# one fresh random environment at the same chi/tolerance, and prints the
# warm-vs-fresh energy per step alongside the recorded warm energy.

using LinearAlgebra, Printf
using TensorKit, PEPSKit, MPSKit, JLD2

isdefined(@__MODULE__, :run_tied_mode) ||
    include(joinpath(@__DIR__, "..", "scripts", "ad_tied_gd.jl"))

function branch_divergence_main(args = ARGS)
    length(args) == 2 || throw(ArgumentError(
        "usage: series_branch_divergence.jl PILOT_OUTDIR HZ"))
    outdir, hz = args[1], parse(Float64, args[2])
    chi = 8
    tag = "hz_" * replace(@sprintf("%.3f", hz), "." => "p")
    hamiltonian, _ = toric_code_hamiltonian(0.0, hz; P = TIED_UP)
    step_paths = sort(filter(
        path -> occursin(tag * "_step", path), readdir(outdir; join = true)))
    isempty(step_paths) && error("no step checkpoints found for $tag in $outdir")
    println("step,warm_energy_cell,fresh_det_cell,fresh_rand_cell,fresh_minus_warm_per_spin,mz_fresh_det")
    flush(stdout)
    for path in step_paths
        data = load(path)
        psi = InfinitePEPS(data["tensors"])
        warm = data["energy"]
        step = data["accepted_steps"]
        e_det, mz_det = NaN, NaN
        env_det = try
            env, _ = converge_tied_environment(
                psi, chi; tol = 1e-8, maxiter = 500, seed = TIED_CTM_SEED)
            env
        catch error_value
            error_value isa CTMRGConvergenceError || rethrow()
            nothing
        end
        if !isnothing(env_det)
            e_det = real(expectation_value(psi, hamiltonian, env_det))
            mz_det = -real(expectation_value(psi, m3_field_like(), env_det)) / 8
        end
        e_rand = NaN
        env_rand = try
            env, _ = converge_tied_environment(
                psi, chi; tol = 1e-8, maxiter = 500, seed = 1)
            env
        catch error_value
            error_value isa CTMRGConvergenceError || rethrow()
            nothing
        end
        !isnothing(env_rand) &&
            (e_rand = real(expectation_value(psi, hamiltonian, env_rand)))
        @printf(
            "%d,%.10f,%.10f,%.10f,%.3e,%.8f\n",
            step, warm, e_det, e_rand,
            (max(e_det, e_rand) - warm) / 8, mz_det)
        flush(stdout)
    end
    return true
end

function m3_field_like()
    lattice = fill(TIED_UP, 2, 2)
    operator = empty_localoperator(lattice)
    unit = field_op(0.0, 1.0, TIED_UP)
    for r in 1:2, c in 1:2
        PEPSKit.add_term!(operator, [CartesianIndex(r, c)], unit)
    end
    return operator
end

if abspath(PROGRAM_FILE) == @__FILE__
    branch_divergence_main()
end
