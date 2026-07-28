using JLD2

"""Return the deterministic on-disk location of one provenance-specific IF cache."""
function uniform_if_cache_path(cache_dir::AbstractString, metadata::AbstractDict)
    return joinpath(cache_dir, "uniform-if-" * uniform_if_key(metadata) * ".jld2")
end

"""Write a complete adapter through a same-directory temporary JLD2 file and atomic rename."""
function atomic_save(path::AbstractString, adapter::UniformIFAdapter; before_rename::Union{Nothing,Function}=nothing)
    directory = dirname(path)
    mkpath(directory)
    temporary_path, temporary_io = mktemp(directory; cleanup=false)
    close(temporary_io)
    try
        JLD2.jldsave(temporary_path;
                     q=adapter.q,
                     v_left=adapter.v_left,
                     v_right=adapter.v_right,
                     metadata=adapter.metadata)
        isnothing(before_rename) || before_rename()
        mv(temporary_path, path; force=true)
    catch
        ispath(temporary_path) && rm(temporary_path; force=true)
        rethrow()
    end
    return path
end

function _load_uniform_if(path::AbstractString, expected_metadata::AbstractDict)
    isfile(path) || throw(ArgumentError("uniform-IF cache does not exist: " * path))
    payload = JLD2.load(path)
    required = ("q", "v_left", "v_right", "metadata")
    all(key -> haskey(payload, key), required) ||
        throw(ArgumentError("uniform-IF cache is incomplete: " * path))
    adapter = UniformIFAdapter(payload["q"], payload["v_left"], payload["v_right"],
                               payload["metadata"])
    _canonical_uniform_if_metadata(adapter.metadata) ==
        _canonical_uniform_if_metadata(_string_metadata(expected_metadata)) ||
        throw(ArgumentError("uniform-IF cache provenance mismatch: " * path))
    return adapter
end

"""
Load a provenance-matched uniform IF cache, or build and atomically persist one.

A mismatched file is rejected rather than silently rebuilt. Pass rebuild=true
only when an explicit replacement was requested.
"""
function load_or_build_uniform_if(cache_dir::AbstractString, metadata::AbstractDict,
                                  builder::Function; rebuild::Bool=false)
    expected_metadata = _string_metadata(metadata)
    _validate_uniform_if_metadata(expected_metadata)
    path = uniform_if_cache_path(cache_dir, expected_metadata)
    if !rebuild && isfile(path)
        return _load_uniform_if(path, expected_metadata)
    end

    adapter = builder()
    adapter isa UniformIFAdapter ||
        throw(ArgumentError("uniform-IF builder must return UniformIFAdapter"))
    _canonical_uniform_if_metadata(adapter.metadata) ==
        _canonical_uniform_if_metadata(expected_metadata) ||
        throw(ArgumentError("uniform-IF builder provenance does not match requested cache"))
    atomic_save(path, adapter)
    return adapter
end
