module RunRecords

using TOML

export write_run_record

_toml_safe(value::NamedTuple) =
    Dict(string(key) => _toml_safe(field) for (key, field) in pairs(value))
_toml_safe(value::AbstractDict) =
    Dict(string(key) => _toml_safe(field) for (key, field) in pairs(value))
_toml_safe(value::AbstractVector) = [_toml_safe(field) for field in value]
_toml_safe(value::Tuple) = [_toml_safe(field) for field in value]
_toml_safe(value::Type) = string(value)
_toml_safe(value) = value

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
