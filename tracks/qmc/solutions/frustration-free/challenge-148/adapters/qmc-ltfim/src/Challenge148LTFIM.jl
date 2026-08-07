module Challenge148LTFIM

using JSON3
using LinearAlgebra
using OnlineStats
using QMC
using Random
using SHA

export build_info, build_model, canonical_json, coupling_matrix, dense_pauli_hamiltonian,
       derive_seed, energy_estimator, honeycomb_reference_bonds, longitudinal_moments,
       main, run_request, triangular_reference_bonds, transverse_estimator,
       validate_graph_payload, validate_pointer

const QMC_REVISION = "524860b9c0e212ac630b0d9754075bb24198da3b"
const QMC_LICENSE = "Apache-2.0"
const SEED_DOMAIN = "qmc-ltfim-seed-v1"
const SEED_DERIVATION = "sha256:qmc-ltfim-seed-v1||u64be"
const SEED_NAMESPACE = "QMC_LTFIM:qmc-ltfim-seed-v1"
const RNG_NAME = "Julia-1.11.6-Random.Xoshiro-xoshiro256++"
const SOURCE_FILE = @__FILE__
const ADAPTER_ROOT = normpath(joinpath(dirname(SOURCE_FILE), ".."))
const O_RDONLY = 0
const O_WRONLY = 1
const O_RDWR = 2
const O_CREAT = 0o100
const O_EXCL = 0o200
const O_DIRECTORY = 0o200000
const O_CLOEXEC = 0o2000000
const O_NOFOLLOW = 0o400000
const LOCK_EX = 2
const AT_FDCWD = -100
const AT_REMOVEDIR = 0x200
const RENAME_NOREPLACE = 1
const SYS_OPENAT = 257
const SYS_LINKAT = 265
const SYS_RENAMEAT2 = 316
const SYS_OPENAT2 = 437
const RESOLVE_NO_MAGICLINKS = 0x02
const RESOLVE_NO_SYMLINKS = 0x04
const RESOLVE_BENEATH = 0x08
const REQUEST_KEYS = Set([
    "schema_version", "adapter", "graph_path", "graph_sha256", "beta", "coupling",
    "field", "seed", "thermalization_sweeps", "retained_samples", "thinning",
    "serial_measurement_stride_samples", "bin_length", "checkpoint_bins",
    "expected_source_hash", "expected_build_hash",
])
const HEX64 = r"^[0-9a-f]{64}$"
const MAX_GRAPH_BYTES = 2 * 1024 * 1024
const MAX_LENGTH = 96
const MAX_SITES = 18_432
const MAX_BONDS = 27_648
const FSYNC_COUNT = Ref(0)

struct GraphSpec
    lattice::String
    length::Int
    site_count::Int
    bonds::Vector{Tuple{Int,Int}}
    sha256::Union{Nothing,String}
end

struct OpenHow
    flags::UInt64
    mode::UInt64
    resolve::UInt64
end

mutable struct SecureDir
    fd::Cint
    identity::Tuple{UInt64,UInt64}
end

struct AnchorLink
    parent::SecureDir
    child::SecureDir
    name::String
end

struct AnchoredDir
    directory::SecureDir
    links::Vector{AnchorLink}
end

mutable struct RunLock
    output::String
    anchored::AnchoredDir
    state_dir::SecureDir
    anchors_dir::SecureDir
    fd::Cint
    state_identity::Tuple{UInt64,UInt64}
    lock_identity::Tuple{UInt64,UInt64}
    selection_identity::Tuple{UInt64,UInt64}
    anchor_identity::Tuple{UInt64,UInt64}
    selection_bytes::Vector{UInt8}
    anchor_bytes::Vector{UInt8}
    anchor_sha256::String
end

function Base.close(directory::SecureDir)
    if directory.fd >= 0
        descriptor = directory.fd
        directory.fd = -1
        ccall(:close, Cint, (Cint,), descriptor) == 0 ||
            throw(SystemError("close directory", Libc.errno()))
    end
    return nothing
end

Base.isopen(directory::SecureDir) = directory.fd >= 0

function Base.close(anchored::AnchoredDir)
    seen = IdSet{SecureDir}()
    for link in anchored.links
        push!(seen, link.parent)
        push!(seen, link.child)
    end
    push!(seen, anchored.directory)
    first_error = nothing
    for directory in seen
        try
            close(directory)
        catch error
            first_error === nothing && (first_error = error)
        end
    end
    first_error === nothing || throw(first_error)
    return nothing
end

mutable struct TracedRNG{R<:AbstractRNG} <: AbstractRNG
    inner::R
    bool_draws::Vector{Bool}
end

Random.rand(rng::TracedRNG) = rand(rng.inner)
Random.rand(rng::TracedRNG, ::Type{Bool}) = begin
    value = rand(rng.inner, Bool)
    push!(rng.bool_draws, value)
    value
end
Random.rand(rng::TracedRNG, sampler::QMC.OperatorSampler) = rand(rng.inner, sampler)

function _plain(value)
    if value isa JSON3.Object
        return Dict(String(k) => _plain(v) for (k, v) in pairs(value))
    elseif value isa AbstractDict
        return Dict(String(k) => _plain(v) for (k, v) in pairs(value))
    elseif value isa JSON3.Array || value isa AbstractVector
        return [_plain(v) for v in value]
    end
    return value
end

function _json(value)::String
    value = _plain(value)
    if value === nothing
        return "null"
    elseif value isa Bool
        return value ? "true" : "false"
    elseif value isa Integer
        return string(value)
    elseif value isa AbstractFloat
        isfinite(value) || throw(ArgumentError("non-finite value is not canonical JSON"))
        isinteger(value) && typemin(Int64) <= value <= typemax(Int64) &&
            return string(round(Int64, value))
        return JSON3.write(Float64(value))
    elseif value isa AbstractString
        return JSON3.write(String(value))
    elseif value isa AbstractVector || value isa Tuple
        return "[" * join((_json(v) for v in value), ",") * "]"
    elseif value isa AbstractDict
        keys_sorted = sort!(collect(String(k) for k in keys(value)))
        return "{" * join((_json(k) * ":" * _json(value[k]) for k in keys_sorted), ",") * "}"
    end
    throw(ArgumentError("unsupported canonical JSON value $(typeof(value))"))
end

canonical_json(value) = _json(value) * "\n"
canonical_bytes(value) = Vector{UInt8}(codeunits(canonical_json(value)))
canonical_hash(value) = bytes2hex(sha256(canonical_bytes(value)))
sha256_bytes(bytes::AbstractVector{UInt8}) = bytes2hex(sha256(bytes))

function _read_json(path::AbstractString; ceiling::Int=MAX_GRAPH_BYTES)
    bytes = secure_read(path; ceiling)
    try
        return _plain(JSON3.read(String(bytes)))
    catch error
        throw(ArgumentError("invalid JSON in $path: $(sprint(showerror, error))"))
    end
end

function _require_keys(value::AbstractDict, expected::Set{String}, name::String)
    actual = Set(String(k) for k in keys(value))
    actual == expected ||
        throw(ArgumentError("$name contains unknown or missing fields: $(sort!(collect(symdiff(actual, expected))))"))
end

function _require_int(value, name; minimum::Int=typemin(Int))
    value isa Integer && !(value isa Bool) || throw(ArgumentError("$name must be an integer"))
    typemin(Int) <= value <= typemax(Int) || throw(ArgumentError("$name integer overflow"))
    result = Int(value)
    result >= minimum || throw(ArgumentError("$name is below its minimum"))
    return result
end

function _require_number(value, name; positive=false, nonnegative=false)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$name must be a number"))
    result = Float64(value)
    isfinite(result) || throw(ArgumentError("$name must be finite"))
    positive && result <= 0 && throw(ArgumentError("$name must be positive"))
    nonnegative && result < 0 && throw(ArgumentError("$name must be nonnegative"))
    return result
end

function triangular_reference_bonds(length::Integer)
    L = Int(length)
    bonds = Set{Tuple{Int,Int}}()
    for y in 0:(L - 1), x in 0:(L - 1)
        left = x + L * y
        for (dx, dy) in ((1, 0), (0, 1), (1, -1))
            right = mod(x + dx, L) + L * mod(y + dy, L)
            left == right || push!(bonds, minmax(left, right))
        end
    end
    return sort!(collect(bonds))
end

function honeycomb_reference_bonds(length::Integer)
    L = Int(length)
    bonds = Set{Tuple{Int,Int}}()
    for y in 0:(L - 1), x in 0:(L - 1)
        a = 2 * (x + L * y)
        for (nx, ny) in ((x, y), (mod(x - 1, L), y), (x, mod(y - 1, L)))
            b = 2 * (nx + L * ny) + 1
            push!(bonds, minmax(a, b))
        end
    end
    return sort!(collect(bonds))
end

function validate_graph_payload(raw::AbstractDict)
    payload = _plain(raw)
    allowed = Set(["lattice", "length", "site_count", "bonds"])
    haskey(payload, "sha256") && push!(allowed, "sha256")
    _require_keys(payload, allowed, "graph")
    lattice = get(payload, "lattice", nothing)
    lattice isa String && lattice in ("triangular", "honeycomb") ||
        throw(ArgumentError("graph lattice is invalid"))
    L = _require_int(get(payload, "length", nothing), "graph length"; minimum=1)
    L <= MAX_LENGTH || throw(ArgumentError("graph length exceeds ceiling"))
    lattice == "triangular" && L < 3 &&
        throw(ArgumentError("triangular graph length must be at least 3"))
    lattice == "honeycomb" && L < 2 &&
        throw(ArgumentError("honeycomb graph length must be at least 2"))
    N = _require_int(get(payload, "site_count", nothing), "graph site_count"; minimum=1)
    N <= MAX_SITES || throw(ArgumentError("graph site count exceeds ceiling"))
    expected_sites = lattice == "triangular" ? Base.checked_mul(L, L) :
                     Base.checked_mul(2, Base.checked_mul(L, L))
    N == expected_sites || throw(ArgumentError("graph site-count invariant failed"))
    raw_bonds = get(payload, "bonds", nothing)
    raw_bonds isa AbstractVector || throw(ArgumentError("graph bonds must be an array"))
    length(raw_bonds) <= MAX_BONDS || throw(ArgumentError("graph bond count exceeds ceiling"))
    bonds = Tuple{Int,Int}[]
    seen = Set{Tuple{Int,Int}}()
    degree = zeros(Int, N)
    adjacency = [Int[] for _ in 1:N]
    for raw_bond in raw_bonds
        (raw_bond isa AbstractVector || raw_bond isa Tuple) && length(raw_bond) == 2 ||
            throw(ArgumentError("graph bond must be an integer pair"))
        left = _require_int(raw_bond[1], "graph bond endpoint"; minimum=0)
        right = _require_int(raw_bond[2], "graph bond endpoint"; minimum=0)
        left < N && right < N || throw(ArgumentError("graph bond endpoint is out of bounds"))
        left != right || throw(ArgumentError("graph self-loop is forbidden"))
        left < right || throw(ArgumentError("graph bond endpoints are not canonical"))
        bond = (left, right)
        bond ∉ seen || throw(ArgumentError("graph duplicate bond"))
        push!(seen, bond)
        push!(bonds, bond)
        degree[left + 1] += 1
        degree[right + 1] += 1
        push!(adjacency[left + 1], right + 1)
        push!(adjacency[right + 1], left + 1)
    end
    issorted(bonds) || throw(ArgumentError("graph bonds are not in canonical order"))
    expected_bonds = lattice == "triangular" ? 3 * N : 3 * N ÷ 2
    length(bonds) == expected_bonds || throw(ArgumentError("graph bond-count invariant failed"))
    expected_degree = lattice == "triangular" ? 6 : 3
    all(==(expected_degree), degree) || throw(ArgumentError("graph degree invariant failed"))
    visited = falses(N)
    queue = [1]
    visited[1] = true
    while !isempty(queue)
        node = popfirst!(queue)
        for neighbor in adjacency[node]
            if !visited[neighbor]
                visited[neighbor] = true
                push!(queue, neighbor)
            end
        end
    end
    all(visited) || throw(ArgumentError("graph is disconnected"))
    reference_bonds = lattice == "triangular" ?
                      triangular_reference_bonds(L) : honeycomb_reference_bonds(L)
    bonds == reference_bonds ||
        throw(ArgumentError("graph lattice topology does not match the canonical periodic construction"))
    embedded = haskey(payload, "sha256") ? payload["sha256"] : nothing
    if embedded !== nothing
        embedded isa String && occursin(HEX64, embedded) ||
            throw(ArgumentError("graph embedded SHA256 is invalid"))
        unhashed = Dict(
            "bonds" => [[a, b] for (a, b) in bonds],
            "lattice" => lattice,
            "length" => L,
            "site_count" => N,
        )
        digest = bytes2hex(sha256(Vector{UInt8}(codeunits(chomp(canonical_json(unhashed))))))
        digest == embedded || throw(ArgumentError("graph embedded SHA256 mismatch"))
    end
    return GraphSpec(lattice, L, N, bonds, embedded)
end

function load_graph(path::String, requested_sha::String)
    bytes = secure_read(path; ceiling=MAX_GRAPH_BYTES)
    payload = try
        _plain(JSON3.read(String(bytes)))
    catch
        throw(ArgumentError("invalid graph JSON"))
    end
    payload isa AbstractDict || throw(ArgumentError("graph payload must be an object"))
    graph = validate_graph_payload(payload)
    graph.sha256 == requested_sha || throw(ArgumentError("graph requested SHA256 mismatch"))
    return graph
end

function coupling_matrix(N::Integer, bonds, coupling::Real)
    J = zeros(Float64, Int(N), Int(N))
    for (left, right) in bonds
        0 <= left < right < N || throw(ArgumentError("noncanonical coupling edge"))
        J[left + 1, right + 1] = -Float64(coupling)
    end
    return J
end

function build_model(N::Integer, bonds, coupling::Real, field::Real)
    Jmatrix = coupling_matrix(N, bonds, coupling)
    return QMC.TFIM(UpperTriangular(Jmatrix), fill(Float64(field), Int(N)))
end

function _site_operator(matrix, site, N)
    result = ones(Float64, 1, 1)
    identity2 = Matrix{Float64}(I, 2, 2)
    for index in 1:N
        result = kron(result, index == site ? matrix : identity2)
    end
    return result
end

function dense_pauli_hamiltonian(N::Integer, bonds, coupling::Real, field::Real)
    N = Int(N)
    dimension = 1 << N
    result = zeros(Float64, dimension, dimension)
    x = [0.0 1.0; 1.0 0.0]
    z = [1.0 0.0; 0.0 -1.0]
    zops = [_site_operator(z, site, N) for site in 1:N]
    for (left, right) in bonds
        result .-= Float64(coupling) .* (zops[left + 1] * zops[right + 1])
    end
    for site in 1:N
        result .-= Float64(field) .* _site_operator(x, site, N)
    end
    return result
end

function derive_seed(seed::Integer)
    0 <= seed <= typemax(UInt64) || throw(ArgumentError("seed is outside uint64"))
    encoded = [UInt8((UInt64(seed) >> shift) & 0xff) for shift in 56:-8:0]
    return sha256(vcat(Vector{UInt8}(codeunits(SEED_DOMAIN)), encoded))
end

function rng_from_seed(seed::Integer)
    digest = derive_seed(seed)
    words = ntuple(4) do word
        offset = 8 * (word - 1)
        foldl((value, byte) -> (value << 8) | UInt64(byte), digest[(offset + 1):(offset + 8)]; init=UInt64(0))
    end
    return TracedRNG(Random.Xoshiro(words...), Bool[])
end

energy_estimator(::QMC.BinaryThermalState, H, beta::Real, num_ops::Integer) =
    H.energy_shift - Float64(num_ops) / Float64(beta)
transverse_estimator(H, beta::Real, site_operator_count::Integer) =
    Float64(site_operator_count) / (Float64(beta) * sum(H.hx)) - 1.0

function longitudinal_moments(state::QMC.BinaryThermalState, H)
    m = QMC.magnetization(QMC.sample(H, state))
    return (m^2, m^4)
end

function _source_hash()
    runner = joinpath(ADAPTER_ROOT, "run_independent.jl")
    bytes = vcat(read(SOURCE_FILE), isfile(runner) ? read(runner) : UInt8[])
    return sha256_bytes(bytes)
end

function _build_hash()
    files = [joinpath(ADAPTER_ROOT, "Project.toml"), joinpath(ADAPTER_ROOT, "Manifest.toml")]
    bytes = Vector{UInt8}(codeunits("julia=$(VERSION)\n"))
    for path in files
        isfile(path) && append!(bytes, read(path))
    end
    return sha256_bytes(bytes)
end

function build_info()
    return Dict(
        "adapter" => "QMC_LTFIM",
        "build_hash" => _build_hash(),
        "julia" => string(VERSION),
        "qmc_license" => QMC_LICENSE,
        "qmc_revision" => QMC_REVISION,
        "rng" => RNG_NAME,
        "seed_derivation" => SEED_DERIVATION,
        "seed_namespace" => SEED_NAMESPACE,
        "source_hash" => _source_hash(),
        "sweep_semantics" => "one QMC_LTFIM mc_step_beta! diagonal-plus-cluster update",
    )
end

function ensure_nosymlinks(path::AbstractString; allow_missing_leaf=false)
    absolute = abspath(path)
    current = "/"
    parts = splitpath(absolute)
    for (index, part) in enumerate(parts)
        part == "/" && continue
        current = joinpath(current, part)
        if !ispath(current)
            allow_missing_leaf && index == length(parts) && return absolute
            throw(ArgumentError("path component does not exist: $current"))
        end
        islink(current) && throw(ArgumentError("symbolic-link path component rejected: $current"))
    end
    return absolute
end

function secure_read(path::AbstractString; ceiling=typemax(Int))
    absolute = ensure_nosymlinks(path)
    fd = ccall(:open, Cint, (Cstring, Cint), absolute, O_RDONLY | O_CLOEXEC | O_NOFOLLOW)
    fd >= 0 || throw(ArgumentError("could not securely open $absolute"))
    io = Base.fdio(fd, true)
    try
        value = read(io)
        length(value) <= ceiling || throw(ArgumentError("input byte ceiling exceeded"))
        return value
    finally
        close(io)
    end
end

_fd_identity(fd::Integer) = begin
    info = stat(fd)
    (UInt64(info.device), UInt64(info.inode))
end

function _component(name::AbstractString)
    value = String(name)
    !isempty(value) && value != "." && value != ".." && !occursin('/', value) &&
        !occursin('\0', value) ||
        throw(ArgumentError("invalid descriptor-relative path component"))
    return value
end

function _openat2_syscall(parent::Integer, value::String, flags::Integer, mode::Integer)
    how = Ref(OpenHow(
        UInt64(flags | O_CLOEXEC | O_NOFOLLOW),
        UInt64(mode),
        UInt64(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS),
    ))
    result = ccall(
        :syscall,
        Clong,
        (Clong, Cint, Cstring, Ref{OpenHow}, Csize_t),
        SYS_OPENAT2,
        parent,
        value,
        how,
        sizeof(OpenHow),
    )
    result >= 0 || throw(SystemError("openat2 $value", Libc.errno()))
    return Cint(result)
end

function _openat_fallback(parent::Integer, value::String, flags::Integer, mode::Integer)
    result = ccall(
        :syscall,
        Clong,
        (Clong, Cint, Cstring, Cint, Cuint),
        SYS_OPENAT,
        parent,
        value,
        flags | O_CLOEXEC | O_NOFOLLOW,
        mode,
    )
    result >= 0 || throw(SystemError("openat $value", Libc.errno()))
    return Cint(result)
end

function _secure_openat(
    parent::Integer,
    name::AbstractString,
    flags::Integer;
    mode=0,
    openat2_call=_openat2_syscall,
)
    value = _component(name)
    try
        return openat2_call(parent, value, flags, mode)
    catch error
        error isa SystemError && error.errnum == Libc.ENOSYS || rethrow(error)
        return _openat_fallback(parent, value, flags, mode)
    end
end

function _secure_dir(fd::Integer, label::String)
    info = try
        stat(fd)
    catch
        ccall(:close, Cint, (Cint,), fd)
        rethrow()
    end
    if !isdir(info)
        ccall(:close, Cint, (Cint,), fd)
        throw(ArgumentError("$label is not a directory"))
    end
    return SecureDir(Cint(fd), (UInt64(info.device), UInt64(info.inode)))
end

function _open_dir(parent::SecureDir, name::String)
    return _secure_dir(_secure_openat(parent.fd, name, O_RDONLY | O_DIRECTORY), name)
end

function _open_dir_optional(parent::SecureDir, name::String)
    try
        return _open_dir(parent, name)
    catch error
        error isa SystemError && error.errnum == Libc.ENOENT && return nothing
        rethrow(error)
    end
end

function _open_file(parent::SecureDir, name::String; optional=false)
    descriptor = try
        _secure_openat(parent.fd, name, O_RDONLY)
    catch error
        optional && error isa SystemError && error.errnum == Libc.ENOENT && return nothing
        rethrow(error)
    end
    info = try
        stat(descriptor)
    catch
        ccall(:close, Cint, (Cint,), descriptor)
        rethrow()
    end
    if !isfile(info)
        ccall(:close, Cint, (Cint,), descriptor)
        throw(ArgumentError("$name is not a regular file"))
    end
    return descriptor
end

function _read_file(parent::SecureDir, name::String; ceiling=typemax(Int), optional=false)
    descriptor = _open_file(parent, name; optional=optional)
    descriptor === nothing && return nothing
    io = Base.fdio(descriptor, true)
    try
        info = stat(descriptor)
        0 <= info.size <= ceiling || throw(ArgumentError("$name exceeds byte ceiling"))
        bytes = read(io, ceiling + (ceiling < typemax(Int)))
        length(bytes) <= ceiling || throw(ArgumentError("$name grew beyond byte ceiling"))
        return bytes
    finally
        close(io)
    end
end

function _file_identity(parent::SecureDir, name::String)
    descriptor = _open_file(parent, name)
    try
        return _fd_identity(descriptor)
    finally
        ccall(:close, Cint, (Cint,), descriptor)
    end
end

function _entries(directory::SecureDir)
    duplicate = ccall(:dup, Cint, (Cint,), directory.fd)
    duplicate >= 0 || throw(SystemError("dup directory", Libc.errno()))
    if ccall(:lseek, Int64, (Cint, Int64, Cint), duplicate, 0, 0) < 0
        error_number = Libc.errno()
        ccall(:close, Cint, (Cint,), duplicate)
        throw(SystemError("rewind directory", error_number))
    end
    stream = ccall(:fdopendir, Ptr{Cvoid}, (Cint,), duplicate)
    if stream == C_NULL
        ccall(:close, Cint, (Cint,), duplicate)
        throw(SystemError("fdopendir", Libc.errno()))
    end
    names = String[]
    try
        while true
            entry = ccall(:readdir, Ptr{Cvoid}, (Ptr{Cvoid},), stream)
            entry == C_NULL && break
            name = unsafe_string(Ptr{UInt8}(entry) + 19)
            name in (".", "..") || push!(names, name)
        end
    finally
        ccall(:closedir, Cint, (Ptr{Cvoid},), stream)
    end
    sort!(names)
    return names
end

function _same_entry(parent::SecureDir, name::String, expected::SecureDir)
    observed = _open_dir(parent, name)
    try
        return observed.identity == expected.identity
    finally
        close(observed)
    end
end

function fsync_fd(fd::Integer, label::String)
    FSYNC_COUNT[] += 1
    selected = tryparse(Int, get(ENV, "QMC_LTFIM_FAIL_FSYNC_AT", "0"))
    selected == FSYNC_COUNT[] && throw(ErrorException("injected fsync failure at $label"))
    ccall(:fsync, Cint, (Cint,), fd) == 0 || throw(SystemError("fsync $label", Libc.errno()))
    crash_selected = tryparse(Int, get(ENV, "QMC_LTFIM_CRASH_FSYNC_AT", "0"))
    crash_selected == FSYNC_COUNT[] && ccall(:_exit, Cvoid, (Cint,), 86)
    return nothing
end

function fsync_file(io::IO, label::String)
    flush(io)
    fsync_fd(Base.fd(io), label)
end

fsync_dir(directory::SecureDir, label::String) = fsync_fd(directory.fd, label)

function failpoint(name::String)
    if get(ENV, "QMC_LTFIM_TEST_PAUSE_AT", "") == name
        ready = get(ENV, "QMC_LTFIM_TEST_READY", "")
        release = get(ENV, "QMC_LTFIM_TEST_RELEASE", "")
        isempty(ready) && throw(ArgumentError("pausepoint ready path missing"))
        isempty(release) && throw(ArgumentError("pausepoint release path missing"))
        open(ready, "w") do io
            write(io, "ready\n")
        end
        deadline = time() + 90
        while !isfile(release)
            time() < deadline || throw(ErrorException("pausepoint release timeout"))
            sleep(0.01)
        end
    end
    get(ENV, "QMC_LTFIM_CRASHPOINT", "") == name &&
        ccall(:_exit, Cvoid, (Cint,), 86)
    if get(ENV, "QMC_LTFIM_FAILPOINT", "") == name
        occurrence = parse(Int, get(ENV, "QMC_LTFIM_FAILPOINT_OCCURRENCE", "1"))
        key = "QMC_LTFIM_INTERNAL_" * uppercase(replace(name, "-" => "_"))
        count = parse(Int, get(ENV, key, "0")) + 1
        ENV[key] = string(count)
        count == occurrence && throw(ErrorException("injected failure at $name"))
    end
end

function write_fsynced(directory::SecureDir, name::String, bytes::Vector{UInt8}, label::String)
    descriptor = _secure_openat(
        directory.fd, name, O_RDWR | O_CREAT | O_EXCL; mode=0o600
    )
    identity = try
        _fd_identity(descriptor)
    catch
        ccall(:close, Cint, (Cint,), descriptor)
        rethrow()
    end
    io = Base.fdio(descriptor, true)
    try
        write(io, bytes)
        fsync_file(io, label)
    finally
        close(io)
    end
    return identity
end

function rename_entry(
    source::SecureDir,
    source_name::String,
    destination::SecureDir,
    destination_name::String;
    noreplace=true,
)
    result = ccall(
        :syscall,
        Clong,
        (Clong, Cint, Cstring, Cint, Cstring, Cuint),
        SYS_RENAMEAT2,
        source.fd,
        _component(source_name),
        destination.fd,
        _component(destination_name),
        noreplace ? RENAME_NOREPLACE : 0,
    )
    result == 0 && return true
    noreplace && Libc.errno() == Libc.EEXIST && return false
    throw(SystemError("renameat2", Libc.errno()))
end

function link_entry(
    source::SecureDir,
    source_name::String,
    destination::SecureDir,
    destination_name::String,
)
    result = ccall(
        :syscall,
        Clong,
        (Clong, Cint, Cstring, Cint, Cstring, Cint),
        SYS_LINKAT,
        source.fd,
        _component(source_name),
        destination.fd,
        _component(destination_name),
        0,
    )
    result == 0 && return true
    Libc.errno() == Libc.EEXIST && return false
    throw(SystemError("linkat", Libc.errno()))
end

function _unlink(directory::SecureDir, name::String; directory_entry=false)
    result = ccall(
        :unlinkat,
        Cint,
        (Cint, Cstring, Cint),
        directory.fd,
        _component(name),
        directory_entry ? AT_REMOVEDIR : 0,
    )
    result == 0 || throw(SystemError("unlinkat $name", Libc.errno()))
end

function _atomic_immutable(
    directory::SecureDir,
    name::String,
    bytes::Vector{UInt8},
    label::String,
)
    temp = ".tmp-$name-$(getpid())-$(rand(UInt32))"
    write_fsynced(directory, temp, bytes, label)
    published = rename_entry(directory, temp, directory, name)
    if published
        failpoint("after-" * replace(label, " " => "-") * "-rename")
        fsync_dir(directory, "$label directory")
    else
        existing = _read_file(directory, name)
        existing == bytes || throw(ArgumentError("existing $label object differs"))
        _unlink(directory, temp)
        fsync_dir(directory, "$label loser cleanup")
    end
    return published
end

function _ensure_anchor_pin(
    anchors::SecureDir,
    anchor_sha::String;
    create::Bool,
)
    anchor_name = "$anchor_sha.json"
    pin_name = "$anchor_sha.pin"
    pin_descriptor = _open_file(anchors, pin_name; optional=true)
    if pin_descriptor === nothing
        create || throw(ArgumentError("canonical run lock anchor inode pin is missing"))
        if link_entry(anchors, anchor_name, anchors, pin_name)
            fsync_dir(anchors, "run lock anchor inode pin directory")
        end
    else
        ccall(:close, Cint, (Cint,), pin_descriptor) == 0 ||
            throw(SystemError("close run lock anchor inode pin", Libc.errno()))
    end
    _entries(anchors) == [anchor_name, pin_name] ||
        throw(ArgumentError("canonical run lock anchor object set mismatch"))
    anchor_identity = _file_identity(anchors, anchor_name)
    pin_identity = _file_identity(anchors, pin_name)
    anchor_identity == pin_identity ||
        throw(ArgumentError("canonical run lock anchor inode pin identity mismatch"))
    _read_file(anchors, pin_name) == _read_file(anchors, anchor_name) ||
        throw(ArgumentError("canonical run lock anchor inode pin content mismatch"))
    return anchor_identity
end

function _create_dir(parent::SecureDir, name::String; exclusive=false)
    result = ccall(:mkdirat, Cint, (Cint, Cstring, Cuint), parent.fd, _component(name), 0o700)
    if result != 0
        (!exclusive && Libc.errno() == Libc.EEXIST) || throw(SystemError("mkdirat $name", Libc.errno()))
    end
    directory = _open_dir(parent, name)
    try
        if result == 0
            fsync_dir(directory, "new directory $name")
            fsync_dir(parent, "new directory parent $name")
        end
        return directory
    catch
        close(directory)
        rethrow()
    end
end

function _open_or_create_output(path::String)
    absolute = abspath(path)
    components = [part for part in splitpath(absolute) if part != "/"]
    isempty(components) && throw(ArgumentError("output may not be filesystem root"))
    parent = _secure_dir(ccall(:open, Cint, (Cstring, Cint), "/", O_RDONLY | O_DIRECTORY | O_CLOEXEC), "root")
    links = AnchorLink[]
    try
        for (index, component) in enumerate(components)
            child = if index == length(components)
                existing = _open_dir_optional(parent, component)
                existing === nothing ? _create_dir(parent, component) : existing
            else
                _open_dir(parent, component)
            end
            push!(links, AnchorLink(parent, child, component))
            parent = child
        end
        return absolute, AnchoredDir(parent, links)
    catch
        close(AnchoredDir(parent, links))
        rethrow()
    end
end

function _verify_anchored(anchored::AnchoredDir)
    for link in anchored.links
        _same_entry(link.parent, link.name, link.child) ||
            throw(ArgumentError("output path ancestor $(link.name) was replaced"))
    end
    return nothing
end

function _archive_entry_raw(
    anchored::AnchoredDir,
    source::SecureDir,
    name::String,
    reason::String,
    source_visible_name::Union{Nothing,String}=nothing,
)
    _verify_anchored(anchored)
    archive = _create_dir(anchored.directory, "archive")
    try
        destination = "$name.$reason.$(time_ns())-$(getpid())"
        failpoint("before-archive-rename")
        _verify_anchored(anchored)
        source_visible_name === nothing ||
            (_same_entry(anchored.directory, source_visible_name, source) ||
             throw(ArgumentError("$source_visible_name directory was replaced")))
        _same_entry(anchored.directory, "archive", archive) ||
            throw(ArgumentError("archive directory was replaced"))
        rename_entry(source, name, archive, destination) ||
            throw(ArgumentError("archive destination unexpectedly exists"))
        _same_entry(anchored.directory, "archive", archive) ||
            throw(ArgumentError("archive directory was replaced after rename"))
        fsync_dir(archive, "archive after $reason")
        fsync_dir(source, "source directory after $reason archive")
        return destination
    finally
        close(archive)
    end
end

function _archive_entry(
    lock::RunLock,
    source::SecureDir,
    source_name::String,
    name::String,
    reason::String,
)
    _verify_visible_directory(lock, source_name, source, source_name)
    return _archive_entry_raw(
        lock.anchored, source, name, reason, source_name
    )
end

function verify_lock(lock::RunLock)
    _verify_anchored(lock.anchored)
    _same_entry(lock.anchored.directory, ".qmc-ltfim-lock-state", lock.state_dir) ||
        throw(ArgumentError("run lock state identity changed"))
    lock_file = _open_file(lock.state_dir, ".qmc-ltfim.lock")
    try
        _fd_identity(lock_file) == lock.lock_identity ||
            throw(ArgumentError("run lock file identity changed"))
    finally
        ccall(:close, Cint, (Cint,), lock_file)
    end
    _read_file(lock.anchored.directory, "run-lock-anchor.json") == lock.selection_bytes ||
        throw(ArgumentError("run lock anchor selection changed"))
    _file_identity(lock.anchored.directory, "run-lock-anchor.json") ==
        lock.selection_identity ||
        throw(ArgumentError("run lock anchor selection identity changed"))
    _same_entry(lock.anchored.directory, "run-lock-anchors", lock.anchors_dir) ||
        throw(ArgumentError("run lock anchors directory changed"))
    _read_file(lock.anchors_dir, "$(lock.anchor_sha256).json") == lock.anchor_bytes ||
        throw(ArgumentError("run lock anchor changed"))
    _file_identity(lock.anchors_dir, "$(lock.anchor_sha256).json") ==
        lock.anchor_identity ||
        throw(ArgumentError("run lock anchor identity changed"))
    _read_file(lock.anchors_dir, "$(lock.anchor_sha256).pin") == lock.anchor_bytes ||
        throw(ArgumentError("run lock anchor inode pin changed"))
    _file_identity(lock.anchors_dir, "$(lock.anchor_sha256).pin") ==
        lock.anchor_identity ||
        throw(ArgumentError("run lock anchor inode pin identity changed"))
    sha256_bytes(lock.anchor_bytes) == lock.anchor_sha256 ||
        throw(ArgumentError("run lock anchor self-hash mismatch"))
end

function acquire_lock(output_path::String, request_hash::String)
    output, anchored = _open_or_create_output(output_path)
    try
        return _acquire_lock(output, anchored, request_hash)
    catch
        close(anchored)
        rethrow()
    end
end

function _acquire_lock(output::String, anchored::AnchoredDir, request_hash::String)
    state_dir = nothing
    anchors_dir = nothing
    fd = Cint(-1)
    locked = false
    try
    _verify_anchored(anchored)
    state_dir = _create_dir(anchored.directory, ".qmc-ltfim-lock-state")
    fd = _secure_openat(state_dir.fd, ".qmc-ltfim.lock", O_RDWR | O_CREAT; mode=0o600)
    fd >= 0 || throw(SystemError("open run lock", Libc.errno()))
    ccall(:flock, Cint, (Cint, Cint), fd, LOCK_EX) == 0 ||
        throw(SystemError("flock run lock", Libc.errno()))
    locked = true
    _verify_anchored(anchored)
    state_identity = state_dir.identity
    lock_identity = _fd_identity(fd)
    anchors_dir = _create_dir(anchored.directory, "run-lock-anchors")
    for name in _entries(anchors_dir)
        startswith(name, ".tmp-") || continue
        _archive_entry_raw(
            anchored,
            anchors_dir,
            name,
            "unpublished-anchor",
            "run-lock-anchors",
        )
    end
    selection_bytes = _read_file(
        anchored.directory, "run-lock-anchor.json"; optional=true
    )
    if selection_bytes !== nothing
        selection = _plain(JSON3.read(String(copy(selection_bytes))))
        _require_keys(
            selection,
            Set(["schema_version", "anchor_sha256", "path"]),
            "run lock anchor selection",
        )
        selection["schema_version"] == "qmc-ltfim-run-lock-anchor-selection-v1" ||
            throw(ArgumentError("run lock anchor selection schema mismatch"))
        anchor_sha = selection["anchor_sha256"]
        anchor_sha isa String && occursin(HEX64, anchor_sha) ||
            throw(ArgumentError("run lock anchor selection hash invalid"))
        selection["path"] == "run-lock-anchors/$anchor_sha.json" ||
            throw(ArgumentError("run lock anchor selection path mismatch"))
        canonical_bytes(selection) == selection_bytes ||
            throw(ArgumentError("run lock anchor selection is not canonical"))
        anchor_names = sort!([
            name for name in _entries(anchors_dir)
            if occursin(r"^[0-9a-f]{64}\.json$", name)
        ])
        anchor_names == ["$anchor_sha.json"] ||
            throw(ArgumentError("distinct or missing canonical run-lock anchor objects"))
        anchor_identity = _ensure_anchor_pin(anchors_dir, anchor_sha; create=false)
        anchor_bytes = _read_file(anchors_dir, "$anchor_sha.json")
        sha256_bytes(anchor_bytes) == anchor_sha ||
            throw(ArgumentError("run lock anchor hash mismatch"))
        anchor = _plain(JSON3.read(String(copy(anchor_bytes))))
        _require_keys(
            anchor,
            Set([
                "schema_version", "request_sha256", "output_namespace",
                "state_device", "state_inode", "lock_device", "lock_inode",
            ]),
            "run lock anchor",
        )
        canonical_bytes(anchor) == anchor_bytes ||
            throw(ArgumentError("run lock anchor is not canonical"))
        anchor["schema_version"] == "qmc-ltfim-run-lock-anchor-v1" ||
            throw(ArgumentError("run lock anchor schema mismatch"))
        anchor["request_sha256"] == request_hash ||
            throw(ArgumentError("stale request run-lock anchor"))
        anchor["output_namespace"] == output ||
            throw(ArgumentError("run-lock output namespace mismatch"))
        Tuple(UInt64(anchor[k]) for k in ("state_device", "state_inode")) == state_identity ||
            throw(ArgumentError("run lock state anchor mismatch"))
        Tuple(UInt64(anchor[k]) for k in ("lock_device", "lock_inode")) == lock_identity ||
            throw(ArgumentError("run lock file anchor mismatch"))
        lock = RunLock(
            output, anchored, state_dir, anchors_dir, fd, state_identity, lock_identity,
            _file_identity(anchored.directory, "run-lock-anchor.json"),
            anchor_identity,
            selection_bytes, anchor_bytes, anchor_sha,
        )
        verify_lock(lock)
        return lock
    end
    existing_anchors = sort!([
        name for name in _entries(anchors_dir)
        if occursin(r"^[0-9a-f]{64}\.json$", name)
    ])
    if !isempty(existing_anchors)
        length(existing_anchors) == 1 ||
            throw(ArgumentError("multiple unselected run-lock anchor objects exist"))
        anchor_bytes = _read_file(anchors_dir, only(existing_anchors))
        anchor_sha = sha256_bytes(anchor_bytes)
        only(existing_anchors) == "$anchor_sha.json" ||
            throw(ArgumentError("unselected run-lock anchor filename mismatch"))
        anchor = try
            _plain(JSON3.read(String(copy(anchor_bytes))))
        catch error
            throw(ArgumentError("invalid unselected run-lock anchor: $(sprint(showerror, error))"))
        end
        _require_keys(
            anchor,
            Set([
                "schema_version", "request_sha256", "output_namespace",
                "state_device", "state_inode", "lock_device", "lock_inode",
            ]),
            "unselected run lock anchor",
        )
        canonical_bytes(anchor) == anchor_bytes ||
            throw(ArgumentError("unselected run-lock anchor is not canonical"))
        anchor["schema_version"] == "qmc-ltfim-run-lock-anchor-v1" ||
            throw(ArgumentError("unselected run-lock anchor schema mismatch"))
        anchor["request_sha256"] == request_hash ||
            throw(ArgumentError("stale unselected run-lock anchor"))
        anchor["output_namespace"] == output ||
            throw(ArgumentError("unselected run-lock output namespace mismatch"))
        Tuple(UInt64(anchor[k]) for k in ("state_device", "state_inode")) == state_identity ||
            throw(ArgumentError("unselected run-lock state anchor mismatch"))
        Tuple(UInt64(anchor[k]) for k in ("lock_device", "lock_inode")) == lock_identity ||
            throw(ArgumentError("unselected run-lock file anchor mismatch"))
        anchor_identity = _ensure_anchor_pin(anchors_dir, anchor_sha; create=true)
        selection = Dict(
            "schema_version" => "qmc-ltfim-run-lock-anchor-selection-v1",
            "anchor_sha256" => anchor_sha,
            "path" => "run-lock-anchors/$anchor_sha.json",
        )
        selection_bytes = canonical_bytes(selection)
        _atomic_immutable(
            anchored.directory,
            "run-lock-anchor.json",
            selection_bytes,
            "anchor-selection",
        )
        lock = RunLock(
            output, anchored, state_dir, anchors_dir, fd, state_identity, lock_identity,
            _file_identity(anchored.directory, "run-lock-anchor.json"),
            anchor_identity,
            selection_bytes, anchor_bytes, anchor_sha,
        )
        verify_lock(lock)
        return lock
    end
    isempty(_entries(anchors_dir)) ||
        throw(ArgumentError("invalid unselected run-lock anchor objects exist"))
    anchor = Dict(
        "schema_version" => "qmc-ltfim-run-lock-anchor-v1",
        "request_sha256" => request_hash,
        "output_namespace" => output,
        "state_device" => state_identity[1],
        "state_inode" => state_identity[2],
        "lock_device" => lock_identity[1],
        "lock_inode" => lock_identity[2],
    )
    anchor_bytes = canonical_bytes(anchor)
    anchor_sha = sha256_bytes(anchor_bytes)
    _atomic_immutable(anchors_dir, "$anchor_sha.json", anchor_bytes, "anchor")
    anchor_identity = _ensure_anchor_pin(anchors_dir, anchor_sha; create=true)
    selection = Dict(
        "schema_version" => "qmc-ltfim-run-lock-anchor-selection-v1",
        "anchor_sha256" => anchor_sha,
        "path" => "run-lock-anchors/$anchor_sha.json",
    )
    selection_bytes = canonical_bytes(selection)
    _atomic_immutable(
        anchored.directory,
        "run-lock-anchor.json",
        selection_bytes,
        "anchor-selection",
    )
    lock = RunLock(
        output, anchored, state_dir, anchors_dir, fd, state_identity, lock_identity,
        _file_identity(anchored.directory, "run-lock-anchor.json"),
        anchor_identity,
        selection_bytes, anchor_bytes, anchor_sha,
    )
    verify_lock(lock)
    return lock
    catch
        if fd >= 0
            locked && ccall(:flock, Cint, (Cint, Cint), fd, 8)
            ccall(:close, Cint, (Cint,), fd)
        end
        anchors_dir === nothing || close(anchors_dir)
        state_dir === nothing || close(state_dir)
        rethrow()
    end
end

function release_lock(lock::RunLock)
    first_error = nothing
    if lock.fd >= 0
        descriptor = lock.fd
        lock.fd = -1
        try
            ccall(:flock, Cint, (Cint, Cint), descriptor, 8) == 0 ||
                throw(SystemError("unlock run lock", Libc.errno()))
        catch error
            first_error = error
        end
        try
            ccall(:close, Cint, (Cint,), descriptor) == 0 ||
                throw(SystemError("close run lock", Libc.errno()))
        catch error
            first_error === nothing && (first_error = error)
        end
    end
    for directory in (lock.anchors_dir, lock.state_dir)
        try
            close(directory)
        catch error
            first_error === nothing && (first_error = error)
        end
    end
    try
        close(lock.anchored)
    catch error
        first_error === nothing && (first_error = error)
    end
    first_error === nothing || throw(first_error)
    return nothing
end

function validate_pointer(pointer::AbstractDict)
    pointer = _plain(pointer)
    _require_keys(
        pointer,
        Set(["schema_version", "anchor_sha256", "generation_sha256", "path"]),
        "current pointer",
    )
    pointer["schema_version"] == "qmc-current-generation-v2" ||
        throw(ArgumentError("current pointer rejects v1 or unknown schema"))
    for field in ("anchor_sha256", "generation_sha256")
        pointer[field] isa String && occursin(HEX64, pointer[field]) ||
            throw(ArgumentError("current pointer $field invalid"))
    end
    pointer["path"] == "generations/$(pointer["generation_sha256"])" ||
        throw(ArgumentError("current pointer path mismatch"))
    return pointer
end

function _validate_bin_record(record, expected_index=nothing)
    record = _plain(record)
    required = Set([
        "schema_version", "adapter", "bin_index", "sample_count", "energy_sum",
        "serial_measurement_stride_samples", "serial_observations",
        "energy_sum_squares", "transverse_magnetization_sum",
        "transverse_magnetization_sum_squares", "m2_sum", "m2_sum_squares",
        "m4_sum", "m4_sum_squares", "operator_count_sum",
        "time_slice_count_sum", "cluster_attempt_count", "cluster_accepted_count",
        "cluster_count_sum", "cluster_size_sum", "cluster_size_observation_count",
        "cluster_list_size_sum", "cluster_list_size_observation_count",
        "sweep_count", "rng", "seed_derivation",
        "seed_namespace",
    ])
    _require_keys(record, required, "QMC_LTFIM bin")
    record["schema_version"] == "qmc-ltfim-bin-v1" ||
        throw(ArgumentError("bin schema mismatch"))
    record["adapter"] == "QMC_LTFIM" || throw(ArgumentError("bin adapter mismatch"))
    expected_index === nothing || record["bin_index"] == expected_index ||
        throw(ArgumentError("bin index mismatch"))
    for field in (
        "sample_count", "operator_count_sum", "time_slice_count_sum",
        "cluster_attempt_count", "cluster_accepted_count", "cluster_count_sum",
        "cluster_size_observation_count", "cluster_list_size_sum",
        "cluster_list_size_observation_count", "sweep_count",
    )
        _require_int(record[field], "bin $field"; minimum=0)
    end
    for field in (
        "energy_sum", "energy_sum_squares", "transverse_magnetization_sum",
        "transverse_magnetization_sum_squares", "m2_sum", "m2_sum_squares",
        "m4_sum", "m4_sum_squares", "cluster_size_sum",
    )
        _require_number(record[field], "bin $field")
    end
    record["sample_count"] > 0 || throw(ArgumentError("bin sample count must be positive"))
    record["serial_measurement_stride_samples"] == 1 ||
        throw(ArgumentError("bin serial measurement stride must be one"))
    serial = record["serial_observations"]
    serial isa AbstractDict ||
        throw(ArgumentError("bin serial observations must be an object"))
    _require_keys(
        serial,
        Set(["energy", "transverse_magnetization", "m2", "m4"]),
        "bin serial observations",
    )
    for field in ("energy", "transverse_magnetization", "m2", "m4")
        values = serial[field]
        values isa AbstractVector && length(values) == record["sample_count"] ||
            throw(ArgumentError("bin serial observation count mismatch"))
        all(value -> value isa Real && isfinite(value), values) ||
            throw(ArgumentError("bin serial observations must be finite"))
    end
    record["cluster_accepted_count"] <= record["cluster_attempt_count"] ||
        throw(ArgumentError("accepted clusters exceed attempted clusters"))
    record["cluster_count_sum"] == record["cluster_attempt_count"] ||
        throw(ArgumentError("cluster attempt/count domain mismatch"))
    record["cluster_size_observation_count"] == record["cluster_count_sum"] ||
        throw(ArgumentError("cluster size/count domain mismatch"))
    record["cluster_list_size_observation_count"] == record["sweep_count"] ||
        throw(ArgumentError("cluster list/sweep domain mismatch"))
    return record
end

function _validate_manifest(
    lock::RunLock,
    generations::SecureDir,
    bins::SecureDir,
    digest,
    bindings,
    request,
)
    verify_lock(lock)
    occursin(HEX64, digest) || throw(ArgumentError("generation hash invalid"))
    generation = _open_dir(generations, digest)
    bytes = try
        _entries(generation) == ["manifest.json"] ||
            throw(ArgumentError("generation directory shape is not exact"))
        _read_file(generation, "manifest.json")
    finally
        close(generation)
    end
    sha256_bytes(bytes) == digest || throw(ArgumentError("generation manifest hash mismatch"))
    manifest = _plain(JSON3.read(String(copy(bytes))))
    canonical_bytes(manifest) == bytes ||
        throw(ArgumentError("generation manifest is not canonical"))
    required = Set([
        "schema_version", "anchor_sha256", "request_sha256", "adapter", "source_hash",
        "build_hash", "seed", "completed_bin_count", "bin_object_hashes",
        "previous_generation_sha256", "replay_update_count",
    ])
    _require_keys(manifest, required, "checkpoint generation")
    manifest["schema_version"] == "qmc-checkpoint-generation-v2" ||
        throw(ArgumentError("checkpoint generation rejects v1"))
    for (key, value) in bindings
        manifest[key] == value || throw(ArgumentError("stale $key generation binding"))
    end
    count = _require_int(manifest["completed_bin_count"], "completed bin count"; minimum=1)
    replay = _require_int(manifest["replay_update_count"], "replay update count"; minimum=0)
    total_bins = request["retained_samples"] ÷ request["bin_length"]
    count <= total_bins || throw(ArgumentError("generation completed bin count exceeds request"))
    checkpoint_counts = collect(
        request["checkpoint_bins"]:request["checkpoint_bins"]:total_bins
    )
    isempty(checkpoint_counts) || last(checkpoint_counts) == total_bins ||
        push!(checkpoint_counts, total_bins)
    isempty(checkpoint_counts) && push!(checkpoint_counts, total_bins)
    count in checkpoint_counts ||
        throw(ArgumentError("generation completed bin checkpoint interval mismatch"))
    replay == request["thermalization_sweeps"] + count * request["bin_length"] * request["thinning"] ||
        throw(ArgumentError("generation replay update count mismatch"))
    previous = manifest["previous_generation_sha256"]
    previous === nothing ||
        (previous isa String && occursin(HEX64, previous)) ||
        throw(ArgumentError("previous generation hash invalid"))
    hashes = manifest["bin_object_hashes"]
    hashes isa AbstractVector && length(hashes) == count ||
        throw(ArgumentError("generation bin hash count mismatch"))
    for (index, hash) in enumerate(hashes)
        hash isa String && occursin(HEX64, hash) || throw(ArgumentError("bin object hash invalid"))
        bin_bytes = _read_file(bins, "$hash.ndjson")
        sha256_bytes(bin_bytes) == hash || throw(ArgumentError("corrupted bin object"))
        record = _plain(JSON3.read(String(copy(bin_bytes))))
        canonical_bytes(record) == bin_bytes || throw(ArgumentError("bin object is not canonical"))
        _validate_bin_record(record, index - 1)
        record["sample_count"] == request["bin_length"] ||
            throw(ArgumentError("bin sample count/request mismatch"))
        record["sweep_count"] == record["sample_count"] * request["thinning"] ||
            throw(ArgumentError("bin sweep/request thinning mismatch"))
    end
    return manifest
end

function _verify_visible_directory(
    lock::RunLock,
    name::String,
    directory::SecureDir,
    label::String,
)
    verify_lock(lock)
    _same_entry(lock.anchored.directory, name, directory) ||
        throw(ArgumentError("$label directory was replaced"))
    return nothing
end

function _record_publication_failure(
    lock::RunLock,
    generation_hash::String,
    pointer_bytes::Vector{UInt8},
    error,
)
    verify_lock(lock)
    diagnostics = _create_dir(lock.anchored.directory, "publication-failures")
    try
        _verify_visible_directory(
            lock,
            "publication-failures",
            diagnostics,
            "publication failures",
        )
        record = Dict(
            "schema_version" => "qmc-ltfim-publication-failure-v1",
            "generation_sha256" => generation_hash,
            "pointer_sha256" => sha256_bytes(pointer_bytes),
            "reason" => sprint(showerror, error),
        )
        bytes = canonical_bytes(record)
        digest = sha256_bytes(bytes)
        _atomic_immutable(
            diagnostics,
            "$digest.json",
            bytes,
            "publication failure diagnostic",
        )
        _verify_visible_directory(
            lock,
            "publication-failures",
            diagnostics,
            "publication failures",
        )
        return digest
    finally
        close(diagnostics)
    end
end

function _publish_pointer(
    lock::RunLock,
    generation_hash::String,
    generations::SecureDir,
    bins::SecureDir,
    bindings,
    request,
)
    verify_lock(lock)
    _verify_visible_directory(lock, "generations", generations, "generations")
    _verify_visible_directory(lock, "bins", bins, "bins")
    selected_generation = _open_dir(generations, generation_hash)
    pointer = Dict(
        "schema_version" => "qmc-current-generation-v2",
        "anchor_sha256" => lock.anchor_sha256,
        "generation_sha256" => generation_hash,
        "path" => "generations/$generation_hash",
    )
    bytes = canonical_bytes(pointer)
    output = lock.anchored.directory
    temp = ".tmp-current-generation-$(getpid())-$(rand(UInt32))"
    temp_identity = nothing
    published = false
    try
        temp_identity = write_fsynced(output, temp, bytes, "current pointer")
        _same_entry(generations, generation_hash, selected_generation) ||
            throw(ArgumentError("selected generation changed before pointer publication"))
        _validate_manifest(
            lock,
            generations,
            bins,
            generation_hash,
            bindings,
            request,
        )
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        failpoint("before-pointer-replace")
        verify_lock(lock)
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        _same_entry(generations, generation_hash, selected_generation) ||
            throw(ArgumentError("selected generation changed before pointer rename"))
        _file_identity(output, temp) == temp_identity ||
            throw(ArgumentError("current pointer staging identity changed"))
        _read_file(output, temp) == bytes ||
            throw(ArgumentError("current pointer staging bytes changed"))
        rename_entry(output, temp, output, "current-generation.json"; noreplace=false)
        published = true
        fsync_dir(output, "run after pointer replace")
        failpoint("after-pointer-replace-before-validation")

        # The pointer is already visible. Revalidate its complete referential
        # closure before this invocation may report success.
        verify_lock(lock)
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        _same_entry(generations, generation_hash, selected_generation) ||
            throw(ArgumentError("selected generation changed after pointer rename"))
        _validate_manifest(
            lock,
            generations,
            bins,
            generation_hash,
            bindings,
            request,
        )
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        _same_entry(generations, generation_hash, selected_generation) ||
            throw(ArgumentError("selected generation changed after validation"))
        _file_identity(output, "current-generation.json") == temp_identity ||
            throw(ArgumentError("published current pointer identity changed"))
        published_bytes = _read_file(output, "current-generation.json")
        published_bytes == bytes ||
            throw(ArgumentError("published current pointer bytes changed"))
        published_pointer = validate_pointer(
            _plain(JSON3.read(String(copy(published_bytes))))
        )
        canonical_bytes(published_pointer) == published_bytes ||
            throw(ArgumentError("published current pointer is not canonical"))
        published_pointer == pointer ||
            throw(ArgumentError("published current pointer semantics changed"))
        verify_lock(lock)
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        return nothing
    catch error
        if !published
            try
                _unlink(output, temp)
                fsync_dir(output, "current pointer staging cleanup")
            catch
            end
        else
            try
                _record_publication_failure(
                    lock, generation_hash, bytes, error
                )
            catch diagnostic_error
                throw(ErrorException(
                    "post-publication validation failed: " *
                    sprint(showerror, error) *
                    "; durable diagnostic failed: " *
                    sprint(showerror, diagnostic_error),
                ))
            end
        end
        rethrow(error)
    finally
        close(selected_generation)
    end
end

function _recover_chain(lock::RunLock, bindings, request)
    verify_lock(lock)
    generations = nothing
    bins = nothing
    archive = nothing
    try
        generations = _create_dir(lock.anchored.directory, "generations")
        bins = _create_dir(lock.anchored.directory, "bins")
        archive = _open_dir_optional(lock.anchored.directory, "archive")
        for name in _entries(lock.anchored.directory)
            occursin(r"^\.tmp-current-generation-[0-9]+-[0-9]+$", name) || continue
            _archive_entry_raw(lock.anchored, lock.anchored.directory, name, "unpublished-pointer")
        end

        generation_names = String[]
        unexpected_entries = String[]
        for name in _entries(generations)
            if occursin(r"^\.tmp-generation-[0-9]+-[0-9]+$", name)
                _archive_entry(
                    lock,
                    generations,
                    "generations",
                    name,
                    "unpublished-generation",
                )
            elseif occursin(HEX64, name)
                push!(generation_names, name)
            else
                push!(unexpected_entries, name)
                _archive_entry(
                    lock,
                    generations,
                    "generations",
                    name,
                    "unexpected-generation-entry",
                )
            end
        end
        isempty(unexpected_entries) ||
            throw(ArgumentError(
                "unexpected generations directory entries archived: $unexpected_entries"
            ))

        pointer = nothing
        pbytes = _read_file(lock.anchored.directory, "current-generation.json"; optional=true)
        if pbytes !== nothing
            pointer = validate_pointer(_plain(JSON3.read(String(copy(pbytes)))))
            canonical_bytes(pointer) == pbytes ||
                throw(ArgumentError("current pointer is not canonical"))
            pointer["anchor_sha256"] == lock.anchor_sha256 ||
                throw(ArgumentError("current pointer anchor mismatch"))
        end
        manifests = Dict{String,Any}()
        invalid_generations = Pair{String,String}[]
        for digest in sort!(generation_names)
            try
                manifests[digest] = _validate_manifest(
                    lock, generations, bins, digest, bindings, request
                )
            catch error
                push!(invalid_generations, digest => sprint(showerror, error))
                _archive_entry(
                    lock,
                    generations,
                    "generations",
                    digest,
                    "invalid-generation",
                )
            end
        end
        isempty(invalid_generations) ||
            throw(ArgumentError("malformed checkpoint generation archived: $(invalid_generations)"))

        failpoint("after-recovery-scan")
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        if archive !== nothing
            _verify_visible_directory(lock, "archive", archive, "archive")
        end

        current = nothing
        if pointer !== nothing
            current = pointer["generation_sha256"]
            haskey(manifests, current) || throw(ArgumentError("current pointer generation missing"))
        else
            genesis = sort!([
                digest for (digest, manifest) in manifests
                if manifest["previous_generation_sha256"] === nothing
            ])
            length(genesis) <= 1 ||
                throw(ArgumentError("multiple distinct valid genesis generation hashes"))
            if length(genesis) == 1
                current = only(genesis)
                _publish_pointer(
                    lock,
                    current,
                    generations,
                    bins,
                    bindings,
                    request,
                )
            end
        end
        if current !== nothing
            while true
                descendants = sort!([
                    digest for (digest, manifest) in manifests
                    if manifest["previous_generation_sha256"] == current
                ])
                isempty(descendants) && break
                length(descendants) == 1 ||
                    throw(ArgumentError("conflicting checkpoint descendants"))
                current = only(descendants)
                _publish_pointer(
                    lock,
                    current,
                    generations,
                    bins,
                    bindings,
                    request,
                )
            end
        end
        chain = Tuple{String,Any}[]
        cursor = current
        while cursor !== nothing
            haskey(manifests, cursor) || throw(ArgumentError("checkpoint ancestry gap"))
            push!(chain, (cursor, manifests[cursor]))
            cursor = manifests[cursor]["previous_generation_sha256"]
        end
        reverse!(chain)
        for (index, (_, manifest)) in enumerate(chain)
            if index == 1
                manifest["previous_generation_sha256"] === nothing ||
                    throw(ArgumentError("non-genesis chain root"))
            else
                manifest["previous_generation_sha256"] == chain[index - 1][1] ||
                    throw(ArgumentError("checkpoint ancestry gap"))
                previous_hashes = chain[index - 1][2]["bin_object_hashes"]
                manifest["bin_object_hashes"][1:length(previous_hashes)] == previous_hashes ||
                    throw(ArgumentError("checkpoint bin prefix changed"))
            end
        end
        Set(first.(chain)) == Set(keys(manifests)) ||
            throw(ArgumentError("unlinked checkpoint generation conflict"))
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        return chain
    finally
        archive === nothing || close(archive)
        bins === nothing || close(bins)
        generations === nothing || close(generations)
    end
end

function _audit_bin_orphans(lock::RunLock, retained_hashes::Vector{String})
    keep = Set(retained_hashes)
    bins = _open_dir(lock.anchored.directory, "bins")
    try
        for name in _entries(bins)
            expected = match(r"^([0-9a-f]{64})\.ndjson$", name)
            expected !== nothing && expected.captures[1] in keep && continue
            reason = expected === nothing ? "invalid-bin-orphan" : "future-orphan"
            _archive_entry(lock, bins, "bins", name, reason)
        end
        return nothing
    finally
        close(bins)
    end
end

function _publish_bin(lock::RunLock, record)
    verify_lock(lock)
    _validate_bin_record(record)
    bytes = canonical_bytes(record)
    digest = sha256_bytes(bytes)
    bins = _open_dir(lock.anchored.directory, "bins")
    try
        failpoint("before-bin-rename")
        _verify_visible_directory(lock, "bins", bins, "bins")
        _atomic_immutable(bins, "$digest.ndjson", bytes, "bin")
        _verify_visible_directory(lock, "bins", bins, "bins")
        return digest, bytes
    finally
        close(bins)
    end
end

function _publish_generation(lock::RunLock, manifest, bindings, request)
    verify_lock(lock)
    bytes = canonical_bytes(manifest)
    digest = sha256_bytes(bytes)
    generations = nothing
    bins = nothing
    stage = nothing
    existing_generation = nothing
    try
        generations = _open_dir(lock.anchored.directory, "generations")
        bins = _open_dir(lock.anchored.directory, "bins")
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        stage_name = ".tmp-generation-$(getpid())-$(rand(UInt32))"
        stage = _create_dir(generations, stage_name; exclusive=true)
        _same_entry(generations, stage_name, stage) ||
            throw(ArgumentError("generation staging directory was replaced"))
        write_fsynced(stage, "manifest.json", bytes, "generation manifest")
        fsync_dir(stage, "staged generation")
        failpoint("before-generation-rename")
        _verify_visible_directory(lock, "generations", generations, "generations")
        _verify_visible_directory(lock, "bins", bins, "bins")
        _same_entry(generations, stage_name, stage) ||
            throw(ArgumentError("generation staging directory was replaced"))

        # Revalidate every referenced canonical bin while the retained bins
        # descriptor is still the output's visible bins directory.
        _verify_visible_directory(lock, "bins", bins, "bins")
        for (index, hash) in enumerate(manifest["bin_object_hashes"])
            bin_bytes = _read_file(bins, "$hash.ndjson")
            sha256_bytes(bin_bytes) == hash ||
                throw(ArgumentError("corrupted bin before publication"))
            bin_record = _plain(JSON3.read(String(copy(bin_bytes))))
            canonical_bytes(bin_record) == bin_bytes ||
                throw(ArgumentError("noncanonical bin before publication"))
            _validate_bin_record(bin_record, index - 1)
            bin_record["sample_count"] == request["bin_length"] ||
                throw(ArgumentError("bin sample count changed before publication"))
            bin_record["sweep_count"] ==
                bin_record["sample_count"] * request["thinning"] ||
                throw(ArgumentError("bin sweep count changed before publication"))
        end
        _verify_visible_directory(lock, "bins", bins, "bins")
        _verify_visible_directory(lock, "generations", generations, "generations")

        published = rename_entry(generations, stage_name, generations, digest)
        if published
            _same_entry(generations, digest, stage) ||
                throw(ArgumentError("published generation directory changed"))
            _verify_visible_directory(lock, "generations", generations, "generations")
            failpoint("after-generation-rename")
            _verify_visible_directory(lock, "generations", generations, "generations")
            fsync_dir(generations, "generations after rename")
        else
            existing_generation = _open_dir(generations, digest)
            existing = _read_file(existing_generation, "manifest.json")
            existing == bytes || throw(ArgumentError("same-hash generation differs"))
            _validate_manifest(lock, generations, bins, digest, bindings, request)
            _archive_entry(
                lock,
                generations,
                "generations",
                stage_name,
                "identical-generation-loser",
            )
        end
        _verify_visible_directory(lock, "bins", bins, "bins")
        _verify_visible_directory(lock, "generations", generations, "generations")
        _publish_pointer(
            lock,
            digest,
            generations,
            bins,
            bindings,
            request,
        )
        return digest
    finally
        existing_generation === nothing || close(existing_generation)
        stage === nothing || close(stage)
        bins === nothing || close(bins)
        generations === nothing || close(generations)
    end
end

function _stats_total(stat)
    count = OnlineStats.nobs(stat)
    return count == 0 ? 0.0 : OnlineStats.mean(stat) * count
end

function _make_bin(index, samples, diagnostics_before, diagnostics_after, cluster_list_sum)
    count = length(samples)
    field(name) = [sample[name] for sample in samples]
    stats = diagnostics_after
    before = diagnostics_before
    cluster_count_sum = round(Int, _stats_total(stats.cluster_count) - _stats_total(before.cluster_count))
    accepted_sum = sum(sample["accepted_clusters"] for sample in samples)
    cluster_size_count = OnlineStats.nobs(stats.cluster_sizes) - OnlineStats.nobs(before.cluster_sizes)
    cluster_size_sum = _stats_total(stats.cluster_sizes) - _stats_total(before.cluster_sizes)
    sweeps = sum(sample["sweeps"] for sample in samples)
    return Dict(
        "schema_version" => "qmc-ltfim-bin-v1",
        "adapter" => "QMC_LTFIM",
        "bin_index" => index,
        "sample_count" => count,
        "serial_measurement_stride_samples" => 1,
        "serial_observations" => Dict(
            "energy" => field("energy"),
            "transverse_magnetization" => field("mx"),
            "m2" => field("m2"),
            "m4" => field("m4"),
        ),
        "energy_sum" => sum(field("energy")),
        "energy_sum_squares" => sum(abs2, field("energy")),
        "transverse_magnetization_sum" => sum(field("mx")),
        "transverse_magnetization_sum_squares" => sum(abs2, field("mx")),
        "m2_sum" => sum(field("m2")),
        "m2_sum_squares" => sum(abs2, field("m2")),
        "m4_sum" => sum(field("m4")),
        "m4_sum_squares" => sum(abs2, field("m4")),
        "operator_count_sum" => sum(sample["num_ops"] for sample in samples),
        "time_slice_count_sum" => sum(sample["capacity"] for sample in samples),
        "cluster_attempt_count" => cluster_count_sum,
        "cluster_accepted_count" => accepted_sum,
        "cluster_count_sum" => cluster_count_sum,
        "cluster_size_sum" => cluster_size_sum,
        "cluster_size_observation_count" => cluster_size_count,
        "cluster_list_size_sum" => cluster_list_sum,
        "cluster_list_size_observation_count" => sweeps,
        "sweep_count" => sweeps,
        "rng" => RNG_NAME,
        "seed_derivation" => SEED_DERIVATION,
        "seed_namespace" => SEED_NAMESPACE,
    )
end

function _copy_runstats(stats)
    # RunStats is immutable but its OnlineStats members are mutable.
    return deepcopy(stats)
end

function parse_request(path::String)
    payload = _read_json(path)
    payload isa AbstractDict || throw(ArgumentError("request must be a JSON object"))
    _require_keys(payload, REQUEST_KEYS, "request")
    payload["schema_version"] == "qmc-request-v1" ||
        throw(ArgumentError("request schema mismatch"))
    payload["adapter"] == "QMC_LTFIM" ||
        throw(ArgumentError("adapter mismatch: QMC_LTFIM required"))
    for field in ("graph_sha256", "expected_source_hash", "expected_build_hash")
        payload[field] isa String && occursin(HEX64, payload[field]) ||
            throw(ArgumentError("request $field invalid"))
    end
    payload["graph_path"] isa String && !isempty(payload["graph_path"]) ||
        throw(ArgumentError("request graph_path invalid"))
    payload["beta"] = _require_number(payload["beta"], "beta"; positive=true)
    payload["coupling"] = _require_number(payload["coupling"], "coupling"; nonnegative=true)
    payload["field"] = _require_number(payload["field"], "field"; positive=true)
    payload["seed"] = _require_int(payload["seed"], "seed"; minimum=0)
    payload["thermalization_sweeps"] =
        _require_int(payload["thermalization_sweeps"], "thermalization_sweeps"; minimum=0)
    payload["retained_samples"] =
        _require_int(payload["retained_samples"], "retained_samples"; minimum=1)
    payload["thinning"] = _require_int(payload["thinning"], "thinning"; minimum=1)
    payload["serial_measurement_stride_samples"] = _require_int(
        payload["serial_measurement_stride_samples"],
        "serial_measurement_stride_samples";
        minimum=1,
    )
    payload["serial_measurement_stride_samples"] == 1 ||
        throw(ArgumentError("serial_measurement_stride_samples must be one"))
    payload["bin_length"] = _require_int(payload["bin_length"], "bin_length"; minimum=1)
    payload["checkpoint_bins"] =
        _require_int(payload["checkpoint_bins"], "checkpoint_bins"; minimum=1)
    payload["retained_samples"] % payload["bin_length"] == 0 ||
        throw(ArgumentError("retained_samples must be divisible by bin_length"))
    info = build_info()
    payload["expected_source_hash"] == info["source_hash"] ||
        throw(ArgumentError("source hash mismatch"))
    payload["expected_build_hash"] == info["build_hash"] ||
        throw(ArgumentError("build hash mismatch"))
    return payload
end

function run_request(request_path::String, output_path::String)
    VERSION == v"1.11.6" || throw(ArgumentError("Julia 1.11.6 is required"))
    FSYNC_COUNT[] = 0
    request = parse_request(request_path)
    graph = load_graph(request["graph_path"], request["graph_sha256"])
    request_hash = sha256_bytes(canonical_bytes(request))
    lock = acquire_lock(output_path, request_hash)
    try
        info = build_info()
        bindings = Dict(
            "anchor_sha256" => lock.anchor_sha256,
            "request_sha256" => request_hash,
            "adapter" => "QMC_LTFIM",
            "source_hash" => info["source_hash"],
            "build_hash" => info["build_hash"],
            "seed" => request["seed"],
        )
        chain = _recover_chain(lock, bindings, request)
        total_bins = request["retained_samples"] ÷ request["bin_length"]
        expected_generation_counts = collect(request["checkpoint_bins"]:request["checkpoint_bins"]:total_bins)
        isempty(expected_generation_counts) || last(expected_generation_counts) == total_bins ||
            push!(expected_generation_counts, total_bins)
        isempty(expected_generation_counts) && push!(expected_generation_counts, total_bins)
        length(chain) <= length(expected_generation_counts) ||
            throw(ArgumentError("too many checkpoint generations"))
        for (index, (_, manifest)) in enumerate(chain)
            manifest["completed_bin_count"] == expected_generation_counts[index] ||
                throw(ArgumentError("checkpoint completed-bin semantics mismatch"))
        end

        rng = rng_from_seed(request["seed"])
        H = build_model(graph.site_count, graph.bonds, request["coupling"], request["field"])
        initial_capacity = max(
            64,
            ceil(Int, 2 * request["beta"] * (sum(H.hx) + 2 * request["coupling"] * length(graph.bonds))),
        )
        state = QMC.BinaryThermalState(H, initial_capacity)
        diagnostics = QMC.Diagnostics(QMC.RunStats(), QMC.NoTransitionMatrix())
        noop(cluster_list_size, qmc_state, model) = nothing
        for _ in 1:request["thermalization_sweeps"]
            # The pinned revision's TFIM-specialized multibranch path is selected
            # explicitly. Its default line path indexes an uninitialized TFIM
            # op_indices entry; selecting the public p=1 update avoids that broken
            # general line path without modifying or extending upstream code.
            empty!(rng.bool_draws)
            QMC.mc_step_beta!(
                noop, rng, state, H, request["beta"], diagnostics; eq=true, p=1.0
            )
            empty!(rng.bool_draws)
        end

        bin_hashes = String[]
        existing_hashes = isempty(chain) ? String[] : Vector{String}(last(chain)[2]["bin_object_hashes"])
        generation_index = 1
        previous_generation = nothing
        retained = 0
        update_count = request["thermalization_sweeps"]
        for bin_index in 0:(total_bins - 1)
            samples = Any[]
            cluster_list_sum = 0
            before = _copy_runstats(diagnostics.runstats)
            for _ in 1:request["bin_length"]
                captured = Ref{Any}(nothing)
                accepted_for_sample = Ref(0)
                cluster_list_for_sample = Ref(0)
                for thin_index in 1:request["thinning"]
                    cluster_total_before = _stats_total(diagnostics.runstats.cluster_count)
                    empty!(rng.bool_draws)
                    function measure!(cluster_list_size, qmc_state, model)
                        cluster_list_for_sample[] += cluster_list_size
                        attempted_clusters = round(
                            Int,
                            _stats_total(diagnostics.runstats.cluster_count) -
                            cluster_total_before,
                        )
                        attempted_clusters <= length(rng.bool_draws) ||
                            error("QMC_LTFIM cluster RNG trace is incomplete")
                        accepted_for_sample[] += count(
                            identity,
                            @view(rng.bool_draws[1:attempted_clusters]),
                        )
                        if thin_index == request["thinning"]
                            num_ops = count(op -> op[1] != 0, qmc_state.operator_list)
                            site_ops = count(op -> op[1] == 1, qmc_state.operator_list)
                            m2, m4 = longitudinal_moments(qmc_state, model)
                            captured[] = Dict(
                                "energy" => energy_estimator(qmc_state, model, request["beta"], num_ops),
                                "mx" => transverse_estimator(model, request["beta"], site_ops),
                                "m2" => m2,
                                "m4" => m4,
                                "num_ops" => num_ops,
                                "capacity" => length(qmc_state.operator_list),
                                "cluster_list_size" => cluster_list_for_sample[],
                                "accepted_clusters" => accepted_for_sample[],
                                "sweeps" => request["thinning"],
                            )
                        end
                    end
                    QMC.mc_step_beta!(
                        measure!,
                        rng,
                        state,
                        H,
                        request["beta"],
                        diagnostics;
                        eq=false,
                        p=1.0,
                    )
                    update_count += 1
                end
                captured[] === nothing && error("QMC_LTFIM measurement callback was not called")
                cluster_list_sum += captured[]["cluster_list_size"]
                push!(samples, captured[])
                retained += 1
            end
            after = _copy_runstats(diagnostics.runstats)
            record = _make_bin(bin_index, samples, before, after, cluster_list_sum)
            digest, bytes = _publish_bin(lock, record)
            push!(bin_hashes, digest)
            if bin_index + 1 <= length(existing_hashes)
                digest == existing_hashes[bin_index + 1] ||
                    throw(ArgumentError("deterministic replay bin hash mismatch"))
                replay_bins = _open_dir(lock.anchored.directory, "bins")
                try
                    _verify_visible_directory(lock, "bins", replay_bins, "bins")
                    _read_file(replay_bins, "$digest.ndjson") == bytes ||
                        throw(ArgumentError("deterministic replay bin bytes mismatch"))
                finally
                    close(replay_bins)
                end
            end
            completed = bin_index + 1
            if completed in expected_generation_counts
                manifest = Dict(
                    "schema_version" => "qmc-checkpoint-generation-v2",
                    "anchor_sha256" => lock.anchor_sha256,
                    "request_sha256" => request_hash,
                    "adapter" => "QMC_LTFIM",
                    "source_hash" => info["source_hash"],
                    "build_hash" => info["build_hash"],
                    "seed" => request["seed"],
                    "completed_bin_count" => completed,
                    "bin_object_hashes" => copy(bin_hashes),
                    "previous_generation_sha256" => previous_generation,
                    "replay_update_count" => update_count,
                )
                if generation_index <= length(chain)
                    expected_digest, expected_manifest = chain[generation_index]
                    canonical_bytes(manifest) == canonical_bytes(expected_manifest) ||
                        throw(ArgumentError("deterministic replay generation mismatch"))
                    previous_generation = expected_digest
                else
                    previous_generation = _publish_generation(
                        lock, manifest, bindings, request
                    )
                end
                generation_index += 1
            end
        end
        length(bin_hashes) == total_bins || error("internal bin count mismatch")
        _audit_bin_orphans(lock, bin_hashes)
        return nothing
    finally
        release_lock(lock)
    end
end

function main(args=ARGS)
    if args == ["--build-info"]
        print(canonical_json(build_info()))
        return 0
    end
    length(args) == 4 || throw(ArgumentError("usage: --request PATH --output-directory PATH"))
    values = Dict(args[index] => args[index + 1] for index in 1:2:length(args))
    Set(keys(values)) == Set(["--request", "--output-directory"]) ||
        throw(ArgumentError("usage: --request PATH --output-directory PATH"))
    run_request(values["--request"], values["--output-directory"])
    return 0
end

end
