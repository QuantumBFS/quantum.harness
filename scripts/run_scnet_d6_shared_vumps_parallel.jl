const ROOT = get(ENV, "HARNESS_ROOT", joinpath(homedir(), "quantum.harness"))
const SOURCE = joinpath(ROOT, "tracks", "polyopt", "solutions", "组一辈子乐队")
include(joinpath(SOURCE, "VUMPSProducer.jl"))
include(joinpath(SOURCE, "MPSKitAdapter.jl"))

using .VUMPSProducer
using .MPSKitAdapter
using .MPSKitAdapter.KullCGRDM
using MosekTools
using Dates

const D = parse(Int, get(ENV, "KULL_D", "6"))
const internal_D = parse(Int, get(ENV, "KULL_INTERNAL_D", string(D)))
const depths = Tuple(parse.(Int, split(get(ENV, "KULL_DEPTHS", "10,20,32"), ',')))
const delta = parse(Float64, get(ENV, "KULL_DELTA", "2.0"))
const k0 = parse(Int, get(ENV, "KULL_K0", "3"))
const mosek_threads = parse(Int, get(ENV, "MOSEK_NUM_THREADS_PER_DEPTH", "30"))
const solver_settings = Dict(
    "MSK_IPAR_LOG" => 0,
    "MSK_IPAR_NUM_THREADS" => mosek_threads,
)
const result_dir = joinpath(ROOT, "results",
    get(ENV, "KULL_RESULT_DIR", "scnet-u1-shared-vumps-parallel"))

function progress(fields...)
    println(join((string(key, "=", value) for (key, value) in fields), " "))
    flush(stdout)
end

function solve_depth(h, blocked, record, depth, vumps_seconds)
    progress("event" => "cell_start", "time" => now(), "D" => D, "depth" => depth,
        "thread" => Threads.threadid())

    problem_box = Ref{Any}()
    build_seconds = @elapsed problem_box[] = build_kull_primal(h;
        frozen=blocked.frozen, depth, k0, symmetry=blocked.symmetry, real_sdp=true,
        optimizer=MosekTools.Optimizer, solver_settings=solver_settings,
        vumps_upper_endpoint=2record["energy_per_site"])
    problem = problem_box[]
    progress("event" => "build_done", "D" => D, "depth" => depth,
        "build_seconds" => build_seconds,
        "variables" => problem.inventory.real_scalar_variables,
        "equalities" => problem.inventory.linear_equalities,
        "blocks" => join(problem.inventory.psd_block_dimensions, ','))

    result_box = Ref{Any}()
    solve_wall_seconds = @elapsed result_box[] = solve_kull_primal!(problem;
        require_local_feasible=false, print_inventory=true)
    result = result_box[]
    certificate = reconstruct_dual_certificate(problem)
    fields = (
        D=D, internal_D=internal_D, depth=depth, delta=delta, k0=k0,
        real_sdp=true,
        source_commit=get(ENV, "HARNESS_SOURCE_COMMIT", "unknown"),
        mps_scalar_type=record["mps_scalar_type"],
        vumps_upper_per_site=record["energy_per_site"],
        vumps_algorithm_error=record["algorithm_error"],
        charge_residual=blocked.metadata["charge_residual"],
        canonical_residual=blocked.frozen.canonical_residual,
        raw_lower_per_site=result.lower_bound_candidate / 2,
        corrected_lower_per_site=certificate.corrected_lower_bound / 2,
        primal_residual=result.constraint_residual,
        dual_stationarity=certificate.maximum_stationarity_residual,
        vumps_seconds=vumps_seconds, build_seconds=build_seconds,
        solve_wall_seconds=solve_wall_seconds, mosek_seconds=result.runtime_seconds,
        variables=problem.inventory.real_scalar_variables,
        equalities=problem.inventory.linear_equalities,
        clean=result.clean, termination_status=result.termination_status,
        job_id=get(ENV, "SLURM_JOB_ID", "local"), completed_at=now())
    progress("event" => "kull_done", pairs(fields)...)

    result_path = joinpath(result_dir, "result-D$(D)-m$(depth).tsv")
    tmp_path = result_path * ".tmp." * get(ENV, "SLURM_JOB_ID", string(getpid()))
    open(tmp_path, "w") do io
        println(io, join(string.(keys(fields)), '\t'))
        println(io, join(string.(values(fields)), '\t'))
        flush(io)
    end
    mv(tmp_path, result_path; force=true)
    progress("event" => "cell_complete", "time" => now(), "depth" => depth,
        "result" => result_path)
    nothing
end

length(unique(depths)) == length(depths) || error("KULL_DEPTHS contains duplicates")
all(>(0), depths) || error("all KULL_DEPTHS values must be positive")
Threads.nthreads() >= length(depths) || error(
    "JULIA_NUM_THREADS must be at least the number of depths ($(length(depths)))")
mkpath(result_dir)
progress("event" => "start", "time" => now(), "D" => D,
    "internal_D" => internal_D, "delta" => delta, "k0" => k0,
    "depths" => join(depths, ','), "julia_threads" => Threads.nthreads(),
    "mosek_threads_per_depth" => mosek_threads,
    "source_commit" => get(ENV, "HARNESS_SOURCE_COMMIT", "unknown"))

vumps_box = Ref{Any}()
vumps_seconds = @elapsed vumps_box[] = run_u1_vumps(; D, internal_D, delta,
    maxiter=300, tol=1e-9, seed=1234 + D, verbosity=1)
produced = vumps_box[]
record = produced.record
record["real_mps"] === true || error("VUMPS did not remain in the real scalar domain")
progress("event" => "vumps_done", "seconds" => vumps_seconds,
    "energy_per_site" => record["energy_per_site"],
    "algorithm_error" => record["algorithm_error"],
    "scalar_type" => record["mps_scalar_type"],
    "clean" => record["clean_convergence"])

blocked = freeze_u1_blocked_mpskit(produced.state, record)
eltype(only(blocked.frozen.tensors)) <: Real || error("frozen MPS is not real")
maximum(abs, imag.(only(blocked.frozen.tensors))) == 0 ||
    error("frozen MPS has a nonzero imaginary part")
progress("event" => "adapter_done",
    "charge_residual" => blocked.metadata["charge_residual"],
    "canonical_residual" => blocked.frozen.canonical_residual)

h = blocked_xxz_hamiltonian(delta)
tasks = map(depths) do depth
    Threads.@spawn solve_depth(h, blocked, record, depth, vumps_seconds)
end
for task in tasks
    fetch(task)
end
progress("event" => "complete", "time" => now())
