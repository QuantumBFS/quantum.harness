#!/usr/bin/env julia

using TOML

include(joinpath(@__DIR__, "build_shastry_full_state_spin_isotypic_mof.jl"))

const FS = FullStateSymmetryReduction
const Spatial = ShastryFullStateSpatialReduction
const Isotypic = ShastryFullStateSpinIsotypicReduction

function orbit_sizes(block)
    actions = [
        first(Isotypic.spatial_row_action(block, block, permutation))
        for permutation in SPIN_AXIS_PERMUTATIONS
    ]
    visited = falses(length(block.rows))
    sizes = Int[]
    for start in eachindex(block.rows)
        visited[start] && continue
        orbit = unique(action[start] for action in actions)
        all(!visited[index] for index in orbit) ||
            error("spin row orbits overlap")
        visited[orbit] .= true
        push!(sizes, length(orbit))
    end
    return sort!(sizes)
end

function block_key(block)
    source = block.source_block
    return join(
        (
            source.family,
            "rx" * string(Int(source.character.rx)),
            "ry" * string(Int(source.character.ry)),
            block.parity,
        ),
        "/",
    )
end

function main()
    problem = GapProblem(
        square_patch_geometry(2),
        shastry_sutherland_model(4//5),
        2//1,
        2;
        basis_mode=:structured,
        basis_spec=StructuredBasisSpec(:full_state_polynomial, 1),
    )
    entries = basis_manifest(problem, :positive).entries
    centered = FullStateReducedRow[
        FullStateReducedRow(:centered, row)
        for row in entries
        if !isempty(row.operator_word.ops)
    ]
    scalar = FullStateReducedRow[
        FullStateReducedRow(:scalar, row)
        for row in entries
        if isempty(row.operator_word.ops)
    ]
    blocks = vcat(
        FS.character_blocks(:positive, :centered, centered),
        FS.character_blocks(:positive, :scalar, scalar),
    )
    patch = problem.patch
    site_map = Int[
        patch.site_to_id[Spatial.shastry_spatial_site(site)]
        for site in patch.sites
    ]
    spatial_blocks = ShastrySpatialPSDBlock[]
    for block in blocks
        append!(
            spatial_blocks,
            Spatial.split_spatial_block(block, site_map),
        )
    end
    reports = Dict{String,Any}()
    for block in spatial_blocks
        block.source_block.character == V4Character(false, false) ||
            continue
        sizes = orbit_sizes(block)
        reports[block_key(block)] = Dict(
            "dimension" => length(block.rows),
            "orbit_size_counts" => Dict(
                string(size) => count(==(size), sizes)
                for size in unique(sizes)
            ),
        )
    end
    TOML.print(
        stdout,
        Dict(
            "positive_basis_dimension" => length(entries),
            "trivial_blocks" => reports,
        );
        sorted=true,
    )
    println()
    flush(stdout)
end

main()
