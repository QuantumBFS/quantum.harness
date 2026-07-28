using SHA
import UniformTEMPO

const UNIFORM_IF_ADAPTER_SCHEMA = "uniform-if-adapter-v1"
const _UNIFORM_IF_METADATA_FIELDS = (
    "adapter_schema",
    "uniformtempo_revision",
    "julia_version",
    "exact_dt_bits",
    "compression_tolerance",
    "bath",
    "coupling_operator",
)

"""A dependency-independent, validated snapshot of a uniform influence functional."""
struct UniformIFAdapter{Q<:AbstractArray{<:Number,4},VL<:AbstractVector{<:Number},VR<:AbstractVector{<:Number}}
    q::Q
    v_left::VL
    v_right::VR
    metadata::Dict{String,Any}

    function UniformIFAdapter(q::AbstractArray{<:Number,4}, v_left::AbstractVector{<:Number},
                              v_right::AbstractVector{<:Number}, metadata::AbstractDict)
        size(q, 1) == size(q, 3) ||
            throw(ArgumentError("uniform-IF q auxiliary dimensions must agree"))
        size(q, 2) == size(q, 4) ||
            throw(ArgumentError("uniform-IF q system dimensions must agree"))
        size(q, 1) > 0 && size(q, 2) > 0 ||
            throw(ArgumentError("uniform-IF q dimensions must be positive"))
        length(v_left) == size(q, 1) ||
            throw(ArgumentError("uniform-IF left boundary length must equal q auxiliary dimension"))
        length(v_right) == size(q, 3) ||
            throw(ArgumentError("uniform-IF right boundary length must equal q auxiliary dimension"))
        checked_metadata = _string_metadata(metadata)
        _validate_uniform_if_metadata(checked_metadata)
        q_copy = Array(q)
        left_copy = collect(v_left)
        right_copy = collect(v_right)
        return new{typeof(q_copy),typeof(left_copy),typeof(right_copy)}(q_copy, left_copy, right_copy,
                                                                          checked_metadata)
    end
end

function _string_metadata(metadata::AbstractDict)
    return Dict(string(key) => value for (key, value) in metadata)
end

function _validate_uniform_if_metadata(metadata::AbstractDict)
    for field in _UNIFORM_IF_METADATA_FIELDS
        haskey(metadata, field) || throw(ArgumentError("uniform-IF metadata is missing " * field))
    end
    metadata["adapter_schema"] == UNIFORM_IF_ADAPTER_SCHEMA ||
        throw(ArgumentError("unsupported uniform-IF adapter schema " * repr(metadata["adapter_schema"])))
    occursin(r"^[01]{64}$", string(metadata["exact_dt_bits"])) ||
        throw(ArgumentError("uniform-IF metadata must store exact_dt_bits as 64 binary digits"))
    return nothing
end

"""Build complete, exact provenance for one bath-only uniform influence functional."""
function uniform_if_metadata(model::SpinBosonModel, exact_dt::Real,
                             compression_tolerance::Real; uniformtempo_revision::AbstractString)
    isfinite(exact_dt) && exact_dt > 0 ||
        throw(ArgumentError("uniform-IF exact dt must be finite and positive"))
    isfinite(compression_tolerance) && compression_tolerance > 0 ||
        throw(ArgumentError("uniform-IF compression tolerance must be finite and positive"))
    isempty(uniformtempo_revision) &&
        throw(ArgumentError("uniform-IF provenance requires a UniformTEMPO revision"))
    return Dict{String,Any}(
        "adapter_schema" => UNIFORM_IF_ADAPTER_SCHEMA,
        "uniformtempo_revision" => String(uniformtempo_revision),
        "julia_version" => string(VERSION),
        "exact_dt_bits" => bitstring(Float64(exact_dt)),
        "compression_tolerance" => bitstring(Float64(compression_tolerance)),
        "bath" => Dict(
            "alpha_bits" => bitstring(model.alpha),
            "omega_c_bits" => bitstring(model.omega_c),
        ),
        "coupling_operator" => "sigma_z",
    )
end

"""Convert the currently supported UniformTEMPO representation into the harness adapter."""
function adapt_uniform_pt(pt; metadata::AbstractDict)
    pt isa UniformTEMPO.UniformPTMPO ||
        throw(ArgumentError("expected UniformTEMPO.UniformPTMPO, got " * string(typeof(pt))))
    # This is intentionally the only source module that reads UniformPTMPO internals.
    return UniformIFAdapter(pt.q, vec(pt.v_l), pt.v_r, metadata)
end

function _canonical_uniform_if_metadata(value)
    if value isa AbstractDict
        entries = String[]
        for key in sort!(collect(keys(value)); by=string)
            push!(entries, repr(string(key)) * ":" * _canonical_uniform_if_metadata(value[key]))
        end
        return "{" * join(entries, ",") * "}"
    elseif value isa AbstractVector || value isa Tuple
        return "[" * join(_canonical_uniform_if_metadata.(value), ",") * "]"
    end
    return repr(value)
end

"""Return the SHA256 cache key for fully specified uniform-IF provenance."""
function uniform_if_key(metadata::AbstractDict)
    checked_metadata = _string_metadata(metadata)
    _validate_uniform_if_metadata(checked_metadata)
    return bytes2hex(sha256(_canonical_uniform_if_metadata(checked_metadata)))
end
