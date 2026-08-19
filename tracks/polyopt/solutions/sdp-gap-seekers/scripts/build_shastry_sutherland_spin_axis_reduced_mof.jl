#!/usr/bin/env julia

using Dates
using SHA
using TOML
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT =
    normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))

include(joinpath(TRACK_ROOT, "src", "SquareJ1J2Prototype.jl"))
using .SquareJ1J2Prototype
include(joinpath(TRACK_ROOT, "src", "GenericGapModel.jl"))
using .GenericGapModel
include(joinpath(TRACK_ROOT, "src", "PrimalGapSymbolics.jl"))
using .PrimalGapSymbolics
include(joinpath(TRACK_ROOT, "src", "PrimalGapAssembly.jl"))
using .PrimalGapAssembly
include(joinpath(TRACK_ROOT, "src", "PrimalGapJuMP.jl"))
using .PrimalGapJuMP
include(joinpath(TRACK_ROOT, "src", "ExactSymmetryReduction.jl"))
using .ExactSymmetryReduction
include(joinpath(TRACK_ROOT, "src", "ReducedPrimalGapAssembly.jl"))
using .ReducedPrimalGapAssembly
include(joinpath(
    TRACK_ROOT,
    "src",
    "ConjugationSymmetryReduction.jl",
))
using .ConjugationSymmetryReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "SpinAxisInvolutionReduction.jl",
))
using .SpinAxisInvolutionReduction
include(joinpath(
    TRACK_ROOT,
    "src",
    "SpinAxisInvolutionPrimalGapJuMP.jl",
))
using .SpinAxisInvolutionPrimalGapJuMP

const RUNMETA_SCHEMA =
    "shastry-sutherland-spin-axis-real-mof-runmeta-v1"
const G_COUPLING = BigInt(4) // BigInt(5)

function progress(message::AbstractString)
    println("[ss-spin-axis-mof] ", message)
    flush(stdout)
end

function parse_rational(text::String)
    parts = split(text, '/')
    length(parts) == 1 &&
        return parse(BigInt, only(parts)) // BigInt(1)
    length(parts) == 2 ||
        throw(ArgumentError("expected integer or rational p/q"))
    denominator = parse(BigInt, parts[2])
    iszero(denominator) &&
        throw(ArgumentError("rational denominator cannot be zero"))
    return parse(BigInt, parts[1]) // denominator
end

function parse_args(arguments::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("--output", "--gamma")
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            haskey(values, argument) &&
                throw(ArgumentError("$argument was supplied more than once"))
            values[argument] = arguments[index + 1]
            index += 2
        elseif argument in ("-h", "--help")
            println(
                "usage: build_shastry_sutherland_spin_axis_reduced_mof.jl " *
                "--gamma P/Q --output REPOSITORY_RELATIVE_PATH",
            )
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    all(haskey(values, key) for key in ("--output", "--gamma")) ||
        throw(ArgumentError("--output and --gamma are required"))

    output = values["--output"]
    isabspath(output) &&
        throw(ArgumentError("--output must be repository-relative"))
    output_path = normpath(joinpath(REPOSITORY_ROOT, output))
    relative = relpath(output_path, REPOSITORY_ROOT)
    (
        relative != ".." &&
        !startswith(relative, ".." * Base.Filesystem.path_separator)
    ) || throw(ArgumentError("--output escapes the repository"))
    ispath(output_path) &&
        throw(ArgumentError("output path already exists"))
    return (
        output=output_path,
        output_relative=relative,
        gamma=parse_rational(values["--gamma"]),
    )
end

file_sha256(path::AbstractString) =
    bytes2hex(open(sha256, path))

function peak_rss_kib()
    isfile("/proc/self/status") || return -1
    for line in eachline("/proc/self/status")
        startswith(line, "VmHWM:") || continue
        fields = split(line)
        return length(fields) >= 2 ? parse(Int, fields[2]) : -1
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

git_output(arguments...) =
    readchomp(Cmd(`git $(arguments)`; dir=REPOSITORY_ROOT))

function source_metadata()
    files = [
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapSymbolics.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/PrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ExactSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ReducedPrimalGapAssembly.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/ConjugationSymmetryReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SpinAxisInvolutionReduction.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SpinAxisInvolutionPrimalGapJuMP.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_sutherland_spin_axis_reduced_mof.jl",
    ]
    dirty = git_output("status", "--porcelain", "--untracked-files=all")
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("symbolic-ref", "--short", "HEAD"),
        "dirty_paths_at_build" =>
            isempty(dirty) ? String[] : split(dirty, '\n'; keepempty=false),
        "files_sha256" => Dict(
            file => file_sha256(joinpath(REPOSITORY_ROOT, file))
            for file in files
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

function verify_reloaded_model(
    model::JuMP.Model,
    assembly::SpinAxisReducedPrimalAssembly,
)
    report = spin_axis_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.spin_axis_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        isnothing(JuMP.constraint_by_name(
            model,
            "spin_axis_reduced_equality[$index]",
        )) && error("MOF lost spin-axis equality $index")
    end

    dimensions = Dict{String,Int}()
    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    for block in blocks
        name = spin_axis_block_name(block)
        reference = JuMP.constraint_by_name(model, name)
        isnothing(reference) && error("MOF lost PSD block $name")
        set = JuMP.constraint_object(reference).set
        set isa JuMP.MOI.PositiveSemidefiniteConeTriangle ||
            error("$name changed cone type during reload")
        set.side_dimension == length(block.rows) ||
            error("$name changed dimension during reload")
        dimensions[name] = set.side_dimension
    end
    expected_constraints =
        1 + length(assembly.equalities) + length(blocks)
    JuMP.num_constraints(
        model;
        count_variable_in_set_constraints=false,
    ) == expected_constraints ||
        error("MOF constraint count changed during reload")
    return Dict(
        "passed" => true,
        "variable_count" => report.spin_axis_moments,
        "constraint_count_excluding_variable_sets" =>
            expected_constraints,
        "psd_constraint_count" => length(blocks),
        "psd_block_dimensions" => dimensions,
        "psd_cone_type" => "PositiveSemidefiniteConeTriangle",
    )
end

function write_toml(path::String, data)
    open(path, "w") do io
        TOML.print(io, data; sorted=true)
    end
end

function write_checksums(
    directory::String,
    filenames::Vector{String},
)
    open(joinpath(directory, "SHA256SUMS"), "w") do io
        for filename in filenames
            println(
                io,
                file_sha256(joinpath(directory, filename)),
                "  ",
                filename,
            )
        end
    end
end

function main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return
    source = source_metadata()
    isempty(source["dirty_paths_at_build"]) ||
        error("refusing to build from a dirty checkout")
    mkpath(options.output)

    progress("exact source assembly")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(G_COUPLING),
        options.gamma,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    source_measurement = @timed assemble_primal_gap(problem)
    primal = source_measurement.value

    progress("exact V4 and facial reduction")
    v4_measurement = @timed assemble_reduced_primal(primal)
    v4 = v4_measurement.value
    v4_report = reduced_assembly_report(v4)

    progress("exact conjugation projection and realification")
    conjugation_measurement =
        @timed assemble_conjugation_reduced_primal(v4)
    conjugation = conjugation_measurement.value
    conjugation_report =
        conjugation_reduced_assembly_report(conjugation)

    progress("exhaustive spin-axis truth gate")
    truth_measurement = @timed spin_axis_reduction_truth(conjugation)
    truth = truth_measurement.value
    truth.exact || error("spin-axis covariance truth gate failed")

    progress("exact spin-axis orbit quotient and block congruence")
    spin_axis_measurement = @timed assemble_spin_axis_reduced_primal(
        conjugation;
        verify_truth=false,
    )
    spin_axis = spin_axis_measurement.value
    spin_axis_report =
        spin_axis_reduced_assembly_report(spin_axis)

    progress("optimizer-free spin-axis real-cone JuMP model")
    jump_measurement =
        @timed build_spin_axis_reduced_jump_primal(spin_axis)
    jump_model = jump_measurement.value

    mof_path = joinpath(options.output, "model.mof.json")
    progress("write MOF")
    write_measurement =
        @timed JuMP.write_to_file(jump_model.model, mof_path)
    mof_sha256 = file_sha256(mof_path)

    progress("reload and verify spin-axis MOF")
    replay_measurement = @timed JuMP.read_from_file(mof_path)
    replay = verify_reloaded_model(
        replay_measurement.value,
        spin_axis,
    )

    runmeta = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "claim_level" =>
            "solver_free_exact_equivalent_spin_axis_real_reduction",
        "solver_invoked" => false,
        "optimizer_attached" => false,
        "output_relative" => options.output_relative,
        "source" => source,
        "runtime" => Dict(
            "julia_version" => string(VERSION),
            "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" =>
                string(Base.pkgversion(JuMP.MOI)),
        ),
        "setup" => Dict(
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => rational_metadata(G_COUPLING),
            "gamma" => rational_metadata(options.gamma),
            "patch_level" => 1,
            "degree_d" => 2,
            "state_class" => "unrestricted",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
        ),
        "source_assembly" => Dict(
            "schema" => primal.schema,
            "problem_sha256" => primal.problem_sha256,
            "assembly_sha256" => primal.assembly_sha256,
            "moment_count" => length(primal.moments),
            "positive_dimension" =>
                length(primal.positive_basis.entries),
            "gap_dimension" => length(primal.gap_basis.entries),
            "stationarity_equality_count" =>
                length(primal.stationarity_equalities),
        ),
        "exact_v4_reduction" => Dict(
            "schema" => v4.schema,
            "assembly_sha256" => v4.assembly_sha256,
            "coefficient_map_sha256" =>
                v4.coefficient_map_sha256,
            "moment_count" => v4_report.reduced_moments,
            "eliminated_moment_count" =>
                v4_report.eliminated_moments,
            "positive_block_dimensions" =>
                v4_report.positive_block_dimensions,
            "gap_block_dimensions" =>
                v4_report.gap_block_dimensions,
            "equality_count" => v4_report.equality_count,
        ),
        "exact_conjugation_reduction" => Dict(
            "schema" => conjugation.schema,
            "assembly_sha256" => conjugation.assembly_sha256,
            "coefficient_map_sha256" =>
                conjugation.coefficient_map_sha256,
            "moment_count" =>
                conjugation_report.real_moments,
            "eliminated_conjugation_odd_moment_count" =>
                conjugation_report.eliminated_conjugation_odd_moments,
            "positive_block_dimensions" =>
                conjugation_report.positive_block_dimensions,
            "gap_block_dimensions" =>
                conjugation_report.gap_block_dimensions,
            "equality_count" =>
                conjugation_report.equality_count,
            "real_psd_triangle_entries" =>
                conjugation_report.real_psd_triangle_entries,
        ),
        "exact_spin_axis_reduction" => Dict(
            "schema" => spin_axis.schema,
            "assembly_sha256" => spin_axis.assembly_sha256,
            "coefficient_map_sha256" =>
                spin_axis.coefficient_map_sha256,
            "moment_count" => spin_axis_report.spin_axis_moments,
            "eliminated_spin_axis_moment_count" =>
                spin_axis_report.eliminated_spin_axis_moments,
            "forced_zero_moment_count" =>
                spin_axis_report.forced_zero_moments,
            "positive_block_dimensions" =>
                spin_axis_report.positive_block_dimensions,
            "gap_block_dimensions" =>
                spin_axis_report.gap_block_dimensions,
            "equality_count" => spin_axis_report.equality_count,
            "real_psd_triangle_entries" =>
                spin_axis_report.real_psd_triangle_entries,
            "maximum_psd_side_dimension" =>
                spin_axis_report.maximum_psd_side_dimension,
            "hamiltonian_invariant" =>
                truth.hamiltonian_invariant,
            "coefficient_covariant" =>
                truth.coefficient_covariant,
            "coefficient_count" => truth.coefficient_count,
            "stable_cross_blocks_zero" =>
                truth.stable_cross_blocks_zero,
            "stable_cross_entry_count" =>
                truth.stable_cross_entry_count,
            "equality_space_invariant" =>
                truth.equality_space_invariant,
            "truth_checks_exhaustive" => truth.exact,
        ),
        "timing" => Dict(
            "source_assembly" => timed_metadata(source_measurement),
            "exact_v4_reduction" => timed_metadata(v4_measurement),
            "conjugation_reduction" =>
                timed_metadata(conjugation_measurement),
            "spin_axis_truth" =>
                timed_metadata(truth_measurement),
            "spin_axis_reduction" =>
                timed_metadata(spin_axis_measurement),
            "jump_build" => timed_metadata(jump_measurement),
            "mof_write" => timed_metadata(write_measurement),
            "mof_reload" => timed_metadata(replay_measurement),
        ),
        "mof" => Dict(
            "filename" => "model.mof.json",
            "bytes" => filesize(mof_path),
            "sha256" => mof_sha256,
        ),
        "replay" => replay,
    )
    write_toml(joinpath(options.output, "runmeta.toml"), runmeta)
    write_checksums(
        options.output,
        ["model.mof.json", "runmeta.toml"],
    )

    progress(
        "complete; moments=$(spin_axis_report.spin_axis_moments), " *
        "psd_blocks=$(length(spin_axis.positive_blocks) + length(spin_axis.gap_blocks)), " *
        "real_psd_entries=$(spin_axis_report.real_psd_triangle_entries), " *
        "mof_bytes=$(filesize(mof_path)), sha256=$mof_sha256",
    )
end

main()
