using SHA
import Pkg
import UniformTEMPO

const UNIFORM_IF_ADAPTER_SCHEMA = "uniform-if-adapter-v2"
const _UNIFORM_IF_METADATA_FIELDS = (
    "adapter_schema",
    "uniformtempo_revision",
    "julia_version",
    "exact_dt_bits",
    "compression_tolerance",
    "bath",
    "coupling_operator",
    "system_dimension",
    "liouville_dimension",
    "temperature_bits",
    "build",
)
const _UNIFORM_IF_BUILD_FIELDS = (
    "auto_nc",
    "n_c",
    "truncation",
    "cap_rank",
    "max_rank",
    "low_rank_svd",
    "svd_filtering_tolerance_bits",
)

"""A dependency-independent, validated snapshot of a uniform influence functional."""
struct UniformIFAdapter{Q<:AbstractArray{<:Number,4},VL<:AbstractVector{<:Number},VR<:AbstractVector{<:Number}}
    q::Q
    v_left::VL
    v_right::VR
    metadata::Dict{String,Any}
    convergence_metadata::Dict{String,Any}

    function UniformIFAdapter(q::AbstractArray{<:Number,4}, v_left::AbstractVector{<:Number},
                              v_right::AbstractVector{<:Number}, metadata::AbstractDict;
                              convergence_metadata::AbstractDict=Dict{String,Any}())
        size(q, 1) == size(q, 3) ||
            throw(ArgumentError("uniform-IF q auxiliary dimensions must agree"))
        size(q, 2) == size(q, 4) ||
            throw(ArgumentError("uniform-IF q system dimensions must agree"))
        size(q, 2) == 4 ||
            throw(ArgumentError("single-spin uniform-IF q system dimensions must equal d² = 4"))
        size(q, 1) > 0 && size(q, 2) > 0 ||
            throw(ArgumentError("uniform-IF q dimensions must be positive"))
        length(v_left) == size(q, 1) ||
            throw(ArgumentError("uniform-IF left boundary length must equal q auxiliary dimension"))
        length(v_right) == size(q, 3) ||
            throw(ArgumentError("uniform-IF right boundary length must equal q auxiliary dimension"))
        checked_metadata = _string_metadata(metadata)
        _validate_uniform_if_metadata(checked_metadata)
        checked_convergence_metadata = _string_metadata(convergence_metadata)
        q_copy = Array(q)
        left_copy = collect(v_left)
        right_copy = collect(v_right)
        return new{typeof(q_copy),typeof(left_copy),typeof(right_copy)}(q_copy, left_copy, right_copy,
                                                                          checked_metadata,
                                                                          checked_convergence_metadata)
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
    metadata["system_dimension"] == 2 ||
        throw(ArgumentError("uniform-IF metadata must declare system_dimension = 2"))
    metadata["liouville_dimension"] == 4 ||
        throw(ArgumentError("uniform-IF metadata must declare liouville_dimension = 4"))
    occursin(r"^[01]{64}$", string(metadata["temperature_bits"])) ||
        throw(ArgumentError("uniform-IF metadata must store temperature_bits as 64 binary digits"))
    bath = metadata["bath"]
    bath isa AbstractDict ||
        throw(ArgumentError("uniform-IF bath provenance must be a dictionary"))
    all(field -> haskey(bath, field), ("alpha_bits", "omega_c_bits")) ||
        throw(ArgumentError("uniform-IF bath provenance is incomplete"))
    build = metadata["build"]
    build isa AbstractDict ||
        throw(ArgumentError("uniform-IF build provenance must be a dictionary"))
    all(field -> haskey(build, field), _UNIFORM_IF_BUILD_FIELDS) ||
        throw(ArgumentError("uniform-IF build provenance is incomplete"))
    return nothing
end

"""Return the active UniformTEMPO package-tree revision, not a caller-provided label."""
function installed_uniformtempo_revision()
    package_id = Base.PkgId(UniformTEMPO)
    dependency = get(Pkg.dependencies(), package_id.uuid, nothing)
    isnothing(dependency) &&
        throw(ArgumentError("active UniformTEMPO dependency identity is unavailable"))
    isnothing(dependency.tree_hash) &&
        throw(ArgumentError("active UniformTEMPO tree revision is unavailable"))
    return string(dependency.tree_hash)
end

"""Build complete, exact provenance for one bath-only uniform influence functional."""
Base.@kwdef struct UniformIFBuildSettings
    auto_nc::Bool = true
    n_c::Int = 100_000
    truncation::Symbol = :rel
    cap_rank::Int = 100_000
    max_rank::Int = 100_000
    low_rank_svd::Bool = false
    svd_filtering_tolerance::Float64 = 0.0
end

function _validate_build_settings(build::UniformIFBuildSettings)
    build.n_c > 0 || throw(ArgumentError("uniform-IF n_c must be positive"))
    build.cap_rank > 0 || throw(ArgumentError("uniform-IF cap_rank must be positive"))
    build.max_rank > 0 || throw(ArgumentError("uniform-IF max_rank must be positive"))
    build.truncation in (:rel, :abs) ||
        throw(ArgumentError("uniform-IF truncation must be :rel or :abs"))
    isfinite(build.svd_filtering_tolerance) && build.svd_filtering_tolerance >= 0 ||
        throw(ArgumentError("uniform-IF SVD filtering tolerance must be finite and nonnegative"))
    return nothing
end

function uniform_if_metadata(model::SpinBosonModel, exact_dt::Real,
                             compression_tolerance::Real;
                             temperature::Real=0.0,
                             build::UniformIFBuildSettings=UniformIFBuildSettings())
    isfinite(exact_dt) && exact_dt > 0 ||
        throw(ArgumentError("uniform-IF exact dt must be finite and positive"))
    isfinite(compression_tolerance) && compression_tolerance > 0 ||
        throw(ArgumentError("uniform-IF compression tolerance must be finite and positive"))
    isfinite(temperature) && temperature >= 0 ||
        throw(ArgumentError("uniform-IF temperature must be finite and nonnegative"))
    _validate_build_settings(build)
    return Dict{String,Any}(
        "adapter_schema" => UNIFORM_IF_ADAPTER_SCHEMA,
        "uniformtempo_revision" => installed_uniformtempo_revision(),
        "julia_version" => string(VERSION),
        "exact_dt_bits" => bitstring(Float64(exact_dt)),
        "compression_tolerance" => bitstring(Float64(compression_tolerance)),
        "bath" => Dict(
            "alpha_bits" => bitstring(model.alpha),
            "omega_c_bits" => bitstring(model.omega_c),
        ),
        "coupling_operator" => "sigma_z",
        "system_dimension" => 2,
        "liouville_dimension" => 4,
        "temperature_bits" => bitstring(Float64(temperature)),
        "build" => Dict(
            "auto_nc" => build.auto_nc,
            "n_c" => build.n_c,
            "truncation" => String(build.truncation),
            "cap_rank" => build.cap_rank,
            "max_rank" => build.max_rank,
            "low_rank_svd" => build.low_rank_svd,
            "svd_filtering_tolerance_bits" => bitstring(build.svd_filtering_tolerance),
        ),
    )
end

function uniform_if_build_settings(config::RunConfig)
    return UniformIFBuildSettings(auto_nc=config.auto_nc, n_c=config.n_c,
                                  truncation=config.truncation, cap_rank=config.cap_rank,
                                  max_rank=config.max_rank, low_rank_svd=config.low_rank_svd,
                                  svd_filtering_tolerance=config.svd_filtering_tolerance)
end

"""
Build or load one uniform IF through the cache-enabled production entry point.

The builder receives (model, exact_dt, compression_tolerance, build_settings)
and returns either a UniformPTMPO or a pair of that tensor and convergence
metadata.
"""
function build_or_load_uniform_if(config::RunConfig, cache_dir::AbstractString,
                                  pt_builder::Function;
                                  model::SpinBosonModel=SpinBosonModel(),
                                  exact_dt::Real=config.dt_target,
                                  rebuild::Bool=config.rebuild_cache)
    settings = uniform_if_build_settings(config)
    metadata = uniform_if_metadata(model, exact_dt, config.compression_tolerance;
                                   temperature=config.temperature, build=settings)
    builder = function ()
        built = pt_builder(model, exact_dt, config.compression_tolerance, settings)
        pt, convergence_metadata = if built isa Tuple
            length(built) == 2 ||
                throw(ArgumentError("uniform-IF builder tuple must contain tensor and convergence metadata"))
            built
        else
            built, Dict{String,Any}()
        end
        convergence_metadata isa AbstractDict ||
            throw(ArgumentError("uniform-IF builder convergence metadata must be a dictionary"))
        return adapt_uniform_pt(pt; metadata=metadata,
                                convergence_metadata=convergence_metadata)
    end
    return load_or_build_uniform_if(cache_dir, metadata, builder; rebuild=rebuild)
end

"""Convert the currently supported UniformTEMPO representation into the harness adapter."""
function adapt_uniform_pt(pt; metadata::AbstractDict,
                          convergence_metadata::AbstractDict=Dict{String,Any}())
    pt isa UniformTEMPO.UniformPTMPO ||
        throw(ArgumentError("expected UniformTEMPO.UniformPTMPO, got " * string(typeof(pt))))
    # This is intentionally the only source module that reads UniformPTMPO internals.
    pt.s_dim == 2 ||
        throw(ArgumentError("single-spin UniformPTMPO must have s_dim = 2"))
    checked_metadata = _string_metadata(metadata)
    _validate_uniform_if_metadata(checked_metadata)
    bitstring(Float64(pt.delta_t)) == checked_metadata["exact_dt_bits"] ||
        throw(ArgumentError("UniformPTMPO delta_t does not match requested exact dt"))
    checked_metadata["uniformtempo_revision"] == installed_uniformtempo_revision() ||
        throw(ArgumentError("UniformTEMPO revision does not match requested cache provenance"))
    size(pt.q, 2) == 4 && size(pt.q, 4) == 4 ||
        throw(ArgumentError("single-spin UniformPTMPO layout must be (aux-out, 4, aux-in, 4)"))
    return UniformIFAdapter(pt.q, vec(pt.v_l), pt.v_r, metadata;
                            convergence_metadata=convergence_metadata)
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
