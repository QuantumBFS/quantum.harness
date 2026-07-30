#!/usr/bin/env julia

include(joinpath(@__DIR__, "build_shastry_full_state_spin_spatial_mof.jl"))
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicReduction.jl",
))
using .ShastryFullStateSpinIsotypicReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicPrimalGapJuMP.jl",
))
using .ShastryFullStateSpinIsotypicPrimalGapJuMP
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicDualCertificateJuMP.jl",
))
using .ShastryFullStateSpinIsotypicDualCertificateJuMP
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicDualCertificateMosek.jl",
))
using .ShastryFullStateSpinIsotypicDualCertificateMosek
include(joinpath(
    TRACK_ROOT,
    "src",
    "ShastryFullStateSpinIsotypicPrimalGapMosek.jl",
))
using .ShastryFullStateSpinIsotypicPrimalGapMosek
using LinearAlgebra
using Mosek
using MosekTools

const SPIN_ISOTYPIC_RUNMETA_SCHEMA =
    "shastry-l1d2-full-state-spin-isotypic-mof-v1"

function spin_isotypic_source_dict()
    source = spin_spatial_source_dict()
    for file in (
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicDualCertificateJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicDualCertificateMosek.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ShastryFullStateSpinIsotypicPrimalGapMosek.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_isotypic_mof.jl",
    )
        source["files_sha256"][file] =
            file_sha256(joinpath(REPOSITORY_ROOT, file))
    end
    return source
end

function spin_isotypic_report_dict(report)
    return Dict(
        "source_moments" => report.source_moments,
        "spin_isotypic_moments" => report.spin_isotypic_moments,
        "eliminated_unused_moments" => report.eliminated_unused_moments,
        "positive_block_dimensions" => report.positive_block_dimensions,
        "gap_block_dimensions" => report.gap_block_dimensions,
        "equality_count" => report.equality_count,
        "psd_triangle_entries" => report.psd_triangle_entries,
        "maximum_side" => report.maximum_side,
    )
end

function spin_isotypic_truth_dict(truth)
    return Dict(
        "exact" => truth.exact,
        "trivial_blocks_exact" => truth.trivial_blocks_exact,
        "retained_block_dimensions" =>
            truth.retained_block_dimensions,
    )
end

function spin_stabilizer_structure_dict(structure)
    return Dict(
        "exact" => structure.exact,
        "dimensions_match" => structure.dimensions_match,
        "records" => [
            Dict(
                string(key) => value isa Symbol ? string(value) : value
                for (key, value) in pairs(record)
            )
            for record in structure.records
        ],
    )
end

function spin_stabilizer_coefficient_truth_dict(truth)
    return Dict(
        "exact" => truth.exact,
        "cross_zero" => truth.cross_zero,
        "cross_entry_count" => truth.cross_entry_count,
        "records" => [
            Dict(
                string(key) => value isa Symbol ? string(value) : value
                for (key, value) in pairs(record)
            )
            for record in truth.records
        ],
    )
end

function spin_l2_congruence_structure_dict(structure)
    return Dict(
        "exact" => structure.exact,
        "target_block_count" => structure.target_block_count,
        "records" => [
            Dict(
                string(key) => value isa Symbol ? string(value) : value
                for (key, value) in pairs(record)
            )
            for record in structure.records
        ],
    )
end

function spin_l2_congruence_truth_dict(truth)
    return Dict(
        "exact" => truth.exact,
        "target_block_count" => truth.target_block_count,
        "entry_count" => truth.entry_count,
        "equal_count" => truth.equal_count,
        "opposite_count" => truth.opposite_count,
        "unmatched_count" => truth.unmatched_count,
        "records" => [
            Dict(
                string(key) => value isa Symbol ? string(value) : value
                for (key, value) in pairs(record)
            )
            for record in truth.records
        ],
    )
end

function verify_reloaded_spin_isotypic_model(
    model::JuMP.Model,
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
)
    report =
        shastry_full_state_spin_isotypic_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.spin_isotypic_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        name = "shastry_l1d2_spin_isotypic_equality[$index]"
        isnothing(JuMP.constraint_by_name(model, name)) &&
            error("MOF lost equality $index")
    end
    for block in [assembly.positive_blocks; assembly.gap_blocks]
        name = shastry_full_state_spin_isotypic_block_name(block)
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type during reload")
        set.side_dimension == length(block.rows) ||
            error("$name changed side dimension during reload")
    end
    return true
end

function affine_residual(reference::JuMP.ConstraintRef)
    object = JuMP.constraint_object(reference)
    object.set isa JuMP.MOI.EqualTo{Float64} ||
        error("affine residual requested for a non-equality constraint")
    function_value = Float64(JuMP.value(reference))
    target = Float64(object.set.value)
    residual = abs(function_value - target)
    expression = JuMP.jump_function(object)
    scale = max(1.0, abs(target))
    if expression isa JuMP.GenericAffExpr
        term_magnitude = abs(Float64(expression.constant))
        for (variable, coefficient) in expression.terms
            term_magnitude +=
                abs(Float64(coefficient) * Float64(JuMP.value(variable)))
        end
        scale = max(scale, term_magnitude)
    else
        scale = max(scale, abs(function_value))
    end
    return Dict(
        "value" => function_value,
        "target" => target,
        "absolute_residual" => residual,
        "scale" => scale,
        "normalized_residual" => residual / scale,
    )
end

function reconstruct_symmetric_constraint(
    reference::JuMP.ConstraintRef,
    dimension::Int,
)
    raw_value = JuMP.value(reference)
    if raw_value isa Symmetric || raw_value isa AbstractMatrix
        matrix = Matrix{Float64}(raw_value)
        size(matrix) == (dimension, dimension) ||
            error("matrix-shaped cone value has the wrong size")
        return matrix
    end
    raw_value isa AbstractVector ||
        error("unsupported real PSD cone value shape $(typeof(raw_value))")
    expected_length = dimension * (dimension + 1) ÷ 2
    length(raw_value) == expected_length ||
        error(
            "packed real PSD value has length $(length(raw_value)); " *
            "expected $expected_length",
        )
    matrix = zeros(Float64, dimension, dimension)
    index = 0
    for column in 1:dimension
        for row in 1:column
            index += 1
            value = Float64(raw_value[index])
            matrix[row, column] = value
            matrix[column, row] = value
        end
    end
    return matrix
end

function spin_isotypic_solution_diagnostics(
    jump_model::ShastryFullStateSpinIsotypicJuMPPrimalModel,
    audit_tolerance::Float64,
)
    normalization = affine_residual(jump_model.normalization_constraint)
    equalities = Dict{String,Any}()
    maximum_absolute_equality_residual = 0.0
    maximum_normalized_equality_residual = 0.0
    for reference in jump_model.equality_constraints
        diagnostic = affine_residual(reference)
        name = JuMP.name(reference)
        equalities[name] = diagnostic
        maximum_absolute_equality_residual = max(
            maximum_absolute_equality_residual,
            diagnostic["absolute_residual"],
        )
        maximum_normalized_equality_residual = max(
            maximum_normalized_equality_residual,
            diagnostic["normalized_residual"],
        )
    end

    blocks = Dict{String,Any}()
    worst_psd_violation = 0.0
    worst_normalized_psd_violation = 0.0
    for reference in jump_model.psd_constraints
        object = JuMP.constraint_object(reference)
        dimension = object.set.side_dimension
        reconstructed = reconstruct_symmetric_constraint(
            reference,
            dimension,
        )
        symmetry_residual = maximum(
            abs,
            reconstructed - transpose(reconstructed),
        )
        eigenvalues = eigvals(Symmetric(reconstructed))
        minimum_eigenvalue = Float64(minimum(eigenvalues))
        maximum_absolute_eigenvalue = Float64(maximum(abs, eigenvalues))
        spectral_scale = max(1.0, maximum_absolute_eigenvalue)
        violation = max(0.0, -minimum_eigenvalue)
        normalized_violation = violation / spectral_scale
        worst_psd_violation = max(worst_psd_violation, violation)
        worst_normalized_psd_violation = max(
            worst_normalized_psd_violation,
            normalized_violation,
        )
        blocks[JuMP.name(reference)] = Dict(
            "dimension" => dimension,
            "minimum_eigenvalue" => minimum_eigenvalue,
            "maximum_absolute_eigenvalue" => maximum_absolute_eigenvalue,
            "symmetry_residual" => Float64(symmetry_residual),
            "psd_violation" => violation,
            "spectral_scale" => spectral_scale,
            "normalized_psd_violation" => normalized_violation,
        )
    end
    passed =
        normalization["normalized_residual"] <= audit_tolerance &&
        maximum_normalized_equality_residual <= audit_tolerance &&
        worst_normalized_psd_violation <= audit_tolerance &&
        all(
            block["symmetry_residual"] <= audit_tolerance
            for block in values(blocks)
        )
    return Dict(
        "available" => true,
        "passed" => passed,
        "audit_tolerance" => audit_tolerance,
        "normalization" => normalization,
        "affine_equalities" => equalities,
        "maximum_absolute_affine_equality_residual" =>
            maximum_absolute_equality_residual,
        "maximum_normalized_affine_equality_residual" =>
            maximum_normalized_equality_residual,
        "psd_blocks" => blocks,
        "worst_psd_violation" => worst_psd_violation,
        "worst_normalized_psd_violation" =>
            worst_normalized_psd_violation,
    )
end

function classify_spin_isotypic_result(
    termination,
    primal,
    dual,
    diagnostics,
)
    feasible_termination = termination in (
        JuMP.MOI.OPTIMAL,
        JuMP.MOI.LOCALLY_SOLVED,
        JuMP.MOI.ALMOST_OPTIMAL,
    )
    feasible_primal = primal in (
        JuMP.MOI.FEASIBLE_POINT,
        JuMP.MOI.NEARLY_FEASIBLE_POINT,
    )
    if feasible_termination && feasible_primal
        return diagnostics["passed"] ?
               "feasible_residual_checked_float" :
               "feasible_status_failed_residual_audit"
    end
    if termination in (
        JuMP.MOI.INFEASIBLE,
        JuMP.MOI.ALMOST_INFEASIBLE,
        JuMP.MOI.INFEASIBLE_OR_UNBOUNDED,
    ) || primal in (
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        JuMP.MOI.NEARLY_INFEASIBILITY_CERTIFICATE,
    ) || dual in (
        JuMP.MOI.INFEASIBILITY_CERTIFICATE,
        JuMP.MOI.NEARLY_INFEASIBILITY_CERTIFICATE,
    )
        return "infeasibility_candidate_requires_independent_ray_replay"
    end
    return "unknown"
end

function write_spin_isotypic_primal_values(
    path::AbstractString,
    jump_model::ShastryFullStateSpinIsotypicJuMPPrimalModel,
    assembly::ShastryFullStateSpinIsotypicReducedPrimalAssembly,
)
    length(jump_model.moment_variables) == length(assembly.moments) ||
        error("primal variable and exact moment inventories differ")
    values = JuMP.value.(jump_model.moment_variables)
    all(isfinite, values) ||
        error("solver returned a nonfinite primal variable")
    temporary = path * ".tmp"
    ispath(path) && error("refusing existing primal-value artifact: $path")
    ispath(temporary) &&
        error("refusing existing primal-value temporary artifact: $temporary")
    open(temporary, "w") do io
        println(
            io,
            "# schema=shastry-full-state-spin-isotypic-primal-values-v1",
        )
        println(io, "# assembly_sha256=", assembly.assembly_sha256)
        println(io, "index\tmoment_canonical\tfloat64_bits")
        for (index, (key, value)) in
            enumerate(zip(assembly.moments, values))
            println(io, index, '\t', key.canonical, '\t', bitstring(value))
        end
    end
    mv(temporary, path)
    return Dict(
        "schema_version" =>
            "shastry-full-state-spin-isotypic-primal-values-v1",
        "filename" => basename(path),
        "variable_count" => length(values),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "encoding" => "index-tab-canonical-moment-tab-ieee754-binary64-bits",
    )
end

function write_mosek_solution_artifact(
    path::AbstractString,
    model::JuMP.Model,
)
    backend = JuMP.unsafe_backend(model)
    backend isa MosekTools.Optimizer ||
        error("direct solve does not expose a MosekTools backend")
    Mosek.solutiondef(backend.task, Mosek.MSK_SOL_ITR) ||
        return Dict(
            "available" => false,
            "reason" => "mosek_interior_solution_not_defined",
        )
    endswith(path, ".bsol.gz") ||
        error("Mosek solution artifact must end in .bsol.gz")
    temporary = replace(path, r"(\.bsol\.gz)$" => s".tmp\1")
    ispath(path) && error("refusing existing Mosek solution artifact: $path")
    ispath(temporary) &&
        error("refusing existing Mosek solution temporary artifact: $temporary")
    Mosek.writebsolution(
        backend.task,
        temporary,
        Mosek.MSK_COMPRESS_GZIP,
    )
    mv(temporary, path)
    return Dict(
        "available" => true,
        "filename" => basename(path),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "mosek_solution_type" => "MSK_SOL_ITR",
        "format" => "mosek-binary-solution-gzip",
    )
end

function write_mosek_task_artifact(
    path::AbstractString,
    model::JuMP.Model,
)
    backend = JuMP.unsafe_backend(model)
    backend isa MosekTools.Optimizer ||
        error("direct solve does not expose a MosekTools backend")
    return write_mosek_task_artifact(path, backend.task)
end

function write_mosek_task_artifact(
    path::AbstractString,
    task::Mosek.Task,
)
    endswith(path, ".task") ||
        error("Mosek binary task artifact must end in .task")
    temporary = replace(path, r"(\.task)$" => s".tmp\1")
    ispath(path) && error("refusing existing Mosek task artifact: $path")
    ispath(temporary) &&
        error("refusing existing Mosek task temporary artifact: $temporary")
    Mosek.writetask(task, temporary)
    mv(temporary, path)
    return Dict(
        "available" => true,
        "filename" => basename(path),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "format" => "mosek-binary-task",
    )
end

const MOSEK_INFEASIBILITY_RAY_MAGIC =
    collect(codeunits("SSMOSEKRAYV1\n"))

function write_ray_u64(io::IO, value::Integer)
    write(io, htol(UInt64(value)))
end

function write_ray_float64_vector(io::IO, values::Vector{Float64})
    write_ray_u64(io, length(values))
    for value in values
        write(io, htol(reinterpret(UInt64, value)))
    end
end

function write_mosek_infeasibility_ray_artifact(
    path::AbstractString,
    model::JuMP.Model,
)
    backend = JuMP.unsafe_backend(model)
    backend isa MosekTools.Optimizer ||
        error("direct solve does not expose a MosekTools backend")
    return write_mosek_infeasibility_ray_artifact(path, backend.task)
end

function write_mosek_infeasibility_ray_artifact(
    path::AbstractString,
    task::Mosek.Task,
)
    problem_status = Mosek.getprosta(task, Mosek.MSK_SOL_ITR)
    solution_status = Mosek.getsolsta(task, Mosek.MSK_SOL_ITR)
    problem_status == Mosek.MSK_PRO_STA_PRIM_INFEAS ||
        error("refusing ray export without primal-infeasible problem status")
    solution_status == Mosek.MSK_SOL_STA_PRIM_INFEAS_CER ||
        error("refusing ray export without a primal-infeasibility certificate")

    y = Mosek.gety(task, Mosek.MSK_SOL_ITR)
    slc = Mosek.getslc(task, Mosek.MSK_SOL_ITR)
    suc = Mosek.getsuc(task, Mosek.MSK_SOL_ITR)
    slx = Mosek.getslx(task, Mosek.MSK_SOL_ITR)
    sux = Mosek.getsux(task, Mosek.MSK_SOL_ITR)
    snx = Mosek.getsnx(task, Mosek.MSK_SOL_ITR)
    doty = Mosek.getaccdotys(task, Mosek.MSK_SOL_ITR)
    bar_duals = [
        Mosek.getbarsj(task, Mosek.MSK_SOL_ITR, index)
        for index in 1:Int(Mosek.getnumbarvar(task))
    ]
    all(
        isfinite,
        Iterators.flatten((y, slc, suc, slx, sux, snx, doty, bar_duals...)),
    ) || error("refusing nonfinite Mosek infeasibility ray")

    endswith(path, ".ray.bin") ||
        error("Mosek ray artifact must end in .ray.bin")
    temporary = path * ".tmp"
    ispath(path) && error("refusing existing Mosek ray artifact: $path")
    ispath(temporary) &&
        error("refusing existing Mosek ray temporary artifact: $temporary")
    open(temporary, "w") do io
        write(io, MOSEK_INFEASIBILITY_RAY_MAGIC)
        write_ray_u64(io, problem_status.value)
        write_ray_u64(io, solution_status.value)
        write_ray_u64(io, Int(Mosek.getnumcon(task)))
        write_ray_u64(io, Int(Mosek.getnumvar(task)))
        write_ray_u64(io, Int(Mosek.getnumcone(task)))
        write_ray_u64(io, Int(Mosek.getnumbarvar(task)))
        for values in (y, slc, suc, slx, sux, snx, doty)
            write_ray_float64_vector(io, values)
        end
        write_ray_u64(io, length(bar_duals))
        for (index, values) in enumerate(bar_duals)
            write_ray_u64(io, Int(Mosek.getdimbarvarj(task, index)))
            write_ray_float64_vector(io, values)
        end
    end
    mv(temporary, path)
    return Dict(
        "available" => true,
        "schema_version" => "shastry-mosek-infeasibility-ray-v1",
        "filename" => basename(path),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "endianness" => "little",
        "problem_status" => sprint(show, problem_status),
        "solution_status" => sprint(show, solution_status),
        "constraint_count" => length(y),
        "scalar_variable_count" => length(slx),
        "affine_conic_dual_count" => length(doty),
        "semidefinite_variable_count" => length(bar_duals),
        "semidefinite_packed_value_count" =>
            sum(length, bar_duals; init=0),
    )
end

const MOSEK_DUAL_CERTIFICATE_MAGIC =
    collect(codeunits("SSMOSEKCERTV1\n"))

function write_mosek_dual_certificate_artifact(
    path::AbstractString,
    task::Mosek.Task,
)
    problem_status = Mosek.getprosta(task, Mosek.MSK_SOL_ITR)
    solution_status = Mosek.getsolsta(task, Mosek.MSK_SOL_ITR)
    solution_status == Mosek.MSK_SOL_STA_OPTIMAL ||
        error("refusing dual-certificate export without an optimal solution")
    Int(Mosek.getnumcone(task)) == 0 ||
        error("dual-certificate artifact does not encode scalar cones")
    Int(Mosek.getnumacc(task)) == 0 ||
        error("dual-certificate artifact does not encode affine cones")

    constraint_values = Mosek.getxc(task, Mosek.MSK_SOL_ITR)
    scalar_values = Mosek.getxx(task, Mosek.MSK_SOL_ITR)
    semidefinite_values = [
        Mosek.getbarxj(task, Mosek.MSK_SOL_ITR, index)
        for index in 1:Int(Mosek.getnumbarvar(task))
    ]
    all(
        isfinite,
        Iterators.flatten((
            constraint_values,
            scalar_values,
            semidefinite_values...,
        )),
    ) || error("refusing nonfinite Mosek dual certificate")

    endswith(path, ".certificate.bin") || error(
        "Mosek dual-certificate artifact must end in .certificate.bin",
    )
    temporary = path * ".tmp"
    ispath(path) &&
        error("refusing existing Mosek dual-certificate artifact: $path")
    ispath(temporary) && error(
        "refusing existing Mosek dual-certificate temporary artifact: " *
        temporary,
    )
    open(temporary, "w") do io
        write(io, MOSEK_DUAL_CERTIFICATE_MAGIC)
        write_ray_u64(io, problem_status.value)
        write_ray_u64(io, solution_status.value)
        write_ray_u64(io, Int(Mosek.getnumcon(task)))
        write_ray_u64(io, Int(Mosek.getnumvar(task)))
        write_ray_u64(io, Int(Mosek.getnumcone(task)))
        write_ray_u64(io, Int(Mosek.getnumacc(task)))
        write_ray_u64(io, Int(Mosek.getnumbarvar(task)))
        write_ray_float64_vector(io, constraint_values)
        write_ray_float64_vector(io, scalar_values)
        write_ray_u64(io, length(semidefinite_values))
        for (index, values) in enumerate(semidefinite_values)
            write_ray_u64(io, Int(Mosek.getdimbarvarj(task, index)))
            write_ray_float64_vector(io, values)
        end
    end
    mv(temporary, path)
    return Dict(
        "available" => true,
        "schema_version" => "shastry-mosek-dual-certificate-v1",
        "filename" => basename(path),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "endianness" => "little",
        "problem_status" => sprint(show, problem_status),
        "solution_status" => sprint(show, solution_status),
        "constraint_count" => length(constraint_values),
        "scalar_variable_count" => length(scalar_values),
        "semidefinite_variable_count" => length(semidefinite_values),
        "semidefinite_packed_value_count" =>
            sum(length, semidefinite_values; init=0),
    )
end

function write_native_mosek_primal_values(
    path::AbstractString,
    primal::ShastryFullStateSpinIsotypicMosekPrimal,
)
    values = Mosek.getxx(primal.task, Mosek.MSK_SOL_ITR)
    ordered = sort!(
        collect(primal.moment_variables);
        by=pair -> last(pair),
    )
    length(ordered) == length(values) ||
        error("native primal moment and value counts differ")
    all(
        Int(index) == position
        for (position, (_, index)) in enumerate(ordered)
    ) || error("native primal moment indices are not contiguous")
    all(isfinite, values) || error("native primal contains nonfinite values")
    temporary = path * ".tmp"
    ispath(path) && error("refusing existing native primal artifact: $path")
    ispath(temporary) &&
        error("refusing existing native primal temporary artifact: $temporary")
    open(temporary, "w") do io
        println(
            io,
            "# schema=shastry-full-state-spin-isotypic-native-primal-values-v1",
        )
        println(
            io,
            "# coefficient_map_sha256=",
            primal.coefficient_map_sha256,
        )
        println(io, "index\tmoment_canonical\tfloat64_bits")
        for (position, (key, _)) in enumerate(ordered)
            println(
                io,
                position,
                '\t',
                key.canonical,
                '\t',
                bitstring(values[position]),
            )
        end
    end
    mv(temporary, path)
    return Dict(
        "schema_version" =>
            "shastry-full-state-spin-isotypic-native-primal-values-v1",
        "filename" => basename(path),
        "variable_count" => length(values),
        "bytes" => filesize(path),
        "sha256" => file_sha256(path),
        "encoding" =>
            "index-tab-canonical-moment-tab-ieee754-binary64-bits",
    )
end

function spin_isotypic_main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = spin_isotypic_source_dict()
    mkpath(options.output)
    checkpoint_path = joinpath(options.output, "runmeta.toml")
    metadata = Dict(
        "schema_version" => options.patch_level == 1 ?
            SPIN_ISOTYPIC_RUNMETA_SCHEMA :
            "shastry-l$(options.patch_level)d2-full-state-spin-isotypic-preflight-v1",
        "state" => "running",
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "mode" => string(options.mode),
        "output_relative" => options.output_relative,
        "source" => source,
        "setup" => Dict(
            "hamiltonian" =>
                "H=sum_dimer S_i.S_j + g sum_square_nn S_i.S_j",
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => rational_dict(options.coupling),
            "gamma" => rational_dict(options.gamma),
            "patch_level" => options.patch_level,
            "degree_d" => 2,
            "basis" => "complete-state-polynomial-v1",
            "stationarity" => "complete-inner-state-v1",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
            "state_class" => "unrestricted",
            "exact_additional_reduction" =>
                get(ENV, "SHASTRY_SU2_RANK4_REDUCTION", "0") == "1" ?
                "spin-S3-isotypic-plus-exact-SO3-rank4-moment-reduction" :
                "spin-S3-moment-quotient-and-isotypic-cone-blocking",
        ),
        "stages" => Dict{String,Any}(),
        "intermediate_truth_mode" => options.patch_level == 1 ?
            "exhaustive-coefficient-gates" :
            "preflight-structural-assembly-final-isotypic-gate",
    )
    write_checkpoint(checkpoint_path, metadata)

    progress(
        "assemble complete L=$(options.patch_level),d=2 " *
        "state-polynomial primal",
    )
    problem = GapProblem(
        square_patch_geometry(options.patch_level),
        shastry_sutherland_model(options.coupling),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    on_demand_moments =
        options.patch_level > 1 ||
        get(ENV, "SHASTRY_ON_DEMAND_MOMENTS", "0") == "1"
    primal_measurement = @timed assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
        materialize_coefficients=options.patch_level == 1 &&
                                 get(
                                     ENV,
                                     "SHASTRY_STRUCTURAL_PRIMAL",
                                     "0",
                                 ) != "1",
        structural_moment_filter=options.patch_level > 1 ||
                                 get(
                                     ENV,
                                     "SHASTRY_FILTER_PRIMAL_MOMENTS",
                                     "0",
                                 ) == "1" ?
                                 :v4_conjugation_even :
                                 :all,
        materialize_moment_inventory=!on_demand_moments,
    )
    primal = primal_measurement.value
    metadata["stages"]["primal"] = measurement_dict(primal_measurement)
    metadata["primal"] = Dict(
        "assembly_sha256" => primal.assembly_sha256,
        "problem_sha256" => primal.problem_sha256,
        "positive_dimension" => length(primal.positive_basis.entries),
        "gap_dimension" => length(primal.gap_basis.entries),
        "moment_count" => length(primal.moments),
        "moment_inventory" => on_demand_moments ?
            "deferred-on-demand-v1" :
            "materialized-v1",
        "stationarity_equality_count" =>
            length(primal.stationarity_equalities),
    )
    write_checkpoint(checkpoint_path, metadata)

    progress("exact V4, conjugation, anti-diagonal, and spin quotient")
    structural_intermediate =
        options.patch_level > 1 ||
        get(ENV, "SHASTRY_STRUCTURAL_INTERMEDIATE", "0") == "1"
    exhaustive_intermediate_truth =
        options.patch_level == 1 && !structural_intermediate
    metadata["intermediate_assembly"] = structural_intermediate ?
        "structural-deferred-coefficients-v1" :
        "materialized-coefficients-v1"
    v4_measurement = @timed assemble_full_state_v4_reduced_primal(
        primal;
        verify_truth=exhaustive_intermediate_truth,
        materialize_coefficients=!structural_intermediate,
    )
    v4 = v4_measurement.value
    metadata["stages"]["v4"] = measurement_dict(v4_measurement)
    real_measurement = @timed assemble_full_state_real_reduced_primal(
        v4;
        verify_truth=exhaustive_intermediate_truth,
        materialize_coefficients=!structural_intermediate,
    )
    real_reduced = real_measurement.value
    metadata["stages"]["conjugation"] =
        measurement_dict(real_measurement)
    spatial_measurement =
        @timed assemble_shastry_full_state_spatial_reduced_primal(
            real_reduced;
            verify_truth=exhaustive_intermediate_truth,
            materialize_coefficients=!structural_intermediate,
        )
    spatial = spatial_measurement.value
    metadata["stages"]["spatial"] = measurement_dict(spatial_measurement)
    spin_measurement =
        @timed assemble_shastry_full_state_spin_spatial_reduced_primal(
            spatial;
            verify_truth=exhaustive_intermediate_truth,
            verify_source_covariance=exhaustive_intermediate_truth,
            materialize_coefficients=!structural_intermediate,
        )
    spin_spatial = spin_measurement.value
    metadata["stages"]["spin_spatial"] =
        measurement_dict(spin_measurement)
    if exhaustive_intermediate_truth
        metadata["spin_spatial_truth"] =
            spin_spatial_truth_dict(something(spin_spatial.truth))
    end
    write_checkpoint(checkpoint_path, metadata)

    materialize_isotypic_coefficients =
        options.mode in (:preflight, :mof)
    stabilizer_split =
        get(ENV, "SHASTRY_STABILIZER_CONE_SPLIT", "0") == "1"
    so3_l2_congruence_truth =
        get(ENV, "SHASTRY_SO3_L2_CONGRUENCE_TRUTH", "0") == "1"
    so3_l2_cone_dedup =
        get(ENV, "SHASTRY_SO3_L2_CONE_DEDUP", "0") == "1"
    so3_l2_truth_only =
        get(ENV, "SHASTRY_SO3_L2_TRUTH_ONLY", "0") == "1"
    if stabilizer_split &&
       get(ENV, "SHASTRY_STABILIZER_COEFFICIENT_TRUTH", "0") != "1"
        error(
            "SHASTRY_STABILIZER_CONE_SPLIT requires the exact " *
            "stabilizer coefficient truth gate",
        )
    end
    if (so3_l2_congruence_truth || so3_l2_cone_dedup) &&
       (!stabilizer_split ||
        get(ENV, "SHASTRY_SU2_RANK4_REDUCTION", "0") != "1")
        error(
            "SO(3) l2 congruence requires the stabilizer split and " *
            "exact SO(3) rank-four projection",
        )
    end
    if so3_l2_cone_dedup && !so3_l2_congruence_truth
        error(
            "SHASTRY_SO3_L2_CONE_DEDUP requires the exact l2 " *
            "congruence truth gate",
        )
    end
    if so3_l2_truth_only && !so3_l2_congruence_truth
        error(
            "SHASTRY_SO3_L2_TRUTH_ONLY requires the exact l2 " *
            "congruence truth gate",
        )
    end
    progress(
        !materialize_isotypic_coefficients ?
        "exact S3 structural cone blocking" :
        "exact S3 isotypic cone blocking",
    )
    isotypic_measurement =
        @timed assemble_shastry_full_state_spin_isotypic_reduced_primal(
            spin_spatial,
            verify_truth=exhaustive_intermediate_truth,
            materialize_coefficients=materialize_isotypic_coefficients,
            stabilizer_split=stabilizer_split,
            so3_l2_dedup=false,
        )
    isotypic = isotypic_measurement.value
    spin_stabilizer_structure =
        shastry_spin_stabilizer_structure(spin_spatial)
    spin_stabilizer_structure.exact ||
        error("spin-stabilizer structural gate failed")
    metadata["stages"]["spin_isotypic"] =
        measurement_dict(isotypic_measurement)
    metadata["spin_stabilizer_structure"] =
        spin_stabilizer_structure_dict(spin_stabilizer_structure)
    if get(ENV, "SHASTRY_STABILIZER_COEFFICIENT_TRUTH", "0") == "1"
        progress("exact nontrivial-character stabilizer cross-zero gate")
        stabilizer_truth_measurement =
            @timed shastry_spin_stabilizer_coefficient_truth(spin_spatial)
        stabilizer_truth = stabilizer_truth_measurement.value
        stabilizer_truth.exact ||
            error("spin-stabilizer coefficient truth gate failed")
        metadata["stages"]["spin_stabilizer_coefficient_truth"] =
            measurement_dict(stabilizer_truth_measurement)
        metadata["spin_stabilizer_coefficient_truth"] =
            spin_stabilizer_coefficient_truth_dict(stabilizer_truth)
    end
    if stabilizer_split
        spin_l2_structure =
            shastry_spin_l2_congruence_structure(isotypic)
        spin_l2_structure.exact ||
            error("spin-l2 congruence structural gate failed")
        metadata["spin_l2_congruence_structure"] =
            spin_l2_congruence_structure_dict(spin_l2_structure)
    end
    if so3_l2_congruence_truth
        progress("exact post-SO(3) l2 cone-congruence gate")
        eliminated_by_thread = [
            Set{MomentKey}()
            for _ in 1:Threads.nthreads()
        ]
        cache_by_thread = [
            Dict{MomentKey,ExactLinearPolynomial}()
            for _ in 1:Threads.nthreads()
        ]
        project = polynomial -> begin
            thread = Threads.threadid()
            su2_rank4_polynomial_projection(
                polynomial,
                isotypic,
                eliminated_by_thread[thread],
                cache_by_thread[thread],
            )
        end
        l2_truth_measurement = @timed shastry_spin_l2_congruence_truth(
            isotypic;
            project=project,
            progress_callback=progress,
        )
        l2_truth = l2_truth_measurement.value
        metadata["stages"]["spin_l2_congruence_truth"] =
            measurement_dict(l2_truth_measurement)
        metadata["spin_l2_congruence_truth"] =
            spin_l2_congruence_truth_dict(l2_truth)
        metadata["spin_l2_congruence_truth"][
            "su2_rank4_eliminated_moments"
        ] = length(union(eliminated_by_thread...))
        write_checkpoint(checkpoint_path, metadata)
        l2_truth.exact ||
            error("post-SO(3) l2 cone-congruence truth gate failed")
        if so3_l2_cone_dedup
            progress("remove exactly congruent duplicate l2 cones")
            dedup_measurement = @timed(
                assemble_shastry_full_state_spin_isotypic_reduced_primal(
                    spin_spatial;
                    verify_truth=false,
                    materialize_coefficients=
                        materialize_isotypic_coefficients,
                    stabilizer_split=true,
                    so3_l2_dedup=true,
                )
            )
            isotypic = dedup_measurement.value
            metadata["stages"]["spin_l2_cone_dedup"] =
                measurement_dict(dedup_measurement)
        end
    end
    report =
        shastry_full_state_spin_isotypic_reduced_assembly_report(isotypic)
    metadata["reduced"] = spin_isotypic_report_dict(report)
    metadata["reduced"]["positive_block_labels"] = String[
        ShastryFullStateSpinIsotypicReduction.block_label(block)
        for block in isotypic.positive_blocks
    ]
    metadata["reduced"]["gap_block_labels"] = String[
        ShastryFullStateSpinIsotypicReduction.block_label(block)
        for block in isotypic.gap_blocks
    ]
    metadata["reduced"]["assembly_sha256"] = isotypic.assembly_sha256
    metadata["reduced"]["stabilizer_cone_split"] = stabilizer_split
    metadata["reduced"]["so3_l2_cone_dedup"] = so3_l2_cone_dedup
    metadata["reduced"]["coefficient_map_sha256"] =
        isotypic.coefficient_map_sha256
    metadata["coefficient_inventory"] = !materialize_isotypic_coefficients ?
        "deferred-structural-v1" :
        "materialized-exact-v1"
    if !isnothing(isotypic.truth)
        metadata["spin_isotypic_truth"] =
            spin_isotypic_truth_dict(something(isotypic.truth))
    end
    write_checkpoint(checkpoint_path, metadata)

    if so3_l2_truth_only
        metadata["solve"] = Dict(
            "classification" => "not_run_exact_so3_l2_truth_only",
            "formulation" =>
                "post-so3-rank4-l2-cone-congruence-gate-v1",
        )
        metadata["state"] = "complete"
        metadata["completed_at_utc"] = Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        )
        write_checkpoint(checkpoint_path, metadata)
        progress("complete exact SO(3) l2 truth; optimization skipped")
        return
    end

    if options.mode == :certificate
        threads = parse(
            Int,
            get(
                ENV,
                "SS_MOSEK_THREADS",
                get(ENV, "SLURM_CPUS_PER_TASK", "1"),
            ),
        )
        time_limit_seconds = parse(
            Float64,
            get(ENV, "SS_MOSEK_TIME_LIMIT_SECONDS", "43200"),
        )
        log_level =
            parse(Int, get(ENV, "SS_MOSEK_LOG_LEVEL", "1"))
        progress("build low-level native Mosek dual certificate")
        certificate_measurement = @timed(
            build_shastry_full_state_spin_isotypic_mosek_dual_certificate(
                isotypic;
                threads=threads,
                time_limit_seconds=time_limit_seconds,
                log_level=log_level,
                progress_callback=progress,
                fingerprint_coefficients=
                    options.patch_level == 1 ||
                    get(
                        ENV,
                        "SHASTRY_CERTIFICATE_FINGERPRINT",
                        "0",
                    ) == "1",
                su2_rank4_reduction=
                    get(ENV, "SHASTRY_SU2_RANK4_REDUCTION", "0") == "1",
            )
        )
        certificate = certificate_measurement.value
        expected_coefficient_map_sha256 = get(
            ENV,
            "SS_EXPECTED_COEFFICIENT_MAP_SHA256",
            "",
        )
        coefficient_regression_passed =
            isempty(expected_coefficient_map_sha256) ||
            certificate.coefficient_map_sha256 ==
            expected_coefficient_map_sha256
        coefficient_regression_passed || error(
            "native dual coefficient-map regression failed: expected " *
            expected_coefficient_map_sha256 *
            ", observed " *
            certificate.coefficient_map_sha256,
        )
        metadata["stages"]["dual_certificate"] =
            measurement_dict(certificate_measurement)
        metadata["dual_certificate"] = Dict(
            "moment_matching_equalities" =>
                length(certificate.moment_constraints),
            "native_psd_blocks" =>
                certificate.native_psd_blocks,
            "equality_multipliers" =>
                certificate.equality_multipliers,
            "scalar_coefficient_terms" =>
                certificate.scalar_coefficient_terms,
            "coefficient_map_sha256" =>
                certificate.coefficient_map_sha256,
            "su2_rank4_reduction" =>
                certificate.su2_rank4_reduction,
            "su2_rank4_eliminated_moments" =>
                certificate.su2_rank4_eliminated_moments,
            "expected_coefficient_map_sha256" =>
                expected_coefficient_map_sha256,
            "coefficient_regression_passed" =>
                coefficient_regression_passed,
        )
        metadata["reduced"]["spin_isotypic_moments"] =
            length(certificate.moment_constraints)
        metadata["reduced"]["coefficient_map_sha256"] =
            certificate.coefficient_map_sha256
        metadata["coefficient_inventory"] =
            certificate.su2_rank4_reduction ?
            "streamed-native-mosek-dual-su2-rank4-v1" :
            "streamed-native-mosek-dual-v1"
        write_checkpoint(checkpoint_path, metadata)
        if get(ENV, "SHASTRY_CERTIFICATE_BUILD_ONLY", "0") == "1"
            metadata["solve"] = Dict(
                "classification" => "not_run_exact_build_only",
                "formulation" => certificate.su2_rank4_reduction ?
                    "low-level-native-mosek-dual-farkas-su2-rank4-v1" :
                    "low-level-native-mosek-dual-farkas-certificate-v2",
            )
            metadata["state"] = "complete"
            metadata["completed_at_utc"] = Dates.format(
                now(UTC),
                dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
            )
            write_checkpoint(checkpoint_path, metadata)
            progress("complete exact certificate build; optimization skipped")
            return
        end
        progress(
            "optimize native dual certificate; threads=$threads, " *
            "time_limit=$(time_limit_seconds)s",
        )
        solve_measurement = @timed(
            optimize_shastry_full_state_spin_isotypic_mosek_dual_certificate!(
                certificate,
            )
        )
        metadata["stages"]["solve"] =
            measurement_dict(solve_measurement)
        solve_result = solve_measurement.value
        audit_tolerance = parse(
            Float64,
            get(ENV, "SS_AUDIT_TOLERANCE", "1e-7"),
        )
        maximum_primal_violation = maximum((
            solve_result.maximum_constraint_violation,
            solve_result.maximum_scalar_variable_violation,
            solve_result.maximum_semidefinite_variable_violation,
        ))
        classification = if solve_result.classification ==
                            "primal_infeasibility_certificate_found"
            if maximum_primal_violation <= audit_tolerance
                progress(
                    "preserve native dual task and exact-bit certificate",
                )
                metadata["mosek_dual_certificate_task"] =
                    write_mosek_task_artifact(
                        joinpath(
                            options.output,
                            "mosek-dual-certificate.task",
                        ),
                        certificate.task,
                    )
                metadata["mosek_dual_certificate"] =
                    write_mosek_dual_certificate_artifact(
                        joinpath(
                            options.output,
                            "mosek-dual-certificate.certificate.bin",
                        ),
                        certificate.task,
                    )
                "infeasibility_certificate_candidate_requires_independent_primal_replay"
            else
                "infeasibility_certificate_failed_residual_audit"
            end
        else
            solve_result.classification
        end
        metadata["solve"] = Dict(
            "formulation" =>
                certificate.su2_rank4_reduction ?
                "low-level-native-mosek-dual-farkas-su2-rank4-v1" :
                "low-level-native-mosek-dual-farkas-certificate-v2",
            "native_solver_classification" =>
                solve_result.classification,
            "classification" => classification,
            "problem_status" =>
                sprint(show, solve_result.problem_status),
            "solution_status" =>
                sprint(show, solve_result.solution_status),
            "maximum_constraint_violation" =>
                solve_result.maximum_constraint_violation,
            "maximum_scalar_variable_violation" =>
                solve_result.maximum_scalar_variable_violation,
            "maximum_semidefinite_variable_violation" =>
                solve_result.maximum_semidefinite_variable_violation,
            "maximum_primal_violation" => maximum_primal_violation,
            "audit_tolerance" => audit_tolerance,
            "threads" => threads,
            "time_limit_seconds" => time_limit_seconds,
        )
        write_checkpoint(checkpoint_path, metadata)
    end

    if options.mode == :native
        threads = parse(
            Int,
            get(
                ENV,
                "SS_MOSEK_THREADS",
                get(ENV, "SLURM_CPUS_PER_TASK", "1"),
            ),
        )
        time_limit_seconds = parse(
            Float64,
            get(ENV, "SS_MOSEK_TIME_LIMIT_SECONDS", "43200"),
        )
        log_level =
            parse(Int, get(ENV, "SS_MOSEK_LOG_LEVEL", "1"))
        progress("build low-level native Mosek primal")
        native_measurement = @timed(
            build_shastry_full_state_spin_isotypic_mosek_primal(
                isotypic;
                threads=threads,
                time_limit_seconds=time_limit_seconds,
                log_level=log_level,
                progress_callback=progress,
                fingerprint_coefficients=
                    options.patch_level == 1 ||
                    get(
                        ENV,
                        "SHASTRY_NATIVE_FINGERPRINT",
                        "0",
                    ) == "1",
                su2_rank4_reduction=
                    get(ENV, "SHASTRY_SU2_RANK4_REDUCTION", "0") == "1",
            )
        )
        native_primal = native_measurement.value
        expected_coefficient_map_sha256 = get(
            ENV,
            "SS_EXPECTED_COEFFICIENT_MAP_SHA256",
            "",
        )
        coefficient_regression_passed =
            isempty(expected_coefficient_map_sha256) ||
            native_primal.coefficient_map_sha256 ==
            expected_coefficient_map_sha256
        coefficient_regression_passed || error(
            "native coefficient-map regression failed: expected " *
            expected_coefficient_map_sha256 *
            ", observed " *
            native_primal.coefficient_map_sha256,
        )
        metadata["stages"]["native_primal"] =
            measurement_dict(native_measurement)
        metadata["native_primal"] = Dict(
            "moment_variables" =>
                length(native_primal.moment_variables),
            "native_psd_blocks" =>
                native_primal.native_psd_blocks,
            "equality_constraints" =>
                native_primal.equality_constraints,
            "scalar_coefficient_terms" =>
                native_primal.scalar_coefficient_terms,
            "coefficient_map_sha256" =>
                native_primal.coefficient_map_sha256,
            "su2_rank4_reduction" =>
                native_primal.su2_rank4_reduction,
            "su2_rank4_eliminated_moments" =>
                native_primal.su2_rank4_eliminated_moments,
            "expected_coefficient_map_sha256" =>
                expected_coefficient_map_sha256,
            "coefficient_regression_passed" =>
                coefficient_regression_passed,
        )
        metadata["reduced"]["spin_isotypic_moments"] =
            length(native_primal.moment_variables)
        metadata["reduced"]["coefficient_map_sha256"] =
            native_primal.coefficient_map_sha256
        metadata["coefficient_inventory"] =
            native_primal.su2_rank4_reduction ?
            "streamed-native-mosek-su2-rank4-v1" :
            "streamed-native-mosek-v1"
        write_checkpoint(checkpoint_path, metadata)
        progress(
            "optimize native Mosek primal; threads=$threads, " *
            "time_limit=$(time_limit_seconds)s",
        )
        solve_measurement = @timed(
            optimize_shastry_full_state_spin_isotypic_mosek_primal!(
                native_primal,
            )
        )
        metadata["stages"]["solve"] =
            measurement_dict(solve_measurement)
        solve_result = solve_measurement.value
        audit_tolerance = parse(
            Float64,
            get(ENV, "SS_AUDIT_TOLERANCE", "1e-7"),
        )
        classification = if solve_result.classification ==
                            "feasible_native_primal"
            if solve_result.maximum_acc_violation <= audit_tolerance &&
               solve_result.maximum_equality_violation <= audit_tolerance
                metadata["primal_values"] = write_native_mosek_primal_values(
                    joinpath(options.output, "native-primal-values.tsv"),
                    native_primal,
                )
                "feasible_residual_checked_float"
            else
                "feasible_status_failed_residual_audit"
            end
        elseif solve_result.classification ==
               "primal_infeasibility_certificate_found"
            progress("preserve native task and exact-bit dual ray")
            metadata["mosek_infeasibility_task"] =
                write_mosek_task_artifact(
                    joinpath(options.output, "mosek-infeasibility.task"),
                    native_primal.task,
                )
            metadata["mosek_infeasibility_ray"] =
                write_mosek_infeasibility_ray_artifact(
                    joinpath(options.output, "mosek-infeasibility.ray.bin"),
                    native_primal.task,
                )
            "infeasibility_candidate_requires_independent_ray_replay"
        else
            "unknown"
        end
        metadata["solve"] = Dict(
            "formulation" =>
                native_primal.su2_rank4_reduction ?
                "low-level-native-mosek-affine-psd-primal-su2-rank4-v1" :
                "low-level-native-mosek-affine-psd-primal-v1",
            "native_solver_classification" => solve_result.classification,
            "classification" => classification,
            "problem_status" =>
                sprint(show, solve_result.problem_status),
            "solution_status" =>
                sprint(show, solve_result.solution_status),
            "maximum_acc_violation" =>
                solve_result.maximum_acc_violation,
            "maximum_equality_violation" =>
                solve_result.maximum_equality_violation,
            "audit_tolerance" => audit_tolerance,
            "threads" => threads,
            "time_limit_seconds" => time_limit_seconds,
        )
        write_checkpoint(checkpoint_path, metadata)
    end

    if options.mode in (:mof, :solve)
        progress(
            options.mode == :mof ?
            "materialize, write, and reload optimizer-free MOF" :
            "stream exact coefficients directly into Mosek",
        )
        if options.mode == :solve
            threads = parse(
                Int,
                get(
                    ENV,
                    "SS_MOSEK_THREADS",
                    get(ENV, "SLURM_CPUS_PER_TASK", "1"),
                ),
            )
            time_limit_seconds = parse(
                Float64,
                get(ENV, "SS_MOSEK_TIME_LIMIT_SECONDS", "43200"),
            )
            log_level =
                parse(Int, get(ENV, "SS_MOSEK_LOG_LEVEL", "1"))
            bridged_optimizer =
                JuMP.MOI.Bridges.full_bridge_optimizer(
                    MosekTools.Optimizer(),
                    Float64,
                )
            direct_model = JuMP.direct_model(bridged_optimizer)
            JuMP.set_time_limit_sec(direct_model, time_limit_seconds)
            JuMP.set_optimizer_attribute(
                direct_model,
                "MSK_IPAR_NUM_THREADS",
                threads,
            )
            JuMP.set_optimizer_attribute(
                direct_model,
                "MSK_IPAR_LOG",
                log_level,
            )
            jump_measurement = @timed(
                build_shastry_full_state_spin_isotypic_streaming_jump_primal(
                    isotypic;
                    model=direct_model,
                    fingerprint_coefficients=
                        options.patch_level == 1 ||
                        get(
                            ENV,
                            "SHASTRY_STREAM_FINGERPRINT",
                            "0",
                        ) == "1",
                )
            )
        else
            jump_measurement =
                @timed build_shastry_full_state_spin_isotypic_jump_primal(
                    isotypic,
                )
        end
        jump_model = jump_measurement.value
        metadata["stages"]["jump"] = measurement_dict(jump_measurement)
        if options.mode == :solve
            metadata["reduced"]["spin_isotypic_moments"] =
                length(jump_model.moment_variables)
            metadata["reduced"]["coefficient_map_sha256"] =
                jump_model.coefficient_map_sha256
            metadata["reduced"]["assembly_sha256"] =
                jump_model.assembly_sha256
            metadata["coefficient_inventory"] =
                "streamed-direct-to-solver-v1"
            metadata["streamed_coefficient_fingerprint"] =
                jump_model.coefficient_map_sha256 !=
                "omitted-streaming-v1"
        end
        write_checkpoint(checkpoint_path, metadata)
    end

    if options.mode == :mof
        mof_path = joinpath(options.output, "model.mof.json")
        write_measurement =
            @timed JuMP.write_to_file(jump_model.model, mof_path)
        metadata["stages"]["write_mof"] =
            measurement_dict(write_measurement)
        metadata["mof_sha256"] = file_sha256(mof_path)
        replay_measurement = @timed JuMP.read_from_file(mof_path)
        verify_reloaded_spin_isotypic_model(
            replay_measurement.value,
            isotypic,
        )
        metadata["stages"]["reload_mof"] =
            measurement_dict(replay_measurement)
    elseif options.mode == :solve
        progress(
            "optimize direct Mosek model; threads=$threads, " *
            "time_limit=$(time_limit_seconds)s",
        )
        solve_measurement = @timed JuMP.optimize!(jump_model.model)
        metadata["stages"]["solve"] = measurement_dict(solve_measurement)
        termination = JuMP.termination_status(jump_model.model)
        primal = JuMP.primal_status(jump_model.model)
        dual = JuMP.dual_status(jump_model.model)
        metadata["solve"] = Dict(
            "termination_status" =>
                string(termination),
            "primal_status" => string(primal),
            "dual_status" => string(dual),
            "raw_status" => try
                JuMP.raw_status(jump_model.model)
            catch exception
                "unavailable: " * sprint(showerror, exception)
            end,
            "result_count" => JuMP.result_count(jump_model.model),
            "has_values" => JuMP.has_values(jump_model.model),
            "has_duals" => JuMP.has_duals(jump_model.model),
            "solver_reported_solve_time_seconds" => try
                JuMP.solve_time(jump_model.model)
            catch
                NaN
            end,
            "threads" => threads,
            "time_limit_seconds" => time_limit_seconds,
        )
        audit_tolerance = parse(
            Float64,
            get(ENV, "SS_AUDIT_TOLERANCE", "1e-7"),
        )
        diagnostics = if JuMP.has_values(jump_model.model)
            progress("export primal values and audit every PSD block")
            metadata["primal_values"] = write_spin_isotypic_primal_values(
                joinpath(options.output, "primal-values.tsv"),
                jump_model,
                isotypic,
            )
            spin_isotypic_solution_diagnostics(
                jump_model,
                audit_tolerance,
            )
        else
            Dict(
                "available" => false,
                "reason" => "solver_returned_no_primal_values",
            )
        end
        metadata["solution_diagnostics"] = diagnostics
        classification = classify_spin_isotypic_result(
            termination,
            primal,
            dual,
            diagnostics,
        )
        metadata["solve"]["classification"] = classification
        metadata["mosek_solution"] = write_mosek_solution_artifact(
            joinpath(options.output, "mosek-solutions.bsol.gz"),
            jump_model.model,
        )
        if classification ==
           "infeasibility_candidate_requires_independent_ray_replay"
            progress("preserve the complete Mosek task for ray replay")
            metadata["mosek_infeasibility_task"] =
                write_mosek_task_artifact(
                    joinpath(options.output, "mosek-infeasibility.task"),
                    jump_model.model,
                )
            metadata["mosek_infeasibility_ray"] =
                write_mosek_infeasibility_ray_artifact(
                    joinpath(options.output, "mosek-infeasibility.ray.bin"),
                    jump_model.model,
                )
        end
        write_checkpoint(checkpoint_path, metadata)
    end

    metadata["state"] = "complete"
    metadata["completed_at_utc"] = Dates.format(
        now(UTC),
        dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
    )
    write_checkpoint(checkpoint_path, metadata)
    progress("complete")
end

if abspath(PROGRAM_FILE) == @__FILE__
    spin_isotypic_main()
end
