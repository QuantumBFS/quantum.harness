include(joinpath(@__DIR__, "rde_beta16_common.jl"))
using .RDEBeta16Common

using Graft
using Graft.Backend
using LinearAlgebra
using Printf

function report_vector(values)
    isempty(values) && return "none"
    return join((@sprintf("%.17g", value) for value in values), ";")
end

function main()
    length(ARGS) == 2 ||
        error("usage: rde_beta16_first_step.jl RUN_ROOT CAP")
    run_root = abspath(ARGS[1])
    cap = parse(Int, ARGS[2])
    cap in (24, 32, 48) || error("cap must be one of 24, 32, 48")
    output = joinpath(
        run_root,
        "outputs",
        "first-step-cap-" * lpad(string(cap), 2, '0') * ".csv",
    )
    subspace_output = joinpath(
        run_root,
        "outputs",
        "first-step-cap-" * lpad(string(cap), 2, '0') * "-subspaces.csv",
    )
    expansion_output = joinpath(
        run_root,
        "outputs",
        "first-step-cap-" * lpad(string(cap), 2, '0') * "-expansions.csv",
    )
    two_site_edge_output = joinpath(
        run_root,
        "outputs",
        "first-step-cap-" * lpad(string(cap), 2, '0') * "-two-site-edges.csv",
    )
    if isfile(output)
        for required_output in
                (subspace_output, expansion_output, two_site_edge_output)
            isfile(required_output) ||
                error("existing first-step summary lacks detailed evidence")
        end
        _, rows = parse_simple_csv(output)
        length(rows) == 1 || error("existing first-step summary has extra rows")
        row = only(rows)
        parse(Int, row["cap"]) == cap ||
            error("existing first-step cap mismatch")
        row["source_lock_sha256"] == source_lock_sha256(run_root) ||
            error("existing first-step source lock mismatch")
        row["revision_lock_sha256"] == revision_lock_sha256(run_root) ||
            error("existing first-step revision lock mismatch")
        row["run_config_sha256"] == run_config_sha256(run_root) ||
            error("existing first-step run-config mismatch")
        row["environment_fingerprint_sha256"] ==
            environment_fingerprint_sha256(run_root) ||
            error("existing first-step environment fingerprint mismatch")
        progress("paired_first_step_already_complete"; details="cap=$cap")
        return
    end
    model, fit = build_model()
    initial = infinite_temperature_state(model.problem).psi
    grid = preparation_grid()
    length(grid) >= 3 ||
        error("the matched diagnostic needs a bootstrap and an implicit step")
    bootstrap_left = grid[1]
    bootstrap_right = grid[2]
    bootstrap_dtau = bootstrap_right - bootstrap_left
    bootstrap_left == 0.0 ||
        error("the global-Krylov bootstrap must start at tau=0")
    initial_max_bond = max_bond_dimension(initial)
    bootstrap_info = checked_global_krylov_bootstrap!(
        initial,
        model.problem.K,
        bootstrap_dtau;
        phase="paired-first-step",
        cap,
    )
    bootstrap_norm = norm(initial)
    isfinite(bootstrap_norm) && bootstrap_norm > 0 ||
        error("global-Krylov bootstrap produced an invalid state norm")
    Graft.normalize!(initial)
    bootstrap_log_amplitude = log(bootstrap_norm)
    bootstrap_final_max_bond = max_bond_dimension(initial)
    diagnostic_left = grid[2]
    diagnostic_right = grid[3]
    diagnostic_dtau = diagnostic_right - diagnostic_left
    system = trapezoid_system(
        initial,
        model.problem.K,
        diagnostic_dtau,
    )
    number_edges = nnodes(topology(initial)) - 1
    residual_policy = make_rde_policy(cap, number_edges)
    two_site_policy = TwoSiteLinearPolicy(
        trunc=TruncationScheme(maxdim=cap),
        sweeps=FIT_SWEEPS * (MAX_ROUNDS + 1),
        krylovdim=KRYLOV_DIM,
        maxiter=KRYLOV_MAXITER,
        local_tol=SOLVE_TOL,
        residual_tol=SOLVE_TOL,
    )

    progress(
        "paired_first_step_start";
        details=(
            "cap=$cap bootstrap_tau=$bootstrap_right " *
            "bootstrap_maxbond=$bootstrap_final_max_bond " *
            "diagnostic_tau_left=$diagnostic_left " *
            "diagnostic_tau_right=$diagnostic_right " *
            "diagnostic_dtau=$diagnostic_dtau"
        ),
    )
    diagnostic = paired_linear_diagnostic(
        system.initial,
        model.problem.K,
        system.rhs,
        residual_policy,
        two_site_policy;
        a0=system.a0,
        a1=system.a1,
        krylovdim=KRYLOV_DIM,
        maxiter=KRYLOV_MAXITER,
        tol=SOLVE_TOL,
        fit_nsweeps=FIT_SWEEPS,
        fit_tol=0.0,
        fit_verbose=true,
    )
    rde = diagnostic.residual_driven_report
    two_site = diagnostic.two_site_report
    classification = diagnostic.classification
    producer_job_id = get(ENV, "SLURM_JOB_ID", "interactive")

    # The classifier is informative; the two exact uncompressed physical
    # residuals below remain the acceptance oracle.
    classification.residual_driven_residual ==
        last(rde.physical_residuals) ||
        error("classifier/RDE physical-residual mismatch")
    classification.two_site_residual ==
        last(two_site.physical_residuals) ||
        error("classifier/two-site physical-residual mismatch")

    subspaces = diagnostic.edge_subspace_evidence
    compatible_subspaces = filter(evidence -> evidence.available, subspaces)
    unavailable_subspaces = filter(evidence -> !evidence.available, subspaces)
    principal_cosines = reduce(
        vcat,
        (evidence.principal_cosines for evidence in compatible_subspaces);
        init=Float64[],
    )
    minimum_principal_cosine =
        isempty(principal_cosines) ? NaN : minimum(principal_cosines)
    maximum_bidirectional_projection_error = maximum(
        (
            max(
                evidence.residual_driven_to_two_site_projection_error,
                evidence.two_site_to_residual_driven_projection_error,
            )
            for evidence in compatible_subspaces
        );
        init=0.0,
    )
    subspace_header = csv_row((
        "cap",
        "child",
        "parent",
        "available",
        "stop_reason",
        "initial_rank",
        "residual_driven_rank",
        "two_site_rank",
        "residual_driven_novel_rank",
        "two_site_novel_rank",
        "principal_cosines",
        "minimum_principal_cosine",
        "residual_driven_to_two_site_projection_error",
        "two_site_to_residual_driven_projection_error",
        "maximum_bidirectional_projection_error",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
        "producer_job_id",
    ))
    subspace_rows = String[]
    for evidence in subspaces
        edge_minimum = isempty(evidence.principal_cosines) ?
            NaN : minimum(evidence.principal_cosines)
        edge_maximum = max(
            evidence.residual_driven_to_two_site_projection_error,
            evidence.two_site_to_residual_driven_projection_error,
        )
        push!(subspace_rows, csv_row((
            cap,
            first(evidence.edge),
            last(evidence.edge),
            evidence.available,
            evidence.stop_reason,
            evidence.initial_rank,
            evidence.residual_driven_rank,
            evidence.two_site_rank,
            evidence.residual_driven_novel_rank,
            evidence.two_site_novel_rank,
            report_vector(evidence.principal_cosines),
            @sprintf("%.17g", edge_minimum),
            @sprintf(
                "%.17g",
                evidence.residual_driven_to_two_site_projection_error,
            ),
            @sprintf(
                "%.17g",
                evidence.two_site_to_residual_driven_projection_error,
            ),
            @sprintf("%.17g", edge_maximum),
            source_lock_sha256(run_root),
            revision_lock_sha256(run_root),
            run_config_sha256(run_root),
            producer_job_id,
        )))
    end
    atomic_write_or_validate(
        subspace_output,
        subspace_header * "\n" * join(subspace_rows, "\n") * "\n",
    )

    expansion_header = csv_row((
        "cap",
        "round",
        "child",
        "parent",
        "rank_before",
        "rank_after",
        "uncovered_weight",
        "relative_weight",
        "selected",
        "requested_rank",
        "added_rank",
        "embedding_error",
        "round_selected_edges",
        "round_total_added",
        "round_weight_threshold",
        "round_embedding_error",
        "round_remaining_add",
        "round_stop_reason",
        "producer_job_id",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
    ))
    expansion_rows = String[]
    for (round, expansion) in enumerate(rde.expansions)
        for edge in expansion.edges
            push!(expansion_rows, csv_row((
                cap,
                round,
                first(edge.edge),
                last(edge.edge),
                edge.rank_before,
                edge.rank_after,
                @sprintf("%.17g", edge.uncovered_weight),
                @sprintf("%.17g", edge.relative_weight),
                edge.selected,
                edge.requested_rank,
                edge.added_rank,
                @sprintf("%.17g", edge.embedding_error),
                expansion.selected_edges,
                expansion.total_added,
                @sprintf("%.17g", expansion.weight_threshold),
                @sprintf("%.17g", expansion.embedding_error),
                expansion.remaining_add,
                expansion.stop_reason,
                producer_job_id,
                source_lock_sha256(run_root),
                revision_lock_sha256(run_root),
                run_config_sha256(run_root),
            )))
        end
    end
    atomic_write_or_validate(
        expansion_output,
        expansion_header * "\n" * join(expansion_rows, "\n") * "\n",
    )

    two_site_edge_header = csv_row((
        "cap",
        "sweep",
        "child",
        "parent",
        "center_on",
        "local_residual_before_truncation",
        "local_residual_after_truncation",
        "retained_rank",
        "discarded_norm",
        "discarded_weight",
        "solver_iterations",
        "solver_operations",
        "solver_converged",
        "transaction_committed",
        "producer_job_id",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
    ))
    two_site_edge_rows = [
        csv_row((
            cap,
            edge.sweep,
            edge.child,
            edge.parent,
            edge.center_on,
            @sprintf("%.17g", edge.local_residual_before_truncation),
            @sprintf("%.17g", edge.local_residual_after_truncation),
            edge.retained_rank,
            @sprintf("%.17g", edge.discarded_norm),
            @sprintf("%.17g", edge.discarded_weight),
            edge.solver_iterations,
            edge.solver_operations,
            edge.solver_converged,
            two_site.transaction_committed,
            producer_job_id,
            source_lock_sha256(run_root),
            revision_lock_sha256(run_root),
            run_config_sha256(run_root),
        ))
        for edge in two_site.edge_reports
    ]
    atomic_write_or_validate(
        two_site_edge_output,
        two_site_edge_header * "\n" *
            join(two_site_edge_rows, "\n") * "\n",
    )

    header = csv_row((
        "cap",
        "classification",
        "residual_driven_converged",
        "two_site_converged",
        "residual_driven_residual",
        "two_site_residual",
        "residual_driven_stop_reason",
        "two_site_stop_reason",
        "residual_driven_total_added",
        "two_site_max_retained_rank",
        "residual_driven_trajectory",
        "two_site_trajectory",
        "compatible_edge_count",
        "unavailable_edge_count",
        "subspace_evidence_available",
        "subspace_evidence_stop_reason",
        "minimum_principal_cosine",
        "maximum_bidirectional_projection_error",
        "physical_residual_tolerance",
        "fit_sweeps",
        "krylov_dim",
        "krylov_maxiter",
        "max_rounds",
        "fit_relative_l2",
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
        "bootstrap_log_amplitude",
        "diagnostic_tau_left",
        "diagnostic_tau_right",
        "diagnostic_dtau",
        "source_lock_sha256",
        "revision_lock_sha256",
        "run_config_sha256",
        "environment_fingerprint_sha256",
        "producer_job_id",
    ))
    max_retained = maximum(
        (edge.retained_rank for edge in two_site.edge_reports);
        init=1,
    )
    row = csv_row((
        cap,
        classification.classification,
        classification.residual_driven_converged,
        classification.two_site_converged,
        @sprintf("%.17g", classification.residual_driven_residual),
        @sprintf("%.17g", classification.two_site_residual),
        rde.stop_reason,
        two_site.stop_reason,
        rde.total_added,
        max_retained,
        report_vector(rde.physical_residuals),
        report_vector(two_site.physical_residuals),
        length(compatible_subspaces),
        length(unavailable_subspaces),
        diagnostic.subspace_evidence_available,
        diagnostic.subspace_evidence_stop_reason,
        @sprintf("%.17g", minimum_principal_cosine),
        @sprintf("%.17g", maximum_bidirectional_projection_error),
        @sprintf("%.17g", SOLVE_TOL),
        FIT_SWEEPS,
        KRYLOV_DIM,
        KRYLOV_MAXITER,
        MAX_ROUNDS,
        @sprintf("%.17g", fit.physical_error.relative_l2),
        "DirectKrylovBootstrap",
        @sprintf("%.17g", bootstrap_right),
        @sprintf("%.17g", bootstrap_dtau),
        bootstrap_info.requested_dimension,
        bootstrap_info.raw_dimension,
        bootstrap_info.retained_dimension,
        bootstrap_info.discarded_dimension,
        bootstrap_info.action_count,
        @sprintf("%.17g", bootstrap_info.projected_residual),
        @sprintf("%.17g", bootstrap_info.gram_condition),
        @sprintf("%.17g", bootstrap_info.initial_projection_error),
        initial_max_bond,
        bootstrap_final_max_bond,
        @sprintf("%.17g", bootstrap_log_amplitude),
        @sprintf("%.17g", diagnostic_left),
        @sprintf("%.17g", diagnostic_right),
        @sprintf("%.17g", diagnostic_dtau),
        source_lock_sha256(run_root),
        revision_lock_sha256(run_root),
        run_config_sha256(run_root),
        environment_fingerprint_sha256(run_root),
        producer_job_id,
    ))
    atomic_write_or_validate(output, header * "\n" * row * "\n")
    progress(
        "paired_first_step_complete";
        details=(
            "cap=$cap classification=$(classification.classification) " *
            "rde_residual=$(classification.residual_driven_residual) " *
            "two_site_residual=$(classification.two_site_residual)"
        ),
    )
end

main()
