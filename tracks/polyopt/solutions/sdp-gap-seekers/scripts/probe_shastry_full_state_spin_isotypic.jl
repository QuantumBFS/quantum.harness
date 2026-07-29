#!/usr/bin/env julia

using TOML

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))

for file in (
    "SquareJ1J2Prototype.jl",
    "GenericGapModel.jl",
    "PrimalGapSymbolics.jl",
    "PrimalGapAssembly.jl",
    "ExactSymmetryReduction.jl",
    "ReducedPrimalGapAssembly.jl",
    "ConjugationSymmetryReduction.jl",
    "FullStateSymmetryReduction.jl",
    "ShastryFullStateSpatialReduction.jl",
    "ShastryFullStateSpinSpatialReduction.jl",
)
    include(joinpath(TRACK_ROOT, "src", file))
end

using .SquareJ1J2Prototype
using .GenericGapModel
using .PrimalGapAssembly
using .FullStateSymmetryReduction
using .ShastryFullStateSpatialReduction
using .ShastryFullStateSpinSpatialReduction

const SpinReduction = ShastryFullStateSpinSpatialReduction

function progress(message)
    println(stderr, "[ss-spin-isotypic-probe] ", message)
    flush(stderr)
end

function normalized_combination(indices::Vector{Int}, coefficients::Vector{Int})
    pairs = sort!(collect(zip(indices, coefficients)); by=first)
    row_sign = sign(first(pairs)[2])
    normalized = [(index, row_sign * coefficient) for (index, coefficient) in pairs]
    key = join(("$index:$coefficient" for (index, coefficient) in normalized), ",")
    return row_sign, key
end

function spatial_row_action(block, permutation)
    source_indices = Dict(
        row => index
        for (index, row) in enumerate(block.source_block.rows)
    )
    target_rows = Dict{String,Int}()
    for (index, row) in enumerate(block.rows)
        row_sign, key = normalized_combination(
            row.source_indices,
            row.coefficients,
        )
        row_sign == 1 || error("source spatial row is not canonically signed")
        haskey(target_rows, key) &&
            error("spatial block contains duplicate combination rows")
        target_rows[key] = index
    end

    targets = Int[]
    signs = Int[]
    for row in block.rows
        mapped_indices = Int[]
        mapped_coefficients = Int[]
        for (source_index, coefficient) in
            zip(row.source_indices, row.coefficients)
            sign, target = SpinReduction.spin_row(
                block.source_block.rows[source_index],
                permutation,
            )
            haskey(source_indices, target) ||
                error("spin action leaves a trivial-character source block")
            push!(mapped_indices, source_indices[target])
            push!(mapped_coefficients, sign * coefficient)
        end
        row_sign, key =
            normalized_combination(mapped_indices, mapped_coefficients)
        haskey(target_rows, key) ||
            error("spin action leaves the spatial combination-row inventory")
        push!(targets, target_rows[key])
        push!(signs, row_sign)
    end
    length(unique(targets)) == length(block.rows) ||
        error("spin row action is not a permutation")
    return targets, signs
end

function orbit_sizes(actions::Vector{Vector{Int}})
    dimension = length(first(actions))
    visited = falses(dimension)
    sizes = Int[]
    for start in 1:dimension
        visited[start] && continue
        orbit = sort!(unique(action[start] for action in actions))
        all(!visited[index] for index in orbit) ||
            error("spin row orbits overlap")
        visited[orbit] .= true
        push!(sizes, length(orbit))
    end
    return sort!(sizes)
end

function block_report(block)
    actions = Vector{Vector{Int}}()
    traces = Int[]
    for permutation in SPIN_AXIS_PERMUTATIONS
        targets, signs = spatial_row_action(block, permutation)
        push!(actions, targets)
        push!(
            traces,
            sum(
                signs[index]
                for index in eachindex(targets)
                if targets[index] == index
                ;
                init=0
            ),
        )
    end
    identity_trace = traces[1]
    transposition_traces = Int[]
    cycle_traces = Int[]
    for (index, permutation) in enumerate(SPIN_AXIS_PERMUTATIONS[2:end])
        trace = traces[index + 1]
        if SpinReduction.permutation_sign(permutation) == -1
            push!(transposition_traces, trace)
        else
            push!(cycle_traces, trace)
        end
    end
    length(unique(transposition_traces)) == 1 ||
        error("transposition character is not class-constant")
    length(unique(cycle_traces)) == 1 ||
        error("three-cycle character is not class-constant")
    transposition_trace = only(unique(transposition_traces))
    cycle_trace = only(unique(cycle_traces))
    trivial = (identity_trace + 3transposition_trace + 2cycle_trace) ÷ 6
    sign_irrep = (identity_trace - 3transposition_trace + 2cycle_trace) ÷ 6
    standard = (identity_trace - cycle_trace) ÷ 3
    trivial + sign_irrep + 2standard == length(block.rows) ||
        error("S3 multiplicities do not reconstruct the block dimension")
    minimum((trivial, sign_irrep, standard)) >= 0 ||
        error("negative S3 multiplicity")
    return Dict(
        "dimension" => length(block.rows),
        "character_identity" => identity_trace,
        "character_transposition" => transposition_trace,
        "character_three_cycle" => cycle_trace,
        "trivial_multiplicity" => trivial,
        "sign_multiplicity" => sign_irrep,
        "standard_multiplicity" => standard,
        "orbit_sizes" => orbit_sizes(actions),
    )
end

block_key(block) = join(
    (
        block.source_block.role,
        block.source_block.family,
        "rx" * string(Int(block.source_block.character.rx)),
        "ry" * string(Int(block.source_block.character.ry)),
        block.parity,
    ),
    "/",
)

triangle(dimension::Int) = dimension * (dimension + 1) ÷ 2

function main()
    progress("assemble complete L=1,d=2 row inventory")
    problem = GapProblem(
        square_patch_geometry(1),
        shastry_sutherland_model(0//1),
        1//1,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    primal = assemble_primal_gap(
        problem;
        stationarity_spec=StationaritySpec(:full_inner_state, 1),
    )
    v4 = assemble_full_state_v4_reduced_primal(
        primal;
        verify_truth=false,
    )
    real_reduced = assemble_full_state_real_reduced_primal(
        v4;
        verify_truth=false,
    )
    spatial = assemble_shastry_full_state_spatial_reduced_primal(
        real_reduced;
        verify_truth=false,
    )

    progress("decompose every trivial-character spatial block under S3")
    blocks = [spatial.positive_blocks; spatial.gap_blocks]
    trivial_reports = Dict{String,Any}()
    retained_dimensions = Int[]
    nontrivial_representatives = Dict{String,Int}()
    for block in blocks
        character = block.source_block.character
        if !character.rx && !character.ry
            report = block_report(block)
            trivial_reports[block_key(block)] = report
            append!(
                retained_dimensions,
                filter(
                    >(0),
                    Int[
                        report["trivial_multiplicity"],
                        report["sign_multiplicity"],
                        report["standard_multiplicity"],
                    ],
                ),
            )
        else
            key = join(
                (
                    block.source_block.role,
                    block.source_block.family,
                    block.parity,
                ),
                "/",
            )
            dimension = length(block.rows)
            if haskey(nontrivial_representatives, key)
                nontrivial_representatives[key] == dimension ||
                    error("nontrivial character blocks have unequal dimensions")
            else
                nontrivial_representatives[key] = dimension
                push!(retained_dimensions, dimension)
            end
        end
    end

    result = Dict(
        "source_positive_block_dimensions" =>
            length.(getfield.(spatial.positive_blocks, :rows)),
        "source_gap_block_dimensions" =>
            length.(getfield.(spatial.gap_blocks, :rows)),
        "source_triangle_entries" => sum(
            triangle(length(block.rows))
            for block in blocks
        ),
        "trivial_character_blocks" => trivial_reports,
        "nontrivial_character_representatives" =>
            nontrivial_representatives,
        "predicted_retained_block_dimensions" =>
            sort!(retained_dimensions; rev=true),
        "predicted_maximum_side" => maximum(retained_dimensions),
        "predicted_triangle_entries" =>
            sum(triangle, retained_dimensions),
    )
    TOML.print(stdout, result; sorted=true)
    println()
    flush(stdout)
end

main()
