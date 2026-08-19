#!/usr/bin/env julia

using Dates
using SHA
using TOML
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT =
    normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))
const SOURCE_ROOT = joinpath(TRACK_ROOT, "src")

for source_file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "PrimalGapJuMP.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "SpinAxisInvolutionReduction.jl",
    "FullSpinPermutationReduction.jl",
    "FullSpinConeReduction.jl",
    "FullSpinIsotypicReduction.jl",
    "ContinuousSpinMomentReduction.jl",
    "ContinuousSpinConeReduction.jl",
    "ContinuousSpinConePrimalGapJuMP.jl",
)
    include(joinpath(SOURCE_ROOT, source_file))
end

using .GenericGapModel
using .PrimalGapAssembly
using .ReducedPrimalGapAssembly
using .ConjugationSymmetryReduction
using .SpinAxisInvolutionReduction
using .FullSpinPermutationReduction
using .FullSpinConeReduction
using .FullSpinIsotypicReduction
using .ContinuousSpinMomentReduction
using .ContinuousSpinConeReduction
using .ContinuousSpinConePrimalGapJuMP

const RUNMETA_SCHEMA =
    "shastry-sutherland-continuous-spin-l2-cone-real-mof-runmeta-v1"
const G_COUPLING = BigInt(4) // BigInt(5)
const ALLOWED_GAMMAS = (BigInt(0) // BigInt(1), BigInt(1) // BigInt(2))

function progress(message::AbstractString)
    println("[ss-continuous-spin-cone-mof] ", message)
    flush(stdout)
end

function parse_rational(text::String)
    parts = split(text, '/')
    length(parts) in (1, 2) ||
        throw(ArgumentError("expected integer or rational p/q"))
    numerator_value = parse(BigInt, first(parts))
    denominator_value =
        length(parts) == 1 ? BigInt(1) : parse(BigInt, last(parts))
    iszero(denominator_value) &&
        throw(ArgumentError("rational denominator cannot be zero"))
    return numerator_value // denominator_value
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
                "usage: build_shastry_sutherland_continuous_spin_cone_reduced_mof.jl " *
                "--gamma {0|1/2} --output REPOSITORY_RELATIVE_PATH",
            )
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    all(haskey(values, key) for key in ("--output", "--gamma")) ||
        throw(ArgumentError("--output and --gamma are required"))

    gamma = parse_rational(values["--gamma"])
    gamma in ALLOWED_GAMMAS ||
        throw(ArgumentError("gamma must be exactly 0 or 1/2"))
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
        gamma=gamma,
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
        joinpath(
            "tracks/polyopt/solutions/sdp-gap-seekers/src",
            source_file,
        )
        for source_file in (
            "SquareJ1J2Prototype.jl",
            "GenericGapModel.jl",
            "PrimalGapSymbolics.jl",
            "PrimalGapAssembly.jl",
            "PrimalGapJuMP.jl",
            "ExactSymmetryReduction.jl",
            "ReducedPrimalGapAssembly.jl",
            "ConjugationSymmetryReduction.jl",
            "SpinAxisInvolutionReduction.jl",
            "FullSpinPermutationReduction.jl",
            "FullSpinConeReduction.jl",
            "FullSpinIsotypicReduction.jl",
            "ContinuousSpinMomentReduction.jl",
            "ContinuousSpinConeReduction.jl",
            "ContinuousSpinConePrimalGapJuMP.jl",
        )
    ]
    push!(
        files,
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/" *
        "build_shastry_sutherland_continuous_spin_cone_reduced_mof.jl",
    )
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

function base_layer_metadata(assembly, report, moment_field::Symbol)
    return Dict(
        "schema" => assembly.schema,
        "assembly_sha256" => assembly.assembly_sha256,
        "coefficient_map_sha256" => assembly.coefficient_map_sha256,
        "moment_count" => getproperty(report, moment_field),
        "positive_block_dimensions" => report.positive_block_dimensions,
        "gap_block_dimensions" => report.gap_block_dimensions,
        "equality_count" => report.equality_count,
    )
end

function cone_layer_metadata(assembly, report, moment_field::Symbol)
    metadata = base_layer_metadata(assembly, report, moment_field)
    metadata["real_psd_triangle_entries"] =
        report.real_psd_triangle_entries
    metadata["maximum_psd_side_dimension"] =
        hasproperty(report, :maximum_psd_side_dimension) ?
        report.maximum_psd_side_dimension :
        maximum([
            report.positive_block_dimensions;
            report.gap_block_dimensions
        ])
    return metadata
end

function verify_reloaded_model(
    model::JuMP.Model,
    assembly::ContinuousSpinConeReducedPrimalAssembly,
)
    report = continuous_spin_cone_reduced_assembly_report(assembly)
    JuMP.num_variables(model) == report.continuous_spin_moments ||
        error("MOF variable count changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("MOF lost normalization")
    for index in eachindex(assembly.equalities)
        name = "continuous_spin_l2_cone_equality[$index]"
        isnothing(JuMP.constraint_by_name(model, name)) &&
            error("MOF lost equality $index")
    end

    dimensions = Dict{String,Int}()
    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    for block in blocks
        name = continuous_spin_cone_block_name(block)
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
        "variable_count" => report.continuous_spin_moments,
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
    primal_measurement = @timed assemble_primal_gap(problem)
    primal = primal_measurement.value

    progress("exact V4 and facial reduction")
    v4_measurement = @timed assemble_reduced_primal(primal)
    v4 = v4_measurement.value
    v4_report = reduced_assembly_report(v4)

    progress("exact conjugation reduction")
    conjugation_measurement =
        @timed assemble_conjugation_reduced_primal(v4)
    conjugation = conjugation_measurement.value
    conjugation_report =
        conjugation_reduced_assembly_report(conjugation)

    progress("exact spin-axis truth and reduction")
    spin_truth_measurement = @timed spin_axis_reduction_truth(conjugation)
    spin_truth = spin_truth_measurement.value
    spin_truth.exact || error("spin-axis truth gate failed")
    spin_measurement = @timed assemble_spin_axis_reduced_primal(
        conjugation;
        verify_truth=false,
    )
    spin = spin_measurement.value
    spin_report = spin_axis_reduced_assembly_report(spin)

    progress("exact full-spin truth and moment reduction")
    full_truth_measurement =
        @timed full_spin_permutation_truth(conjugation)
    full_truth = full_truth_measurement.value
    full_truth.exact || error("full-spin truth gate failed")
    full_measurement = @timed assemble_full_spin_reduced_primal(
        spin;
        verify_truth=false,
    )
    full = full_measurement.value
    full_report = full_spin_reduced_assembly_report(full)

    progress("exact nontrivial-character cone truth and reduction")
    cone_truth_measurement =
        @timed full_spin_nontrivial_cone_redundancy_truth(full)
    cone_truth = cone_truth_measurement.value
    cone_truth.exact || error("full-spin cone truth gate failed")
    cone_measurement = @timed assemble_full_spin_cone_reduced_primal(
        full;
        verify_truth=false,
    )
    cone = cone_measurement.value
    cone_report = full_spin_cone_reduced_assembly_report(cone)

    progress("exact trivial-isotypic truth and reduction")
    isotypic_truth_measurement =
        @timed full_spin_trivial_isotypic_truth(cone)
    isotypic_truth = isotypic_truth_measurement.value
    isotypic_truth.exact || error("isotypic truth gate failed")
    isotypic_measurement =
        @timed assemble_full_spin_isotypic_reduced_primal(
            cone;
            verify_truth=false,
        )
    isotypic = isotypic_measurement.value
    isotypic_report =
        full_spin_isotypic_reduced_assembly_report(isotypic)

    progress("exact continuous-spin moment truth and reduction")
    continuous_truth_measurement =
        @timed continuous_spin_moment_truth(isotypic)
    continuous_truth = continuous_truth_measurement.value
    continuous_truth.exact ||
        error("continuous-spin moment truth gate failed")
    continuous_measurement =
        @timed assemble_continuous_spin_reduced_primal(
            isotypic;
            verify_truth=false,
        )
    continuous = continuous_measurement.value
    continuous_report =
        continuous_spin_reduced_assembly_report(continuous)

    progress("exact continuous-spin l=2 cone truth and reduction")
    l2_truth_measurement =
        @timed continuous_spin_l2_cone_redundancy_truth(continuous)
    l2_truth = l2_truth_measurement.value
    l2_truth.exact ||
        error("continuous-spin l=2 cone truth gate failed")
    l2_measurement =
        @timed assemble_continuous_spin_cone_reduced_primal(
            continuous;
            verify_truth=false,
        )
    l2 = l2_measurement.value
    l2_report = continuous_spin_cone_reduced_assembly_report(l2)

    progress("optimizer-free continuous-spin l=2 cone JuMP model")
    jump_measurement =
        @timed build_continuous_spin_cone_reduced_jump_primal(l2)
    jump_model = jump_measurement.value
    mof_path = joinpath(options.output, "model.mof.json")

    progress("write and independently reload MOF")
    write_measurement =
        @timed JuMP.write_to_file(jump_model.model, mof_path)
    replay_measurement = @timed JuMP.read_from_file(mof_path)
    replay = verify_reloaded_model(replay_measurement.value, l2)

    reductions = Dict(
        "exact_v4_reduction" =>
            base_layer_metadata(v4, v4_report, :reduced_moments),
        "exact_conjugation_reduction" =>
            cone_layer_metadata(
                conjugation,
                conjugation_report,
                :real_moments,
            ),
        "exact_spin_axis_reduction" =>
            cone_layer_metadata(spin, spin_report, :spin_axis_moments),
        "exact_full_spin_reduction" =>
            cone_layer_metadata(full, full_report, :full_spin_moments),
        "exact_full_spin_cone_reduction" =>
            cone_layer_metadata(
                cone,
                cone_report,
                :cone_reduced_moments,
            ),
        "exact_full_spin_isotypic_reduction" =>
            cone_layer_metadata(
                isotypic,
                isotypic_report,
                :isotypic_moments,
            ),
        "exact_continuous_spin_moment_reduction" =>
            cone_layer_metadata(
                continuous,
                continuous_report,
                :continuous_spin_moments,
            ),
        "exact_continuous_spin_l2_cone_reduction" =>
            cone_layer_metadata(
                l2,
                l2_report,
                :continuous_spin_moments,
            ),
    )
    reductions["exact_spin_axis_reduction"]["truth_checks_exhaustive"] =
        spin_truth.exact
    reductions["exact_full_spin_reduction"]["truth_checks_exhaustive"] =
        full_truth.exact
    reductions["exact_full_spin_cone_reduction"]["truth_checks_exhaustive"] =
        cone_truth.exact
    reductions["exact_full_spin_isotypic_reduction"]["truth_checks_exhaustive"] =
        isotypic_truth.exact
    continuous_metadata =
        reductions["exact_continuous_spin_moment_reduction"]
    continuous_metadata["source_moment_count"] =
        continuous_truth.source_moment_count
    continuous_metadata["eliminated_moment_count"] =
        continuous_truth.eliminated_moment_count
    continuous_metadata["skeleton_count"] =
        continuous_truth.skeleton_count
    continuous_metadata["rank_two_skeleton_count"] =
        continuous_truth.rank_two_skeleton_count
    continuous_metadata["rank_four_skeleton_count"] =
        continuous_truth.rank_four_skeleton_count
    continuous_metadata["rational_rotation_component_check_count"] =
        continuous_truth.rational_rotation_component_check_count
    continuous_metadata["rational_rotation_invariant"] =
        continuous_truth.rational_rotation_invariant
    continuous_metadata["truth_checks_exhaustive"] =
        continuous_truth.exact
    l2_metadata =
        reductions["exact_continuous_spin_l2_cone_reduction"]
    l2_metadata["duplicate_cone_dimensions"] =
        l2_truth.duplicate_cone_dimensions
    l2_metadata["row_map_ranks"] = l2_truth.row_map_ranks
    l2_metadata["component_squared_norms"] =
        l2_truth.component_squared_norms
    l2_metadata["coefficient_congruence_exact"] =
        l2_truth.coefficient_congruence_exact
    l2_metadata["coefficient_entry_count"] =
        l2_truth.coefficient_entry_count
    l2_metadata["nonzero_coefficient_entry_count"] =
        l2_truth.nonzero_coefficient_entry_count
    l2_metadata["truth_checks_exhaustive"] = l2_truth.exact

    runmeta = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "created_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "claim_level" =>
            "solver_free_exact_equivalent_continuous_spin_l2_cone_real_reduction",
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
        "reductions" => reductions,
        "timing" => Dict(
            "source_assembly" => timed_metadata(primal_measurement),
            "exact_v4_reduction" => timed_metadata(v4_measurement),
            "conjugation_reduction" =>
                timed_metadata(conjugation_measurement),
            "spin_axis_truth" => timed_metadata(spin_truth_measurement),
            "spin_axis_reduction" => timed_metadata(spin_measurement),
            "full_spin_truth" => timed_metadata(full_truth_measurement),
            "full_spin_reduction" => timed_metadata(full_measurement),
            "full_spin_cone_truth" =>
                timed_metadata(cone_truth_measurement),
            "full_spin_cone_reduction" =>
                timed_metadata(cone_measurement),
            "full_spin_isotypic_truth" =>
                timed_metadata(isotypic_truth_measurement),
            "full_spin_isotypic_reduction" =>
                timed_metadata(isotypic_measurement),
            "continuous_spin_moment_truth" =>
                timed_metadata(continuous_truth_measurement),
            "continuous_spin_moment_reduction" =>
                timed_metadata(continuous_measurement),
            "continuous_spin_l2_cone_truth" =>
                timed_metadata(l2_truth_measurement),
            "continuous_spin_l2_cone_reduction" =>
                timed_metadata(l2_measurement),
            "jump_build" => timed_metadata(jump_measurement),
            "mof_write" => timed_metadata(write_measurement),
            "mof_reload" => timed_metadata(replay_measurement),
        ),
        "mof" => Dict(
            "filename" => "model.mof.json",
            "bytes" => filesize(mof_path),
            "sha256" => file_sha256(mof_path),
        ),
        "replay" => replay,
    )
    write_toml(joinpath(options.output, "runmeta.toml"), runmeta)
    write_checksums(
        options.output,
        ["model.mof.json", "runmeta.toml"],
    )
    progress(
        "complete; moments=$(l2_report.continuous_spin_moments), " *
        "psd_blocks=$(length(l2.positive_blocks) + length(l2.gap_blocks)), " *
        "real_psd_entries=$(l2_report.real_psd_triangle_entries), " *
        "mof_bytes=$(filesize(mof_path)), " *
        "sha256=$(file_sha256(mof_path))",
    )
end

main()
