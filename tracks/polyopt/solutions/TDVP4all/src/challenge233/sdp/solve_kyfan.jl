#!/usr/bin/env julia

using Clarabel
using JSON3
using JuMP
using LinearAlgebra
using Printf
using SHA

const MOI = JuMP.MOI
const PROBLEM_PURPOSE = "finite-N-ky-fan-effect-moment-problem"
const SOLVER_PURPOSE_V1 = "numerical-ky-fan-dual"
const SOLVER_PURPOSE_V2 = "numerical-ky-fan-reduced-dual-v2"
const SOLVER_SETTINGS = (
    max_iter = 500,
    tol_gap_abs = 1.0e-9,
    tol_gap_rel = 1.0e-9,
    tol_feas = 1.0e-9,
)
const SOLVER_FLOAT = Float64
const SolverVariableRef = GenericVariableRef{SOLVER_FLOAT}
const SolverAffExpr =
    GenericAffExpr{SOLVER_FLOAT,SolverVariableRef}


function sha256_file(path::AbstractString)
    return bytes2hex(open(sha256, path))
end


function sync_stream(stream)
    flush(stream)
    result = ccall(:fsync, Cint, (Cint,), fd(stream))
    result == 0 || error("fsync failed")
end


function atomic_write_json(path::AbstractString, payload)
    mkpath(dirname(path))
    temporary = string(path, ".tmp-", getpid())
    open(temporary, "w") do stream
        JSON3.write(stream, payload)
        write(stream, '\n')
        sync_stream(stream)
    end
    mv(temporary, path; force = true)
    return path
end


function read_json(path::AbstractString)
    isfile(path) || error("missing JSON file: $path")
    return JSON3.read(read(path, String))
end


function require_field(value, key::AbstractString)
    haskey(value, key) || error("missing JSON field: $key")
    return value[key]
end


function parse_fraction(text)::SOLVER_FLOAT
    parts = split(String(text), '/'; limit = 2)
    length(parts) == 2 || error("fraction must be numerator/denominator: $text")
    numerator = parse(BigInt, parts[1])
    denominator = parse(BigInt, parts[2])
    denominator != 0 || error("fraction denominator must be nonzero: $text")
    value = SOLVER_FLOAT(numerator) / SOLVER_FLOAT(denominator)
    isfinite(value) || error("fraction is not finite: $text")
    return value
end


function float_string(value::Real)
    isfinite(value) || error("cannot serialize a non-finite Float64")
    return @sprintf("%.17g", Float64(value))
end


function affine_form(form, variables)
    expression = SolverAffExpr(
        parse_fraction(require_field(form, "constant"))
    )
    for term in require_field(form, "terms")
        length(term) == 2 || error("affine term must have two entries")
        variable_index = Int(term[1]) + 1
        1 <= variable_index <= length(variables) ||
            error("affine variable index is out of range")
        coefficient = parse_fraction(term[2])
        add_to_expression!(
            expression,
            coefficient,
            variables[variable_index],
        )
    end
    return expression
end


function forms_equal(left, right)
    String(require_field(left, "constant")) ==
        String(require_field(right, "constant")) || return false
    left_terms = require_field(left, "terms")
    right_terms = require_field(right, "terms")
    length(left_terms) == length(right_terms) || return false
    for index in eachindex(left_terms)
        left_term = left_terms[index]
        right_term = right_terms[index]
        length(left_term) == 2 || return false
        length(right_term) == 2 || return false
        Int(left_term[1]) == Int(right_term[1]) || return false
        String(left_term[2]) == String(right_term[2]) || return false
    end
    return true
end


function new_model()
    model = GenericModel{SOLVER_FLOAT}()
    set_optimizer(model, Clarabel.Optimizer{SOLVER_FLOAT})
    set_silent(model)
    for (name, value) in pairs(SOLVER_SETTINGS)
        set_optimizer_attribute(model, String(name), value)
    end
    return model
end


function assert_triangle_psd(reference)
    index_type = typeof(JuMP.index(reference))
    set_type = index_type.parameters[2]
    set_type == MOI.PositiveSemidefiniteConeTriangle ||
        error("square or unexpected PSD cone is forbidden: $set_type")
end


function solver_seed_accuracy(model)
    has_values(model) && has_duals(model) || return nothing
    statuses = (
        termination_status(model),
        primal_status(model),
        dual_status(model),
    )
    statuses == (
        MOI.OPTIMAL,
        MOI.FEASIBLE_POINT,
        MOI.FEASIBLE_POINT,
    ) && return "full"
    statuses == (
        MOI.ALMOST_OPTIMAL,
        MOI.NEARLY_FEASIBLE_POINT,
        MOI.NEARLY_FEASIBLE_POINT,
    ) && raw_status(model) == "ALMOST_SOLVED" && return "reduced"
    return nothing
end


function acceptable_status(model)
    return solver_seed_accuracy(model) !== nothing
end


function dual_calibration()
    scalar_model = new_model()
    @variable(scalar_model, scalar_x)
    scalar_constraint = @constraint(
        scalar_model,
        Symmetric([scalar_x - 1.0;;]) in PSDCone(),
    )
    assert_triangle_psd(scalar_constraint)
    @objective(scalar_model, Min, scalar_x)
    optimize!(scalar_model)
    acceptable_status(scalar_model) ||
        error("scalar PSD dual calibration did not solve")
    scalar_dual = Matrix(dual(scalar_constraint))
    scalar_objective = objective_value(scalar_model)
    scalar_lower_identity = -scalar_dual[1, 1] * (-1.0)

    matrix_model = new_model()
    @variable(matrix_model, matrix_x)
    matrix_constraint = @constraint(
        matrix_model,
        Symmetric([1.0 matrix_x; matrix_x 1.0]) in PSDCone(),
    )
    assert_triangle_psd(matrix_constraint)
    @objective(matrix_model, Min, 2.0 * matrix_x)
    optimize!(matrix_model)
    acceptable_status(matrix_model) ||
        error("matrix PSD dual calibration did not solve")
    matrix_dual = Matrix(dual(matrix_constraint))
    matrix_objective = objective_value(matrix_model)
    matrix_lower_identity = -tr(matrix_dual)

    identity_sign_calibrated =
        isapprox(scalar_objective, 1.0; atol = 1.0e-8, rtol = 0.0) &&
        isapprox(
            scalar_lower_identity,
            scalar_objective;
            atol = 1.0e-8,
            rtol = 0.0,
        ) &&
        isapprox(
            matrix_lower_identity,
            matrix_objective;
            atol = 1.0e-7,
            rtol = 0.0,
        )
    offdiagonal_scaling_calibrated =
        isapprox(
            2.0 * matrix_dual[1, 2],
            2.0;
            atol = 1.0e-7,
            rtol = 0.0,
        )
    identity_sign_calibrated ||
        error("PSD dual lower-bound identity sign calibration failed")
    offdiagonal_scaling_calibrated ||
        error("PSD dual off-diagonal scaling calibration failed")

    return (
        scalar_objective = scalar_objective,
        matrix_objective = matrix_objective,
        dual_cone = "triangle-psd",
        dual_identity_sign_calibrated = identity_sign_calibrated,
        offdiagonal_scaling_calibrated =
            offdiagonal_scaling_calibrated,
    )
end


function load_problem_v1(problem_directory::AbstractString)
    directory = abspath(problem_directory)
    manifest_path = joinpath(directory, "manifest.json")
    manifest = read_json(manifest_path)
    String(require_field(manifest, "purpose")) == PROBLEM_PURPOSE ||
        error("unexpected problem manifest purpose")
    problem_name = String(require_field(manifest, "problem_file"))
    basename(problem_name) == problem_name ||
        error("problem_file must be a basename")
    problem_path = joinpath(directory, problem_name)
    expected_hash = lowercase(String(require_field(
        manifest,
        "problem_sha256",
    )))
    actual_hash = sha256_file(problem_path)
    expected_hash == actual_hash ||
        error("problem SHA-256 mismatch")
    problem = read_json(problem_path)
    String(require_field(problem, "purpose")) == PROBLEM_PURPOSE ||
        error("unexpected problem purpose")
    return (
        directory = directory,
        manifest_path = manifest_path,
        manifest_sha256 = sha256_file(manifest_path),
        problem_path = problem_path,
        problem_sha256 = actual_hash,
        problem = problem,
    )
end


function require_sha256(value, component::AbstractString)
    text = String(value)
    text == lowercase(text) ||
        error("$component must be a lowercase SHA-256")
    occursin(r"^[0-9a-f]{64}$", text) ||
        error("$component must be a lowercase SHA-256")
    return text
end


function v2_run_root(problem_directory::AbstractString)
    directory = abspath(problem_directory)
    basename(directory) == "problem" ||
        error("schema-v2 problem directory must be named problem")
    cell_directory = dirname(directory)
    cells_directory = dirname(cell_directory)
    basename(cells_directory) == "cells" ||
        error("schema-v2 problem must use run/cells/<cell>/problem layout")
    return dirname(cells_directory)
end


function resolve_bound_file(
    manifest_path::AbstractString,
    reference,
    run_root::AbstractString,
    component::AbstractString,
)
    text = String(reference)
    isempty(text) && error("$component reference is empty")
    isabspath(text) &&
        error("$component reference must be relative")
    occursin('\\', text) &&
        error("$component reference must use POSIX separators")
    normpath(text) == text ||
        error("$component reference is not normalized")
    any(part -> part == "" || part == ".", split(text, '/')) &&
        error("$component reference is not normalized")
    candidate = abspath(joinpath(dirname(manifest_path), text))
    isfile(candidate) ||
        error("missing $component artifact: $candidate")
    path = realpath(candidate)
    root = realpath(run_root)
    relative = relpath(path, root)
    (
        relative == ".." ||
        startswith(relative, "../") ||
        startswith(relative, "..\\")
    ) &&
        error("$component reference escapes the run root")
    return path
end


function verify_artifact_hash(
    path::AbstractString,
    expected,
    component::AbstractString,
)
    expected_hash = require_sha256(expected, "$component SHA-256")
    actual_hash = sha256_file(path)
    actual_hash == expected_hash ||
        error("$component SHA-256 mismatch")
    return actual_hash
end


function contains_json_key(payload, target::AbstractString)
    if payload isa JSON3.Object
        haskey(payload, target) && return true
        return any(
            child -> contains_json_key(child, target),
            values(payload),
        )
    elseif payload isa JSON3.Array
        return any(
            child -> contains_json_key(child, target),
            payload,
        )
    end
    return false
end


function compact_json_sha256(value)
    return bytes2hex(sha256(codeunits(JSON3.write(value))))
end


function collect_form_indices!(indices::Set{Int}, form, component)
    parse_fraction(require_field(form, "constant"))
    for term in require_field(form, "terms")
        length(term) == 2 ||
            error("$component affine term must have two entries")
        index = Int(term[1])
        index >= 0 ||
            error("$component variable index must be nonnegative")
        parse_fraction(term[2])
        push!(indices, index)
    end
end


function validate_v2_reduction(reduction)
    String(require_field(reduction, "purpose")) ==
        "finite-N-ky-fan-solver-reduction" ||
        error("unexpected solver reduction purpose")
    Int(require_field(reduction, "schema_version")) == 2 ||
        error("unexpected solver reduction schema version")
    contains_json_key(reduction, "detuning") &&
        error("solver reduction must be detuning independent")
    selected_view = String(require_field(reduction, "selected_view"))
    selected_view in ("parameterized", "row-reduced") ||
        error("solver view is not named by the reduction")
    equality = require_field(reduction, "equality")
    if haskey(equality, "selected_view")
        String(equality["selected_view"]) == selected_view ||
            error("solver view is not named by the equality reduction")
    end
    statistics = require_field(reduction, "statistics")
    variable_count = Int(require_field(
        statistics,
        "solver_variable_count",
    ))
    variable_count > 0 ||
        error("reduced variable count must be positive")

    indices = Set{Int}()
    components = require_field(reduction, "objective_components")
    Set(String(key) for key in keys(components)) ==
        Set(["rabi", "minus-number"]) ||
        error("reduced objective component inventory mismatch")
    for (name, form) in pairs(components)
        collect_form_indices!(
            indices,
            form,
            "objective component $(String(name))",
        )
    end

    spatial = Dict{String,Any}()
    for block in require_field(reduction, "spatial")
        identifier = String(require_field(block, "identifier"))
        haskey(spatial, identifier) &&
            error("duplicate spatial block identifier: $identifier")
        spatial[identifier] = block
    end
    isempty(spatial) && error("solver reduction has no spatial blocks")

    seen_blocks = Set{String}()
    for block in require_field(reduction, "psd_blocks")
        identifier = String(require_field(block, "identifier"))
        identifier in seen_blocks &&
            error("duplicate reduced PSD block identifier: $identifier")
        push!(seen_blocks, identifier)
        dimension = Int(require_field(block, "dimension"))
        dimension > 0 ||
            error("reduced PSD block dimension must be positive")
        spatial_identifier = String(require_field(
            block,
            "spatial_block",
        ))
        haskey(spatial, spatial_identifier) ||
            error("reduced PSD block names an unknown spatial block")
        String(require_field(block, "source_block")) in (
            "gamma",
            "blockade-complement",
        ) || error("reduced PSD block has an unknown source effect")
        previous = (-1, -1)
        for item in require_field(block, "upper_entries")
            row = Int(require_field(item, "row"))
            column = Int(require_field(item, "column"))
            0 <= row <= column < dimension ||
                error("reduced PSD upper coordinate is out of range")
            (row, column) > previous ||
                error("reduced PSD upper coordinates are not unique and sorted")
            previous = (row, column)
            collect_form_indices!(
                indices,
                require_field(item, "form"),
                "reduced PSD entry",
            )
        end
    end
    isempty(seen_blocks) && error("solver reduction has no PSD blocks")

    if selected_view == "row-reduced"
        for row in require_field(equality, "kept_rows")
            collect_form_indices!(
                indices,
                require_field(row, "form"),
                "kept equality",
            )
        end
    end
    indices == Set(0:(variable_count - 1)) ||
        error("reduced variable indices must be contiguous from zero")
    return (
        selected_view = selected_view,
        variable_count = variable_count,
        spatial = spatial,
    )
end


function load_problem_v2(problem_directory::AbstractString)
    directory = abspath(problem_directory)
    run_root = v2_run_root(directory)
    manifest_path = joinpath(directory, "manifest.json")
    manifest = read_json(manifest_path)
    Int(require_field(manifest, "schema_version")) == 2 ||
        error("unexpected schema-v2 problem manifest version")
    String(require_field(manifest, "purpose")) ==
        "finite-N-ky-fan-instance-binding" ||
        error("unexpected schema-v2 problem manifest purpose")

    instance_path = resolve_bound_file(
        manifest_path,
        require_field(manifest, "instance_file"),
        run_root,
        "instance",
    )
    structure_path = resolve_bound_file(
        manifest_path,
        require_field(manifest, "structure_reference"),
        run_root,
        "structure",
    )
    structure_manifest_path = resolve_bound_file(
        manifest_path,
        require_field(manifest, "structure_manifest_reference"),
        run_root,
        "structure manifest",
    )
    reduction_path = resolve_bound_file(
        manifest_path,
        require_field(manifest, "reduction_reference"),
        run_root,
        "solver reduction",
    )
    reduction_manifest_path = resolve_bound_file(
        manifest_path,
        require_field(manifest, "reduction_manifest_reference"),
        run_root,
        "solver reduction manifest",
    )

    instance_sha256 = verify_artifact_hash(
        instance_path,
        require_field(manifest, "instance_sha256"),
        "instance",
    )
    structure_sha256 = verify_artifact_hash(
        structure_path,
        require_field(manifest, "structure_sha256"),
        "structure",
    )
    verify_artifact_hash(
        structure_manifest_path,
        require_field(manifest, "structure_manifest_sha256"),
        "structure manifest",
    )
    reduction_sha256 = verify_artifact_hash(
        reduction_path,
        require_field(manifest, "reduction_sha256"),
        "solver reduction",
    )
    verify_artifact_hash(
        reduction_manifest_path,
        require_field(manifest, "reduction_manifest_sha256"),
        "solver reduction manifest",
    )

    structure_manifest = read_json(structure_manifest_path)
    String(require_field(structure_manifest, "purpose")) ==
        "finite-N-ky-fan-shared-structure" ||
        error("unexpected shared structure manifest purpose")
    String(require_field(structure_manifest, "structure_sha256")) ==
        structure_sha256 ||
        error("shared structure manifest hash binding mismatch")
    Int(require_field(structure_manifest, "structure_bytes")) ==
        filesize(structure_path) ||
        error("shared structure byte count mismatch")
    structure = read_json(structure_path)
    Int(require_field(structure, "schema_version")) == 2 ||
        error("unexpected shared structure schema version")
    String(require_field(structure, "purpose")) ==
        "finite-N-ky-fan-effect-moment-structure" ||
        error("unexpected shared structure purpose")

    reduction_manifest = read_json(reduction_manifest_path)
    String(require_field(reduction_manifest, "purpose")) ==
        "finite-N-ky-fan-shared-solver-reduction" ||
        error("unexpected shared reduction manifest purpose")
    String(require_field(reduction_manifest, "reduction_sha256")) ==
        reduction_sha256 ||
        error("shared reduction manifest hash binding mismatch")
    String(require_field(reduction_manifest, "structure_sha256")) ==
        structure_sha256 ||
        error("shared reduction/structure hash mismatch")
    Int(require_field(reduction_manifest, "reduction_bytes")) ==
        filesize(reduction_path) ||
        error("shared reduction byte count mismatch")

    instance = read_json(instance_path)
    String(require_field(instance, "purpose")) ==
        "finite-N-ky-fan-effect-moment-instance" ||
        error("unexpected instance purpose")
    String(require_field(instance, "structure_sha256")) ==
        structure_sha256 ||
        error("instance/structure hash mismatch")
    detuning = parse_fraction(require_field(instance, "detuning"))
    0.0 <= detuning <= 3.0 ||
        error("instance detuning lies outside [0,3]")

    reduction = read_json(reduction_path)
    String(require_field(reduction, "structure_sha256")) ==
        structure_sha256 ||
        error("structure/reduction hash mismatch")
    validated = validate_v2_reduction(reduction)
    return (
        schema_version = 2,
        directory = directory,
        run_root = run_root,
        manifest_path = manifest_path,
        manifest_sha256 = sha256_file(manifest_path),
        instance_path = instance_path,
        instance_sha256 = instance_sha256,
        structure_path = structure_path,
        structure_sha256 = structure_sha256,
        reduction_path = reduction_path,
        reduction_sha256 = reduction_sha256,
        instance = instance,
        reduction = reduction,
        detuning = detuning,
        selected_view = validated.selected_view,
        variable_count = validated.variable_count,
        spatial = validated.spatial,
    )
end


function load_problem(problem_directory::AbstractString)
    manifest = read_json(joinpath(abspath(problem_directory), "manifest.json"))
    version = Int(require_field(manifest, "schema_version"))
    if version == 1
        loaded = load_problem_v1(problem_directory)
        return (; schema_version = 1, loaded...)
    elseif version == 2
        return load_problem_v2(problem_directory)
    end
    error("unsupported problem manifest schema version: $version")
end


function build_model_v1(problem)
    variable_payload = require_field(problem, "variables")
    number_of_variables = length(variable_payload)
    for (position, variable) in enumerate(variable_payload)
        Int(require_field(variable, "index")) == position - 1 ||
            error("problem variable indices must be contiguous from zero")
    end

    model = new_model()
    @variable(model, variables[1:number_of_variables])

    equality_references = Any[]
    equality_identifiers = String[]
    seen_equalities = Set{String}()
    for row in require_field(problem, "equalities")
        identifier = String(require_field(row, "identifier"))
        identifier in seen_equalities &&
            error("duplicate equality identifier: $identifier")
        push!(seen_equalities, identifier)
        expression = affine_form(require_field(row, "form"), variables)
        push!(
            equality_references,
            @constraint(model, expression == 0.0),
        )
        push!(equality_identifiers, identifier)
    end

    psd_references = Any[]
    psd_identifiers = String[]
    psd_dimensions = Int[]
    seen_blocks = Set{String}()
    for block in require_field(problem, "psd_blocks")
        identifier = String(require_field(block, "identifier"))
        occursin(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", identifier) ||
            error("unsafe PSD block identifier: $identifier")
        identifier in seen_blocks &&
            error("duplicate PSD block identifier: $identifier")
        push!(seen_blocks, identifier)
        dimension = Int(require_field(block, "dimension"))
        dimension > 0 || error("PSD block dimension must be positive")
        rows = require_field(block, "entries")
        length(rows) == dimension ||
            error("PSD block row count does not match dimension")
        for row in rows
            length(row) == dimension ||
                error("PSD block column count does not match dimension")
        end

        entries = Matrix{SolverAffExpr}(undef, dimension, dimension)
        for row_index in 1:dimension
            for column_index in row_index:dimension
                upper = rows[row_index][column_index]
                lower = rows[column_index][row_index]
                forms_equal(upper, lower) ||
                    error("PSD block is not exactly symmetric")
                expression = affine_form(upper, variables)
                entries[row_index, column_index] = expression
                entries[column_index, row_index] = copy(expression)
            end
        end
        reference = @constraint(
            model,
            Symmetric(entries, :U) in PSDCone(),
        )
        assert_triangle_psd(reference)
        push!(psd_references, reference)
        push!(psd_identifiers, identifier)
        push!(psd_dimensions, dimension)
    end
    isempty(psd_references) && error("problem has no PSD blocks")

    objective = affine_form(require_field(problem, "objective"), variables)
    @objective(model, Min, objective)
    return (
        model = model,
        variables = variables,
        equality_references = equality_references,
        equality_identifiers = equality_identifiers,
        psd_references = psd_references,
        psd_identifiers = psd_identifiers,
        psd_dimensions = psd_dimensions,
    )
end


function build_model_v2(loaded)
    reduction = loaded.reduction
    model = new_model()
    @variable(model, variables[1:loaded.variable_count])

    equality_references = Any[]
    equality_identifiers = String[]
    if loaded.selected_view == "row-reduced"
        seen_equalities = Set{String}()
        for row in require_field(
            require_field(reduction, "equality"),
            "kept_rows",
        )
            identifier = String(require_field(row, "identifier"))
            identifier in seen_equalities &&
                error("duplicate kept equality identifier: $identifier")
            push!(seen_equalities, identifier)
            expression = affine_form(
                require_field(row, "form"),
                variables,
            )
            push!(
                equality_references,
                @constraint(model, expression == 0.0),
            )
            push!(equality_identifiers, identifier)
        end
    end

    psd_references = Any[]
    psd_identifiers = String[]
    psd_dimensions = Int[]
    psd_metadata = Any[]
    for block in require_field(reduction, "psd_blocks")
        identifier = String(require_field(block, "identifier"))
        dimension = Int(require_field(block, "dimension"))
        entries = [
            SolverAffExpr(zero(SOLVER_FLOAT))
            for _ in 1:dimension, _ in 1:dimension
        ]
        for item in require_field(block, "upper_entries")
            row = Int(require_field(item, "row")) + 1
            column = Int(require_field(item, "column")) + 1
            expression = affine_form(
                require_field(item, "form"),
                variables,
            )
            entries[row, column] = expression
            entries[column, row] = copy(expression)
        end
        reference = @constraint(
            model,
            Symmetric(entries, :U) in PSDCone(),
        )
        assert_triangle_psd(reference)
        spatial_identifier = String(require_field(
            block,
            "spatial_block",
        ))
        spatial = loaded.spatial[spatial_identifier]
        push!(psd_references, reference)
        push!(psd_identifiers, identifier)
        push!(psd_dimensions, dimension)
        push!(
            psd_metadata,
            (
                source_effect = String(require_field(
                    block,
                    "source_block",
                )),
                spatial_block = spatial_identifier,
                irrep_label = String(require_field(
                    spatial,
                    "irrep_label",
                )),
                irrep_degree = Int(require_field(
                    spatial,
                    "irrep_degree",
                )),
                transform_sha256 = compact_json_sha256(
                    require_field(spatial, "transform")
                ),
                transform_hash_encoding =
                    "sha256-json3-compact-source-order",
            ),
        )
    end

    components = require_field(reduction, "objective_components")
    objective = (
        affine_form(
            require_field(components, "rabi"),
            variables,
        )
        + loaded.detuning * affine_form(
            require_field(components, "minus-number"),
            variables,
        )
    )
    @objective(model, Min, objective)
    return (
        model = model,
        variables = variables,
        equality_references = equality_references,
        equality_identifiers = equality_identifiers,
        psd_references = psd_references,
        psd_identifiers = psd_identifiers,
        psd_dimensions = psd_dimensions,
        psd_metadata = psd_metadata,
    )
end


function write_f64le_matrix(path::AbstractString, matrix)
    rows, columns = size(matrix)
    rows == columns || error("dual matrix must be square")
    open(path, "w") do stream
        for row in 1:rows
            for column in 1:columns
                value = Float64(matrix[row, column])
                isfinite(value) ||
                    error("dual matrix contains a non-finite entry")
                bits = reinterpret(UInt64, value)
                write(stream, htol(bits))
            end
        end
        sync_stream(stream)
    end
    return path
end


function package_versions()
    return (
        julia = string(VERSION),
        jump = string(pkgversion(JuMP)),
        clarabel = string(pkgversion(Clarabel)),
        json3 = string(pkgversion(JSON3)),
    )
end


function solver_settings()
    return (
        scalar_type = string(SOLVER_FLOAT),
        precision_bits = precision(SOLVER_FLOAT),
        max_iter = SOLVER_SETTINGS.max_iter,
        tol_gap_abs = float_string(SOLVER_SETTINGS.tol_gap_abs),
        tol_gap_rel = float_string(SOLVER_SETTINGS.tol_gap_rel),
        tol_feas = float_string(SOLVER_SETTINGS.tol_feas),
    )
end


function numerical_diagnostics(model)
    solver = MOI.get(unsafe_backend(model), MOI.RawSolver())
    info = solver.info
    return (
        iterations = Int(info.iterations),
        cost_primal = float_string(info.cost_primal),
        cost_dual = float_string(info.cost_dual),
        res_primal = float_string(info.res_primal),
        res_dual = float_string(info.res_dual),
        gap_abs = float_string(info.gap_abs),
        gap_rel = float_string(info.gap_rel),
        ktratio = float_string(info.ktratio),
        has_values = has_values(model),
        has_duals = has_duals(model),
    )
end


function solve_problem(
    problem_directory::AbstractString,
    output_directory::AbstractString;
    selection = (mode = "direct",),
)
    calibration = dual_calibration()
    loaded = load_problem(problem_directory)
    built = (
        loaded.schema_version == 1
        ? build_model_v1(loaded.problem)
        : build_model_v2(loaded)
    )
    solver_purpose = (
        loaded.schema_version == 1
        ? SOLVER_PURPOSE_V1
        : SOLVER_PURPOSE_V2
    )
    output = abspath(output_directory)
    if isdir(output) && !isempty(readdir(output))
        error("solver output directory is not empty: $output")
    end
    mkpath(output)

    wall_seconds = @elapsed optimize!(built.model)
    termination = termination_status(built.model)
    primal = primal_status(built.model)
    dual_state = dual_status(built.model)
    numerical_accuracy = solver_seed_accuracy(built.model)
    if numerical_accuracy === nothing
        common_failure = (
            schema_version = loaded.schema_version,
            purpose = solver_purpose,
            success = false,
            termination_status = string(termination),
            primal_status = string(primal),
            dual_status = string(dual_state),
            raw_status = raw_status(built.model),
            wall_time_seconds = wall_seconds,
            numerical_diagnostics = numerical_diagnostics(built.model),
            versions = package_versions(),
            settings = solver_settings(),
            selection = selection,
        )
        failure = if loaded.schema_version == 1
            (; common_failure..., problem_sha256 = loaded.problem_sha256)
        else
            (
                ;
                common_failure...,
                problem_manifest_sha256 = loaded.manifest_sha256,
                structure_sha256 = loaded.structure_sha256,
                instance_sha256 = loaded.instance_sha256,
                reduction_sha256 = loaded.reduction_sha256,
                solver_view = loaded.selected_view,
            )
        end
        atomic_write_json(joinpath(output, "solver-result.json"), failure)
        error(
            "solver did not return an exportable primal-dual seed: " *
            "$(termination), $(primal), $(dual_state)",
        )
    end

    equality_multipliers = Any[]
    for (identifier, reference) in zip(
        built.equality_identifiers,
        built.equality_references,
    )
        multiplier = Float64(dual(reference))
        isfinite(multiplier) ||
            error("equality dual contains a non-finite entry")
        push!(
            equality_multipliers,
            (
                identifier = identifier,
                value = float_string(multiplier),
            ),
        )
    end

    psd_duals = Any[]
    maximum_asymmetry = 0.0
    for (position, values) in enumerate(
        zip(
            built.psd_identifiers,
            built.psd_dimensions,
            built.psd_references,
        ),
    )
        identifier, dimension, reference = values
        numerical = Matrix(dual(reference))
        size(numerical) == (dimension, dimension) ||
            error("PSD dual matrix dimension mismatch")
        all(isfinite, numerical) ||
            error("PSD dual matrix contains a non-finite entry")
        asymmetry = maximum(abs, numerical - transpose(numerical))
        maximum_asymmetry = max(maximum_asymmetry, asymmetry)
        symmetric = (numerical + transpose(numerical)) / 2.0
        filename = (
            loaded.schema_version == 1
            ? "dual-$identifier.f64le"
            : @sprintf("dual-reduced-%04d.f64le", position)
        )
        path = joinpath(output, filename)
        write_f64le_matrix(path, symmetric)
        metadata = (
            block = identifier,
            dimension = dimension,
            file = filename,
            layout = "row-major",
            scalar_format = "float64-little-endian",
            byte_count = filesize(path),
            sha256 = sha256_file(path),
            numerical_asymmetry_max = float_string(asymmetry),
        )
        if loaded.schema_version == 2
            metadata = (; metadata..., built.psd_metadata[position]...)
        end
        push!(psd_duals, metadata)
    end

    variable_values = [
        float_string(value(variable))
        for variable in built.variables
    ]
    common_result = (
        schema_version = loaded.schema_version,
        purpose = solver_purpose,
        success = true,
        problem_manifest_sha256 = loaded.manifest_sha256,
        termination_status = string(termination),
        primal_status = string(primal),
        dual_status = string(dual_state),
        raw_status = raw_status(built.model),
        numerical_accuracy = numerical_accuracy,
        numerical_diagnostics = numerical_diagnostics(built.model),
        objective = objective_value(built.model),
        dual_objective = dual_objective_value(built.model),
        solve_time_seconds = solve_time(built.model),
        wall_time_seconds = wall_seconds,
        result_count = result_count(built.model),
        dual_cone = calibration.dual_cone,
        dual_identity_sign_calibrated =
            calibration.dual_identity_sign_calibrated,
        offdiagonal_scaling_calibrated =
            calibration.offdiagonal_scaling_calibrated,
        maximum_dual_asymmetry = float_string(maximum_asymmetry),
        equality_multipliers = equality_multipliers,
        psd_duals = psd_duals,
        variable_values = variable_values,
        versions = package_versions(),
        settings = solver_settings(),
        selection = selection,
    )
    result = if loaded.schema_version == 1
        (; common_result..., problem_sha256 = loaded.problem_sha256)
    else
        (
            ;
            common_result...,
            structure_sha256 = loaded.structure_sha256,
            instance_sha256 = loaded.instance_sha256,
            reduction_sha256 = loaded.reduction_sha256,
            solver_view = loaded.selected_view,
        )
    end
    result_path = joinpath(output, "solver-result.json")
    atomic_write_json(result_path, result)

    files = Any[
        (
            file = "solver-result.json",
            sha256 = sha256_file(result_path),
            byte_count = filesize(result_path),
        ),
    ]
    for dual_metadata in psd_duals
        push!(
            files,
            (
                file = dual_metadata.file,
                sha256 = dual_metadata.sha256,
                byte_count = dual_metadata.byte_count,
            ),
        )
    end
    common_manifest = (
        schema_version = loaded.schema_version,
        purpose = "numerical-ky-fan-solve-manifest",
        success = true,
        problem_manifest_sha256 = loaded.manifest_sha256,
        solver_result_file = "solver-result.json",
        solver_result_sha256 = sha256_file(result_path),
        files = files,
        selection = selection,
    )
    manifest = if loaded.schema_version == 1
        (; common_manifest..., problem_sha256 = loaded.problem_sha256)
    else
        (
            ;
            common_manifest...,
            structure_sha256 = loaded.structure_sha256,
            instance_sha256 = loaded.instance_sha256,
            reduction_sha256 = loaded.reduction_sha256,
            solver_view = loaded.selected_view,
        )
    end
    manifest_path = joinpath(output, "solver-manifest.json")
    atomic_write_json(manifest_path, manifest)

    summary = (
        status = "solved",
        objective = objective_value(built.model),
        solver_manifest = manifest_path,
    )
    return (
        loaded.schema_version == 1
        ? (; summary..., problem_sha256 = loaded.problem_sha256)
        : (
            ;
            summary...,
            structure_sha256 = loaded.structure_sha256,
            instance_sha256 = loaded.instance_sha256,
            reduction_sha256 = loaded.reduction_sha256,
        )
    )
end


function resolve_paths(arguments)
    problem_directory = nothing
    output_directory = nothing
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument == "--problem-dir"
            index < length(arguments) ||
                error("--problem-dir requires a value")
            problem_directory = arguments[index + 1]
            index += 2
        elseif argument == "--output-dir"
            index < length(arguments) ||
                error("--output-dir requires a value")
            output_directory = arguments[index + 1]
            index += 2
        else
            error("unknown argument: $argument")
        end
    end

    if problem_directory !== nothing || output_directory !== nothing
        problem_directory !== nothing ||
            error("--problem-dir and --output-dir must be supplied together")
        output_directory !== nothing ||
            error("--problem-dir and --output-dir must be supplied together")
        return (
            problem_directory = String(problem_directory),
            output_directory = String(output_directory),
            selection = (mode = "direct",),
        )
    end

    run_spec_path = get(ENV, "HARNESS_RUN_SPEC", "")
    isempty(run_spec_path) &&
        error("set HARNESS_RUN_SPEC for array mode")
    task_text = get(ENV, "SLURM_ARRAY_TASK_ID", "")
    isempty(task_text) &&
        error("set SLURM_ARRAY_TASK_ID for array mode")
    task_index = parse(Int, task_text)
    run_spec = read_json(run_spec_path)
    cells = require_field(run_spec, "cells")
    1 <= task_index <= length(cells) ||
        error("SLURM_ARRAY_TASK_ID is outside the one-based cell range")
    cell = cells[task_index]
    cell_id = String(require_field(cell, "cell_id"))
    occursin(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", cell_id) ||
        error("unsafe cell_id: $cell_id")
    run_directory = dirname(abspath(run_spec_path))
    cell_directory = joinpath(run_directory, "cells", cell_id)
    return (
        problem_directory = joinpath(cell_directory, "problem"),
        output_directory = joinpath(cell_directory, "solver"),
        selection = (
            mode = "slurm-array",
            cell_id = cell_id,
            cell_index = task_index,
            run_spec_sha256 = sha256_file(abspath(run_spec_path)),
        ),
    )
end


function main(arguments)
    if arguments == ["--self-test"]
        println(JSON3.write(dual_calibration()))
        return 0
    end
    paths = resolve_paths(arguments)
    summary = solve_problem(
        paths.problem_directory,
        paths.output_directory;
        selection = paths.selection,
    )
    println(JSON3.write(summary))
    return 0
end


try
    exit(main(ARGS))
catch exception
    showerror(stderr, exception, catch_backtrace())
    write(stderr, '\n')
    exit(1)
end
