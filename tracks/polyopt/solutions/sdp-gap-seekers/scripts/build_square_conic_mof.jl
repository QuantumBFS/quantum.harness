#!/usr/bin/env julia

using Dates
using SHA
using TOML
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT = normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))

include(joinpath(TRACK_ROOT, "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(TRACK_ROOT, "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(TRACK_ROOT, "src", "CoreMGK.jl"))
using .CoreMGK
include(joinpath(TRACK_ROOT, "src", "SquareGapConic.jl"))
using .SquareGapConic

const RUNMETA_SCHEMA = "square-conic-mof-runmeta-v1"

function progress(message::AbstractString)
    println("[square-conic-mof] ", message)
    flush(stdout)
end

function parse_rational(token::AbstractString)
    occursin("//", token) ||
        throw(ArgumentError("rational argument must be p//q, got: $token"))
    parts = split(token, "//")
    length(parts) == 2 ||
        throw(ArgumentError("rational argument must be p//q, got: $token"))
    return parse(BigInt, String(strip(parts[1]))) //
           parse(BigInt, String(strip(parts[2])))
end

function usage()
    println(
        """
        Usage:
          julia --project=julia-env \\
            tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_conic_mof.jl \\
            --basis {bare_weight_one|one_symbol_lift} --g p//q --gamma p//q \\
            --output tracks/polyopt/solutions/sdp-gap-seekers/results/<run-id>

        Builds one solver-free Square J1-J2 conic MOF from the exact M/G-K core
        (CoreMGKPlan via SquareGapConic). L=1, d=2, unrestricted. This script
        never attaches an optimizer and never calls optimize!().

        The output directory must not already exist.""",
    )
end

function parse_args(args::Vector{String})
    basis = nothing
    g = nothing
    gamma = nothing
    output = nothing
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("-h", "--help")
            usage()
            return nothing
        elseif argument == "--basis"
            basis = args[index + 1]
            index += 2
        elseif argument == "--g"
            g = parse_rational(args[index + 1])
            index += 2
        elseif argument == "--gamma"
            gamma = parse_rational(args[index + 1])
            index += 2
        elseif argument == "--output"
            output = args[index + 1]
            index += 2
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    isnothing(basis) && throw(ArgumentError("--basis is required"))
    basis in ("bare_weight_one", "one_symbol_lift") ||
        throw(ArgumentError("--basis must be bare_weight_one or one_symbol_lift"))
    isnothing(g) && throw(ArgumentError("--g is required"))
    isnothing(gamma) && throw(ArgumentError("--gamma is required"))
    isnothing(output) && throw(ArgumentError("--output is required"))
    isabspath(output) &&
        throw(ArgumentError("--output must be repository-relative"))
    output_path = normpath(joinpath(REPOSITORY_ROOT, output))
    relative_output = relpath(output_path, REPOSITORY_ROOT)
    (
        relative_output != ".." &&
        !startswith(relative_output, ".." * Base.Filesystem.path_separator)
    ) ||
        throw(ArgumentError("--output escapes the repository"))
    ispath(output_path) &&
        throw(ArgumentError("output path already exists: $output"))
    basis_symbol = Symbol(basis)
    return (basis_symbol, g, gamma, output_path)
end

function file_sha256(path::AbstractString)
    return bytes2hex(open(sha256, path))
end

function peak_rss_kib()
    status_path = "/proc/self/status"
    isfile(status_path) || return -1
    for line in eachline(status_path)
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        length(fields) >= 2 || return -1
        return parse(Int, fields[2])
    end
    return -1
end

function timed_metadata(measurement)
    return Dict(
        "wall_seconds" => measurement.time,
        "gc_seconds" => measurement.gctime,
        "allocated_bytes" => measurement.bytes,
        "peak_process_rss_kib_after_step" => peak_rss_kib(),
    )
end

function git_output(args...)
    command = Cmd(`git $(args)`; dir = REPOSITORY_ROOT)
    return readchomp(command)
end

function source_metadata()
    relative_files = String[
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/CoreMGK.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareGapConic.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_conic_mof.jl",
    ]
    dirty_text = git_output("status", "--porcelain", "--untracked-files=all")
    dirty_paths = isempty(dirty_text) ?
        String[] : split(dirty_text, '\n'; keepempty = false)
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths_at_build" => dirty_paths,
        "files_sha256" => Dict(
            path => file_sha256(joinpath(REPOSITORY_ROOT, path))
            for path in relative_files
        ),
    )
end

function rational_metadata(value::Rational)
    return Dict(
        "numerator" => string(numerator(value)),
        "denominator" => string(denominator(value)),
        "canonical" => string(value),
        "float64" => Float64(value),
    )
end

function hermitian_cone_dimensions(model::JuMP.Model)
    dimensions = Dict{String,Int}()
    for name in ("positive_psd", "gap_psd")
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) &&
            error("reloaded MOF has no constraint named $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle ||
            error("reloaded $name is not a Hermitian PSD cone")
        dimensions[name] = set.side_dimension
    end
    return dimensions
end

function verify_reloaded_model(model::JuMP.Model, assembly::ConicAssembly)
    expected_variables = length(assembly.moments)
    variables = JuMP.all_variables(model)
    length(variables) == expected_variables ||
        error("MOF variable count changed during reload")
    expected_variable_names = [
        "moment[$index]" for index in 1:expected_variables
    ]
    JuMP.name.(variables) == expected_variable_names ||
        error("MOF variable order or names changed during reload")

    stationarity_count = length(assembly.stationarity_equalities)
    expected_constraint_count = 1 + stationarity_count + 2
    actual_constraint_count = JuMP.num_constraints(
        model;
        count_variable_in_set_constraints = false,
    )
    actual_constraint_count == expected_constraint_count ||
        error("MOF constraint count changed during reload")

    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("reloaded MOF has no normalization constraint")
    for index in 1:stationarity_count
        isnothing(JuMP.constraint_by_name(model, "stationarity[$index]")) &&
            error("reloaded MOF lost stationarity[$index]")
    end
    dimensions = hermitian_cone_dimensions(model)
    dimensions["positive_psd"] == length(assembly.plan.positive_basis.entries) ||
        error("positive cone dimension changed during reload")
    dimensions["gap_psd"] == length(assembly.plan.gap_basis.entries) ||
        error("gap cone dimension changed during reload")
    JuMP.objective_sense(model) == JuMP.MOI.FEASIBILITY_SENSE ||
        error("reloaded MOF does not have a feasibility objective")

    return Dict(
        "passed" => true,
        "variable_count" => expected_variables,
        "constraint_count_excluding_variable_sets" => actual_constraint_count,
        "normalization_count" => 1,
        "stationarity_equality_count" => stationarity_count,
        "hermitian_psd_cone_count" => 2,
        "hermitian_psd_cone_dimensions" => dimensions,
        "objective_sense" => "feasibility",
        "first_variable_name" => first(expected_variable_names),
        "last_variable_name" => last(expected_variable_names),
    )
end

function write_toml(path::AbstractString, data)
    open(path, "w") do io
        TOML.print(io, data; sorted = true)
    end
    return path
end

function main(args::Vector{String} = ARGS)
    parsed = parse_args(args)
    isnothing(parsed) && return 0
    basis_symbol, g, gamma, output_path = parsed
    mkpath(output_path)
    progress("bundle path: $(relpath(output_path, REPOSITORY_ROOT))")
    progress("no optimizer will be attached or invoked")

    patch = square_patch_geometry(1)
    model_h = square_j1j2_model(g)
    problem = GapProblem(
        patch,
        model_h,
        gamma,
        2;
        basis_mode = :structured,
        basis_spec = StructuredBasisSpec(basis_symbol, 1),
    )

    GC.gc()
    assembly_measurement = @timed assemble_square_conic(problem)
    assembly = assembly_measurement.value
    progress(
        "exact assembly complete; moments=$(length(assembly.moments)), " *
        "equalities=$(length(assembly.stationarity_equalities)), " *
        "assembly_sha256=$(assembly.assembly_sha256)",
    )

    GC.gc()
    jump_measurement = @timed build_square_conic_jump(assembly)
    jump_model = jump_measurement.value
    progress("optimizer-free JuMP model complete")

    mof_filename = "model.mof.json"
    mof_path = joinpath(output_path, mof_filename)
    GC.gc()
    export_measurement = @timed JuMP.write_to_file(jump_model.model, mof_path)
    mof_sha256 = file_sha256(mof_path)
    progress(
        "MOF written; bytes=$(filesize(mof_path)), sha256=$mof_sha256",
    )

    GC.gc()
    replay_measurement = @timed JuMP.read_from_file(mof_path)
    replayed_model = replay_measurement.value
    replay = verify_reloaded_model(replayed_model, assembly)
    progress("independent MOF reload checks passed")

    runmeta = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "claim_level" => "solver_free_structural_artifact",
        "solver_invoked" => false,
        "optimizer_attached" => false,
        "assembly_module" => "SquareGapConic (CoreMGK-driven)",
        "source" => source_metadata(),
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "julia_executable" => Base.julia_cmd().exec[1],
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
        ),
        "setup" => Dict(
            "model" => "square-j1-j2",
            "hamiltonian" =>
                "H=(1/4)sum_J1(XX+YY+ZZ)+(g/4)sum_J2(XX+YY+ZZ)",
            "j1_sign" => "positive_antiferromagnetic",
            "j1" => rational_metadata(BigInt(1) // BigInt(1)),
            "g_j2_over_j1" => rational_metadata(g),
            "gamma" => rational_metadata(gamma),
            "patch_name" => problem.patch.name,
            "patch_level_L" => problem.patch.level,
            "outer_site_count" => length(problem.patch.sites),
            "inner_site_count" => length(problem.patch.inner_ids),
            "boundary_interpretation" =>
                "local_consistency_window_no_physical_boundary_condition",
            "degree_d" => problem.d,
            "basis_family" => string(basis_symbol),
            "basis_version" => 1,
            "state_symmetry" => "none_unrestricted",
            "conserved_sector_projection" => "none",
            "target" => "feasibility_only",
            "observable_objective" => "none",
        ),
        "basis" => Dict(
            "positive_family" => string(assembly.plan.positive_basis.family),
            "positive_family_version" =>
                assembly.plan.positive_basis.family_version,
            "positive_dimension" =>
                length(assembly.plan.positive_basis.entries),
            "positive_is_complete" =>
                assembly.plan.positive_basis.is_complete,
            "positive_sha256" => assembly.plan.positive_basis.sha256,
            "gap_family" => string(assembly.plan.gap_basis.family),
            "gap_family_version" => assembly.plan.gap_basis.family_version,
            "gap_dimension" => length(assembly.plan.gap_basis.entries),
            "gap_is_complete" => assembly.plan.gap_basis.is_complete,
            "gap_sha256" => assembly.plan.gap_basis.sha256,
        ),
        "stationarity" => Dict(
            "family" => string(assembly.stationarity_spec.family),
            "family_version" => assembly.stationarity_spec.version,
            "is_complete" => false,
            "selection_rule" => assembly.stationarity_selection_rule,
            "nonzero_real_equality_count" =>
                length(assembly.stationarity_equalities),
            "candidates_sha256" => assembly.stationarity_candidates_sha256,
            "equalities_sha256" => assembly.stationarity_equalities_sha256,
        ),
        "exact_assembly" => Dict(
            "problem_sha256" => assembly.problem_sha256,
            "hamiltonian_term_count" =>
                length(assembly.plan.hamiltonian_terms),
            "moment_count" => length(assembly.moments),
            "moments_sha256" => assembly.moments_sha256,
            "coefficient_map_sha256" => assembly.coefficient_map_sha256,
            "assembly_sha256" => assembly.assembly_sha256,
            "state_class" => assembly.plan.state_class,
        ),
        "mof" => Dict(
            "filename" => mof_filename,
            "size_bytes" => filesize(mof_path),
            "sha256" => mof_sha256,
            "variable_order_contract" => "moment[1]...moment[n]",
            "identity_variable" => "moment[1]",
            "normalization_constraint" => "normalization",
            "positive_cone_constraint" => "positive_psd",
            "gap_cone_constraint" => "gap_psd",
        ),
        "replay" => replay,
        "performance" => Dict(
            "exact_assembly" => timed_metadata(assembly_measurement),
            "jump_model_construction" => timed_metadata(jump_measurement),
            "mof_export" => timed_metadata(export_measurement),
            "mof_reload" => timed_metadata(replay_measurement),
        ),
    )
    runmeta_path = joinpath(output_path, "runmeta.toml")
    write_toml(runmeta_path, runmeta)
    checksums_path = joinpath(output_path, "SHA256SUMS")
    open(checksums_path, "w") do io
        println(io, mof_sha256, "  ", mof_filename)
        println(io, file_sha256(runmeta_path), "  runmeta.toml")
    end
    progress("runmeta and checksums written")
    progress("bundle complete; MOF reload checks passed")
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
