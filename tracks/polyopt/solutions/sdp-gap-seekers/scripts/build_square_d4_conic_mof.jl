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
include(joinpath(TRACK_ROOT, "src", "SquareSymmetryD4.jl"))
using .SquareSymmetryD4
include(joinpath(TRACK_ROOT, "src", "SquareSymmetryBlock.jl"))
using .SquareSymmetryBlock
include(joinpath(TRACK_ROOT, "src", "SquareGapConic.jl"))
using .SquareGapConic

const RUNMETA_SCHEMA = "square-d4-conic-mof-runmeta-v1"

function progress(message::AbstractString)
    println("[square-d4-conic-mof] ", message)
    flush(stdout)
end

function parse_rational(token::AbstractString)
    occursin("//", token) || throw(ArgumentError("rational argument must be p//q, got: $token"))
    parts = split(token, "//")
    return parse(BigInt, String(strip(parts[1]))) // parse(BigInt, String(strip(parts[2])))
end

function usage()
    println("""
        Usage:
          julia --project=julia-env \\
            tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_d4_conic_mof.jl \\
            --basis {bare_weight_one|bare_operator} --g p//q --gamma p//q \\
            --output tracks/polyopt/solutions/sdp-gap-seekers/results/<run-id>

        Builds one solver-free D4-blocked Square J1-J2 conic MOF. L=1, d=2,
        unrestricted. The positive HermitianPSDCone is split into D4 irrep
        blocks (an exactly-equivalent reparameterization via group averaging).
        Never attaches an optimizer.""")
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
            basis = args[index + 1]; index += 2
        elseif argument == "--g"
            g = parse_rational(args[index + 1]); index += 2
        elseif argument == "--gamma"
            gamma = parse_rational(args[index + 1]); index += 2
        elseif argument == "--output"
            output = args[index + 1]; index += 2
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    isnothing(basis) && throw(ArgumentError("--basis is required"))
    basis in ("bare_weight_one", "bare_operator") ||
        throw(ArgumentError("--basis must be bare_weight_one or bare_operator"))
    isnothing(g) && throw(ArgumentError("--g is required"))
    isnothing(gamma) && throw(ArgumentError("--gamma is required"))
    isnothing(output) && throw(ArgumentError("--output is required"))
    isabspath(output) && throw(ArgumentError("--output must be repository-relative"))
    output_path = normpath(joinpath(REPOSITORY_ROOT, output))
    relative_output = relpath(output_path, REPOSITORY_ROOT)
    (relative_output != ".." && !startswith(relative_output, ".." * Base.Filesystem.path_separator)) ||
        throw(ArgumentError("--output escapes the repository"))
    ispath(output_path) && throw(ArgumentError("output path already exists: $output"))
    return (Symbol(basis), g, gamma, output_path)
end

file_sha256(path::AbstractString) = bytes2hex(open(sha256, path))

function peak_rss_kib()
    isfile("/proc/self/status") || return -1
    for line in eachline("/proc/self/status")
        startswith(line, "VmHWM:") || continue
        return parse(Int, split(line)[2])
    end
    return -1
end

timed_metadata(m) = Dict(
    "wall_seconds" => m.time, "gc_seconds" => m.gctime,
    "allocated_bytes" => m.bytes, "peak_process_rss_kib_after_step" => peak_rss_kib(),
)

function git_output(args...)
    return readchomp(Cmd(`git $(args)`; dir = REPOSITORY_ROOT))
end

function source_metadata()
    relative_files = String[
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareJ1J2Prototype.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/GenericGapModel.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/CoreMGK.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareSymmetryD4.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareSymmetryBlock.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/src/SquareGapConic.jl",
        "tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_d4_conic_mof.jl",
    ]
    dirty_text = git_output("status", "--porcelain", "--untracked-files=all")
    dirty_paths = isempty(dirty_text) ? String[] : split(dirty_text, '\n'; keepempty = false)
    return Dict(
        "git_commit" => git_output("rev-parse", "HEAD"),
        "git_tree" => git_output("rev-parse", "HEAD^{tree}"),
        "git_branch" => git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths_at_build" => dirty_paths,
        "files_sha256" => Dict(path => file_sha256(joinpath(REPOSITORY_ROOT, path)) for path in relative_files),
    )
end

function rational_metadata(value::Rational)
    return Dict("numerator" => string(numerator(value)), "denominator" => string(denominator(value)),
        "canonical" => string(value), "float64" => Float64(value))
end

function verify_reloaded_model(model::JuMP.Model, assembly::ConicAssembly, d4_basis::D4SymmetryBasis)
    expected_variables = length(assembly.moments)
    variables = JuMP.all_variables(model)
    length(variables) == expected_variables || error("MOF variable count changed during reload")
    JuMP.name.(variables) == ["moment[$i]" for i in 1:expected_variables] ||
        error("MOF variable order or names changed during reload")
    isnothing(JuMP.constraint_by_name(model, "normalization")) &&
        error("reloaded MOF has no normalization constraint")
    for index in 1:length(assembly.stationarity_equalities)
        isnothing(JuMP.constraint_by_name(model, "stationarity[$index]")) &&
            error("reloaded MOF lost stationarity[$index]")
    end
    block_dims = Int[]
    for irrep in d4_basis.block_irreps
        ref = JuMP.constraint_by_name(model, "positive_psd_d4_$irrep")
        isnothing(ref) && error("reloaded MOF lost positive_psd_d4_$irrep")
        set = JuMP.constraint_object(ref).set
        set isa JuMP.MOI.HermitianPositiveSemidefiniteConeTriangle ||
            error("reloaded positive_psd_d4_$irrep is not a Hermitian PSD cone")
        push!(block_dims, set.side_dimension)
    end
    isnothing(JuMP.constraint_by_name(model, "gap_psd")) && error("reloaded MOF lost gap_psd")
    JuMP.objective_sense(model) == JuMP.MOI.FEASIBILITY_SENSE ||
        error("reloaded MOF does not have a feasibility objective")
    expected_constraint_count = 1 + length(assembly.stationarity_equalities) + length(d4_basis.block_irreps) + 1
    actual = JuMP.num_constraints(model; count_variable_in_set_constraints = false)
    actual == expected_constraint_count || error("MOF constraint count $actual != expected $expected_constraint_count")
    return Dict("passed" => true, "variable_count" => expected_variables,
        "constraint_count_excluding_variable_sets" => actual,
        "positive_d4_block_irreps" => String.(d4_basis.block_irreps),
        "positive_d4_block_side_dimensions" => block_dims,
        "objective_sense" => "feasibility")
end

function write_toml(path, data)
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
    progress("bundle path: $(relpath(output_path, REPOSITORY_ROOT)); no optimizer will be attached")

    patch = square_patch_geometry(1)
    problem = GapProblem(patch, square_j1j2_model(g), gamma, 2;
        basis_mode = :structured, basis_spec = StructuredBasisSpec(basis_symbol, 1))

    GC.gc()
    asm_m = @timed assemble_square_conic(problem)
    assembly = asm_m.value
    progress("assembly: moments=$(length(assembly.moments)), equalities=$(length(assembly.stationarity_equalities)), sha=$(assembly.assembly_sha256)")

    elements = d4_matrices()
    perms = d4_site_perms(patch, elements)
    GC.gc()
    sym_m = @timed sym = symmetry_adapted_basis(assembly.plan.positive_basis.entries, elements, perms)
    progress("D4 basis: $(block_label(sym)); build=$(round(sym_m.time; digits=3))s")
    verify = verify_block_structure(sym, elements, perms)
    verify.block_diagonal_for_all_g || error("D4 basis failed block-diagonal verification: max_off_block=$(verify.max_off_block_abs)")

    GC.gc()
    jump_m = @timed d4model = build_square_d4_conic_jump(assembly, sym)
    progress("D4 JuMP model: blocks=$(length(d4model.positive_block_constraints))")

    mof_path = joinpath(output_path, "model.mof.json")
    GC.gc()
    exp_m = @timed JuMP.write_to_file(d4model.model, mof_path)
    mof_sha = file_sha256(mof_path)
    progress("MOF written: bytes=$(filesize(mof_path)), sha256=$mof_sha")

    GC.gc()
    replay_m = @timed replayed = JuMP.read_from_file(mof_path)
    replay = verify_reloaded_model(replayed, assembly, sym)
    progress("independent MOF reload checks passed")

    runmeta = Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "created_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ"),
        "claim_level" => "solver_free_structural_artifact",
        "solver_invoked" => false,
        "optimizer_attached" => false,
        "assembly_module" => "SquareGapConic (CoreMGK-driven) + D4 block-diagonalization",
        "equivalence_note" => "D4 block-diagonalization is an exactly-equivalent reparameterization of the unrestricted relaxation (group averaging); not a symmetry-restricted bound.",
        "source" => source_metadata(),
        "runtime" => Dict("julia_version" => string(VERSION), "jump_version" => string(Base.pkgversion(JuMP)),
            "mathoptinterface_version" => string(Base.pkgversion(JuMP.MOI))),
        "setup" => Dict("model" => "square-j1-j2",
            "hamiltonian" => "H=(1/4)sum_J1(XX+YY+ZZ)+(g/4)sum_J2(XX+YY+ZZ)",
            "j1" => rational_metadata(BigInt(1) // BigInt(1)), "g_j2_over_j1" => rational_metadata(g),
            "gamma" => rational_metadata(gamma), "patch_level_L" => problem.patch.level,
            "outer_site_count" => length(problem.patch.sites), "inner_site_count" => length(problem.patch.inner_ids),
            "degree_d" => problem.d, "basis_family" => string(basis_symbol), "basis_version" => 1,
            "state_symmetry" => "none_unrestricted", "target" => "feasibility_only"),
        "basis" => Dict("positive_family" => string(assembly.plan.positive_basis.family),
            "positive_family_version" => assembly.plan.positive_basis.family_version,
            "positive_dimension" => length(assembly.plan.positive_basis.entries),
            "positive_sha256" => assembly.plan.positive_basis.sha256,
            "gap_family" => string(assembly.plan.gap_basis.family),
            "gap_family_version" => assembly.plan.gap_basis.family_version,
            "gap_dimension" => length(assembly.plan.gap_basis.entries),
            "gap_sha256" => assembly.plan.gap_basis.sha256),
        "d4_symmetry" => Dict("group" => "D4", "generators" => ["C4", "sigma"],
            "gate_1_hamiltonian_invariant" => true, "gate_2_basis_closed" => true,
            "gate_block_diagonal_verified" => verify.block_diagonal_for_all_g,
            "max_off_block_abs" => verify.max_off_block_abs,
            "positive_block_irreps" => String.(sym.block_irreps),
            "positive_block_side_dimensions" => [length(r) for r in sym.block_ranges]),
        "stationarity" => Dict("family" => string(assembly.stationarity_spec.family),
            "nonzero_real_equality_count" => length(assembly.stationarity_equalities),
            "equalities_sha256" => assembly.stationarity_equalities_sha256),
        "exact_assembly" => Dict("problem_sha256" => assembly.problem_sha256,
            "moment_count" => length(assembly.moments), "moments_sha256" => assembly.moments_sha256,
            "coefficient_map_sha256" => assembly.coefficient_map_sha256,
            "assembly_sha256" => assembly.assembly_sha256),
        "mof" => Dict("filename" => "model.mof.json", "size_bytes" => filesize(mof_path),
            "sha256" => mof_sha, "variable_order_contract" => "moment[1]...moment[n]",
            "identity_variable" => "moment[1]", "normalization_constraint" => "normalization",
            "positive_block_constraint_prefix" => "positive_psd_d4_", "gap_cone_constraint" => "gap_psd"),
        "replay" => replay,
        "performance" => Dict("exact_assembly" => timed_metadata(asm_m), "d4_basis" => timed_metadata(sym_m),
            "jump_model_construction" => timed_metadata(jump_m), "mof_export" => timed_metadata(exp_m),
            "mof_reload" => timed_metadata(replay_m)),
    )
    runmeta_path = joinpath(output_path, "runmeta.toml")
    write_toml(runmeta_path, runmeta)
    open(joinpath(output_path, "SHA256SUMS"), "w") do io
        println(io, mof_sha, "  model.mof.json")
        println(io, file_sha256(runmeta_path), "  runmeta.toml")
    end
    progress("runmeta and checksums written; bundle complete")
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
