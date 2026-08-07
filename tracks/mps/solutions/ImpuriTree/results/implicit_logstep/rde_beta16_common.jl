module RDEBeta16Common

using Dates
using LinearAlgebra
using Printf

using Graft
using Graft.Backend
using GraftImpurity

# Qualified parallel-runtime pattern: Julia threads own the Graft task
# fan-out; backend pools stay serial to avoid nested oversubscription.
Graft.configure_parallel_runtime!(; blas_threads=1, strided_threads=1)
println("PARALLEL_RUNTIME julia_threads=", Threads.nthreads(),
    " blas_threads=1 strided_threads=1")

export BETA, NPOLES, GTAU_POINTS, SOLVE_TOL, FIT_SWEEPS, KRYLOV_DIM,
    KRYLOV_MAXITER, MAX_ROUNDS, WEIGHT_ATOL, WEIGHT_RTOL,
    ENRICHMENT_ATOL, ENRICHMENT_RTOL, BOOTSTRAP_TAU,
    BOOTSTRAP_KRYLOV_DIM, BOOTSTRAP_GRAM_ATOL, BOOTSTRAP_GRAM_RTOL,
    BOOTSTRAP_MAX_EXACT_BOND, BOOTSTRAP_MAX_EXACT_PAYLOAD,
    PREP_CAP, PREP_METHOD, PREP_METHOD_LABEL, progress,
    fit_bath, build_problem, build_model, max_bond_dimension,
    make_rde_policy, make_rde_evolver, make_bootstrap_evolver,
    make_two_site_policy, make_prep_evolver,
    checked_global_krylov_bootstrap!, checked_implicit_step!,
    trapezoid_system, source_lock_sha256, revision_lock_sha256,
    run_config_sha256, environment_fingerprint_sha256, atomic_write,
    atomic_write_or_validate, csv_row, parse_simple_csv,
    require_matched_cap, preparation_grid, propagation_grid

const U = parse(Float64, get(ENV, "GRAFT_RDE_U", "2.0"))
const EPSILON_D =
    parse(Float64, get(ENV, "GRAFT_RDE_EPSILON_D", string(-U / 2)))
const NPOLES = parse(Int, get(ENV, "GRAFT_RDE_NPOLES", "9"))
const NEPSILON = 20_001

function required_solver_environment(name::AbstractString)
    haskey(ENV, name) ||
        error("$name must come from the immutable logs/run-config.env")
    return ENV[name]
end

const BETA = parse(Float64, required_solver_environment("GRAFT_RDE_BETA"))
const NTAU_FIT = parse(Int, required_solver_environment("GRAFT_RDE_NTAU_FIT"))
const GTAU_POINTS = collect(range(0.0, BETA; length=17))
const SOLVE_TOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_SOLVE_TOL"))
const FIT_SWEEPS =
    parse(Int, required_solver_environment("GRAFT_RDE_FIT_SWEEPS"))
const KRYLOV_DIM =
    parse(Int, required_solver_environment("GRAFT_RDE_KRYLOV_DIM"))
const KRYLOV_MAXITER =
    parse(Int, required_solver_environment("GRAFT_RDE_KRYLOV_MAXITER"))
const MAX_ROUNDS =
    parse(Int, required_solver_environment("GRAFT_RDE_MAX_ROUNDS"))
const WEIGHT_ATOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_WEIGHT_ATOL"))
const WEIGHT_RTOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_WEIGHT_RTOL"))
const ENRICHMENT_ATOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_ENRICHMENT_ATOL"))
const ENRICHMENT_RTOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_ENRICHMENT_RTOL"))
const BOOTSTRAP_TAU =
    parse(Float64, required_solver_environment("GRAFT_RDE_BOOTSTRAP_TAU"))
const BOOTSTRAP_KRYLOV_DIM =
    parse(Int, required_solver_environment("GRAFT_RDE_BOOTSTRAP_KRYLOV_DIM"))
const BOOTSTRAP_GRAM_ATOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_BOOTSTRAP_GRAM_ATOL"))
const BOOTSTRAP_GRAM_RTOL =
    parse(Float64, required_solver_environment("GRAFT_RDE_BOOTSTRAP_GRAM_RTOL"))
const BOOTSTRAP_MAX_EXACT_BOND = parse(
    Int,
    required_solver_environment("GRAFT_RDE_BOOTSTRAP_MAX_EXACT_BOND"),
)
const BOOTSTRAP_MAX_EXACT_PAYLOAD = parse(
    Int,
    required_solver_environment("GRAFT_RDE_BOOTSTRAP_MAX_EXACT_PAYLOAD"),
)
const PREP_CAP =
    parse(Int, required_solver_environment("GRAFT_RDE_PREP_CAP"))
const PREP_METHOD =
    Symbol(required_solver_environment("GRAFT_RDE_PREP_METHOD"))
const PREP_METHOD_LABEL = PREP_METHOD === :two_site ?
    "TwoSiteLinearSolve" : "ResidualDrivenExpansion"
const STEP_FAILURE_POLICY =
    Symbol(required_solver_environment("GRAFT_RDE_STEP_FAILURE_POLICY"))
const TWO_SITE_TRUNC_RTOL = parse(
    Float64,
    required_solver_environment("GRAFT_RDE_TWO_SITE_TRUNC_RTOL"),
)
const EXACT_RESIDUAL_MAX_BOND = parse(
    Int,
    required_solver_environment("GRAFT_EXACT_RESIDUAL_MAX_BOND"),
)
const EXACT_RESIDUAL_MAX_PAYLOAD = parse(
    Int,
    required_solver_environment("GRAFT_EXACT_RESIDUAL_MAX_PAYLOAD"),
)

isfinite(SOLVE_TOL) && SOLVE_TOL > 0 ||
    error("GRAFT_RDE_SOLVE_TOL must be finite and positive")
FIT_SWEEPS >= 1 || error("GRAFT_RDE_FIT_SWEEPS must be positive")
KRYLOV_DIM >= 2 || error("GRAFT_RDE_KRYLOV_DIM must be at least 2")
KRYLOV_MAXITER >= 1 || error("GRAFT_RDE_KRYLOV_MAXITER must be positive")
MAX_ROUNDS >= 1 || error("GRAFT_RDE_MAX_ROUNDS must be positive")
isfinite(BOOTSTRAP_TAU) && BOOTSTRAP_TAU > 0 ||
    error("GRAFT_RDE_BOOTSTRAP_TAU must be finite and positive")
BOOTSTRAP_KRYLOV_DIM == 2 ||
    error("GRAFT_RDE_BOOTSTRAP_KRYLOV_DIM must equal the frozen value 2")
BOOTSTRAP_MAX_EXACT_BOND >= 1 ||
    error("GRAFT_RDE_BOOTSTRAP_MAX_EXACT_BOND must be positive")
BOOTSTRAP_MAX_EXACT_PAYLOAD >= 1 ||
    error("GRAFT_RDE_BOOTSTRAP_MAX_EXACT_PAYLOAD must be positive")
PREP_CAP >= 1 || error("GRAFT_RDE_PREP_CAP must be positive")
PREP_METHOD in (:residual_driven, :two_site) ||
    error("GRAFT_RDE_PREP_METHOD must be residual_driven or two_site")
STEP_FAILURE_POLICY in (:error, :warn) ||
    error("GRAFT_RDE_STEP_FAILURE_POLICY must be error or warn")
0 <= TWO_SITE_TRUNC_RTOL <= 1 ||
    error("GRAFT_RDE_TWO_SITE_TRUNC_RTOL must lie in [0, 1]")
isfinite(BETA) && BETA > 0 || error("GRAFT_RDE_BETA must be finite and positive")
NTAU_FIT >= 17 || error("GRAFT_RDE_NTAU_FIT must be at least 17")
for (name, value) in (
    ("GRAFT_RDE_WEIGHT_ATOL", WEIGHT_ATOL),
    ("GRAFT_RDE_WEIGHT_RTOL", WEIGHT_RTOL),
    ("GRAFT_RDE_ENRICHMENT_ATOL", ENRICHMENT_ATOL),
    ("GRAFT_RDE_ENRICHMENT_RTOL", ENRICHMENT_RTOL),
    ("GRAFT_RDE_BOOTSTRAP_GRAM_ATOL", BOOTSTRAP_GRAM_ATOL),
    ("GRAFT_RDE_BOOTSTRAP_GRAM_RTOL", BOOTSTRAP_GRAM_RTOL),
)
    isfinite(value) && value >= 0 ||
        error("$name must be finite and nonnegative")
end

function progress(stage; details="")
    println(
        "PROGRESS timestamp=$(Dates.now()) stage=$stage" *
        (isempty(details) ? "" : " $details"),
    )
    flush(stdout)
end

function semicircular_density(energy)
    abs(energy) <= 2 || return 0.0
    return sqrt(max(4 - energy^2, 0.0)) / (2pi)
end

function fermi_tau_kernel(tau, energy, beta)
    return energy > 0 ?
        exp(-tau * energy) / (1 + exp(-beta * energy)) :
        exp(-(tau - beta) * energy) / (1 + exp(beta * energy))
end

function continuum_delta_tau(tau, beta)
    energies = range(-2.0, 2.0; length=NEPSILON)
    step = 4.0 / (NEPSILON - 1)
    total = 0.0
    for (index, energy) in enumerate(energies)
        weight = (index == 1 || index == NEPSILON) ? 0.5 : 1.0
        total += weight * semicircular_density(energy) *
                 fermi_tau_kernel(tau, energy, beta)
    end
    return -step * total
end

function fit_bath()
    taus = collect(range(0.0, BETA; length=NTAU_FIT))
    scalar_samples = continuum_delta_tau.(taus, BETA)
    samples = Matrix{ComplexF64}[
        ComplexF64[sample 0; 0 sample] for sample in scalar_samples
    ]
    flavors = [:up, :down]
    layout = FlavorLayout(
        flavors,
        Dict(flavor => :impurity for flavor in flavors),
        Dict(:impurity => flavors);
        basis=:paper_2107_13941_spin,
    )
    partition = Partition(:spin => flavors)
    input = BathFitInput(
        layout,
        taus,
        :spin => samples;
        domain=:imaginary_time,
        statistics=:fermion,
        metadata=(;
            source=:paper_2107_13941_semicircular_bath,
            beta=BETA,
            half_bandwidth=2.0,
        ),
    )
    expansion = real_pole_bath_fit(
        input,
        ESPRITTauKernel(
            n_poles=NPOLES,
            pole_tolerance=1e-6,
            projection_tolerance=1e-12,
        ),
        partition,
    )
    fit = only(expansion.trace.fits)
    fit.selected_poles == NPOLES ||
        error("ESPRIT selected $(fit.selected_poles), expected $NPOLES poles")
    return expansion, fit
end

function build_problem(expansion)
    F = fermion_ops_z2()
    poles = expansion.poles.poles
    residues = expansion.poles.residues
    couplings_up = sqrt.(real.([residue[1, 1] for residue in residues]))
    couplings_down = sqrt.(real.([residue[2, 2] for residue in residues]))

    number_physical_modes = 2NPOLES + 2
    topo = mps_topology(number_physical_modes)
    phys = Dict(nodeid(topo, i) => F.P for i in 1:number_physical_modes)
    up_bath = [nodeid(topo, index) for index in 1:NPOLES]
    impurity_up = nodeid(topo, NPOLES + 1)
    impurity_down = nodeid(topo, NPOLES + 2)
    down_bath = [
        nodeid(topo, NPOLES + 2 + index) for index in 1:NPOLES
    ]

    H = OpSum()
    H += Term(
        U,
        SiteOp(impurity_up, :N, F.N),
        SiteOp(impurity_down, :N, F.N),
    )
    H += Term(EPSILON_D, SiteOp(impurity_up, :N, F.N))
    H += Term(EPSILON_D, SiteOp(impurity_down, :N, F.N))
    for index in 1:NPOLES
        H += Term(poles[index], SiteOp(up_bath[index], :N, F.N))
        H += Term(poles[index], SiteOp(down_bath[index], :N, F.N))
        H += Term(
            couplings_up[index],
            SiteOp(impurity_up, :Cd, F.Cd),
            SiteOp(up_bath[index], :C, F.C),
        )
        H += Term(
            couplings_up[index],
            SiteOp(impurity_up, :C, F.C),
            SiteOp(up_bath[index], :Cd, F.Cd),
        )
        H += Term(
            couplings_down[index],
            SiteOp(impurity_down, :Cd, F.Cd),
            SiteOp(down_bath[index], :C, F.C),
        )
        H += Term(
            couplings_down[index],
            SiteOp(impurity_down, :C, F.C),
            SiteOp(down_bath[index], :Cd, F.Cd),
        )
    end

    # U*n_up*n_down is positive, so occupied negative one-body eigenvalues
    # give a rigorous many-body lower bound used for a nonnegative shift.
    one_body = zeros(Float64, NPOLES + 1, NPOLES + 1)
    one_body[1, 1] = EPSILON_D
    for index in 1:NPOLES
        one_body[index + 1, index + 1] = poles[index]
        one_body[1, index + 1] = couplings_up[index]
        one_body[index + 1, 1] = couplings_up[index]
    end
    lower_bound =
        2sum(min(value, 0.0) for value in eigvals(Hermitian(one_body)))
    shifted_H = H + Term(
        -lower_bound,
        SiteOp(impurity_up, :I_shift, F.I),
    )
    problem = purification_problem(shifted_H, topo, phys; hermitian=true)
    return (; problem, F, impurity_up, lower_bound)
end

function build_model()
    progress("bath_fit_start"; details="beta=$BETA poles=$NPOLES")
    expansion, fit = fit_bath()
    progress(
        "bath_fit_complete";
        details="relative_l2=$(fit.physical_error.relative_l2)",
    )
    model = build_problem(expansion)
    progress(
        "problem_build_complete";
        details="nodes=$(nnodes(model.problem.topo_doubled)) lower_bound=$(model.lower_bound)",
    )
    return model, fit
end

function max_bond_dimension(psi)
    dims = Int[]
    topo = topology(psi)
    for child in 1:nnodes(topo)
        topo.parent[child] == 0 && continue
        push!(dims, dim(virtualspace(psi, child)))
    end
    return isempty(dims) ? 1 : maximum(dims)
end

function make_rde_policy(cap::Integer, number_edges::Integer)
    cap in (24, 32, 48) || cap == PREP_CAP ||
        throw(ArgumentError(
            "RDE cap must be one of 24, 32, 48, or the declared " *
            "production cap $PREP_CAP; got $cap"))
    number_edges >= 1 ||
        throw(ArgumentError("RDE benchmark needs at least one tree edge"))
    return ResidualDrivenExpansion(
        trunc=TruncationScheme(maxdim=Int(cap)),
        # No scoring-surrogate truncation: the authoritative residual is exact,
        # and this benchmark must not fail because a hidden surrogate was small.
        residual_trunc=TruncationScheme(),
        max_add=Int(cap),
        max_total_add=Int(number_edges * cap),
        max_edges=Int(number_edges),
        max_rounds=MAX_ROUNDS,
        schedule=:largest_uncovered,
        weight_atol=WEIGHT_ATOL,
        weight_rtol=WEIGHT_RTOL,
        enrichment_atol=ENRICHMENT_ATOL,
        enrichment_rtol=ENRICHMENT_RTOL,
        compression_atol=1e-12,
        compression_rtol=1e-10,
        residual_max_bond=EXACT_RESIDUAL_MAX_BOND,
        residual_max_payload=EXACT_RESIDUAL_MAX_PAYLOAD,
    )
end

function make_rde_evolver(cap::Integer, number_edges::Integer)
    return ImplicitLogTime(
        scheme=LogTrapezoid(),
        krylovdim=KRYLOV_DIM,
        maxiter=KRYLOV_MAXITER,
        tol=SOLVE_TOL,
        fit_nsweeps=FIT_SWEEPS,
        fit_tol=0.0,
        fit_verbose=true,
        normalize=false,
        energy_shift=false,
        expansion=make_rde_policy(cap, number_edges),
    )
end

function make_two_site_policy(cap::Integer)
    return TwoSiteLinearPolicy(
        trunc=TruncationScheme(maxdim=Int(cap), rtol=TWO_SITE_TRUNC_RTOL),
        sweeps=FIT_SWEEPS * (MAX_ROUNDS + 1),
        krylovdim=KRYLOV_DIM,
        maxiter=KRYLOV_MAXITER,
        local_tol=SOLVE_TOL,
        residual_tol=SOLVE_TOL,
    )
end

function make_prep_evolver(cap::Integer, number_edges::Integer)
    PREP_METHOD === :two_site || return make_rde_evolver(cap, number_edges)
    policy = make_two_site_policy(cap)
    return ImplicitLogTime(
        scheme=LogTrapezoid(),
        krylovdim=KRYLOV_DIM,
        maxiter=KRYLOV_MAXITER,
        tol=SOLVE_TOL,
        # The core constructor requires the sweep budget to be declared on
        # the evolver and the policy identically.
        fit_nsweeps=policy.sweeps,
        fit_tol=0.0,
        fit_verbose=true,
        normalize=false,
        energy_shift=false,
        two_site=policy,
    )
end

function make_bootstrap_evolver()
    return DirectKrylovBootstrap(
        krylovdim=BOOTSTRAP_KRYLOV_DIM,
        max_basis=BOOTSTRAP_KRYLOV_DIM,
        gram_atol=BOOTSTRAP_GRAM_ATOL,
        gram_rtol=BOOTSTRAP_GRAM_RTOL,
        max_exact_bond=BOOTSTRAP_MAX_EXACT_BOND,
        max_exact_payload=BOOTSTRAP_MAX_EXACT_PAYLOAD,
        optimize=true,
    )
end

function checked_global_krylov_bootstrap!(
        psi,
        hamiltonian,
        dtau;
        phase,
        cap)
    dtau > 0 || throw(ArgumentError("bootstrap dtau must be positive"))
    isapprox(dtau, BOOTSTRAP_TAU; atol=0, rtol=0) ||
        error(
            "$phase bootstrap dtau=$dtau does not match the immutable " *
            "BOOTSTRAP_TAU=$BOOTSTRAP_TAU",
        )
    initial_max_bond = max_bond_dimension(psi)
    evolver = make_bootstrap_evolver()
    step!(evolver, psi, hamiltonian, -dtau)
    info = evolver.last_info
    info === nothing && error("$phase bootstrap returned no last_info")
    all(
        isfinite,
        (
            info.gram_threshold,
            info.gram_condition,
            info.initial_projection_error,
            info.projected_residual,
        ),
    ) || error("$phase bootstrap returned non-finite diagnostics")
    info.retained_dimension >= 2 ||
        error(
            "$phase bootstrap retained only $(info.retained_dimension) " *
            "global Krylov direction(s)",
        )
    info.initial_projection_error <= 1e-10 ||
        error(
            "$phase bootstrap initial projection error " *
            "$(info.initial_projection_error) exceeds 1e-10",
        )
    final_max_bond = max_bond_dimension(psi)
    final_max_bond > initial_max_bond ||
        error(
            "$phase bootstrap did not open the bond manifold: " *
            "$initial_max_bond -> $final_max_bond",
        )
    final_max_bond <= cap ||
        error(
            "$phase bootstrap final max bond $final_max_bond exceeds " *
            "the matched cap $cap",
        )
    @printf(
        "GLOBAL_KRYLOV_BOOTSTRAP_RESULT phase=%s dtau=%.12g requested_dimension=%d retained_dimension=%d action_count=%d projected_residual=%.9e initial_projection_error=%.9e initial_maxbond=%d final_maxbond=%d cap=%d\n",
        phase,
        dtau,
        info.requested_dimension,
        info.retained_dimension,
        info.action_count,
        info.projected_residual,
        info.initial_projection_error,
        initial_max_bond,
        final_max_bond,
        cap,
    )
    flush(stdout)
    return info
end

function checked_implicit_step!(evolver, psi, hamiltonian, dtau;
                                phase, step_index, tau_right)
    dtau > 0 || throw(ArgumentError("implicit dtau must be positive"))
    step!(evolver, psi, hamiltonian, -dtau)
    info = evolver.last_info
    info === nothing &&
        error("$phase step $step_index returned no last_info")
    isfinite(info.normres) ||
        error("$phase step $step_index returned non-finite physical residual")
    if info.converged != 1 || info.normres > SOLVE_TOL
        STEP_FAILURE_POLICY === :warn ||
            error(
                "$phase implicit step $step_index failed at tau=$tau_right: " *
                "converged=$(info.converged) " *
                "physical_residual=$(info.normres) tolerance=$SOLVE_TOL",
            )
        @printf(
            "IMPLICIT_STEP_WARNING phase=%s step=%d tau=%.12g dtau=%.12g converged=%d physical_residual=%.9e tolerance=%.9e maxbond=%d\n",
            phase,
            step_index,
            tau_right,
            dtau,
            info.converged,
            info.normres,
            SOLVE_TOL,
            max_bond_dimension(psi),
        )
    end
    @printf(
        "IMPLICIT_RESULT phase=%s step=%d tau=%.12g dtau=%.12g converged=%d physical_residual=%.9e numiter=%d numops=%d maxbond=%d\n",
        phase,
        step_index,
        tau_right,
        dtau,
        info.converged,
        info.normres,
        info.numiter,
        info.numops,
        max_bond_dimension(psi),
    )
    flush(stdout)
    return info
end

function trapezoid_system(psi, hamiltonian, dtau)
    dtau > 0 || throw(ArgumentError("trapezoid dtau must be positive"))
    old = copy(psi)
    acted = apply(hamiltonian, old; center=center(old))
    rhs = exact_linear_combination(
        [old, acted],
        [one(eltype(old)), -dtau / 2];
        max_bond=4096,
        max_payload=100_000_000,
    )
    return (; initial=old, rhs, a0=one(eltype(old)), a1=dtau / 2)
end

function source_lock_sha256(run_root::AbstractString)
    path = joinpath(run_root, "logs", "source-lock.sha256")
    isfile(path) || error("missing immutable source lock: $path")
    fields = split(strip(read(path, String)))
    length(fields) >= 1 || error("empty immutable source lock: $path")
    return fields[1]
end

function revision_lock_sha256(run_root::AbstractString)
    path = joinpath(run_root, "logs", "source-revisions.sha256")
    isfile(path) || error("missing immutable revision lock: $path")
    fields = split(strip(read(path, String)))
    length(fields) >= 1 || error("empty immutable revision lock: $path")
    return fields[1]
end

function run_config_sha256(run_root::AbstractString)
    path = joinpath(run_root, "logs", "run-config.sha256")
    isfile(path) || error("missing immutable run-config lock: $path")
    fields = split(strip(read(path, String)))
    length(fields) >= 1 || error("empty immutable run-config lock: $path")
    return fields[1]
end

function environment_fingerprint_sha256(run_root::AbstractString)
    path = joinpath(
        run_root,
        "logs",
        "environment-fingerprint.sha256",
    )
    isfile(path) || error("missing immutable environment fingerprint: $path")
    fields = split(strip(read(path, String)))
    length(fields) >= 1 ||
        error("empty immutable environment fingerprint: $path")
    return fields[1]
end

function atomic_write(path::AbstractString, content::AbstractString)
    ispath(path) && error("refusing to overwrite immutable output: $path")
    mkpath(dirname(path))
    temporary = path * ".tmp." * string(getpid())
    open(temporary, "w") do io
        write(io, content)
        flush(io)
    end
    mv(temporary, path)
    return path
end

function atomic_write_or_validate(
        path::AbstractString,
        content::AbstractString)
    if isfile(path)
        read(path, String) == content ||
            error("existing immutable output differs from recomputed content: $path")
        return path
    end
    return atomic_write(path, content)
end

function csv_row(values)
    fields = String[]
    for value in values
        text = string(value)
        occursin(',', text) &&
            error("simple benchmark CSV field contains a comma: $text")
        push!(fields, text)
    end
    return join(fields, ",")
end

function parse_simple_csv(
        path::AbstractString;
        allow_header_only::Bool=false)
    lines = filter(!isempty, strip.(readlines(path)))
    isempty(lines) && error("CSV is empty: $path")
    length(lines) >= 2 || allow_header_only ||
        error("CSV has no data rows: $path")
    header = split(first(lines), ",")
    length(lines) == 1 &&
        return header, Dict{String,String}[]
    rows = Dict{String,String}[]
    for line in lines[2:end]
        values = split(line, ",")
        length(values) == length(header) ||
            error("malformed CSV row in $path: $line")
        push!(rows, Dict(header .=> values))
    end
    return header, rows
end

function require_matched_cap(match_root::AbstractString)
    cap_path = joinpath(match_root, "outputs", "matched_cap.txt")
    merged_path =
        joinpath(match_root, "outputs", "first_step_diagnostics.csv")
    isfile(cap_path) ||
        error("fail-closed: no matched first-step cap at $cap_path")
    isfile(merged_path) ||
        error("fail-closed: missing paired diagnostic table $merged_path")
    cap = parse(Int, strip(read(cap_path, String)))
    cap in (24, 32, 48) ||
        error("fail-closed: invalid matched cap $cap")
    _, rows = parse_simple_csv(merged_path)
    row_index = findfirst(row -> parse(Int, row["cap"]) == cap, rows)
    row_index === nothing &&
        error("fail-closed: matched cap $cap absent from diagnostic table")
    row = rows[row_index]
    row["classification"] == "matched" ||
        error("fail-closed: cap $cap classification is $(row["classification"])")
    row["run_config_sha256"] == run_config_sha256(match_root) ||
        error("fail-closed: matched-cap run-config hash is inconsistent")
    row["revision_lock_sha256"] == revision_lock_sha256(match_root) ||
        error("fail-closed: matched-cap revision lock is inconsistent")
    row["environment_fingerprint_sha256"] ==
        environment_fingerprint_sha256(match_root) ||
        error("fail-closed: matched-cap environment lock is inconsistent")
    parse(Bool, row["residual_driven_converged"]) ||
        error("fail-closed: RDE did not converge at cap $cap")
    parse(Bool, row["two_site_converged"]) ||
        error("fail-closed: two-site diagnostic did not converge at cap $cap")
    parse(Float64, row["residual_driven_residual"]) <= SOLVE_TOL ||
        error("fail-closed: RDE exact physical residual exceeds tolerance")
    parse(Float64, row["two_site_residual"]) <= SOLVE_TOL ||
        error("fail-closed: two-site exact physical residual exceeds tolerance")
    return cap
end

function preparation_grid()
    logarithmic = logarithmic_time_grid(0.05, BETA / 2)
    measurement_checkpoints = GTAU_POINTS ./ 2
    return sort(unique(vcat(logarithmic, measurement_checkpoints)))
end

function propagation_grid(tau::Real)
    tau_value = Float64(tau)
    tau_value == 0 && return [0.0]
    tau_value >= 0.05 ||
        return [0.0, tau_value]
    return logarithmic_time_grid(0.05, tau_value)
end

end
