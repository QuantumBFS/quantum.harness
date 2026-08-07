include(joinpath(@__DIR__, "rde_beta16_common.jl"))
using .RDEBeta16Common

using Graft
using LinearAlgebra
using Printf

const PREPARATION_SCHEMA = 4

function checkpoint_metadata(run_root, match_root, cap, matched_cap)
    return (;
        schema=PREPARATION_SCHEMA,
        phase=:rde_beta16_preparation,
        beta=BETA,
        poles=NPOLES,
        cap,
        matched_cap,
        method=Symbol(PREP_METHOD_LABEL),
        solve_tol=SOLVE_TOL,
        fit_sweeps=FIT_SWEEPS,
        krylov_dim=KRYLOV_DIM,
        krylov_maxiter=KRYLOV_MAXITER,
        max_rounds=MAX_ROUNDS,
        bootstrap_method=:DirectKrylovBootstrap,
        bootstrap_tau=BOOTSTRAP_TAU,
        bootstrap_krylov_dim=BOOTSTRAP_KRYLOV_DIM,
        bootstrap_gram_atol=BOOTSTRAP_GRAM_ATOL,
        bootstrap_gram_rtol=BOOTSTRAP_GRAM_RTOL,
        bootstrap_max_exact_bond=BOOTSTRAP_MAX_EXACT_BOND,
        bootstrap_max_exact_payload=BOOTSTRAP_MAX_EXACT_PAYLOAD,
        source_lock_sha256=source_lock_sha256(run_root),
        revision_lock_sha256=revision_lock_sha256(run_root),
        run_config_sha256=run_config_sha256(run_root),
        environment_fingerprint_sha256=
            environment_fingerprint_sha256(run_root),
        matched_source_lock_sha256=source_lock_sha256(match_root),
        matched_revision_lock_sha256=revision_lock_sha256(match_root),
        matched_run_config_sha256=run_config_sha256(match_root),
        matched_environment_fingerprint_sha256=
            environment_fingerprint_sha256(match_root),
        match_root=abspath(match_root),
    )
end

function validate_metadata(actual, expected)
    for field in keys(expected)
        hasproperty(actual, field) ||
            error("preparation checkpoint metadata lacks $field")
        getproperty(actual, field) == getproperty(expected, field) ||
            error(
                "preparation checkpoint $field mismatch: " *
                "$(getproperty(actual, field)) != $(getproperty(expected, field))",
            )
    end
end

function main()
    length(ARGS) == 2 ||
        error("usage: rde_beta16_prepare.jl RUN_ROOT MATCH_ROOT")
    run_root = abspath(ARGS[1])
    match_root = abspath(ARGS[2])
    matched_cap = require_matched_cap(match_root)
    cap = PREP_CAP
    cap >= matched_cap ||
        error(
            "fail-closed: production cap $cap is below the matched " *
            "first-step cap $matched_cap",
        )
    revision_lock_sha256(run_root) == revision_lock_sha256(match_root) ||
        println(
            "MATCH_ROOT_NOTE revision locks differ: reusing matched " *
            "evidence produced from an earlier committed revision",
        )
    # The matched first-step evidence may be reused across harness/config
    # updates; only the committed source revisions above are load-bearing.
    source_lock_sha256(run_root) == source_lock_sha256(match_root) ||
        println(
            "MATCH_ROOT_NOTE source locks differ: reusing matched evidence " *
            "produced by an earlier harness revision",
        )
    run_config_sha256(run_root) == run_config_sha256(match_root) ||
        println(
            "MATCH_ROOT_NOTE run configs differ: reusing matched evidence " *
            "produced under an earlier solver config",
        )
    environment_fingerprint_sha256(run_root) ==
        environment_fingerprint_sha256(match_root) ||
        println(
            "MATCH_ROOT_NOTE environment fingerprints differ: reusing " *
            "matched evidence from an earlier environment",
        )
    metadata = checkpoint_metadata(run_root, match_root, cap, matched_cap)
    checkpoint_path =
        joinpath(run_root, "outputs", "checkpoints", "preparation.jld2")
    final_path = joinpath(run_root, "outputs", "preparation-final.jld2")
    summary_path = joinpath(run_root, "outputs", "preparation-summary.csv")
    mkpath(dirname(checkpoint_path))

    model, fit = build_model()
    grid = preparation_grid()
    number_edges = nnodes(model.problem.topo_doubled) - 1
    evolver = make_prep_evolver(cap, number_edges)

    if isfile(final_path)
        completed = resume(final_path)
        validate_metadata(completed.metadata, metadata)
        completed.state.trajectory.final.beta == BETA ||
            error("existing final preparation has the wrong beta")
        isfile(summary_path) ||
            error("existing final preparation lacks its summary")
        _, summary_rows = parse_simple_csv(summary_path)
        length(summary_rows) == 1 ||
            error("existing preparation summary has extra rows")
        summary_row = only(summary_rows)
        summary_row["run_config_sha256"] == metadata.run_config_sha256 ||
            error("existing preparation summary run-config mismatch")
        summary_row["revision_lock_sha256"] ==
            metadata.revision_lock_sha256 ||
            error("existing preparation summary revision-lock mismatch")
        summary_row["environment_fingerprint_sha256"] ==
            metadata.environment_fingerprint_sha256 ||
            error(
                "existing preparation summary environment fingerprint mismatch",
            )
        progress(
            "preparation_already_complete";
            details="cap=$cap checkpoint=$final_path",
        )
        return
    end

    if isfile(checkpoint_path)
        saved = resume(checkpoint_path)
        validate_metadata(saved.metadata, metadata)
        psi = saved.state.psi
        log_amplitude = saved.state.log_amplitude
        next_step = saved.state.next_step
        checkpoints = saved.state.checkpoints
        maximum_step_residual = saved.state.maximum_step_residual
        bootstrap_summary = saved.state.bootstrap_summary
        bootstrap_application_count =
            saved.state.bootstrap_application_count
        progress(
            "preparation_resumed";
            details="next_step=$next_step cap=$cap maxbond=$(max_bond_dimension(psi))",
        )
    else
        state0 = infinite_temperature_state(model.problem)
        psi = copy(state0.psi)
        log_amplitude = 0.0
        next_step = 1
        checkpoints = Dict{Float64,typeof(state0)}(0.0 => state0)
        maximum_step_residual = 0.0
        bootstrap_summary = nothing
        bootstrap_application_count = 0
        checkpoint!(
            (;
                psi,
                log_amplitude,
                next_step,
                checkpoints,
                maximum_step_residual,
                bootstrap_summary,
                bootstrap_application_count,
            ),
            checkpoint_path;
            keep=2,
            metadata,
        )
    end

    number_steps = length(grid) - 1
    1 <= next_step <= number_steps + 1 ||
        error("invalid preparation restart step $next_step")
    if next_step == 1
        bootstrap_summary === nothing ||
            error("pending preparation already has bootstrap diagnostics")
        bootstrap_application_count == 0 ||
            error("pending preparation has a nonzero bootstrap count")
    else
        bootstrap_summary === nothing &&
            error("resumed preparation lacks bootstrap diagnostics")
        bootstrap_application_count == 1 ||
            error("resumed preparation bootstrap count is not one")
    end
    for step_index in next_step:number_steps
        left = grid[step_index]
        right = grid[step_index + 1]
        dtau = right - left
        if step_index == 1
            left == 0.0 ||
                error("the global-Krylov bootstrap must start at tau=0")
            initial_max_bond = max_bond_dimension(psi)
            info = checked_global_krylov_bootstrap!(
                psi,
                model.problem.K,
                dtau;
                phase="preparation",
                cap,
            )
            bootstrap_summary = (;
                method=:DirectKrylovBootstrap,
                tau_right=right,
                dtau,
                requested_dimension=info.requested_dimension,
                raw_dimension=info.raw_dimension,
                retained_dimension=info.retained_dimension,
                discarded_dimension=info.discarded_dimension,
                action_count=info.action_count,
                projected_residual=info.projected_residual,
                gram_condition=info.gram_condition,
                initial_projection_error=info.initial_projection_error,
                initial_max_bond,
                final_max_bond=max_bond_dimension(psi),
            )
            bootstrap_application_count = 1
        else
            info = checked_implicit_step!(
                evolver,
                psi,
                model.problem.K,
                dtau;
                phase="preparation",
                step_index,
                tau_right=right,
            )
            maximum_step_residual =
                max(maximum_step_residual, info.normres)
        end
        state_norm = norm(psi)
        isfinite(state_norm) && state_norm > 0 ||
            error("preparation step $step_index produced invalid norm $state_norm")
        Graft.normalize!(psi)
        log_amplitude += log(state_norm)

        physical_beta = 2right
        if any(isapprox(physical_beta, target; atol=1e-12, rtol=0)
               for target in GTAU_POINTS)
            beta_key = only(
                target for target in GTAU_POINTS
                if isapprox(physical_beta, target; atol=1e-12, rtol=0)
            )
            logZ = model.problem.log_hilbert_dim + 2log_amplitude
            checkpoints[beta_key] = PurifiedState(
                copy(psi),
                beta_key,
                log_amplitude,
                logZ,
                (;
                    source=:rde_beta16_preparation,
                    cap,
                    lower_bound=model.lower_bound,
                    source_lock_sha256=metadata.source_lock_sha256,
                    revision_lock_sha256=metadata.revision_lock_sha256,
                    run_config_sha256=metadata.run_config_sha256,
                    environment_fingerprint_sha256=
                        metadata.environment_fingerprint_sha256,
                ),
            )
        end

        checkpoint!(
            (;
                psi,
                log_amplitude,
                next_step=step_index + 1,
                checkpoints,
                maximum_step_residual,
                bootstrap_summary,
                bootstrap_application_count,
            ),
            checkpoint_path;
            keep=2,
            metadata,
        )
    end

    Set(keys(checkpoints)) == Set(GTAU_POINTS) ||
        error(
            "preparation checkpoint set mismatch: got $(sort(collect(keys(checkpoints))))",
        )
    final_state = checkpoints[BETA]
    bootstrap_summary === nothing &&
        error("preparation completed without a global-Krylov bootstrap")
    bootstrap_application_count == 1 ||
        error("preparation bootstrap application count is not one")
    trajectory = PurificationTrajectory(
        final_state,
        checkpoints,
        grid,
        (;
            source=:rde_beta16_preparation,
            cap,
            source_lock_sha256=metadata.source_lock_sha256,
            matched_source_lock_sha256=metadata.matched_source_lock_sha256,
            revision_lock_sha256=metadata.revision_lock_sha256,
            matched_revision_lock_sha256=metadata.matched_revision_lock_sha256,
            run_config_sha256=metadata.run_config_sha256,
            matched_run_config_sha256=metadata.matched_run_config_sha256,
            environment_fingerprint_sha256=
                metadata.environment_fingerprint_sha256,
            matched_environment_fingerprint_sha256=
                metadata.matched_environment_fingerprint_sha256,
            lower_bound=model.lower_bound,
            bootstrap_method=:DirectKrylovBootstrap,
            bootstrap_tau=BOOTSTRAP_TAU,
        ),
    )
    header = csv_row((
        "beta",
        "cap",
        "saved_states",
        "steps",
        "bootstrap_steps",
        "bootstrap_application_count",
        "implicit_steps",
        "maximum_step_physical_residual",
        "physical_residual_tolerance",
        "fit_sweeps",
        "krylov_dim",
        "krylov_maxiter",
        "max_rounds",
        "bootstrap_method",
        "bootstrap_tau_right",
        "bootstrap_dtau",
        "bootstrap_requested_dimension",
        "bootstrap_raw_dimension",
        "bootstrap_retained_dimension",
        "bootstrap_discarded_dimension",
        "bootstrap_action_count",
        "bootstrap_projected_residual",
        "bootstrap_gram_condition",
        "bootstrap_initial_projection_error",
        "bootstrap_initial_maxbond",
        "bootstrap_final_maxbond",
        "fit_relative_l2",
        "logZ_shifted",
        "logZ_unshifted",
        "source_lock_sha256",
        "matched_source_lock_sha256",
        "revision_lock_sha256",
        "matched_revision_lock_sha256",
        "run_config_sha256",
        "matched_run_config_sha256",
        "environment_fingerprint_sha256",
        "matched_environment_fingerprint_sha256",
    ))
    logZ_unshifted = final_state.logZ - BETA * model.lower_bound
    row = csv_row((
        BETA,
        cap,
        length(checkpoints),
        number_steps,
        1,
        bootstrap_application_count,
        number_steps - 1,
        @sprintf("%.17g", maximum_step_residual),
        @sprintf("%.17g", SOLVE_TOL),
        FIT_SWEEPS,
        KRYLOV_DIM,
        KRYLOV_MAXITER,
        MAX_ROUNDS,
        bootstrap_summary.method,
        @sprintf("%.17g", bootstrap_summary.tau_right),
        @sprintf("%.17g", bootstrap_summary.dtau),
        bootstrap_summary.requested_dimension,
        bootstrap_summary.raw_dimension,
        bootstrap_summary.retained_dimension,
        bootstrap_summary.discarded_dimension,
        bootstrap_summary.action_count,
        @sprintf("%.17g", bootstrap_summary.projected_residual),
        @sprintf("%.17g", bootstrap_summary.gram_condition),
        @sprintf("%.17g", bootstrap_summary.initial_projection_error),
        bootstrap_summary.initial_max_bond,
        bootstrap_summary.final_max_bond,
        @sprintf("%.17g", fit.physical_error.relative_l2),
        @sprintf("%.17g", final_state.logZ),
        @sprintf("%.17g", logZ_unshifted),
        metadata.source_lock_sha256,
        metadata.matched_source_lock_sha256,
        metadata.revision_lock_sha256,
        metadata.matched_revision_lock_sha256,
        metadata.run_config_sha256,
        metadata.matched_run_config_sha256,
        metadata.environment_fingerprint_sha256,
        metadata.matched_environment_fingerprint_sha256,
    ))
    atomic_write_or_validate(summary_path, header * "\n" * row * "\n")
    checkpoint!(
        (; trajectory),
        final_path;
        keep=0,
        metadata,
    )
    progress(
        "preparation_complete";
        details=(
            "cap=$cap states=$(length(checkpoints)) " *
            "max_physical_residual=$maximum_step_residual"
        ),
    )
end

main()
