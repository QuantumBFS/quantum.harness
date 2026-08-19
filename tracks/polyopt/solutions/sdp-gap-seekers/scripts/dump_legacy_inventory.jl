#!/usr/bin/env julia
# dump_legacy_inventory.jl  — v1 canonical inventory dump (solver-free)
#
# Emits the legacy SpectralGap mathematical inventory in the v1 schema
# (notes/legacy-inventory-schema.md) for:
#   - 1D transverse-field Ising, N=9, g=1/2, d=2   (example.jl TFIM benchmark)
#   - Kagome Heisenberg,  N=5,             d=2   (smallest example.jl cluster)
#
# Output file (in cwd unless --output is given):
#   legacy_inventory.math.txt   byte-stable math inventory (H, basis, gbasis,
#                               tsupp affine rows, pos/gpos block metadata)
#
# This script never runs a solver, so it never creates
# legacy_inventory.runmeta.txt. Solver-run metadata belongs to an explicitly
# requested paired solver run and is outside the mathematical hash.
#
# Solver-free: calls ONLY ncpoly construction + get_basis/get_kagome_basis/
# get_bulkbasis/get_kagome_bulkbasis + reduce!/PSDstate_entry/isz/reduce_mirror.
# It does NOT call certify_*_gap, construct a JuMP model, or instantiate/call a
# Mosek optimizer, so it avoids the Mosek-11 zero-dim-PSD bug. Importing
# SpectralGap still loads its JuMP/MosekTools package dependencies. The tsupp
# construction MIRRORS the support-collection loops of
# certify_Ising_gap / certify_Heisenberg_kagome_gap line-for-line.
#
# Run on SCNet:
#   julia --startup-file=no --project=julia-env \
#     tracks/polyopt/solutions/sdp-gap-seekers/scripts/dump_legacy_inventory.jl \
#     --output legacy_inventory.math.txt
#
# STATUS: the pre-hash-fix generator was validated on SCNet (solver-free).
# Its asserts passed:
# Ising N=9 d=2 -> H=17 terms, lb=[211,50], lgb=[11,14], |tsupp|=2705;
# Kagome N=5 d=2 -> H=18 terms, lb=[31,22], lgb=[0,1], |tsupp|=10982.
# The corrected serialization + verifier still need two independent clean SCNet
# reproductions before any output is committed as the frozen oracle.

using SpectralGap

include(joinpath(@__DIR__, "..", "src", "LegacyInventoryFormat.jl"))
using .LegacyInventoryFormat

# ---- SpectralGap internals (not exported) -----------------------------------
get_basis_(args...; kw...)        = SpectralGap.get_basis(args...; kw...)
get_bulkbasis_(args...; kw...)    = SpectralGap.get_bulkbasis(args...; kw...)
get_kagome_basis_(args...; kw...) = SpectralGap.get_kagome_basis(args...; kw...)
get_kagome_bulkbasis_(args...; kw...) = SpectralGap.get_kagome_bulkbasis(args...; kw...)
reduce_!(args...; kw...)          = SpectralGap.reduce!(args...; kw...)
PSDstate_entry_(args...; kw...)   = SpectralGap.PSDstate_entry(args...; kw...)
isz_(args...; kw...)              = SpectralGap.isz(args...; kw...)
reduce_mirror_(args...; kw...)    = SpectralGap.reduce_mirror(args...; kw...)
reduce_perm_(args...; kw...)      = SpectralGap.reduce_perm(args...; kw...)

# ---- helpers ----------------------------------------------------------------
# exact rational of a Float coefficient known to be a short binary fraction
rat(c::Real) = rationalize(Int, c)

function write_header(io; model, config, basis_ordering)
    println(io, "format_version = 1")
    println(io, "generator = dump_legacy_inventory.jl")
    println(io, "spectralgap_source = ", spectralgap_source())
    println(io, "model = ", model)
    println(io, "config = ", config)
    println(io, "normalization = spin-1/2, S=sigma/2, Heisenberg factor 1/4")
    println(io, "encoding = Pauli index = 3*(site-1)+alpha; alpha in {1=x,2=y,3=z}")
    println(io, "basis_ordering = ", basis_ordering)
    println(io)
end

function write_terms(io, supp, coe)
    # stable id: sort terms by (num, den, support) — type-stable key
    entries = [(rat(c), s) for (s, c) in zip(supp, coe)]
    sort!(entries; by = e -> (numerator(e[1]), denominator(e[1]), e[2]))
    println(io, "[H]")
    println(io, "nterms = ", length(entries))
    for (i, (r, s)) in enumerate(entries)
        println(io, "H[", i, "] coeff=", numerator(r), "/", denominator(r),
                " support=", canonical_int_vector(s))
    end
end

function write_basis_block(io, scope, lbl, block)
    println(io, "[basis.", scope, ".label", lbl, "]")
    println(io, "id = basis.", scope, ".L", lbl)
    println(io, "dimension = ", length(block))
    for (i, entry) in enumerate(block)
        word, aux = entry
        println(
            io,
            "entry[", i, "] word=", canonical_int_vector(word),
            " aux=", canonical_nested_int_vectors(aux),
        )
    end
end

# Mirror certify_Ising_gap's support collection for the tsupp affine rows.
# Returns the deduped, sorted tsupp (Vector{Vector{Vector{Int}}}).
function ising_tsupp(basis, gbasis, H, N)
    lb  = length.(basis)
    lgb = length.(gbasis)
    tsupp = Vector{Vector{Int}}[]            # eltype: Vector{Vector{Int}}
    for i in 1:length(basis), j in 1:lb[i], k in j:lb[i]
        bi, c = reduce_!([basis[i][j][1]; basis[i][k][1]], N)   # defaults: model="Ising"
        if c != 0
            if isempty(bi)
                push!(tsupp, sort([basis[i][j][2]; basis[i][k][2]]))
            else
                push!(tsupp, sort([basis[i][j][2]; basis[i][k][2]; [bi]]))
            end
        end
    end
    for l in 1:length(gbasis), i in 1:lgb[l], j in i:lgb[l]
        bis = PSDstate_entry_(gbasis[l][i][1], gbasis[l][j][1], H, N)[1]
        for bi in bis
            if isempty(bi)
                push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]]))
            else
                push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]; [bi]]))
            end
        end
        if !isz_(gbasis[l][i][1]; model="Ising") && !isz_(gbasis[l][j][1]; model="Ising")
            temp = [reduce_mirror_(gbasis[l][i][1], N), reduce_mirror_(gbasis[l][j][1], N)]
            push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]; temp]))
        end
    end
    sort!(tsupp); unique!(tsupp)
    return tsupp
end

# Mirror certify_Heisenberg_kagome_gap's support collection (model="kagome",
# reduce_perm). Three loops: basis pairs, gbasis pairs (PSDstate_entry +
# reduce_perm mirror), and the 9-site even-component-count posepsd9 supports.
# The N>5 stationarity-monomial block is JuMP wiring and adds no tsupp rows, so
# it is not mirrored here.
function kagome_tsupp(basis, gbasis, H, N)
    lb  = length.(basis)
    lgb = length.(gbasis)
    tsupp = Vector{Vector{Int}}[]
    for i in 1:length(basis), j in 1:lb[i], k in j:lb[i]
        bi, c = reduce_!([basis[i][j][1]; basis[i][k][1]], N; model = "kagome")
        if c != 0
            if isempty(bi)
                push!(tsupp, sort([basis[i][j][2]; basis[i][k][2]]))
            else
                push!(tsupp, sort([basis[i][j][2]; basis[i][k][2]; [bi]]))
            end
        end
    end
    for l in 1:length(gbasis), i in 1:lgb[l], j in i:lgb[l]
        bis = PSDstate_entry_(gbasis[l][i][1], gbasis[l][j][1], H, N; model = "kagome")[1]
        for bi in bis
            if isempty(bi)
                push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]]))
            else
                push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]; [bi]]))
            end
        end
        if !isz_(gbasis[l][i][1]; model = "kagome") && !isz_(gbasis[l][j][1]; model = "kagome")
            temp = [reduce_perm_(gbasis[l][i][1]), reduce_perm_(gbasis[l][j][1])]
            push!(tsupp, sort([gbasis[l][i][2]; gbasis[l][j][2]; temp]))
        end
    end
    for i in 0:3, j in 0:3, k in 0:3, l in 0:3, s in 0:3, t in 0:3, u in 0:3, v in 0:3, w in 0:3
        ind = [i, j, k, l, s, t, u, v, w]
        if all(x -> iseven(sum(ind .== x)), 1:3)
            inx = ind .!= 0
            push!(tsupp, [reduce_perm_(3 * (Vector(1:9)[inx] .- 1) + ind[inx])])
        end
    end
    sort!(tsupp); unique!(tsupp)
    return tsupp
end

function write_tsupp(io, tsupp)
    println(io, "[tsupp]")
    println(io, "nrows = ", length(tsupp))
    for (i, row) in enumerate(tsupp)
        println(io, "row[", i, "] = ", canonical_nested_int_vectors(row))
    end
end

function write_blocks(io, scope, lbls)
    println(io, "[", scope, ".blocks]")
    for (k, lbl) in enumerate(lbls)
        println(io, "block[", k, "] kind=", scope, " label=", lbl,
                " basis_id=basis.", scope, ".L", lbl)
        # dimension line is filled by the caller via write_block_dims
    end
end

# ---- Ising case -------------------------------------------------------------
function dump_ising(header_io, payload_io, N, g_raz, d)
    g_float = Float64(g_raz)
    @info "Ising N=$N g=$g_raz d=$d"
    H = ncpoly([[3*[i; i+1] for i in 1:N-1]; [[3i - 2] for i in 1:N]],
               [-ones(N - 1); g_float * ones(N)])
    # ---- asserts (§4) ----
    @assert length(H.supp) == 17 "Ising N=$N H must have 17 terms, got $(length(H.supp))"
    for i in 1:N-1
        @assert rat(H.coe[i]) == -1 "Ising ZZ coeff $i must be -1, got $(H.coe[i])"
    end
    for i in N:length(H.supp)
        @assert rat(H.coe[i]) == g_raz "Ising TF coeff $i must be $g_raz, got $(H.coe[i])"
    end

    basis  = [get_basis_(N, d; label = i) for i in [1,2]]
    gbasis = [get_bulkbasis_(N, d - 1; label = i) for i in [1,2]]
    lb, lgb = length.(basis), length.(gbasis)
    tsupp = ising_tsupp(basis, gbasis, H, N)

    # ---- human/provenance header (§2.1, excluded from math SHA) ----
    write_header(
        header_io;
        model = "1D-transverse-field-Ising",
        config = string(
            "N=", N,
            " g=", numerator(g_raz), "/", denominator(g_raz),
            " d=", d,
        ),
        basis_ordering = "get_basis label=1 then label=2; entries in emission order",
    )
    # ---- H (§2.2) ----
    write_terms(payload_io, H.supp, H.coe); println(payload_io)
    # ---- basis blocks (§2.3) ----
    write_basis_block(payload_io, "pos", 1, basis[1]); println(payload_io)
    write_basis_block(payload_io, "pos", 2, basis[2]); println(payload_io)
    write_basis_block(payload_io, "gpos", 1, gbasis[1]); println(payload_io)
    write_basis_block(payload_io, "gpos", 2, gbasis[2]); println(payload_io)
    # ---- tsupp affine rows (§2.4) ----
    write_tsupp(payload_io, tsupp); println(payload_io)
    # ---- block layout metadata (§2.5) ----
    println(payload_io, "[pos.blocks]")
    for (k, dim) in enumerate(lb)
        println(payload_io, "block[", k, "] kind=pos label=", k,
                " dimension=", dim, " basis_id=basis.pos.L", k)
    end
    println(payload_io, "[gpos.blocks]")
    for (k, dim) in enumerate(lgb)
        println(payload_io, "block[", k, "] kind=gpos label=", k,
                " dimension=", dim, " basis_id=basis.gpos.L", k)
    end
    return (lb=lb, lgb=lgb, ntsupp=length(tsupp), nterms=length(H.supp))
end

# ---- Kagome case (H + basis + tsupp; model="kagome", reduce_perm) -----------
function dump_kagome(header_io, payload_io, N, d)
    @info "Kagome N=$N d=$d"
    triples = [[1, 2, 3], [1, 4, 5]]
    edges = Vector{Int}[]
    inner_triples, inner_edges = triples, edges
    H = ncpoly(
        vcat([
            [[3*a[1]-2; 3*a[2]-2], [3*a[1]-1; 3*a[2]-1], [3*a[1]; 3*a[2]],
             [3*a[1]-2; 3*a[3]-2], [3*a[1]-1; 3*a[3]-1], [3*a[1]; 3*a[3]],
             [3*a[2]-2; 3*a[3]-2], [3*a[2]-1; 3*a[3]-1], [3*a[2]; 3*a[3]]] for a in triples]...),
        0.25 * ones(9 * length(triples)))
    # ---- asserts (§4) ----
    @assert length(H.supp) == 18 "Kagome N=$N H must have 18 terms, got $(length(H.supp))"
    for c in H.coe
        @assert rat(c) == 1//4 "Kagome coeff must be 1/4, got $c"
    end

    basis  = [get_kagome_basis_(N, triples, edges, d; label = i) for i in 1:2]
    gbasis = [get_kagome_bulkbasis_(N, inner_triples, inner_edges, d - 1; label = i) for i in 1:2]
    lb, lgb = length.(basis), length.(gbasis)
    tsupp = kagome_tsupp(basis, gbasis, H, N)

    write_header(
        header_io;
        model = "kagome-Heisenberg",
        config = string("N=", N, " d=", d),
        basis_ordering = "get_kagome_basis label=1 then label=2; entries in emission order",
    )
    write_terms(payload_io, H.supp, H.coe); println(payload_io)
    write_basis_block(payload_io, "pos", 1, basis[1]); println(payload_io)
    write_basis_block(payload_io, "pos", 2, basis[2]); println(payload_io)
    write_basis_block(payload_io, "gpos", 1, gbasis[1]); println(payload_io)
    write_basis_block(payload_io, "gpos", 2, gbasis[2]); println(payload_io)
    write_tsupp(payload_io, tsupp); println(payload_io)
    println(payload_io, "[pos.blocks]")
    for (k, dim) in enumerate(lb)
        println(payload_io, "block[", k, "] kind=pos label=", k, " dimension=", dim,
                " basis_id=basis.pos.L", k)
    end
    println(payload_io, "[gpos.blocks]")
    for (k, dim) in enumerate(lgb)
        println(payload_io, "block[", k, "] kind=gpos label=", k, " dimension=", dim,
                " basis_id=basis.gpos.L", k)
    end
    return (lb=lb, lgb=lgb, ntsupp=length(tsupp), nterms=length(H.supp))
end

function spectralgap_source()
    # Prefer the exact source commit without relying on `git -C` (unavailable on
    # one legacy remote). This is provenance only and is excluded from math SHA.
    source_root = normpath(joinpath(dirname(pathof(SpectralGap)), ".."))
    try
        git_top = strip(read(
            Cmd(`git rev-parse --show-toplevel`; dir = source_root),
            String,
        ))
        realpath(git_top) == realpath(source_root) ||
            error("SpectralGap source is not its own git checkout")
        commit = strip(read(Cmd(`git rev-parse HEAD`; dir = source_root), String))
        occursin(r"^[0-9a-f]{40}$", commit) ||
            error("git returned a non-SHA revision")
        dirty = !isempty(strip(read(
            Cmd(`git status --porcelain`; dir = source_root),
            String,
        )))
        version = try
            string(pkgversion(SpectralGap))
        catch
            "unknown"
        end
        return "git=$commit dirty=$dirty package_version=$version"
    catch
        version = try
            string(pkgversion(SpectralGap))
        catch
            "unknown"
        end
        return "git=unavailable dirty=unknown package_version=$version"
    end
end

# ---- main: build and verify the solver-free mathematical inventory ----------
function parse_output_path(args)
    isempty(args) && return "legacy_inventory.math.txt"
    length(args) == 2 && args[1] == "--output" ||
        throw(ArgumentError("usage: dump_legacy_inventory.jl [--output PATH]"))
    return args[2]
end

function main(args = ARGS)
    output_path = parse_output_path(args)
    ising_header, ising_payload = IOBuffer(), IOBuffer()
    stats_ising = dump_ising(ising_header, ising_payload, 9, 1//2, 2)
    kagome_header, kagome_payload = IOBuffer(), IOBuffer()
    stats_kagome = dump_kagome(kagome_header, kagome_payload, 5, 2)
    records = [
        InventoryRecord(String(take!(ising_header)), String(take!(ising_payload))),
        InventoryRecord(String(take!(kagome_header)), String(take!(kagome_payload))),
    ]

    write_math_inventory(output_path, records)
    report = verify_math_inventory_file(output_path)

    @info "wrote solver-free math inventory: $output_path"
    @info "Ising  : H=$(stats_ising.nterms) terms, lb=$(stats_ising.lb), lgb=$(stats_ising.lgb), |tsupp|=$(stats_ising.ntsupp)"
    @info "Kagome : H=$(stats_kagome.nterms) terms, lb=$(stats_kagome.lb), lgb=$(stats_kagome.lgb), |tsupp|=$(stats_kagome.ntsupp)"
    @info "sha256(canonical math payload) = ", report.math_sha256
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
