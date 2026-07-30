module RunRecords

using TOML

export run_result_path, write_run_record

_toml_safe(value::NamedTuple) =
    Dict(string(key) => _toml_safe(field) for (key, field) in pairs(value))
_toml_safe(value::AbstractDict) =
    Dict(string(key) => _toml_safe(field) for (key, field) in pairs(value))
_toml_safe(value::AbstractVector) = [_toml_safe(field) for field in value]
_toml_safe(value::Tuple) = [_toml_safe(field) for field in value]
_toml_safe(value::Type) = string(value)
_toml_safe(value) = value

function run_result_path(
    root::AbstractString,
    run_directory::AbstractString,
    delta::Real,
    maxdim::Integer,
    seed_id::Integer,
)
    occursin(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", run_directory) ||
        throw(ArgumentError("invalid run directory: $run_directory"))
    run_directory in (".", "..") &&
        throw(ArgumentError("invalid run directory: $run_directory"))
    delta_directory = if iszero(delta)
        "delta-0"
    elseif delta == 0.15
        "delta-0p15"
    else
        throw(ArgumentError("delta must be 0 or 0.15"))
    end
    maxdim > 0 || throw(ArgumentError("maxdim must be positive"))
    seed_id >= 0 || throw(ArgumentError("seed id must be nonnegative"))
    return joinpath(
        root,
        "runs",
        run_directory,
        delta_directory,
        "chi-$maxdim",
        "seed-$(lpad(seed_id, 4, '0')).toml",
    )
end

function write_run_record(path::AbstractString, result; run_metadata = Dict())
    mkpath(dirname(abspath(path)))
    document = Dict(
        "run" => _toml_safe(run_metadata),
        "result" => _toml_safe(result),
    )
    temporary_path = "$path.tmp.$(getpid())"
    open(temporary_path, "w") do io
        TOML.print(io, document; sorted = true)
    end
    mv(temporary_path, path; force = true)
    return path
end

end
