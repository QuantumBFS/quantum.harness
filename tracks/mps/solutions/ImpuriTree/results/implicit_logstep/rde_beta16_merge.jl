include(joinpath(@__DIR__, "rde_beta16_common.jl"))
using .RDEBeta16Common

const FIRST_STEP_SUBSPACE_HEADER = split(
    "cap,child,parent,available,stop_reason,initial_rank," *
    "residual_driven_rank,two_site_rank,residual_driven_novel_rank," *
    "two_site_novel_rank,principal_cosines,minimum_principal_cosine," *
    "residual_driven_to_two_site_projection_error," *
    "two_site_to_residual_driven_projection_error," *
    "maximum_bidirectional_projection_error,source_lock_sha256," *
    "revision_lock_sha256,run_config_sha256,producer_job_id",
    ",",
)

const FIRST_STEP_EXPANSION_HEADER = split(
    "cap,round,child,parent,rank_before,rank_after,uncovered_weight," *
    "relative_weight,selected,requested_rank,added_rank,embedding_error," *
    "round_selected_edges,round_total_added,round_weight_threshold," *
    "round_embedding_error,round_remaining_add,round_stop_reason," *
    "producer_job_id,source_lock_sha256,revision_lock_sha256," *
    "run_config_sha256",
    ",",
)

const FIRST_STEP_TWO_SITE_EDGE_HEADER = split(
    "cap,sweep,child,parent,center_on,local_residual_before_truncation," *
    "local_residual_after_truncation,retained_rank,discarded_norm," *
    "discarded_weight,solver_iterations,solver_operations," *
    "solver_converged,transaction_committed,producer_job_id," *
    "source_lock_sha256,revision_lock_sha256,run_config_sha256",
    ",",
)

function merge_first_step(run_root)
    caps = (24, 32, 48)
    rows = Dict{String,String}[]
    header = String[]
    expected_lock = source_lock_sha256(run_root)
    expected_revision_lock = revision_lock_sha256(run_root)
    expected_config_hash = run_config_sha256(run_root)
    expected_environment_fingerprint =
        environment_fingerprint_sha256(run_root)
    for cap in caps
        path = joinpath(
            run_root,
            "outputs",
            "first-step-cap-" * lpad(string(cap), 2, '0') * ".csv",
        )
        isfile(path) || error("missing first-step result for cap $cap")
        local_header, local_rows = parse_simple_csv(path)
        length(local_rows) == 1 ||
            error("first-step result for cap $cap has multiple rows")
        isempty(header) ? (header = local_header) :
            header == local_header || error("first-step CSV headers differ")
        row = only(local_rows)
        parse(Int, row["cap"]) == cap || error("first-step cap mismatch")
        row["source_lock_sha256"] == expected_lock ||
            error("first-step source lock mismatch at cap $cap")
        row["revision_lock_sha256"] == expected_revision_lock ||
            error("first-step revision lock mismatch at cap $cap")
        row["run_config_sha256"] == expected_config_hash ||
            error("first-step run-config mismatch at cap $cap")
        row["environment_fingerprint_sha256"] ==
            expected_environment_fingerprint ||
            error("first-step environment fingerprint mismatch at cap $cap")
        row["bootstrap_method"] == "DirectKrylovBootstrap" ||
            error("first-step bootstrap method mismatch at cap $cap")
        parse(Float64, row["bootstrap_tau_right"]) == BOOTSTRAP_TAU ||
            error("first-step bootstrap tau mismatch at cap $cap")
        parse(Float64, row["bootstrap_dtau"]) == BOOTSTRAP_TAU ||
            error("first-step bootstrap dtau mismatch at cap $cap")
        parse(Int, row["bootstrap_requested_dimension"]) ==
            BOOTSTRAP_KRYLOV_DIM ||
            error("first-step bootstrap dimension mismatch at cap $cap")
        parse(Int, row["bootstrap_retained_dimension"]) >= 2 ||
            error("first-step bootstrap retained no growth direction at cap $cap")
        bootstrap_initial_maxbond =
            parse(Int, row["bootstrap_initial_maxbond"])
        bootstrap_final_maxbond =
            parse(Int, row["bootstrap_final_maxbond"])
        bootstrap_final_maxbond > bootstrap_initial_maxbond ||
            error("first-step bootstrap did not open bonds at cap $cap")
        bootstrap_final_maxbond <= cap ||
            error("first-step bootstrap exceeded cap $cap")
        parse(Float64, row["diagnostic_tau_left"]) == BOOTSTRAP_TAU ||
            error("first-step diagnostic did not start after bootstrap")
        parse(Float64, row["diagnostic_dtau"]) > 0 ||
            error("first-step diagnostic has a nonpositive dtau")
        subspace_path = joinpath(
            run_root,
            "outputs",
            "first-step-cap-" * lpad(string(cap), 2, '0') * "-subspaces.csv",
        )
        isfile(subspace_path) ||
            error("missing per-edge subspace evidence for cap $cap")
        subspace_header, subspace_rows = parse_simple_csv(subspace_path)
        subspace_header == FIRST_STEP_SUBSPACE_HEADER ||
            error("invalid per-edge subspace header at cap $cap")
        expected_edges = 2 * (2NPOLES + 2) - 1
        length(subspace_rows) == expected_edges ||
            error(
                "expected $expected_edges per-edge rows at cap $cap; " *
                "got $(length(subspace_rows))",
            )
        all(
            subspace_row ->
                parse(Int, subspace_row["cap"]) == cap &&
                subspace_row["source_lock_sha256"] == expected_lock &&
                subspace_row["revision_lock_sha256"] ==
                    expected_revision_lock &&
                subspace_row["run_config_sha256"] == expected_config_hash &&
                subspace_row["producer_job_id"] == row["producer_job_id"],
            subspace_rows,
        ) || error("invalid per-edge subspace evidence at cap $cap")
        for detail_suffix in ("expansions", "two-site-edges")
            detail_path = joinpath(
                run_root,
                "outputs",
                "first-step-cap-" * lpad(string(cap), 2, '0') *
                    "-$detail_suffix.csv",
            )
            isfile(detail_path) ||
                error("missing $detail_suffix evidence for cap $cap")
            detail_header, detail_rows = parse_simple_csv(
                detail_path;
                allow_header_only=detail_suffix == "expansions",
            )
            expected_detail_header = detail_suffix == "expansions" ?
                FIRST_STEP_EXPANSION_HEADER :
                FIRST_STEP_TWO_SITE_EDGE_HEADER
            detail_header == expected_detail_header ||
                error("invalid $detail_suffix header at cap $cap")
            if isempty(detail_rows)
                detail_suffix == "expansions" &&
                    parse(Int, row["residual_driven_total_added"]) == 0 ||
                    error("empty $detail_suffix evidence for cap $cap")
                continue
            end
            all(
                detail_row ->
                    parse(Int, detail_row["cap"]) == cap &&
                    detail_row["source_lock_sha256"] == expected_lock &&
                    detail_row["revision_lock_sha256"] ==
                        expected_revision_lock &&
                    detail_row["run_config_sha256"] ==
                        expected_config_hash &&
                    detail_row["producer_job_id"] ==
                        row["producer_job_id"],
                detail_rows,
            ) || error("invalid $detail_suffix evidence at cap $cap")
        end
        parse(Int, row["compatible_edge_count"]) +
            parse(Int, row["unavailable_edge_count"]) == expected_edges ||
            error("subspace summary counts do not cover all edges at cap $cap")
        push!(rows, row)
    end
    length(unique(row["producer_job_id"] for row in rows)) == 1 ||
        error("first-step caps were not produced by one parallel Slurm job")
    for bootstrap_field in (
        "bootstrap_method",
        "bootstrap_requested_dimension",
        "bootstrap_raw_dimension",
        "bootstrap_retained_dimension",
        "bootstrap_discarded_dimension",
        "bootstrap_action_count",
        "bootstrap_initial_maxbond",
        "bootstrap_final_maxbond",
    )
        length(unique(row[bootstrap_field] for row in rows)) == 1 ||
            error(
                "parallel cap runs did not share an identical " *
                "$bootstrap_field",
            )
    end
    for bootstrap_field in (
        "bootstrap_tau_right",
        "bootstrap_dtau",
        "bootstrap_projected_residual",
        "bootstrap_gram_condition",
        "bootstrap_initial_projection_error",
        "bootstrap_log_amplitude",
        "diagnostic_tau_left",
        "diagnostic_tau_right",
        "diagnostic_dtau",
    )
        values = parse.(Float64, (row[bootstrap_field] for row in rows))
        all(
            value -> isapprox(
                value,
                first(values);
                atol=1e-12,
                rtol=1e-12,
            ),
            values,
        ) ||
            error(
                "parallel cap runs did not share a numerically identical " *
                "$bootstrap_field",
            )
    end

    matched = Int[]
    for row in rows
        residual_driven_residual =
            parse(Float64, row["residual_driven_residual"])
        two_site_residual = parse(Float64, row["two_site_residual"])
        rde_converged = parse(Bool, row["residual_driven_converged"])
        two_site_converged = parse(Bool, row["two_site_converged"])
        if row["classification"] == "matched" &&
           rde_converged &&
           two_site_converged &&
           residual_driven_residual <= SOLVE_TOL &&
           two_site_residual <= SOLVE_TOL
            push!(matched, parse(Int, row["cap"]))
        end
    end

    output =
        joinpath(run_root, "outputs", "first_step_diagnostics.csv")
    content = join(header, ",") * "\n"
    for row in rows
        content *= csv_row(row[field] for field in header) * "\n"
    end
    atomic_write_or_validate(output, content)
    isempty(matched) &&
        error(
            "fail-closed: no cap is matched by both methods under the exact " *
            "physical-residual tolerance $SOLVE_TOL",
        )
    selected = minimum(matched)
    atomic_write_or_validate(
        joinpath(run_root, "outputs", "matched_cap.txt"),
        string(selected) * "\n",
    )
    progress(
        "first_step_merge_complete";
        details="matched_caps=$(sort(matched)) selected_cap=$selected",
    )
end

function merge_gtau(run_root)
    expected_lock = source_lock_sha256(run_root)
    expected_revision_lock = revision_lock_sha256(run_root)
    expected_config_hash = run_config_sha256(run_root)
    expected_environment_fingerprint =
        environment_fingerprint_sha256(run_root)
    rows = Dict{String,String}[]
    header = String[]
    for point_index in eachindex(GTAU_POINTS)
        label = lpad(string(point_index), 2, '0')
        path = joinpath(run_root, "outputs", "points", "gtau-$label.csv")
        isfile(path) || error("missing Gtau point $point_index")
        local_header, local_rows = parse_simple_csv(path)
        length(local_rows) == 1 || error("Gtau point $point_index has extra rows")
        isempty(header) ? (header = local_header) :
            header == local_header || error("Gtau point CSV headers differ")
        row = only(local_rows)
        parse(Int, row["point_index"]) == point_index ||
            error("Gtau point index mismatch at $point_index")
        parse(Float64, row["tau"]) == GTAU_POINTS[point_index] ||
            error("Gtau tau mismatch at point $point_index")
        row["source_lock_sha256"] == expected_lock ||
            error("Gtau source lock mismatch at point $point_index")
        row["revision_lock_sha256"] == expected_revision_lock ||
            error("Gtau revision lock mismatch at point $point_index")
        row["run_config_sha256"] == expected_config_hash ||
            error("Gtau run-config mismatch at point $point_index")
        row["environment_fingerprint_sha256"] ==
            expected_environment_fingerprint ||
            error("Gtau environment fingerprint mismatch at point $point_index")
        row["preparation_environment_fingerprint_sha256"] ==
            expected_environment_fingerprint ||
            error(
                "Gtau preparation environment fingerprint mismatch at " *
                "point $point_index",
            )
        row["sign_convention"] == "Gtau_equals_minus_correlator" ||
            error("Gtau sign convention mismatch at point $point_index")
        row["preparation_bootstrap_method"] == "DirectKrylovBootstrap" ||
            error("Gtau preparation bootstrap mismatch at point $point_index")
        parse(Float64, row["preparation_bootstrap_tau"]) == BOOTSTRAP_TAU ||
            error(
                "Gtau preparation bootstrap tau mismatch at point $point_index",
            )
        parse(Int, row["preparation_bootstrap_application_count"]) == 1 ||
            error(
                "Gtau preparation bootstrap count mismatch at point $point_index",
            )
        row["branch_manifold_source"] ==
            "preparation_checkpoint_virtual_spaces" ||
            error("Gtau branch manifold source mismatch at point $point_index")
        parse(Int, row["branch_bootstrap_application_count"]) == 0 ||
            error("Gtau point $point_index unexpectedly ran a branch bootstrap")
        row["branch_evolution_method"] == PREP_METHOD_LABEL ||
            error("Gtau branch evolution mismatch at point $point_index")
        parse(Bool, row["all_implicit_steps_converged"]) ||
            error("Gtau point $point_index contains an unconverged step")
        if parse(Float64, row["maximum_step_physical_residual"]) > SOLVE_TOL
            STEP_FAILURE_POLICY === :warn ||
                error(
                    "Gtau point $point_index exceeded the residual tolerance",
                )
            println(
                "GTAU_POINT_WARNING point=$point_index " *
                "maximum_step_physical_residual=" *
                row["maximum_step_physical_residual"] *
                " tolerance=$SOLVE_TOL",
            )
        end
        correlator = complex(
            parse(Float64, row["correlator_real"]),
            parse(Float64, row["correlator_imag"]),
        )
        gtau = complex(
            parse(Float64, row["gtau_real"]),
            parse(Float64, row["gtau_imag"]),
        )
        all(isfinite, (real(correlator), imag(correlator), real(gtau), imag(gtau))) ||
            error("Gtau point $point_index is non-finite")
        isapprox(gtau, -correlator; atol=1e-13, rtol=1e-12) ||
            error("Gtau=-correlator check failed at point $point_index")
        push!(rows, row)
    end

    length(rows) == 17 || error("expected exactly 17 Gtau rows")
    output = joinpath(run_root, "outputs", "gtau_beta16.csv")
    content = join(header, ",") * "\n"
    for row in rows
        content *= csv_row(row[field] for field in header) * "\n"
    end
    atomic_write_or_validate(output, content)

    plot_input = joinpath(run_root, "outputs", "gtau_beta16_plot.dat")
    plot_content = "# tau gtau_real gtau_imag\n"
    for row in rows
        plot_content *= join(
            (row["tau"], row["gtau_real"], row["gtau_imag"]),
            " ",
        ) * "\n"
    end
    atomic_write_or_validate(plot_input, plot_content)
    progress(
        "gtau_merge_complete";
        details="points=$(length(rows)) csv=$output plot_input=$plot_input",
    )
end

function main()
    length(ARGS) == 2 ||
        error("usage: rde_beta16_merge.jl first-step|gtau RUN_ROOT")
    mode = ARGS[1]
    run_root = abspath(ARGS[2])
    if mode == "first-step"
        merge_first_step(run_root)
    elseif mode == "gtau"
        merge_gtau(run_root)
    else
        error("unknown merge mode: $mode")
    end
end

main()
