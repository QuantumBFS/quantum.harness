const _TASK_SCHEMA_VERSION = 1
const _TASK_LATTICES = (:triangle, :honeycomb)
const _TASK_JSON_FIELDS = (
    "schema_version",
    "lattice",
    "L",
    "J",
    "h",
    "c",
    "replica",
    "seed",
    "thermalization_sweeps",
    "measurement_sweeps",
    "base_bin_size",
    "checkpoint_interval_bins",
    "output_path",
)

"""An immutable Route A manifest for one independent cluster Markov chain."""
struct ClusterTask
    schema_version::Int
    lattice::Symbol
    L::Int
    J::Float64
    h::Float64
    c::Float64
    replica::Int
    seed::UInt64
    thermalization_sweeps::Int
    measurement_sweeps::Int
    base_bin_size::Int
    checkpoint_interval_bins::Int
    output_path::String
end

_float64_token(value::Float64) = "f64:" * string(reinterpret(UInt64, value), base=16, pad=16)
_uint64_token(value::UInt64) = "u64:" * string(value, base=16, pad=16)
_utf8_token(value::String) = "utf8:" * bytes2hex(codeunits(value))

function _validate_lattice_size(lattice::Symbol, L::Int)
    lattice in _TASK_LATTICES || throw(ArgumentError("unsupported task lattice: $lattice"))
    if lattice === :triangle
        L >= 3 || throw(ArgumentError("triangle task requires L >= 3"))
    else
        L >= 2 || throw(ArgumentError("honeycomb task requires L >= 2"))
    end
    return nothing
end

"""Validate a task manifest and return the original immutable task on success."""
function validate_task(task::ClusterTask)
    task.schema_version == _TASK_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported task schema version: $(task.schema_version)"))
    _validate_lattice_size(task.lattice, task.L)
    isfinite(task.J) && task.J >= 0 || throw(ArgumentError("J must be finite and nonnegative"))
    isfinite(task.h) && !iszero(task.h) || throw(ArgumentError("h must be finite and nonzero"))
    isfinite(task.c) && task.c > 0 || throw(ArgumentError("c must be finite and positive"))
    isfinite(beta_for_aspect(task.h, task.L; c=task.c)) ||
        throw(ArgumentError("derived beta must be finite"))
    task.replica > 0 || throw(ArgumentError("replica must be positive"))
    !iszero(task.seed) || throw(ArgumentError("seed must be nonzero"))
    task.thermalization_sweeps >= 0 ||
        throw(ArgumentError("thermalization_sweeps must be nonnegative"))
    task.measurement_sweeps > 0 ||
        throw(ArgumentError("measurement_sweeps must be positive"))
    task.base_bin_size > 0 || throw(ArgumentError("base_bin_size must be positive"))
    task.checkpoint_interval_bins > 0 ||
        throw(ArgumentError("checkpoint_interval_bins must be positive"))
    task.measurement_sweeps % task.base_bin_size == 0 ||
        throw(ArgumentError("measurement_sweeps must be divisible by base_bin_size"))
    !isempty(task.output_path) || throw(ArgumentError("output_path must be nonempty"))
    return task
end

"""
Return the locale-independent, fixed-order bytes represented as a String for task hashing.

Float64 values are represented by their IEEE-754 bits.  In particular, the sign
bit of `h` is retained: `h` and `-h` have the same aspect-ratio beta but distinct
task identities.
"""
function canonical_task_string(task::ClusterTask)
    validate_task(task)
    return join((
        "schema_version=$(task.schema_version)",
        "lattice=$(String(task.lattice))",
        "L=$(task.L)",
        "J=$(_float64_token(task.J))",
        "h=$(_float64_token(task.h))",
        "c=$(_float64_token(task.c))",
        "replica=$(task.replica)",
        "seed=$(_uint64_token(task.seed))",
        "thermalization_sweeps=$(task.thermalization_sweeps)",
        "measurement_sweeps=$(task.measurement_sweeps)",
        "base_bin_size=$(task.base_bin_size)",
        "checkpoint_interval_bins=$(task.checkpoint_interval_bins)",
        "output_path=$(_utf8_token(task.output_path))",
    ), "|")
end

"""Return the lowercase SHA-256 digest of a validated task's canonical representation."""
task_hash(task::ClusterTask) = bytes2hex(sha256(codeunits(canonical_task_string(task))))

"""Return the stable Route A identifier used for task result and checkpoint names."""
function task_id(task::ClusterTask)
    validate_task(task)
    return "ra-$(task.lattice)-L$(lpad(task.L, 4, '0'))-r$(lpad(task.replica, 3, '0'))-$(task_hash(task)[1:8])"
end

function _scientific_key(
    route::Union{Symbol,AbstractString},
    lattice::Symbol,
    L::Integer,
    h::Real,
    c::Real,
    replica::Integer,
)
    route_name = String(route)
    isempty(route_name) && throw(ArgumentError("route must be nonempty"))
    L_int = try
        Int(L)
    catch error
        error isa InexactError || rethrow()
        throw(ArgumentError("L must fit in Int"))
    end
    replica_int = try
        Int(replica)
    catch error
        error isa InexactError || rethrow()
        throw(ArgumentError("replica must fit in Int"))
    end
    h_float = Float64(h)
    c_float = Float64(c)
    _validate_lattice_size(lattice, L_int)
    isfinite(h_float) && !iszero(h_float) || throw(ArgumentError("h must be finite and nonzero"))
    isfinite(c_float) && c_float > 0 || throw(ArgumentError("c must be finite and positive"))
    replica_int > 0 || throw(ArgumentError("replica must be positive"))
    return join((
        "route=$(_utf8_token(route_name))",
        "lattice=$(String(lattice))",
        "L=$(L_int)",
        "h=$(_float64_token(h_float))",
        "c=$(_float64_token(c_float))",
        "replica=$(replica_int)",
    ), "|")
end

"""Derive a nonzero UInt64 seed from the first eight SHA-256 bytes of a scientific key."""
function task_seed(
    route::Union{Symbol,AbstractString},
    lattice::Symbol,
    L::Integer,
    h::Real,
    c::Real,
    replica::Integer,
)
    digest = sha256(codeunits(_scientific_key(route, lattice, L, h, c, replica)))
    seed = zero(UInt64)
    for byte in @view digest[1:8]
        seed = (seed << 8) | UInt64(byte)
    end
    !iszero(seed) || throw(ArgumentError("scientific key derived the forbidden zero seed"))
    return seed
end

task_seed(lattice::Symbol, L::Integer, h::Real, c::Real, replica::Integer) =
    task_seed(:route_a, lattice, L, h, c, replica)

function _task_json(task::ClusterTask)
    return (
        schema_version=task.schema_version,
        lattice=String(task.lattice),
        L=task.L,
        J=task.J,
        h=task.h,
        c=task.c,
        replica=task.replica,
        seed=_uint64_token(task.seed),
        thermalization_sweeps=task.thermalization_sweeps,
        measurement_sweeps=task.measurement_sweeps,
        base_bin_size=task.base_bin_size,
        checkpoint_interval_bins=task.checkpoint_interval_bins,
        output_path=task.output_path,
    )
end

"""Write a validated task to a fixed-field-order JSON manifest and return `path`."""
function write_task(path::AbstractString, task::ClusterTask)
    validate_task(task)
    open(path, "w") do io
        JSON.print(io, _task_json(task))
    end
    return String(path)
end

function _read_int(value, name::String)
    value isa Integer && !(value isa Bool) || throw(ArgumentError("$name must be an integer"))
    try
        return Int(value)
    catch error
        error isa InexactError || rethrow()
        throw(ArgumentError("$name must fit in Int"))
    end
end

function _read_float(value, name::String)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$name must be a number"))
    return Float64(value)
end

function _read_seed(value)
    value isa AbstractString || throw(ArgumentError("seed must be a u64 token string"))
    startswith(value, "u64:") && ncodeunits(value) == 20 ||
        throw(ArgumentError("seed must be exactly u64: followed by 16 hexadecimal digits"))
    hex = value[5:end]
    all(isxdigit, hex) || throw(ArgumentError("seed contains non-hexadecimal digits"))
    return parse(UInt64, hex; base=16)
end

"""Read, strictly validate, and return an immutable task JSON manifest."""
function read_task(path::AbstractString)
    parsed = JSON.parsefile(path)
    parsed isa AbstractDict || throw(ArgumentError("task manifest must be a JSON object"))
    Set(string.(keys(parsed))) == Set(_TASK_JSON_FIELDS) ||
        throw(ArgumentError("task manifest has missing or unknown fields"))
    lattice = parsed["lattice"]
    lattice isa AbstractString || throw(ArgumentError("lattice must be a string"))
    output_path = parsed["output_path"]
    output_path isa AbstractString || throw(ArgumentError("output_path must be a string"))
    task = ClusterTask(
        _read_int(parsed["schema_version"], "schema_version"),
        Symbol(lattice),
        _read_int(parsed["L"], "L"),
        _read_float(parsed["J"], "J"),
        _read_float(parsed["h"], "h"),
        _read_float(parsed["c"], "c"),
        _read_int(parsed["replica"], "replica"),
        _read_seed(parsed["seed"]),
        _read_int(parsed["thermalization_sweeps"], "thermalization_sweeps"),
        _read_int(parsed["measurement_sweeps"], "measurement_sweeps"),
        _read_int(parsed["base_bin_size"], "base_bin_size"),
        _read_int(parsed["checkpoint_interval_bins"], "checkpoint_interval_bins"),
        String(output_path),
    )
    return validate_task(task)
end
