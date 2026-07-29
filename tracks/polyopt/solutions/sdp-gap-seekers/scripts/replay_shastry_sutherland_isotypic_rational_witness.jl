#!/usr/bin/env julia

using Dates
using LinearAlgebra
using SHA
using TOML

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT =
    normpath(joinpath(TRACK_ROOT, "..", "..", "..", ".."))
const SOURCE_ROOT = joinpath(TRACK_ROOT, "src")

for source_file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "SpinAxisInvolutionReduction.jl",
    "FullSpinPermutationReduction.jl",
    "FullSpinConeReduction.jl",
    "FullSpinIsotypicReduction.jl",
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
using .PrimalGapSymbolics:
    ExactRational,
    ExactLinearPolynomial,
    MomentKey,
    moment_key

const REPLAY_SCHEMA =
    "shastry-sutherland-full-spin-isotypic-rational-witness-replay-v1"
const WITNESS_SCHEMA =
    "shastry-sutherland-full-spin-isotypic-rational-witness-v1"
const RESULT_SCHEMA =
    "shastry-sutherland-full-spin-isotypic-real-solve-result-v2"
const RUNMETA_SCHEMA =
    "shastry-sutherland-full-spin-isotypic-real-mof-runmeta-v1"
const EXPECTED_MODEL_SHA256 =
    "22aa6d169fabbe6b9f41eeba4ddc7d37fb1f8b769427714875760ae94dc559f9"
const EXPECTED_RUNMETA_SHA256 =
    "8e84bde7043d0023cbd82181d83f1a70622f222b6a706d0a36b9f45283e94e99"
const EXPECTED_SOURCE_COMMIT =
    "792e61c648c2c729327f37aee511ca2464b39161"
const EXPECTED_SOURCE_TREE =
    "f9be3021137afd19809b10f0182867b81941595d"
const G_COUPLING = BigInt(4) // BigInt(5)
const GAMMA = BigInt(1) // BigInt(2)
const DENOMINATOR_POWERS = (6, 8, 10, 12)

function progress(message::AbstractString)
    println("[ss-isotypic-rational-witness] ", message)
    flush(stdout)
end

file_sha256(path::AbstractString) =
    bytes2hex(open(sha256, path))

function repository_path(relative::AbstractString)
    isabspath(relative) &&
        throw(ArgumentError("path must be repository-relative"))
    path = normpath(joinpath(REPOSITORY_ROOT, relative))
    checked = relpath(path, REPOSITORY_ROOT)
    (
        checked != ".." &&
        !startswith(checked, ".." * Base.Filesystem.path_separator)
    ) || throw(ArgumentError("path escapes the repository"))
    return path
end

function parse_args(arguments::Vector{String})
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        argument = arguments[index]
        if argument in ("--input-directory", "--solve-directory", "--output")
            index < length(arguments) ||
                throw(ArgumentError("$argument requires a value"))
            haskey(values, argument) &&
                throw(ArgumentError("$argument was supplied more than once"))
            values[argument] = arguments[index + 1]
            index += 2
        elseif argument in ("-h", "--help")
            println(
                "usage: replay_shastry_sutherland_isotypic_rational_witness.jl " *
                "--input-directory BUILDER_RESULT " *
                "--solve-directory SOLVE_RESULT --output RUN_DIRECTORY",
            )
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
    end
    required = ("--input-directory", "--solve-directory", "--output")
    all(haskey(values, key) for key in required) ||
        throw(ArgumentError("all input, solve, and output paths are required"))
    return (
        input=repository_path(values["--input-directory"]),
        solve=repository_path(values["--solve-directory"]),
        output=repository_path(values["--output"]),
    )
end

function read_checksum_manifest(path::AbstractString)
    result = Dict{String,String}()
    for line in eachline(path)
        fields = split(strip(line); limit=2)
        length(fields) == 2 ||
            error("malformed checksum line in $path")
        filename = strip(fields[2])
        startswith(filename, "*") && (filename = filename[2:end])
        haskey(result, filename) &&
            error("duplicate checksum entry for $filename")
        result[filename] = fields[1]
    end
    return result
end

function require_equal(actual, expected, label::AbstractString)
    actual == expected ||
        error("$label mismatch: expected $(repr(expected)), got $(repr(actual))")
    return actual
end

function validate_inputs(options)
    input_model = joinpath(options.input, "model.mof.json")
    input_runmeta = joinpath(options.input, "runmeta.toml")
    input_checksums = joinpath(options.input, "SHA256SUMS")
    solve_result = joinpath(options.solve, "result.toml")
    solve_values = joinpath(options.solve, "primal-values.tsv")
    solve_checksums = joinpath(options.solve, "SHA256SUMS")
    for path in (
        input_model,
        input_runmeta,
        input_checksums,
        solve_result,
        solve_values,
        solve_checksums,
    )
        isfile(path) || error("required input is missing: $path")
    end
    mkpath(options.output)
    isempty(readdir(options.output)) ||
        error("rational replay output directory is not empty")

    input_manifest = read_checksum_manifest(input_checksums)
    solve_manifest = read_checksum_manifest(solve_checksums)
    model_sha256 = file_sha256(input_model)
    runmeta_sha256 = file_sha256(input_runmeta)
    result_sha256 = file_sha256(solve_result)
    values_sha256 = file_sha256(solve_values)
    require_equal(
        input_manifest["model.mof.json"],
        model_sha256,
        "input model manifest",
    )
    require_equal(
        input_manifest["runmeta.toml"],
        runmeta_sha256,
        "input runmeta manifest",
    )
    require_equal(
        solve_manifest["result.toml"],
        result_sha256,
        "solve result manifest",
    )
    require_equal(
        solve_manifest["primal-values.tsv"],
        values_sha256,
        "primal values manifest",
    )
    require_equal(
        model_sha256,
        EXPECTED_MODEL_SHA256,
        "allowlisted gamma=1/2 model",
    )
    require_equal(
        runmeta_sha256,
        EXPECTED_RUNMETA_SHA256,
        "allowlisted gamma=1/2 runmeta",
    )

    runmeta = TOML.parsefile(input_runmeta)
    result = TOML.parsefile(solve_result)
    require_equal(runmeta["schema_version"], RUNMETA_SCHEMA, "runmeta schema")
    require_equal(result["schema_version"], RESULT_SCHEMA, "result schema")
    require_equal(result["completed"], true, "solve completion")
    require_equal(result["expected_gamma"], "1//2", "result gamma")
    require_equal(
        result["classification"],
        "feasible_residual_checked_float",
        "solve classification",
    )
    require_equal(
        result["statuses"]["termination"],
        "OPTIMAL",
        "solve termination",
    )
    require_equal(
        result["statuses"]["primal"],
        "FEASIBLE_POINT",
        "solve primal status",
    )
    require_equal(
        result["input_hashes"]["model_mof_sha256"],
        model_sha256,
        "result model hash",
    )
    require_equal(
        result["input_hashes"]["runmeta_sha256"],
        runmeta_sha256,
        "result runmeta hash",
    )
    require_equal(
        result["primal_values"]["sha256"],
        values_sha256,
        "result primal-value hash",
    )
    require_equal(
        result["primal_values"]["variable_count"],
        3_250,
        "result primal-value count",
    )
    require_equal(
        result["primal_values"]["schema_version"],
        "shastry-sutherland-full-spin-isotypic-primal-values-v1",
        "result primal-value schema",
    )
    require_equal(
        result["solution_diagnostics"]["passed"],
        true,
        "floating residual audit",
    )

    setup = runmeta["setup"]
    require_equal(setup["model"], "shastry-sutherland", "model")
    require_equal(setup["patch_level"], 1, "patch level")
    require_equal(setup["degree_d"], 2, "degree")
    require_equal(setup["state_class"], "unrestricted", "state class")
    require_equal(
        setup["physical_boundary_condition"],
        "none-local-consistency-window",
        "boundary condition",
    )
    require_equal(
        setup["g_square_over_dimer"]["canonical"],
        "4//5",
        "coupling",
    )
    require_equal(setup["gamma"]["canonical"], "1//2", "gamma")

    require_equal(
        runmeta["source"]["git_commit"],
        EXPECTED_SOURCE_COMMIT,
        "builder source commit",
    )
    require_equal(
        runmeta["source"]["git_tree"],
        EXPECTED_SOURCE_TREE,
        "builder source tree",
    )
    require_equal(
        runmeta["source"]["dirty_paths_at_build"],
        String[],
        "builder dirty paths",
    )
    recorded_files = runmeta["source"]["files_sha256"]
    for (relative, expected_sha256) in recorded_files
        path = repository_path(relative)
        isfile(path) || error("recorded source is missing: $relative")
        require_equal(
            file_sha256(path),
            expected_sha256,
            "recorded source hash for $relative",
        )
    end
    return (
        model_sha256=model_sha256,
        runmeta_sha256=runmeta_sha256,
        result_sha256=result_sha256,
        values_sha256=values_sha256,
        runmeta=runmeta,
        result=result,
        values_path=solve_values,
    )
end

function bits_to_float(bits::AbstractString)
    ncodeunits(bits) == 64 ||
        error("Float64 bit string does not have 64 bits")
    all(character -> character in ('0', '1'), bits) ||
        error("Float64 bit string contains a nonbinary character")
    return reinterpret(Float64, parse(UInt64, bits; base=2))
end

function read_primal_values(
    path::AbstractString,
    expected_model_sha256::AbstractString,
    expected_runmeta_sha256::AbstractString,
)
    lines = readlines(path)
    length(lines) >= 4 || error("primal-value table is truncated")
    require_equal(
        lines[1],
        "# schema=shastry-sutherland-full-spin-isotypic-primal-values-v1",
        "primal-value schema",
    )
    require_equal(
        lines[2],
        "# model_mof_sha256=$expected_model_sha256",
        "primal-value model hash",
    )
    require_equal(
        lines[3],
        "# runmeta_sha256=$expected_runmeta_sha256",
        "primal-value runmeta hash",
    )
    require_equal(
        lines[4],
        "index\tname\tfloat64_bits",
        "primal-value header",
    )
    names = String[]
    values = Float64[]
    for (expected_index, line) in enumerate(lines[5:end])
        fields = split(line, '\t')
        length(fields) == 3 ||
            error("malformed primal-value row $expected_index")
        require_equal(
            parse(Int, fields[1]),
            expected_index,
            "primal-value row index",
        )
        push!(names, fields[2])
        push!(values, bits_to_float(fields[3]))
    end
    length(values) == 3_250 ||
        error("primal-value table has $(length(values)) variables")
    all(isfinite, values) ||
        error("primal-value table contains a nonfinite value")
    return names, values
end

function validate_exact_assembly(
    runmeta,
    primal,
    v4,
    conjugation,
    spin,
    full,
    cone,
    isotypic,
)
    require_equal(
        primal.assembly_sha256,
        runmeta["source_assembly"]["assembly_sha256"],
        "source assembly hash",
    )
    for (key, assembly) in (
        ("exact_v4_reduction", v4),
        ("exact_conjugation_reduction", conjugation),
        ("exact_spin_axis_reduction", spin),
        ("exact_full_spin_reduction", full),
        ("exact_full_spin_cone_reduction", cone),
        ("exact_full_spin_isotypic_reduction", isotypic),
    )
        metadata = runmeta[key]
        require_equal(assembly.schema, metadata["schema"], "$key schema")
        require_equal(
            assembly.assembly_sha256,
            metadata["assembly_sha256"],
            "$key assembly hash",
        )
        require_equal(
            assembly.coefficient_map_sha256,
            metadata["coefficient_map_sha256"],
            "$key coefficient hash",
        )
    end
    report = full_spin_isotypic_reduced_assembly_report(isotypic)
    require_equal(report.isotypic_moments, 3_250, "isotypic moments")
    require_equal(
        report.positive_block_dimensions,
        [36, 36, 36, 45, 37, 36, 36, 45],
        "isotypic positive dimensions",
    )
    require_equal(report.gap_block_dimensions, [1], "isotypic gap dimensions")
    require_equal(report.equality_count, 0, "isotypic equality count")
    require_equal(
        report.real_psd_triangle_entries,
        6_104,
        "isotypic PSD entries",
    )
    return report
end

function expected_variable_names(count::Int)
    return [
        "full_spin_isotypic_invariant_moment[$index]"
        for index in 1:count
    ]
end

function rounded_values(values::Vector{Float64}, power::Int)
    denominator_value = BigInt(10)^power
    numerators = BigInt[]
    exact_values = ExactRational[]
    for (index, value) in enumerate(values)
        exact_float = rationalize(BigInt, value; tol=0)
        numerator_value = round(
            BigInt,
            exact_float * denominator_value,
            RoundNearest,
        )
        if index == 1
            numerator_value = denominator_value
        end
        push!(numerators, numerator_value)
        push!(exact_values, numerator_value // denominator_value)
    end
    return denominator_value, numerators, exact_values
end

function evaluate_polynomial(
    polynomial::ExactLinearPolynomial,
    values::Vector{ExactRational},
    indices::Dict{MomentKey,Int},
)
    result = Complex{ExactRational}(0, 0)
    for (key, coefficient) in polynomial.terms
        haskey(indices, key) ||
            error("exact coefficient contains an unknown moment")
        result += coefficient * values[indices[key]]
    end
    iszero(imag(result)) ||
        error("exact isotypic matrix entry is not real")
    return real(result)
end

function exact_block_matrix(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    block::FullSpinIsotypicPSDBlock,
    values::Vector{ExactRational},
    indices::Dict{MomentKey,Int},
)
    dimension = length(block.rows)
    matrix = Matrix{ExactRational}(undef, dimension, dimension)
    for row in 1:dimension, column in row:dimension
        polynomial = full_spin_isotypic_block_entry(
            assembly,
            block,
            block.rows[row],
            block.rows[column],
        )
        entry = evaluate_polynomial(polynomial, values, indices)
        matrix[row, column] = entry
        matrix[column, row] = entry
    end
    return matrix
end

function exact_ldl_positive_pivots(matrix::Matrix{ExactRational})
    size(matrix, 1) == size(matrix, 2) ||
        error("LDL input is not square")
    dimension = size(matrix, 1)
    lower = zeros(ExactRational, dimension, dimension)
    pivots = zeros(ExactRational, dimension)
    for column in 1:dimension
        lower[column, column] = 1
        pivot = matrix[column, column]
        for prior in 1:(column - 1)
            pivot -=
                lower[column, prior]^2 * pivots[prior]
        end
        pivot > 0 || return nothing
        pivots[column] = pivot
        for row in (column + 1):dimension
            value = matrix[row, column]
            for prior in 1:(column - 1)
                value -=
                    lower[row, prior] *
                    lower[column, prior] *
                    pivots[prior]
            end
            lower[row, column] = value / pivot
        end
    end
    return pivots
end

function block_name(block::FullSpinIsotypicPSDBlock)
    source = block.source_block
    return join(
        (
            "isotypic_full_spin",
            source.role,
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.kind,
            "real_psd",
        ),
        "_",
    )
end

function attempt_rational_witness(
    assembly::FullSpinIsotypicReducedPrimalAssembly,
    floating_values::Vector{Float64},
)
    indices = Dict(
        key => index
        for (index, key) in enumerate(assembly.moments)
    )
    blocks = [assembly.positive_blocks; assembly.gap_blocks]
    attempts = Dict{String,Any}[]
    for power in DENOMINATOR_POWERS
        progress("testing common decimal denominator 10^$power")
        denominator_value, numerators, values =
            rounded_values(floating_values, power)
        require_equal(values[1], ExactRational(1), "normalization")
        block_metadata = Dict{String,Any}()
        all_positive = true
        for block in blocks
            name = block_name(block)
            matrix = exact_block_matrix(
                assembly,
                block,
                values,
                indices,
            )
            minimum_eigenvalue =
                minimum(eigvals(Symmetric(Float64.(matrix))))
            if !(minimum_eigenvalue > 0)
                block_metadata[name] = Dict(
                    "dimension" => size(matrix, 1),
                    "float64_minimum_eigenvalue" =>
                        minimum_eigenvalue,
                    "exact_ldl_positive" => false,
                    "reason" => "floating_prefilter_not_positive",
                )
                all_positive = false
                break
            end
            pivots = exact_ldl_positive_pivots(matrix)
            if isnothing(pivots)
                block_metadata[name] = Dict(
                    "dimension" => size(matrix, 1),
                    "float64_minimum_eigenvalue" =>
                        minimum_eigenvalue,
                    "exact_ldl_positive" => false,
                    "reason" => "nonpositive_exact_ldl_pivot",
                )
                all_positive = false
                break
            end
            exact_pivots = something(pivots)
            block_metadata[name] = Dict(
                "dimension" => size(matrix, 1),
                "float64_minimum_eigenvalue" =>
                    minimum_eigenvalue,
                "exact_ldl_positive" => true,
                "minimum_exact_ldl_pivot" =>
                    string(minimum(exact_pivots)),
                "ldl_pivot_count" => length(exact_pivots),
            )
        end
        push!(
            attempts,
            Dict(
                "denominator_power" => power,
                "denominator" => string(denominator_value),
                "all_blocks_exactly_positive_definite" => all_positive,
                "blocks" => block_metadata,
            ),
        )
        all_positive &&
            return (
                passed=true,
                denominator_power=power,
                denominator=denominator_value,
                numerators=numerators,
                exact_values=values,
                blocks=block_metadata,
                attempts=attempts,
            )
    end
    return (
        passed=false,
        attempts=attempts,
    )
end

function write_witness(
    path::AbstractString,
    denominator_value::BigInt,
    numerators::Vector{BigInt},
    names::Vector{String},
    provenance,
)
    open(path, "w") do io
        println(io, "# schema=", WITNESS_SCHEMA)
        println(io, "# denominator=", denominator_value)
        println(io, "# model_mof_sha256=", provenance.model_sha256)
        println(io, "# runmeta_sha256=", provenance.runmeta_sha256)
        println(io, "# solve_result_sha256=", provenance.result_sha256)
        println(io, "# primal_values_sha256=", provenance.values_sha256)
        println(io, "index\tname\tnumerator")
        for index in eachindex(numerators)
            println(
                io,
                index,
                '\t',
                names[index],
                '\t',
                numerators[index],
            )
        end
    end
end

function write_toml(path::AbstractString, data)
    open(path, "w") do io
        TOML.print(io, data; sorted=true)
    end
end

function main(arguments::Vector{String}=ARGS)
    options = parse_args(arguments)
    isnothing(options) && return 0
    started = time()
    provenance = validate_inputs(options)
    names, floating_values = read_primal_values(
        provenance.values_path,
        provenance.model_sha256,
        provenance.runmeta_sha256,
    )
    require_equal(
        names,
        expected_variable_names(length(names)),
        "primal variable names",
    )

    progress("rebuilding the exact gamma=1/2 isotypic assembly")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(G_COUPLING),
        GAMMA,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:one_symbol_lift, 1),
    )
    primal = assemble_primal_gap(problem)
    v4 = assemble_reduced_primal(primal)
    conjugation = assemble_conjugation_reduced_primal(v4)
    spin = assemble_spin_axis_reduced_primal(
        conjugation;
        verify_truth=false,
    )
    full = assemble_full_spin_reduced_primal(
        spin;
        verify_truth=false,
    )
    cone = assemble_full_spin_cone_reduced_primal(
        full;
        verify_truth=false,
    )
    isotypic = assemble_full_spin_isotypic_reduced_primal(
        cone;
        verify_truth=false,
    )
    report = validate_exact_assembly(
        provenance.runmeta,
        primal,
        v4,
        conjugation,
        spin,
        full,
        cone,
        isotypic,
    )

    progress("rounding and replaying exact rational PSD matrices")
    witness = attempt_rational_witness(isotypic, floating_values)
    witness.passed ||
        error("no configured rational denominator produced an exact witness")
    witness_path = joinpath(options.output, "rational-witness.tsv")
    write_witness(
        witness_path,
        witness.denominator,
        witness.numerators,
        names,
        provenance,
    )
    replay_path = joinpath(options.output, "exact-replay.toml")
    replay = Dict(
        "schema_version" => REPLAY_SCHEMA,
        "completed_at_utc" => Dates.format(
            now(UTC),
            dateformat"yyyy-mm-ddTHH:MM:SS.sssZ",
        ),
        "passed" => true,
        "claim" =>
            "exact_rational_strictly_feasible_witness_for_finite_relaxation",
        "setup" => Dict(
            "model" => "shastry-sutherland",
            "g_square_over_dimer" => "4//5",
            "gamma" => "1//2",
            "patch_level" => 1,
            "degree_d" => 2,
            "state_class" => "unrestricted",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
        ),
        "input_hashes" => Dict(
            "model_mof_sha256" => provenance.model_sha256,
            "runmeta_sha256" => provenance.runmeta_sha256,
            "solve_result_sha256" => provenance.result_sha256,
            "primal_values_sha256" => provenance.values_sha256,
        ),
        "exact_assembly" => Dict(
            "assembly_sha256" => isotypic.assembly_sha256,
            "coefficient_map_sha256" =>
                isotypic.coefficient_map_sha256,
            "moment_count" => report.isotypic_moments,
            "positive_block_dimensions" =>
                report.positive_block_dimensions,
            "gap_block_dimensions" =>
                report.gap_block_dimensions,
            "equality_count" => report.equality_count,
            "real_psd_triangle_entries" =>
                report.real_psd_triangle_entries,
        ),
        "rational_witness" => Dict(
            "filename" => basename(witness_path),
            "sha256" => file_sha256(witness_path),
            "variable_count" => length(witness.numerators),
            "common_denominator" => string(witness.denominator),
            "denominator_power" => witness.denominator_power,
            "normalization_exact" =>
                witness.exact_values[1] == ExactRational(1),
        ),
        "exact_psd_replay" => Dict(
            "all_blocks_exactly_positive_definite" => true,
            "block_count" => length(witness.blocks),
            "blocks" => witness.blocks,
            "attempts" => witness.attempts,
        ),
        "wall_seconds" => time() - started,
    )
    write_toml(replay_path, replay)
    open(joinpath(options.output, "SHA256SUMS"), "w") do io
        for filename in ("rational-witness.tsv", "exact-replay.toml")
            println(
                io,
                file_sha256(joinpath(options.output, filename)),
                "  ",
                filename,
            )
        end
    end
    progress(
        "exact witness passed with denominator 10^" *
        "$(witness.denominator_power)",
    )
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main())
end
