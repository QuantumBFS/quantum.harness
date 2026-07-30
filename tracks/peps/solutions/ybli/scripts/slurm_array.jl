"""
Cluster submission template for parallel Born-rule sampling on Slurm.

This script generates a Slurm array job where each task handles one
independent replica at a specific (model, L, coupling) point.

Manifest schema (one row per task):
  (model, coupling, L, Ly, sector, backend, chi, replica_id)

Reproducible RNG (workflow 7.3):
  key = hash(experiment_uuid, model, L, coupling, sector, replica_id)
  counter = (sweep_or_row, site, proposal_slot, random_slot)

Output (workflow 7.4): one HDF5/JLD2 file per replica containing:
  - manifest hash, git commit, code version
  - model convention and parameters
  - accumulated log-normalization / log-R sums
  - block means and covariances
  - acceptance, autocorrelation diagnostics
  - checkpoint state

Usage:
  1. Edit the configuration section below
  2. Run: julia --project=julia-env scripts/slurm_array.jl --generate
  3. Submit: sbatch slurm/array_*.sh
  4. Merge:  julia --project=julia-env scripts/slurm_array.jl --merge
"""

using Random
using Printf
using Dates

# Include the module
include("../src/OpenCriticality.jl")
using .OpenCriticality

# ====================================================================
# Configuration
# ====================================================================

const EXPERIMENT_UUID = "open-criticality-122-v1"

# Pilot grid (workflow 7.5)
const L_VALUES = [6, 8, 10, 12, 16]
const LY_FACTOR = 100  # Ly = 100 * L
const N_REPLICAS = 8
const BURN_IN_SWEEPS = 100
const PRODUCTION_SWEEPS = 1000

# Model selection: :classical_ising, :nishimori, :measured_toric_code
const MODEL_TYPE = :classical_ising
const COUPLING = log(1 + sqrt(2)) / 2  # beta_c for Ising

# Backend: :dense (small L) or :boundary_mps (large L)
const BACKEND = :dense
const CHI = 64
const TOL = 1e-12

# Output directory
const OUTPUT_DIR = "results"

# ====================================================================
# Manifest generation
# ====================================================================

"""
    generate_manifest()

Create the manifest as a vector of NamedTuples, one per Slurm array task.
"""
function generate_manifest()
    manifest = NamedTuple{(:model, :coupling, :L, :Ly, :sector, :backend, :chi, :replica_id), Tuple{Symbol,Float64,Int,Int,String,Symbol,Int,Int}}[]
    for L in L_VALUES
        Ly = LY_FACTOR * L
        for rep in 1:N_REPLICAS
            push!(manifest, (
                model=MODEL_TYPE,
                coupling=COUPLING,
                L=L,
                Ly=Ly,
                sector="default",
                backend=BACKEND,
                chi=CHI,
                replica_id=rep
            ))
        end
    end
    return manifest
end

"""
    manifest_hash(entry)

Compute a deterministic hash from manifest fields for reproducibility.
"""
function manifest_hash(entry)
    s = string(entry.model, "_", entry.coupling, "_", entry.L, "_",
               entry.Ly, "_", entry.sector, "_", entry.backend, "_",
               entry.chi, "_", entry.replica_id)
    return hash(s * EXPERIMENT_UUID)
end

# ====================================================================
# Reproducible RNG
# ====================================================================

"""
    make_rng(entry)

Create a deterministic RNG from the manifest entry.
Uses hash(manifest fields + experiment UUID) as the seed.

Note: for production, replace with a counter-based generator (Philox)
that supports independent streams.  MersenneTwister is sufficient for
testing but does not guarantee independence across streams.
"""
function make_rng(entry)
    seed = abs(manifest_hash(entry)) % typemax(UInt64)
    return MersenneTwister(seed)
end

# ====================================================================
# Single-task execution
# ====================================================================

"""
    run_task(entry)

Run one complete independent trajectory for the given manifest entry.
Returns a results dictionary.
"""
function run_task(entry)
    L = entry.L
    Ly = entry.Ly
    rng = make_rng(entry)

    # Build model
    if entry.model == :classical_ising
        model = ClassicalIsing(L=L, beta=entry.coupling)
    elseif entry.model == :nishimori
        model = NishimoriRBIM(L=L)
    elseif entry.model == :measured_toric_code
        model = MeasuredToricCode(L=L)
    else
        error("Unknown model: $(entry.model)")
    end

    conv = convention(model)

    # Sample configurations and compute observables
    if conv.disorder == :clean
        # Clean model: single deterministic configuration
        config = sample_config(model, rng, Ly)
        logZ = dense_logZ(model, config)
        gamma0 = leading_lyapunov(model, config; burn_in=max(1, Ly ÷ 10))
        return Dict(
            "logZ" => logZ,
            "gamma0" => gamma0,
            "Phi_L" => free_energy_per_row(conv, logZ, Ly),
            "L" => L,
            "Ly" => Ly,
            "replica_id" => entry.replica_id,
        )
    else
        # Disordered model: direct iid sampling
        nsamples = min(PRODUCTION_SWEEPS, 200)
        logZs = Float64[]
        gamma0s = Float64[]
        for _ in 1:nsamples
            config = sample_config(model, rng, Ly)
            push!(logZs, dense_logZ(model, config))
            # Only compute Lyapunov for a subset
            if length(gamma0s) < 50
                push!(gamma0s, leading_lyapunov(model, config; burn_in=max(1, Ly ÷ 10)))
            end
        end
        return Dict(
            "logZ_mean" => mean(logZs),
            "logZ_std" => std(logZs),
            "logZ_samples" => logZs,
            "gamma0_mean" => mean(gamma0s),
            "gamma0_std" => std(gamma0s),
            "L" => L,
            "Ly" => Ly,
            "nsamples" => nsamples,
            "replica_id" => entry.replica_id,
        )
    end
end

# ====================================================================
# Main entry points
# ====================================================================

function main()
    mode = length(ARGS) > 0 ? ARGS[1] : "run"

    if mode == "--generate"
        # Generate Slurm scripts
        manifest = generate_manifest()
        ntasks = length(manifest)
        println("Generating Slurm array job: $ntasks tasks")
        _write_slurm_script(manifest)
        println("Slurm script written to slurm/array_job.sh")
        println("Submit with: sbatch slurm/array_job.sh")

    elseif mode == "--merge"
        # Merge results from completed tasks
        println("Merging results from $(OUTPUT_DIR)/...")
        _merge_results()

    else
        # Run a single task (for testing or Slurm execution)
        task_id = length(ARGS) > 1 ? parse(Int, ARGS[2]) : 1
        manifest = generate_manifest()
        if task_id > length(manifest)
            error("Task ID $task_id exceeds manifest size $(length(manifest))")
        end
        entry = manifest[task_id]
        println("Running task $task_id: L=$(entry.L), Ly=$(entry.Ly), rep=$(entry.replica_id)")
        result = run_task(entry)
        println("Result: $result")
        # In production, save to HDF5/JLD2 here
    end
end

function _write_slurm_script(manifest)
    mkpath("slurm")
    ntasks = length(manifest)
    open("slurm/array_job.sh", "w") do io
        println(io, "#!/bin/bash")
        println(io, "#SBATCH --job-name=open-criticality")
        println(io, "#SBATCH --array=1-$ntasks%64")
        println(io, "#SBATCH --time=24:00:00")
        println(io, "#SBATCH --partition=compute")
        println(io, "#SBATCH --cpus-per-task=4")
        println(io, "#SBATCH --mem=8G")
        println(io, "")
        println(io, "module load julia")
        println(io, "")
        println(io, "cd $SLURM_SUBMIT_DIR")
        println(io, "")
        println(io, "julia --project=julia-env tracks/peps/solutions/ybli/scripts/slurm_array.jl run \$SLURM_ARRAY_TASK_ID")
    end
end

function _merge_results()
    # Placeholder: in production, read all HDF5 files and combine
    println("Merge not yet implemented. Collect results manually.")
    println("Expected output: results/task_*.h5")
end

# Run
main()