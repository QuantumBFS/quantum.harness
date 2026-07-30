module LegacyInventoryFormat

using SHA

export InventoryRecord,
       canonical_int_vector,
       canonical_math_payload,
       canonical_nested_int_vectors,
       math_sha256,
       parse_math_inventory,
       render_math_inventory,
       verify_math_inventory,
       verify_math_inventory_file,
       write_math_inventory

"""
One legacy-model record split into provenance and mathematical bytes.

`header` is human/provenance metadata and is deliberately excluded from the
canonical hash. `payload` is the exact §2.2–2.5 serialization and is hashed
byte-for-byte.
"""
struct InventoryRecord
    header::String
    payload::String

    function InventoryRecord(header::AbstractString, payload::AbstractString)
        header_string = String(header)
        payload_string = String(payload)
        occursin('\r', header_string) &&
            throw(ArgumentError("inventory header must use LF newlines"))
        occursin('\r', payload_string) &&
            throw(ArgumentError("inventory payload must use LF newlines"))
        startswith(header_string, "format_version = 1\n") ||
            throw(ArgumentError("inventory header must start with format_version = 1"))
        endswith(header_string, "\n\n") ||
            throw(ArgumentError("inventory header must end with one blank line"))
        startswith(payload_string, "[H]\n") ||
            throw(ArgumentError("inventory payload must start with [H]"))
        endswith(payload_string, '\n') ||
            throw(ArgumentError("inventory payload must end with LF"))
        occursin(r"(?m)^format_version = ", payload_string) &&
            throw(ArgumentError("format_version belongs in the unhashed header"))
        occursin(r"(?m)^sha256 = ", payload_string) &&
            throw(ArgumentError("sha256 line must not be part of the payload"))
        new(header_string, payload_string)
    end
end

"""Machine-independent decimal serialization of an integer vector."""
canonical_int_vector(values::AbstractVector{<:Integer}) =
    string("[", join(string.(values), ", "), "]")

"""Machine-independent decimal serialization of a nested integer vector."""
canonical_nested_int_vectors(values::AbstractVector{<:AbstractVector{<:Integer}}) =
    string("[", join(canonical_int_vector.(values), ", "), "]")

function parse_canonical_int_vector(encoded::AbstractString)
    text = String(encoded)
    match(r"^\[(?:-?[0-9]+(?:, -?[0-9]+)*)?\]$", text) === nothing &&
        throw(ArgumentError("non-canonical integer vector: $text"))
    inner = text[2:end-1]
    values = isempty(inner) ? Int[] : parse.(Int, split(inner, ", "))
    canonical_int_vector(values) == text ||
        throw(ArgumentError("non-canonical integer vector: $text"))
    return values
end

function parse_canonical_nested_int_vectors(encoded::AbstractString)
    text = String(encoded)
    startswith(text, '[') && endswith(text, ']') ||
        throw(ArgumentError("non-canonical nested integer vector: $text"))
    text == "[]" && return Vector{Int}[]

    inner = text[2:end-1]
    values = Vector{Int}[]
    position = firstindex(inner)
    while position <= lastindex(inner)
        inner[position] == '[' ||
            throw(ArgumentError("non-canonical nested integer vector: $text"))
        close_position = findnext(']', inner, position)
        close_position === nothing &&
            throw(ArgumentError("non-canonical nested integer vector: $text"))
        push!(values, parse_canonical_int_vector(inner[position:close_position]))
        position = nextind(inner, close_position)
        position > lastindex(inner) && break
        startswith(SubString(inner, position), ", [") ||
            throw(ArgumentError("non-canonical nested integer vector: $text"))
        position = nextind(inner, position, 2)
    end
    canonical_nested_int_vectors(values) == text ||
        throw(ArgumentError("non-canonical nested integer vector: $text"))
    return values
end

function validate_pauli_word(
    values::AbstractVector{<:Integer},
    max_site::Integer,
    context,
)
    all(index -> 1 <= index <= 3max_site, values) ||
        throw(ArgumentError(
            "$context contains a Pauli index outside 1:$(3max_site)",
        ))
    sites = cld.(values, 3)
    all(delta -> delta > 0, diff(sites)) ||
        throw(ArgumentError(
            "$context must have strictly increasing sites with at most one Pauli per site",
        ))
    return values
end

function validate_pauli_words(
    values::AbstractVector{<:AbstractVector{<:Integer}},
    max_site::Integer,
    context,
)
    for (index, value) in enumerate(values)
        validate_pauli_word(value, max_site, "$context word[$index]")
    end
    return values
end

"""Exact bytes hashed by the v1 legacy-inventory contract."""
function canonical_math_payload(records::AbstractVector{InventoryRecord})
    isempty(records) && throw(ArgumentError("inventory needs at least one model record"))
    return join((record.payload for record in records))
end

"""Lowercase SHA-256 of the canonical mathematical payload."""
math_sha256(records::AbstractVector{InventoryRecord}) =
    bytes2hex(sha256(canonical_math_payload(records)))

"""
Render the human/provenance headers, mathematical records, and final hash.

The header of each record is interleaved for readability, but only the
concatenation of `record.payload` in record order contributes to the hash.
"""
function render_math_inventory(records::AbstractVector{InventoryRecord})
    digest = math_sha256(records)
    body = join((record.header * record.payload for record in records))
    return string(body, "sha256 = ", digest, "\n")
end

"""Write only the solver-free mathematical inventory. No run metadata is created."""
function write_math_inventory(path::AbstractString,
                              records::AbstractVector{InventoryRecord})
    open(path, "w") do io
        write(io, render_math_inventory(records))
    end
    return String(path)
end

function finish_record!(records, header_lines, payload_lines)
    isempty(header_lines) && throw(ArgumentError("inventory record has no header"))
    isempty(payload_lines) && throw(ArgumentError("inventory record has no payload"))
    header = string(join(header_lines, "\n"), "\n")
    payload = string(join(payload_lines, "\n"), "\n")
    push!(records, InventoryRecord(header, payload))
    empty!(header_lines)
    empty!(payload_lines)
    return nothing
end

"""
Parse a rendered inventory without trusting its stored hash.

The exact hash scope is reconstructed from the `[H]`-through-block payload of
each model record; all preceding header lines stay outside that scope.
"""
function parse_math_inventory(text::AbstractString)
    content = String(text)
    occursin('\r', content) &&
        throw(ArgumentError("inventory must use LF newlines"))
    endswith(content, '\n') ||
        throw(ArgumentError("inventory must end with LF"))

    lines = split(content, '\n'; keepempty = true)
    isempty(lines[end]) ||
        throw(ArgumentError("inventory must have exactly terminated lines"))
    pop!(lines)
    isempty(lines) && throw(ArgumentError("inventory is empty"))

    hash_match = match(r"^sha256 = ([0-9a-f]{64})$", pop!(lines))
    hash_match === nothing &&
        throw(ArgumentError("inventory must end with one lowercase sha256 line"))
    stored_sha256 = only(hash_match.captures)

    records = InventoryRecord[]
    header_lines = String[]
    payload_lines = String[]
    state = :outside

    for line in lines
        if line == "format_version = 1"
            if state == :payload
                finish_record!(records, header_lines, payload_lines)
            elseif state == :header
                throw(ArgumentError("new record started before [H] payload"))
            end
            push!(header_lines, line)
            state = :header
        elseif state == :outside
            isempty(line) ||
                throw(ArgumentError("content before first format_version header"))
        elseif state == :header
            if line == "[H]"
                isempty(header_lines) &&
                    throw(ArgumentError("missing record header"))
                isempty(header_lines[end]) ||
                    throw(ArgumentError("header must end with one blank line before [H]"))
                push!(payload_lines, line)
                state = :payload
            else
                push!(header_lines, line)
            end
        else
            push!(payload_lines, line)
        end
    end

    state == :payload ||
        throw(ArgumentError("last inventory record has no payload"))
    finish_record!(records, header_lines, payload_lines)
    return (records = records, stored_sha256 = stored_sha256)
end

function header_value(header::String, key::String)
    prefix = string(key, " = ")
    values = [
        line[length(prefix) + 1:end]
        for line in split(header, '\n')
        if startswith(line, prefix)
    ]
    length(values) == 1 ||
        throw(ArgumentError("header must contain exactly one '$key = ' line"))
    return String(only(values))
end

function expected_h_terms(model::String)
    terms = Tuple{Int,Int,Vector{Int}}[]
    if model == "1D-transverse-field-Ising"
        append!(terms, [(-1, 1, [3i, 3(i + 1)]) for i in 1:8])
        append!(terms, [(1, 2, [3i - 2]) for i in 1:9])
    elseif model == "kagome-Heisenberg"
        for triangle in ([1, 2, 3], [1, 4, 5])
            for (a, b) in ((triangle[1], triangle[2]),
                           (triangle[1], triangle[3]),
                           (triangle[2], triangle[3]))
                for alpha in 1:3
                    push!(terms, (1, 4, [3a - 3 + alpha, 3b - 3 + alpha]))
                end
            end
        end
    else
        throw(ArgumentError("unexpected legacy model: $model"))
    end
    sort!(terms; by = term -> (term[1], term[2], term[3]))
    return terms
end

const EXPECTED_MODELS = ["1D-transverse-field-Ising", "kagome-Heisenberg"]
const EXPECTED_CONFIGS = Dict(
    "1D-transverse-field-Ising" => "N=9 g=1/2 d=2",
    "kagome-Heisenberg" => "N=5 d=2",
)
const EXPECTED_BASIS_DIMENSIONS = Dict(
    "1D-transverse-field-Ising" => Dict(
        ("pos", 1) => 211,
        ("pos", 2) => 50,
        ("gpos", 1) => 11,
        ("gpos", 2) => 14,
    ),
    "kagome-Heisenberg" => Dict(
        ("pos", 1) => 31,
        ("pos", 2) => 22,
        ("gpos", 1) => 0,
        ("gpos", 2) => 1,
    ),
)
const EXPECTED_TSUPP_COUNTS = Dict(
    "1D-transverse-field-Ising" => 2705,
    "kagome-Heisenberg" => 10982,
)
const EXPECTED_NORMALIZATION =
    "spin-1/2, S=sigma/2, Heisenberg factor 1/4"
const EXPECTED_ENCODING =
    "Pauli index = 3*(site-1)+alpha; alpha in {1=x,2=y,3=z}"
const EXPECTED_BASIS_ORDERING = Dict(
    "1D-transverse-field-Ising" =>
        "get_basis label=1 then label=2; entries in emission order",
    "kagome-Heisenberg" =>
        "get_kagome_basis label=1 then label=2; entries in emission order",
)

function take_line!(lines, cursor, context)
    cursor[] <= length(lines) ||
        throw(ArgumentError("$context is truncated"))
    line = lines[cursor[]]
    cursor[] += 1
    return line
end

function expect_line!(lines, cursor, expected, context)
    actual = take_line!(lines, cursor, context)
    actual == expected ||
        throw(ArgumentError("$context expected '$expected', got '$actual'"))
    return nothing
end

function verify_header(record::InventoryRecord, expected_model::String; freeze::Bool)
    lines = split(record.header, '\n'; keepempty = true)
    length(lines) == 10 && isempty(lines[9]) && isempty(lines[10]) ||
        throw(ArgumentError("$expected_model header must contain eight ordered fields"))
    expected_prefixes = [
        "format_version = ",
        "generator = ",
        "spectralgap_source = ",
        "model = ",
        "config = ",
        "normalization = ",
        "encoding = ",
        "basis_ordering = ",
    ]
    for (line, prefix) in zip(lines[1:8], expected_prefixes)
        startswith(line, prefix) ||
            throw(ArgumentError("$expected_model header fields are missing or reordered"))
        length(line) > length(prefix) ||
            throw(ArgumentError("$expected_model header field '$prefix' is empty"))
    end

    lines[1] == "format_version = 1" ||
        throw(ArgumentError("$expected_model format_version must be 1"))
    model = String(lines[4][length("model = ") + 1:end])
    model == expected_model ||
        throw(ArgumentError("expected $expected_model record, got $model"))
    lines[5] == "config = $(EXPECTED_CONFIGS[model])" ||
        throw(ArgumentError("$model configuration does not match the v1 contract"))
    lines[6] == "normalization = $EXPECTED_NORMALIZATION" ||
        throw(ArgumentError("$model normalization does not match the v1 contract"))
    lines[7] == "encoding = $EXPECTED_ENCODING" ||
        throw(ArgumentError("$model encoding does not match the v1 contract"))
    lines[8] == "basis_ordering = $(EXPECTED_BASIS_ORDERING[model])" ||
        throw(ArgumentError("$model basis ordering does not match the v1 contract"))

    source = String(lines[3][length("spectralgap_source = ") + 1:end])
    source_match = match(
        r"^git=([0-9a-f]{40}|unavailable) dirty=(false|true|unknown) package_version=(unknown|[0-9]+(?:\.[0-9]+){1,2}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$",
        source,
    )
    source_match === nothing &&
        throw(ArgumentError("$model has a malformed SpectralGap source header"))
    source_commit, source_dirty, source_version = source_match.captures
    if source_commit == "unavailable"
        source_dirty == "unknown" ||
            throw(ArgumentError("$model unavailable source must have dirty=unknown"))
    else
        source_dirty != "unknown" ||
            throw(ArgumentError("$model exact git source cannot have dirty=unknown"))
    end
    if freeze
        source_commit != "unavailable" && source_dirty == "false" ||
            throw(ArgumentError(
                "$model freeze verification needs an exact clean SpectralGap git source",
            ))
        source_version == "unknown" &&
            throw(ArgumentError("$model freeze verification needs a package version"))
    end
    return source
end

function parse_h_section!(lines, cursor, model)
    expect_line!(lines, cursor, "[H]", "$model H section")
    nterms_line = take_line!(lines, cursor, "$model H section")
    nterms_match = match(r"^nterms = (0|[1-9][0-9]*)$", nterms_line)
    nterms_match === nothing &&
        throw(ArgumentError("$model has an invalid nterms line"))
    declared_nterms = parse(Int, only(nterms_match.captures))

    terms = Tuple{Int,Int,Vector{Int}}[]
    for id in 1:declared_nterms
        line = take_line!(lines, cursor, "$model H section")
        term_match = match(
            r"^H\[([1-9][0-9]*)\] coeff=(0|-?[1-9][0-9]*)/([1-9][0-9]*) support=(\[[0-9, -]*\])$",
            line,
        )
        term_match === nothing &&
            throw(ArgumentError("$model has a malformed H term"))
        encoded_id, num, den, support = term_match.captures
        parse(Int, encoded_id) == id ||
            throw(ArgumentError("$model H term IDs are not consecutive"))
        parsed_support = parse_canonical_int_vector(support)
        max_site = model == "kagome-Heisenberg" ? 5 : 9
        validate_pauli_word(parsed_support, max_site, "$model H[$id] support")
        push!(terms, (
            parse(Int, num),
            parse(Int, den),
            parsed_support,
        ))
    end
    expect_line!(lines, cursor, "", "$model H section")

    expected = expected_h_terms(model)
    declared_nterms == length(expected) && terms == expected ||
        throw(ArgumentError("$model Hamiltonian is not the frozen exact-rational case"))
    return declared_nterms
end

function parse_basis_section!(lines, cursor, model, scope, label)
    context = "$model basis.$scope.label$label section"
    expect_line!(lines, cursor, "[basis.$scope.label$label]", context)
    expect_line!(lines, cursor, "id = basis.$scope.L$label", context)

    dimension_line = take_line!(lines, cursor, context)
    dimension_match = match(r"^dimension = (0|[1-9][0-9]*)$", dimension_line)
    dimension_match === nothing &&
        throw(ArgumentError("$context has an invalid dimension"))
    dimension = parse(Int, only(dimension_match.captures))
    expected_dimension = EXPECTED_BASIS_DIMENSIONS[model][(scope, label)]
    dimension == expected_dimension ||
        throw(ArgumentError(
            "$context dimension=$dimension, expected $expected_dimension",
        ))

    entries = Tuple{Vector{Int},Vector{Vector{Int}}}[]
    for id in 1:dimension
        line = take_line!(lines, cursor, context)
        entry_match = match(
            r"^entry\[([1-9][0-9]*)\] word=(\[[0-9, -]*\]) aux=(.+)$",
            line,
        )
        entry_match === nothing &&
            throw(ArgumentError("$context has a malformed entry"))
        encoded_id, word, aux = entry_match.captures
        parse(Int, encoded_id) == id ||
            throw(ArgumentError("$context entry IDs are not consecutive"))
        parsed_word = parse_canonical_int_vector(word)
        parsed_aux = parse_canonical_nested_int_vectors(aux)
        max_site = model == "kagome-Heisenberg" ? 5 : 9
        validate_pauli_word(parsed_word, max_site, "$context entry[$id] word")
        validate_pauli_words(parsed_aux, max_site, "$context entry[$id] aux")
        push!(entries, (parsed_word, parsed_aux))
    end
    expect_line!(lines, cursor, "", context)
    return dimension
end

function parse_tsupp_section!(lines, cursor, model)
    context = "$model tsupp section"
    expect_line!(lines, cursor, "[tsupp]", context)
    nrows_line = take_line!(lines, cursor, context)
    nrows_match = match(r"^nrows = (0|[1-9][0-9]*)$", nrows_line)
    nrows_match === nothing &&
        throw(ArgumentError("$model has an invalid nrows line"))
    nrows = parse(Int, only(nrows_match.captures))
    expected_nrows = EXPECTED_TSUPP_COUNTS[model]
    nrows == expected_nrows ||
        throw(ArgumentError("$model tsupp nrows=$nrows, expected $expected_nrows"))

    rows = Vector{Vector{Int}}[]
    for id in 1:nrows
        line = take_line!(lines, cursor, context)
        row_match = match(r"^row\[([1-9][0-9]*)\] = (.+)$", line)
        row_match === nothing &&
            throw(ArgumentError("$model has a malformed tsupp row"))
        encoded_id, encoded_row = row_match.captures
        parse(Int, encoded_id) == id ||
            throw(ArgumentError("$model tsupp row IDs are not consecutive"))
        parsed_row = parse_canonical_nested_int_vectors(encoded_row)
        validate_pauli_words(parsed_row, 9, "$model tsupp row[$id]")
        push!(rows, parsed_row)
    end
    expect_line!(lines, cursor, "", context)
    issorted(rows) ||
        throw(ArgumentError("$model tsupp rows are not canonical-sorted"))
    length(unique(rows)) == length(rows) ||
        throw(ArgumentError("$model tsupp contains structurally duplicate rows"))
    return nrows
end

function parse_block_sections!(lines, cursor, model)
    dimensions = EXPECTED_BASIS_DIMENSIONS[model]
    for scope in ("pos", "gpos")
        context = "$model $scope.blocks section"
        expect_line!(lines, cursor, "[$scope.blocks]", context)
        for label in 1:2
            dimension = dimensions[(scope, label)]
            expect_line!(
                lines,
                cursor,
                "block[$label] kind=$scope label=$label dimension=$dimension " *
                "basis_id=basis.$scope.L$label",
                context,
            )
        end
    end
    cursor[] == length(lines) + 1 ||
        throw(ArgumentError("$model payload has unknown or trailing content"))
    return nothing
end

function verify_payload(payload::String, model::String)
    lines = split(payload, '\n'; keepempty = true)
    isempty(lines[end]) ||
        throw(ArgumentError("$model payload must end with LF"))
    pop!(lines)
    cursor = Ref(1)

    h_count = parse_h_section!(lines, cursor, model)
    basis_dimensions = Int[]
    for (scope, label) in
        (("pos", 1), ("pos", 2), ("gpos", 1), ("gpos", 2))
        push!(
            basis_dimensions,
            parse_basis_section!(lines, cursor, model, scope, label),
        )
    end
    tsupp_count = parse_tsupp_section!(lines, cursor, model)
    parse_block_sections!(lines, cursor, model)
    return (
        h_count = h_count,
        basis_dimensions = basis_dimensions,
        tsupp_count = tsupp_count,
    )
end

"""
Verify the stored digest and the two frozen Hamiltonian/count contracts.

This verifier is solver-free and depends only on Julia standard libraries.
"""
function verify_math_inventory(text::AbstractString; freeze::Bool = false)
    parsed = parse_math_inventory(text)
    records = parsed.records
    computed_sha256 = math_sha256(records)
    computed_sha256 == parsed.stored_sha256 ||
        throw(ArgumentError(
            "math SHA mismatch: stored=$(parsed.stored_sha256) computed=$computed_sha256",
        ))
    render_math_inventory(records) == String(text) ||
        throw(ArgumentError("inventory parse/render is not byte-identical"))

    length(records) == length(EXPECTED_MODELS) ||
        throw(ArgumentError("inventory must contain exactly two model records"))
    models = [
        header_value(record.header, "model")
        for record in records
    ]
    models == EXPECTED_MODELS ||
        throw(ArgumentError("records must be ordered Ising then Kagome"))
    spectralgap_sources = [
        verify_header(record, model; freeze)
        for (record, model) in zip(records, models)
    ]
    length(unique(spectralgap_sources)) == 1 ||
        throw(ArgumentError("all records must report the same SpectralGap source"))

    payload_reports = [
        verify_payload(record.payload, model)
        for (record, model) in zip(records, models)
    ]
    return (
        math_sha256 = computed_sha256,
        models = models,
        spectralgap_source = only(unique(spectralgap_sources)),
        h_counts = [report.h_count for report in payload_reports],
        basis_dimensions = [
            report.basis_dimensions
            for report in payload_reports
        ],
        tsupp_counts = [report.tsupp_count for report in payload_reports],
        freeze_verified = freeze,
    )
end

verify_math_inventory_file(path::AbstractString; freeze::Bool = false) =
    verify_math_inventory(read(path, String); freeze)

end
