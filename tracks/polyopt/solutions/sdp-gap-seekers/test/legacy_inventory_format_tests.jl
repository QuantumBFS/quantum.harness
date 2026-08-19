using Test

include(joinpath(@__DIR__, "..", "src", "LegacyInventoryFormat.jl"))
using .LegacyInventoryFormat

const CLEAN_SOURCE_A =
    "git=$(repeat("a", 40)) dirty=false package_version=0.3.0"
const CLEAN_SOURCE_B =
    "git=$(repeat("b", 40)) dirty=false package_version=0.3.0"

function fixture_header(model, config; source = CLEAN_SOURCE_A)
    basis_ordering = if model == "1D-transverse-field-Ising"
        "get_basis label=1 then label=2; entries in emission order"
    else
        "get_kagome_basis label=1 then label=2; entries in emission order"
    end
    return string(
        "format_version = 1\n",
        "generator = fixture\n",
        "spectralgap_source = ", source, "\n",
        "model = ", model, "\n",
        "config = ", config, "\n",
        "normalization = spin-1/2, S=sigma/2, Heisenberg factor 1/4\n",
        "encoding = Pauli index = 3*(site-1)+alpha; alpha in {1=x,2=y,3=z}\n",
        "basis_ordering = ", basis_ordering, "\n",
        "\n",
    )
end

function fixture_h_terms(model)
    if model == "1D-transverse-field-Ising"
        terms = [
            ((-1, 1), [3i, 3(i + 1)]) for i in 1:8
        ]
        append!(terms, [((1, 2), [3i - 2]) for i in 1:9])
    elseif model == "kagome-Heisenberg"
        triples = ([1, 2, 3], [1, 4, 5])
        terms = Tuple{Tuple{Int,Int},Vector{Int}}[]
        for triangle in triples
            for (a, b) in ((triangle[1], triangle[2]),
                           (triangle[1], triangle[3]),
                           (triangle[2], triangle[3]))
                for alpha in 1:3
                    push!(terms, ((1, 4), [3a - 3 + alpha, 3b - 3 + alpha]))
                end
            end
        end
    else
        error("unsupported fixture model: $model")
    end
    sort!(terms; by = term -> (term[1][1], term[1][2], term[2]))
    return terms
end

function fixture_payload(model)
    terms = fixture_h_terms(model)
    dimensions = if model == "1D-transverse-field-Ising"
        Dict(("pos", 1) => 211, ("pos", 2) => 50, ("gpos", 1) => 11, ("gpos", 2) => 14)
    else
        Dict(("pos", 1) => 31, ("pos", 2) => 22, ("gpos", 1) => 0, ("gpos", 2) => 1)
    end
    tsupp_count = model == "1D-transverse-field-Ising" ? 2705 : 10982
    io = IOBuffer()
    println(io, "[H]")
    println(io, "nterms = ", length(terms))
    for (id, ((num, den), support)) in enumerate(terms)
        println(
            io,
            "H[", id, "] coeff=", num, "/", den,
            " support=", canonical_int_vector(support),
        )
    end
    println(io)
    for (scope, label) in (("pos", 1), ("pos", 2), ("gpos", 1), ("gpos", 2))
        dimension = dimensions[(scope, label)]
        println(io, "[basis.", scope, ".label", label, "]")
        println(io, "id = basis.", scope, ".L", label)
        println(io, "dimension = ", dimension)
        for id in 1:dimension
            max_index = model == "kagome-Heisenberg" ? 15 : 27
            word = id == 1 ? Int[] : [mod1(id, max_index)]
            aux = id == 1 ? [Int[]] : Vector{Int}[]
            println(
                io,
                "entry[", id, "] word=", canonical_int_vector(word),
                " aux=", canonical_nested_int_vectors(aux),
            )
        end
        println(io)
    end
    println(io, "[tsupp]")
    println(io, "nrows = ", tsupp_count)
    rows = Vector{Vector{Int}}[Vector{Int}[]]
    for value in 0:tsupp_count - 2
        word = Int[]
        remainder = value
        for site in 1:9
            alpha = mod(remainder, 4)
            alpha != 0 && push!(word, 3(site - 1) + alpha)
            remainder = div(remainder, 4)
        end
        push!(rows, [word])
    end
    sort!(rows)
    for (id, row) in enumerate(rows)
        println(io, "row[", id, "] = ", canonical_nested_int_vectors(row))
    end
    println(io)
    println(io, "[pos.blocks]")
    for label in 1:2
        println(
            io,
            "block[", label, "] kind=pos label=", label,
            " dimension=", dimensions[("pos", label)],
            " basis_id=basis.pos.L", label,
        )
    end
    println(io, "[gpos.blocks]")
    for label in 1:2
        println(
            io,
            "block[", label, "] kind=gpos label=", label,
            " dimension=", dimensions[("gpos", label)],
            " basis_id=basis.gpos.L", label,
        )
    end
    return String(take!(io))
end

const FIXTURE_ISING_PAYLOAD = fixture_payload("1D-transverse-field-Ising")
const FIXTURE_KAGOME_PAYLOAD = fixture_payload("kagome-Heisenberg")

function fixture_records(; source = CLEAN_SOURCE_A)
    return [
        InventoryRecord(
            fixture_header("1D-transverse-field-Ising", "N=9 g=1/2 d=2"; source),
            FIXTURE_ISING_PAYLOAD,
        ),
        InventoryRecord(
            fixture_header("kagome-Heisenberg", "N=5 d=2"; source),
            FIXTURE_KAGOME_PAYLOAD,
        ),
    ]
end

function without_section(payload, first_marker, next_marker)
    first_range = findfirst(first_marker, payload)
    next_range = findfirst(next_marker, payload)
    first_range === nothing && error("missing fixture marker: $first_marker")
    next_range === nothing && error("missing fixture marker: $next_marker")
    first_position = first(first_range)
    next_position = first(next_range)
    prefix = first_position == firstindex(payload) ?
        "" : payload[firstindex(payload):prevind(payload, first_position)]
    return string(prefix, payload[next_position:end])
end

function fixture_line(payload, prefix)
    matches = filter(line -> startswith(line, prefix), split(payload, '\n'))
    length(matches) == 1 || error("fixture prefix is not unique: $prefix")
    return String(only(matches))
end

@testset "legacy inventory canonical hash scope" begin
    records_a = fixture_records(source = CLEAN_SOURCE_A)
    records_b = fixture_records(source = CLEAN_SOURCE_B)

    @test math_sha256(records_a) == math_sha256(records_b)
    @test render_math_inventory(records_a) != render_math_inventory(records_b)
    @test verify_math_inventory(render_math_inventory(records_a)).math_sha256 ==
          verify_math_inventory(render_math_inventory(records_b)).math_sha256

    row3 = fixture_line(records_a[1].payload, "row[3] = ")
    changed_payload = replace(records_a[1].payload, row3 => "row[3] = [[27]]")
    records_c = [InventoryRecord(records_a[1].header, changed_payload), records_a[2]]
    @test math_sha256(records_a) != math_sha256(records_c)
end

@testset "legacy inventory typed-empty canonical serialization" begin
    @test canonical_int_vector(Int[]) == "[]"
    @test canonical_int_vector(Int32[]) == "[]"
    @test canonical_nested_int_vectors(Vector{Int}[]) == "[]"
    @test canonical_nested_int_vectors([Int[]]) == "[[]]"
    @test canonical_nested_int_vectors([Int32[], Int32[1, 2]]) == "[[], [1, 2]]"
end

@testset "legacy inventory solver-free write and verification" begin
    records = fixture_records()
    mktempdir() do output_dir
        math_path = joinpath(output_dir, "legacy_inventory.math.txt")
        write_math_inventory(math_path, records)

        @test isfile(math_path)
        @test !ispath(joinpath(output_dir, "legacy_inventory.runmeta.txt"))

        report = verify_math_inventory_file(math_path)
        @test report.models == ["1D-transverse-field-Ising", "kagome-Heisenberg"]
        @test report.h_counts == [17, 18]
        @test report.basis_dimensions == [[211, 50, 11, 14], [31, 22, 0, 1]]
        @test report.tsupp_counts == [2705, 10982]
        @test report.math_sha256 == math_sha256(records)
        @test !report.freeze_verified
        @test verify_math_inventory_file(math_path; freeze = true).freeze_verified
    end
end

@testset "legacy inventory tamper detection" begin
    rendered = render_math_inventory(fixture_records())

    row3 = fixture_line(fixture_records()[1].payload, "row[3] = ")
    payload_tamper = replace(rendered, row3 => "row[3] = [[27]]"; count = 1)
    @test_throws ArgumentError verify_math_inventory(payload_tamper)

    records = fixture_records()
    bad_payload = replace(records[1].payload, "nterms = 17" => "nterms = 16"; count = 1)
    bad_count = render_math_inventory(
        [InventoryRecord(records[1].header, bad_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(bad_count)
end

@testset "legacy inventory strict grammar and semantics" begin
    records = fixture_records()

    missing_basis_payload = without_section(
        records[1].payload,
        "[basis.pos.label1]\n",
        "[basis.pos.label2]\n",
    )
    missing_basis = render_math_inventory(
        [InventoryRecord(records[1].header, missing_basis_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(missing_basis)

    wrong_block_payload = replace(
        records[1].payload,
        "block[1] kind=pos label=1 dimension=211 basis_id=basis.pos.L1" =>
            "block[1] kind=pos label=1 dimension=210 basis_id=basis.pos.L1",
    )
    wrong_block = render_math_inventory(
        [InventoryRecord(records[1].header, wrong_block_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(wrong_block)

    row3 = fixture_line(records[1].payload, "row[3] = ")
    row4 = fixture_line(records[1].payload, "row[4] = ")
    row3_value = split(row3, " = "; limit = 2)[2]
    row4_value = split(row4, " = "; limit = 2)[2]
    duplicate_row_payload = replace(
        records[1].payload,
        row4 => "row[4] = $row3_value",
    )
    duplicate_row = render_math_inventory(
        [InventoryRecord(records[1].header, duplicate_row_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(duplicate_row)

    unsorted_rows_payload = replace(
        records[1].payload,
        string(row3, "\n", row4) =>
            string("row[3] = ", row4_value, "\nrow[4] = ", row3_value),
    )
    unsorted_rows = render_math_inventory(
        [InventoryRecord(records[1].header, unsorted_rows_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(unsorted_rows)

    whitespace_row_payload = replace(records[1].payload, row3 => string(row3, "  "))
    whitespace_row = render_math_inventory(
        [InventoryRecord(records[1].header, whitespace_row_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(whitespace_row)

    trailing_payload = string(records[1].payload, "unknown = content\n")
    trailing = render_math_inventory(
        [InventoryRecord(records[1].header, trailing_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(trailing)

    wrong_header = replace(
        records[1].header,
        "normalization = spin-1/2, S=sigma/2, Heisenberg factor 1/4" =>
            "normalization = WRONG",
    )
    wrong_semantics = render_math_inventory(
        [InventoryRecord(wrong_header, records[1].payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(wrong_semantics)

    leading_count_payload = replace(
        records[1].payload,
        "nterms = 17" => "nterms = 017",
    )
    leading_count = render_math_inventory(
        [InventoryRecord(records[1].header, leading_count_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(leading_count; freeze = true)

    negative_word_payload = replace(
        records[1].payload,
        "entry[2] word=[2] aux=[]" => "entry[2] word=[-1] aux=[]",
    )
    negative_word = render_math_inventory(
        [InventoryRecord(records[1].header, negative_word_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(negative_word; freeze = true)

    same_site_word_payload = replace(
        records[1].payload,
        "entry[2] word=[2] aux=[]" => "entry[2] word=[1, 2] aux=[]",
    )
    same_site_word = render_math_inventory(
        [InventoryRecord(records[1].header, same_site_word_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(same_site_word; freeze = true)

    kagome_out_of_range_payload = replace(
        records[2].payload,
        "entry[2] word=[2] aux=[]" => "entry[2] word=[16] aux=[]",
    )
    kagome_out_of_range = render_math_inventory(
        [records[1], InventoryRecord(records[2].header, kagome_out_of_range_payload)],
    )
    @test_throws ArgumentError verify_math_inventory(kagome_out_of_range; freeze = true)

    leading_coefficient_payload = replace(
        records[1].payload,
        "H[9] coeff=1/2" => "H[9] coeff=01/2",
    )
    leading_coefficient = render_math_inventory(
        [InventoryRecord(records[1].header, leading_coefficient_payload), records[2]],
    )
    @test_throws ArgumentError verify_math_inventory(leading_coefficient; freeze = true)

    garbage_source = render_math_inventory(fixture_records(source = "garbage"))
    @test_throws ArgumentError verify_math_inventory(garbage_source)

    garbage_version = render_math_inventory(
        fixture_records(
            source = "git=$(repeat("d", 40)) dirty=false package_version=banana",
        ),
    )
    @test_throws ArgumentError verify_math_inventory(garbage_version)

    @test_throws ArgumentError verify_math_inventory(string("\n", render_math_inventory(records)))
end

@testset "legacy inventory explicit freeze provenance gate" begin
    dirty = render_math_inventory(
        fixture_records(
            source = "git=$(repeat("c", 40)) dirty=true package_version=0.3.0",
        ),
    )
    @test !verify_math_inventory(dirty).freeze_verified
    @test_throws ArgumentError verify_math_inventory(dirty; freeze = true)

    unavailable = render_math_inventory(
        fixture_records(
            source = "git=unavailable dirty=unknown package_version=0.3.0",
        ),
    )
    @test !verify_math_inventory(unavailable).freeze_verified
    @test_throws ArgumentError verify_math_inventory(unavailable; freeze = true)
end
