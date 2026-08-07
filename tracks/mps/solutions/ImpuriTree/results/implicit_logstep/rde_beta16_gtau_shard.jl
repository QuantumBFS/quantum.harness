include(joinpath(@__DIR__, "rde_beta16_common.jl"))
using .RDEBeta16Common

using Graft
using LinearAlgebra
using Printf

const GTAU_SCHEMA = 4

function validate_preparation(prepared, prep_root, match_root, cap)
    metadata = prepared.metadata
    hasproperty(metadata, :phase) &&
        metadata.phase == :rde_beta16_preparation ||
        error("preparation checkpoint has the wrong phase")
    metadata.cap == cap ||
        error("preparation cap $(metadata.cap) != production cap $cap")
    hasproperty(metadata, :method) &&
        metadata.method == Symbol(PREP_METHOD_LABEL) ||
        error(
            "preparation evolution method mismatch: expected " *
            PREP_METHOD_LABEL,
        )
    metadata.source_lock_sha256 == source_lock_sha256(prep_root) ||
        error("preparation source lock mismatch")
    metadata.revision_lock_sha256 == revision_lock_sha256(prep_root) ||
        error("preparation revision lock mismatch")
    metadata.run_config_sha256 == run_config_sha256(prep_root) ||
        error("preparation run-config mismatch")
    metadata.environment_fingerprint_sha256 ==
        environment_fingerprint_sha256(prep_root) ||
        error("preparation environment fingerprint mismatch")
    metadata.matched_source_lock_sha256 == source_lock_sha256(match_root) ||
        error("preparation matched-source lock mismatch")
    metadata.matched_revision_lock_sha256 ==
        revision_lock_sha256(match_root) ||
        error("preparation matched revision lock mismatch")
    metadata.matched_run_config_sha256 == run_config_sha256(match_root) ||
        error("preparation matched run-config mismatch")
    metadata.matched_environment_fingerprint_sha256 ==
        environment_fingerprint_sha256(match_root) ||
        error("preparation matched environment fingerprint mismatch")
    metadata.schema == 4 ||
        error("preparation checkpoint schema lacks method provenance")
    hasproperty(metadata, :bootstrap_method) &&
        metadata.bootstrap_method == :DirectKrylovBootstrap ||
        error("preparation did not use the required global-Krylov bootstrap")
    metadata.bootstrap_tau == BOOTSTRAP_TAU ||
        error("preparation bootstrap tau mismatch")
    metadata.bootstrap_krylov_dim == BOOTSTRAP_KRYLOV_DIM ||
        error("preparation bootstrap Krylov dimension mismatch")
    trajectory = prepared.state.trajectory
    trajectory.final.beta == BETA ||
        error("preparation beta mismatch")
    Set(keys(trajectory.checkpoints)) == Set(GTAU_POINTS) ||
        error("preparation does not contain all 17 beta checkpoints")
    provenance = trajectory.metadata
    hasproperty(provenance, :bootstrap_method) &&
        provenance.bootstrap_method == :DirectKrylovBootstrap ||
        error("preparation trajectory lacks global-Krylov provenance")
    provenance.bootstrap_tau == BOOTSTRAP_TAU ||
        error("preparation trajectory bootstrap tau mismatch")
    provenance.environment_fingerprint_sha256 ==
        environment_fingerprint_sha256(prep_root) ||
        error("preparation trajectory environment fingerprint mismatch")
    provenance.matched_environment_fingerprint_sha256 ==
        environment_fingerprint_sha256(match_root) ||
        error("preparation trajectory matched environment fingerprint mismatch")
    return trajectory
end

function point_metadata(run_root, prep_root, cap, point_index, tau)
    return (;
        schema=GTAU_SCHEMA,
        phase=:rde_beta16_gtau_point,
        beta=BETA,
        cap,
        point_index,
        tau,
        solve_tol=SOLVE_TOL,
        fit_sweeps=FIT_SWEEPS,
        krylov_dim=KRYLOV_DIM,
        krylov_maxiter=KRYLOV_MAXITER,
        max_rounds=MAX_ROUNDS,
        preparation_bootstrap_method=:DirectKrylovBootstrap,
        preparation_bootstrap_tau=BOOTSTRAP_TAU,
        preparation_bootstrap_application_count=1,
        branch_manifold_source=:preparation_checkpoint_virtual_spaces,
        branch_bootstrap_application_count=0,
        branch_evolution_method=Symbol(PREP_METHOD_LABEL),
        source_lock_sha256=source_lock_sha256(run_root),
        revision_lock_sha256=revision_lock_sha256(run_root),
        run_config_sha256=run_config_sha256(run_root),
        environment_fingerprint_sha256=
            environment_fingerprint_sha256(run_root),
        preparation_source_lock_sha256=source_lock_sha256(prep_root),
        preparation_revision_lock_sha256=revision_lock_sha256(prep_root),
        preparation_run_config_sha256=run_config_sha256(prep_root),
        preparation_environment_fingerprint_sha256=
            environment_fingerprint_sha256(prep_root),
        preparation_root=abspath(prep_root),
        sign_convention=:Gtau_equals_minus_correlator,
    )
end

function validate_point_metadata(actual, expected)
    for field in keys(expected)
        hasproperty(actual, field) ||
            error("Gtau checkpoint metadata lacks $field")
        getproperty(actual, field) == getproperty(expected, field) ||
            error("Gtau checkpoint metadata mismatch for $field")
    end
end

function existing_point_is_valid(
        path,
        point_index,
        tau,
        cap,
        source_lock,
        revision_lock,
        config_hash,
        environment_fingerprint)
    _, rows = parse_simple_csv(path)
    length(rows) == 1 || error("point output must contain exactly one row: $path")
    row = only(rows)
    parse(Int, row["point_index"]) == point_index ||
        error("existing point index mismatch")
    parse(Float64, row["tau"]) == tau ||
        error("existing point tau mismatch")
    parse(Int, row["cap"]) == cap || error("existing point cap mismatch")
    row["source_lock_sha256"] == source_lock ||
        error("existing point source lock mismatch")
    row["revision_lock_sha256"] == revision_lock ||
        error("existing point revision lock mismatch")
    row["run_config_sha256"] == config_hash ||
        error("existing point run-config mismatch")
    row["environment_fingerprint_sha256"] == environment_fingerprint ||
        error("existing point environment fingerprint mismatch")
    row["preparation_environment_fingerprint_sha256"] ==
        environment_fingerprint ||
        error("existing point preparation environment fingerprint mismatch")
    row["sign_convention"] == "Gtau_equals_minus_correlator" ||
        error("existing point sign convention mismatch")
    row["preparation_bootstrap_method"] == "DirectKrylovBootstrap" ||
        error("existing point preparation bootstrap mismatch")
    parse(Float64, row["preparation_bootstrap_tau"]) == BOOTSTRAP_TAU ||
        error("existing point preparation bootstrap tau mismatch")
    parse(Int, row["preparation_bootstrap_application_count"]) == 1 ||
        error("existing point preparation bootstrap count mismatch")
    row["branch_manifold_source"] ==
        "preparation_checkpoint_virtual_spaces" ||
        error("existing point branch manifold source mismatch")
    parse(Int, row["branch_bootstrap_application_count"]) == 0 ||
        error("existing point unexpectedly ran a branch bootstrap")
    row["branch_evolution_method"] == PREP_METHOD_LABEL ||
        error("existing point branch evolution method mismatch")
    parse(Bool, row["all_implicit_steps_converged"]) ||
        error("existing point contains an unconverged implicit step")
    return nothing
end

function run_point(run_root, prep_root, trajectory, model, cap, point_index)
    tau = GTAU_POINTS[point_index]
    label = lpad(string(point_index), 2, '0')
    output = joinpath(run_root, "outputs", "points", "gtau-$label.csv")
    source_lock = source_lock_sha256(run_root)
    if isfile(output)
        existing_point_is_valid(
            output,
            point_index,
            tau,
            cap,
            source_lock,
            revision_lock_sha256(run_root),
            run_config_sha256(run_root),
            environment_fingerprint_sha256(run_root),
        )
        progress(
            "gtau_point_already_complete";
            details="point=$point_index tau=$tau",
        )
        return
    end

    checkpoint_path =
        joinpath(run_root, "outputs", "checkpoints", "gtau-$label.jld2")
    mkpath(dirname(checkpoint_path))
    metadata = point_metadata(run_root, prep_root, cap, point_index, tau)
    state_b = state_at(trajectory, BETA - tau; atol=1e-12)
    bra = apply_local(
        state_b.psi,
        adjoint(model.F.C),
        model.impurity_up,
    )
    grid = propagation_grid(tau)
    number_steps = length(grid) - 1
    number_edges = nnodes(topology(state_b.psi)) - 1
    evolver = make_prep_evolver(cap, number_edges)

    if isfile(checkpoint_path)
        saved = resume(checkpoint_path)
        validate_point_metadata(saved.metadata, metadata)
        ket = saved.state.ket
        ket_log_amplitude = saved.state.ket_log_amplitude
        next_step = saved.state.next_step
        maximum_step_residual = saved.state.maximum_step_residual
        progress(
            "gtau_point_resumed";
            details="point=$point_index tau=$tau next_step=$next_step",
        )
    else
        ket = apply_local(
            state_b.psi,
            model.F.Cd,
            model.impurity_up,
        )
        ket_norm = norm(ket)
        isfinite(ket_norm) && ket_norm > 0 ||
            error("Gtau point $point_index has invalid inserted-state norm")
        Graft.normalize!(ket)
        ket_log_amplitude = log(ket_norm)
        next_step = 1
        maximum_step_residual = 0.0
        checkpoint!(
            (;
                ket,
                ket_log_amplitude,
                next_step,
                maximum_step_residual,
            ),
            checkpoint_path;
            keep=2,
            metadata,
        )
    end

    1 <= next_step <= number_steps + 1 ||
        error("invalid Gtau restart step $next_step")
    for step_index in next_step:number_steps
        left = grid[step_index]
        right = grid[step_index + 1]
        dtau = right - left
        info = checked_implicit_step!(
            evolver,
            ket,
            model.problem.K,
            dtau;
            phase="gtau-$label",
            step_index,
            tau_right=right,
        )
        maximum_step_residual = max(maximum_step_residual, info.normres)
        ket_norm = norm(ket)
        isfinite(ket_norm) && ket_norm > 0 ||
            error("Gtau point $point_index step $step_index has invalid norm")
        Graft.normalize!(ket)
        ket_log_amplitude += log(ket_norm)
        checkpoint!(
            (;
                ket,
                ket_log_amplitude,
                next_step=step_index + 1,
                maximum_step_residual,
            ),
            checkpoint_path;
            keep=2,
            metadata,
        )
    end

    correlator = exp(
        2state_b.log_amplitude +
        ket_log_amplitude -
        2trajectory.final.log_amplitude,
    ) * inner(bra, ket)
    gtau = -correlator
    all(isfinite, (real(correlator), imag(correlator), real(gtau), imag(gtau))) ||
        error("Gtau point $point_index produced a non-finite value")
    gtau == -correlator || error("Gtau sign convention was not applied")

    header = csv_row((
        "point_index",
        "tau",
        "cap",
        "correlator_real",
        "correlator_imag",
        "gtau_real",
        "gtau_imag",
        "implicit_steps",
        "all_implicit_steps_converged",
        "maximum_step_physical_residual",
        "physical_residual_tolerance",
        "fit_sweeps",
        "krylov_dim",
        "krylov_maxiter",
        "max_rounds",
        "preparation_bootstrap_method",
        "preparation_bootstrap_tau",
        "preparation_bootstrap_application_count",
        "branch_manifold_source",
        "branch_bootstrap_application_count",
        "branch_evolution_method",
        "sign_convention",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
        "environment_fingerprint_sha256",
        "preparation_source_lock_sha256",
        "preparation_revision_lock_sha256",
        "preparation_run_config_sha256",
        "preparation_environment_fingerprint_sha256",
    ))
    row = csv_row((
        point_index,
        @sprintf("%.17g", tau),
        cap,
        @sprintf("%.17g", real(correlator)),
        @sprintf("%.17g", imag(correlator)),
        @sprintf("%.17g", real(gtau)),
        @sprintf("%.17g", imag(gtau)),
        number_steps,
        true,
        @sprintf("%.17g", maximum_step_residual),
        @sprintf("%.17g", SOLVE_TOL),
        FIT_SWEEPS,
        KRYLOV_DIM,
        KRYLOV_MAXITER,
        MAX_ROUNDS,
        "DirectKrylovBootstrap",
        @sprintf("%.17g", BOOTSTRAP_TAU),
        1,
        "preparation_checkpoint_virtual_spaces",
        0,
        PREP_METHOD_LABEL,
        "Gtau_equals_minus_correlator",
        source_lock,
        revision_lock_sha256(run_root),
        run_config_sha256(run_root),
        environment_fingerprint_sha256(run_root),
        source_lock_sha256(prep_root),
        revision_lock_sha256(prep_root),
        run_config_sha256(prep_root),
        environment_fingerprint_sha256(prep_root),
    ))
    atomic_write(output, header * "\n" * row * "\n")
    progress(
        "gtau_point_complete";
        details=(
            "point=$point_index tau=$tau gtau=$gtau " *
            "max_physical_residual=$maximum_step_residual"
        ),
    )
end

function main()
    length(ARGS) == 4 ||
        error(
            "usage: rde_beta16_gtau_shard.jl " *
            "RUN_ROOT PREP_ROOT WORKER_INDEX WORKER_COUNT",
        )
    run_root = abspath(ARGS[1])
    prep_root = abspath(ARGS[2])
    worker_index = parse(Int, ARGS[3])
    worker_count = parse(Int, ARGS[4])
    worker_count == 8 ||
        error("the registered Gtau fanout requires exactly 8 workers")
    0 <= worker_index < worker_count ||
        error("worker index must lie in 0:$(worker_count - 1)")

    prep_match_root = get(ENV, "GRAFT_RDE_MATCH_ROOT") do
        error("GRAFT_RDE_MATCH_ROOT must identify the first-step run")
    end
    matched_cap = require_matched_cap(prep_match_root)
    cap = PREP_CAP
    cap >= matched_cap ||
        error(
            "fail-closed: production cap $cap is below the matched " *
            "first-step cap $matched_cap",
        )
    run_lock = source_lock_sha256(run_root)
    run_lock == source_lock_sha256(prep_root) ||
        println(
            "PREP_ROOT_NOTE source locks differ: consuming a preparation " *
            "staged from an earlier harness revision",
        )
    revision_lock = revision_lock_sha256(run_root)
    revision_lock == revision_lock_sha256(prep_root) ||
        error("fail-closed: Gtau and preparation revision locks differ")
    revision_lock == revision_lock_sha256(prep_match_root) ||
        println(
            "MATCH_ROOT_NOTE revision locks differ: reusing matched " *
            "evidence produced from an earlier committed revision",
        )
    config_hash = run_config_sha256(run_root)
    config_hash == run_config_sha256(prep_root) ||
        error("fail-closed: Gtau and preparation run configs differ")
    environment_fingerprint =
        environment_fingerprint_sha256(run_root)
    environment_fingerprint ==
        environment_fingerprint_sha256(prep_root) ||
        error("fail-closed: Gtau and preparation environments differ")
    # The matched first-step evidence may be reused across harness/config
    # updates; only the committed source revisions above are load-bearing.
    run_lock == source_lock_sha256(prep_match_root) ||
        println(
            "MATCH_ROOT_NOTE source locks differ: reusing matched evidence " *
            "produced by an earlier harness revision",
        )
    config_hash == run_config_sha256(prep_match_root) ||
        println(
            "MATCH_ROOT_NOTE run configs differ: reusing matched evidence " *
            "produced under an earlier solver config",
        )
    environment_fingerprint ==
        environment_fingerprint_sha256(prep_match_root) ||
        println(
            "MATCH_ROOT_NOTE environment fingerprints differ: reusing " *
            "matched evidence from an earlier environment",
        )
    prepared = resume(joinpath(prep_root, "outputs", "preparation-final.jld2"))
    trajectory =
        validate_preparation(prepared, prep_root, prep_match_root, cap)
    model, _ = build_model()

    point_indices = collect((worker_index + 1):worker_count:length(GTAU_POINTS))
    progress(
        "gtau_shard_start";
        details="worker=$worker_index workers=$worker_count points=$point_indices",
    )
    for point_index in point_indices
        run_point(
            run_root,
            prep_root,
            trajectory,
            model,
            cap,
            point_index,
        )
    end
    progress("gtau_shard_complete"; details="worker=$worker_index")
end

main()
