using LsqFit

const FSS_MODELS = (:M1, :M2, :M3)
const FSS_L_MINS = (8, 12, 16, 24)
const FSS_YT_FIXED = 1.5868
const FSS_YI_FIXED = -0.821
const FSS_YT_BOUNDS = (1.50, 1.67)
const FSS_BOOTSTRAP_SEED = 148900
const FSS_BOOTSTRAP_DRAWS = 2000
const ROUTE_A_PRELIMINARY_STATUS = "route A preliminary; not a final Challenge #148 verdict"

struct BinderFitResult
    model::Symbol
    L_min::Int
    yt_mode::Symbol
    parameter_names::Tuple{Vararg{Symbol}}
    parameters::NamedTuple
    covariance::Matrix{Float64}
    chi2::Float64
    dof::Int
    reduced_chi2::Float64
    converged::Bool
    accepted::Bool
    rejection_reasons::Vector{String}
    nrows::Int
    sizes::Vector{Int}
end

"""One audited Markov-chain replica with the raw time-magnetization bins needed by Route A."""
struct ReplicaBinderData
    lattice::Symbol
    L::Int
    h::Float64
    c::Float64
    replica::Int
    chain_id::String
    m2_bins::Vector{Float64}
    m4_bins::Vector{Float64}

    function ReplicaBinderData(
        lattice::Symbol,
        L::Integer,
        h::Real,
        c::Real,
        replica::Integer,
        chain_id::AbstractString,
        m2_bins::AbstractVector{<:Real},
        m4_bins::AbstractVector{<:Real},
    )
        lattice in (:triangle, :honeycomb) || throw(ArgumentError("unsupported replica lattice"))
        L > 0 || throw(ArgumentError("replica size must be positive"))
        isfinite(h) || throw(ArgumentError("replica field must be finite"))
        isfinite(c) && c > 0 || throw(ArgumentError("replica aspect ratio must be finite and positive"))
        replica > 0 || throw(ArgumentError("replica index must be positive"))
        isempty(chain_id) && throw(ArgumentError("replica chain ID must be nonempty"))
        length(m2_bins) == length(m4_bins) > 0 ||
            throw(ArgumentError("replica Binder bin columns must be nonempty and equal length"))
        normalized_m2 = Float64.(m2_bins)
        normalized_m4 = Float64.(m4_bins)
        all(isfinite, normalized_m2) && all(isfinite, normalized_m4) ||
            throw(ArgumentError("replica Binder bins must be finite"))
        mean(normalized_m4) != 0 || throw(ArgumentError("replica fourth moment must be nonzero"))
        return new(
            lattice, Int(L), Float64(h), Float64(c), Int(replica), String(chain_id),
            normalized_m2, normalized_m4,
        )
    end
end

struct RatioBootstrapResult
    samples::Vector{Float64}
    seed::Int
    draws::Int
end

struct CombinedBinderData
    campaign_id::String
    campaign_checksum::String
    julia_manifest_sha256::String
    git_commit::String
    julia_version::String
    algorithm::String
    observable_schema_version::Int
    content_sha256::String
    records::Vector{ReplicaBinderData}
end

const _COMBINED_FIELDS = (
    "schema_version", "kind", "campaign_id", "campaign_checksum", "julia_manifest_sha256",
    "git_commit", "julia_version", "algorithm", "observable_schema_version", "chains",
)
const _COMBINED_CHAIN_FIELDS = (
    "task_id", "task_hash", "task", "provenance", "completed_bins", "raw_bins",
)
const _COMBINED_TASK_FIELDS = (
    "schema_version", "lattice", "L", "J", "h", "c", "replica", "seed",
    "thermalization_sweeps", "measurement_sweeps", "base_bin_size",
    "checkpoint_interval_bins", "output_path", "canonical_task",
)
const _COMBINED_RAW_FIELDS = (
    "energy_per_site", "m_time2", "m_time4", "m_equal2", "m_equal4", "cuts_mean",
    "cut_histogram",
)
const _COMBINED_PROVENANCE_FIELDS = (
    "git_commit", "manifest_sha256", "julia_version", "hostname", "slurm_job_id",
    "slurm_array_task_id", "started_at", "completed_at", "wall_seconds",
)
const _FROZEN_SIZES = (8, 12, 16, 24, 32, 48, 64)
const _FROZEN_THERMAL_SIZES = (24, 48)
const _FROZEN_THERMAL_C = (1.5, 2.0)
const _FROZEN_X_ANCHORS = (-0.6, 0.0, 0.6)
const _FROZEN_H_OLD = Dict(:triangle => 4.76811, :honeycomb => 2.13250)

function _exact_keys(value, expected, label::String)
    value isa AbstractDict || throw(ArgumentError("$label must be an object"))
    Set(string.(keys(value))) == Set(expected) ||
        throw(ArgumentError("$label has missing or unknown fields"))
    return value
end

function _schema_int(value, label::String)
    value isa Integer && !(value isa Bool) || throw(ArgumentError("$label must be an integer"))
    return Int(value)
end

function _schema_float(value, label::String)
    value isa Real && !(value isa Bool) || throw(ArgumentError("$label must be numeric"))
    result = Float64(value)
    isfinite(result) || throw(ArgumentError("$label must be finite"))
    return result
end

function _schema_column(raw, name::String, bins::Int)
    values = raw[name]
    values isa AbstractVector && length(values) == bins ||
        throw(ArgumentError("combined raw bin column $name has the wrong length"))
    return [_schema_float(value, "combined raw bin $name") for value in values]
end

_sha1_token(value) = value isa AbstractString && occursin(r"^[0-9a-f]{40}$", value)
_sha256_token(value) = value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value)

function _validate_frozen_task(task::ClusterTask)
    task.J == 1.0 || throw(ArgumentError("Route A analysis requires frozen J=1"))
    task.L in _FROZEN_SIZES || throw(ArgumentError("Route A analysis received an unapproved size"))
    approved_c = task.L in _FROZEN_THERMAL_SIZES ? (1.0, _FROZEN_THERMAL_C...) : (1.0,)
    task.c in approved_c || throw(ArgumentError("Route A analysis received an unapproved aspect ratio"))
    anchors = [_FROZEN_H_OLD[task.lattice] + x * task.L^-FSS_YT_FIXED for x in _FROZEN_X_ANCHORS]
    task.h in anchors || throw(ArgumentError("Route A analysis received an unapproved field anchor"))
    task.replica in 1:8 || throw(ArgumentError("Route A analysis requires frozen replicas 1 through 8"))
    return task
end

function _validate_chain_provenance(provenance, combined, index::Int)
    _exact_keys(provenance, _COMBINED_PROVENANCE_FIELDS, "combined chain $index provenance")
    provenance["git_commit"] == combined["git_commit"] ||
        throw(ArgumentError("combined chain provenance commit mismatch"))
    provenance["manifest_sha256"] == combined["julia_manifest_sha256"] ||
        throw(ArgumentError("combined chain provenance manifest mismatch"))
    provenance["julia_version"] == combined["julia_version"] ||
        throw(ArgumentError("combined chain provenance runtime mismatch"))
    provenance["hostname"] isa AbstractString && !isempty(provenance["hostname"]) ||
        throw(ArgumentError("combined chain provenance hostname is invalid"))
    for name in ("slurm_job_id", "slurm_array_task_id")
        value = provenance[name]
        value === nothing || value isa AbstractString ||
            throw(ArgumentError("combined chain provenance $name is invalid"))
    end
    for name in ("started_at", "completed_at")
        provenance[name] isa AbstractString && !isempty(provenance[name]) ||
            throw(ArgumentError("combined chain provenance $name is invalid"))
    end
    wall_seconds = provenance["wall_seconds"]
    wall_seconds isa Real && !(wall_seconds isa Bool) && isfinite(wall_seconds) && wall_seconds >= 0 ||
        throw(ArgumentError("combined chain provenance wall_seconds is invalid"))
    return nothing
end

function _validate_complete_frozen_grid(records::Vector{ReplicaBinderData})
    expected = Set{Tuple{Symbol,Int,Float64,Float64}}()
    for lattice in (:triangle, :honeycomb), L in _FROZEN_SIZES
        for h in (_FROZEN_H_OLD[lattice] + x * L^-FSS_YT_FIXED for x in _FROZEN_X_ANCHORS)
            push!(expected, (lattice, L, h, 1.0))
            if L in _FROZEN_THERMAL_SIZES
                for c in _FROZEN_THERMAL_C
                    push!(expected, (lattice, L, h, c))
                end
            end
        end
    end
    groups = _replica_groups(records)
    Set(keys(groups)) == expected || throw(ArgumentError("combined data do not match the complete frozen science grid"))
    all(Set(getfield.(group, :replica)) == Set(1:8) for group in values(groups)) ||
        throw(ArgumentError("combined data do not contain all eight frozen replicas"))
    return nothing
end

function _parsed_content_snapshot(path::AbstractString, parser; reader=read)
    content = reader(path)
    content isa AbstractVector{UInt8} ||
        throw(ArgumentError("content reader must return bytes"))
    bytes = Vector{UInt8}(content)
    content_sha256 = bytes2hex(sha256(bytes))
    return (value=parser(bytes), content_sha256=content_sha256)
end

"""Strictly consume the version-1 `route_a_combined_bins` artifact emitted by Task 8."""
function read_combined_binder_data(path::AbstractString; reader=read)
    islink(path) && throw(ArgumentError("combined data must not be a symlink"))
    isfile(path) || throw(ArgumentError("combined data must be a regular file"))
    snapshot = try
        _parsed_content_snapshot(
            path, bytes -> JSON.parse(String(bytes); dicttype=Dict); reader=reader)
    catch error
        throw(ArgumentError("could not parse combined data: $(sprint(showerror, error))"))
    end
    combined = snapshot.value
    _exact_keys(combined, _COMBINED_FIELDS, "combined data")
    _schema_int(combined["schema_version"], "combined schema_version") == 1 ||
        throw(ArgumentError("unsupported combined-data schema version"))
    combined["kind"] == "route_a_combined_bins" || throw(ArgumentError("unsupported combined-data kind"))
    combined["algorithm"] == "continuous_time_cluster" ||
        throw(ArgumentError("unsupported combined-data algorithm"))
    _schema_int(combined["observable_schema_version"], "observable schema version") == 2 ||
        throw(ArgumentError("unsupported observable schema version"))
    combined["julia_version"] == string(VERSION) ||
        throw(ArgumentError("combined data were produced by a different Julia runtime"))
    combined["campaign_id"] isa AbstractString && !isempty(combined["campaign_id"]) ||
        throw(ArgumentError("combined campaign_id is invalid"))
    _sha256_token(combined["campaign_checksum"]) ||
        throw(ArgumentError("combined campaign checksum is invalid"))
    _sha256_token(combined["julia_manifest_sha256"]) ||
        throw(ArgumentError("combined Julia manifest token is invalid"))
    _sha1_token(combined["git_commit"]) || throw(ArgumentError("combined Git commit token is invalid"))
    chains = combined["chains"]
    chains isa AbstractVector && !isempty(chains) ||
        throw(ArgumentError("combined data must contain chains"))

    records = ReplicaBinderData[]
    seen_ids = Set{String}()
    seen_groups = Set{Tuple{Symbol,Int,Float64,Float64,Int}}()
    for (index, chain) in enumerate(chains)
        _exact_keys(chain, _COMBINED_CHAIN_FIELDS, "combined chain $index")
        task = _exact_keys(chain["task"], _COMBINED_TASK_FIELDS, "combined chain $index task")
        raw = _exact_keys(chain["raw_bins"], _COMBINED_RAW_FIELDS, "combined chain $index raw_bins")
        _validate_chain_provenance(chain["provenance"], combined, index)
        bins = _schema_int(chain["completed_bins"], "combined chain $index completed_bins")
        bins > 0 || throw(ArgumentError("combined chain must contain bins"))
        for name in _COMBINED_RAW_FIELDS[1:6]
            _schema_column(raw, name, bins)
        end
        histograms = raw["cut_histogram"]
        histograms isa AbstractVector && length(histograms) == bins ||
            throw(ArgumentError("combined cut_histogram has the wrong length"))
        lattice_value = task["lattice"]
        lattice_value isa AbstractString || throw(ArgumentError("combined task lattice must be a string"))
        task_record = ClusterTask(
            _schema_int(task["schema_version"], "combined task schema_version"),
            Symbol(lattice_value),
            _schema_int(task["L"], "combined task L"),
            _schema_float(task["J"], "combined task J"),
            _schema_float(task["h"], "combined task h"),
            _schema_float(task["c"], "combined task c"),
            _schema_int(task["replica"], "combined task replica"),
            _read_seed(task["seed"]),
            _schema_int(task["thermalization_sweeps"], "combined task thermalization_sweeps"),
            _schema_int(task["measurement_sweeps"], "combined task measurement_sweeps"),
            _schema_int(task["base_bin_size"], "combined task base_bin_size"),
            _schema_int(task["checkpoint_interval_bins"], "combined task checkpoint_interval_bins"),
            String(task["output_path"]),
        )
        _validate_frozen_task(validate_task(task_record))
        chain_id = chain["task_id"]
        chain_hash = chain["task_hash"]
        chain_id isa AbstractString && chain_hash isa AbstractString ||
            throw(ArgumentError("combined task identity fields must be strings"))
        chain_id == task_id(task_record) && chain_hash == task_hash(task_record) &&
            task["canonical_task"] == canonical_task_string(task_record) ||
            throw(ArgumentError("combined task identity does not match task metadata"))
        String(chain_id) in seen_ids && throw(ArgumentError("combined data have a duplicate chain ID"))
        push!(seen_ids, String(chain_id))
        scientific = (task_record.lattice, task_record.L, task_record.h, task_record.c, task_record.replica)
        scientific in seen_groups && throw(ArgumentError("combined data have a duplicate scientific replica"))
        push!(seen_groups, scientific)
        push!(records, ReplicaBinderData(
            task_record.lattice, task_record.L, task_record.h, task_record.c,
            task_record.replica, String(chain_id), _schema_column(raw, "m_time2", bins),
            _schema_column(raw, "m_time4", bins),
        ))
    end
    _validate_complete_frozen_grid(records)
    return CombinedBinderData(
        String(combined["campaign_id"]),
        String(combined["campaign_checksum"]),
        String(combined["julia_manifest_sha256"]),
        String(combined["git_commit"]),
        String(combined["julia_version"]),
        String(combined["algorithm"]),
        Int(combined["observable_schema_version"]),
        snapshot.content_sha256,
        records,
    )
end

function _point_value(point, name::Symbol)
    hasproperty(point, name) || throw(ArgumentError("Binder point is missing $name"))
    return getproperty(point, name)
end

function _direct_rows(points, L_min::Int)
    rows = [point for point in points if Symbol(_point_value(point, :source)) === :direct && Int(_point_value(point, :L)) >= L_min]
    isempty(rows) && throw(ArgumentError("fit window contains no direct-anchor rows"))
    coordinates = [(Int(_point_value(row, :L)), Float64(_point_value(row, :h))) for row in rows]
    length(unique(coordinates)) == length(coordinates) ||
        throw(ArgumentError("primary fit rows must be independent direct anchors"))
    all(isfinite(Float64(_point_value(row, :Q))) for row in rows) ||
        throw(ArgumentError("Binder values must be finite"))
    all(row -> begin
        sigma = Float64(_point_value(row, :sigma))
        isfinite(sigma) && sigma > 0
    end, rows) || throw(ArgumentError("row uncertainties must be finite and positive"))
    return rows
end

function _parameter_names(model::Symbol, yt_mode::Symbol)
    model in FSS_MODELS || throw(ArgumentError("unsupported FSS model: $model"))
    yt_mode in (:fixed, :free) || throw(ArgumentError("unsupported yt mode: $yt_mode"))
    base = model === :M1 ? (:hc, :Qc, :a1, :b1) :
           model === :M2 ? (:hc, :Qc, :a1, :a2, :b1) :
                           (:hc, :Qc, :a1, :b1, :b2)
    return yt_mode === :free ? (base..., :yt) : base
end

function _fss_model(model::Symbol, yt_mode::Symbol)
    names = _parameter_names(model, yt_mode)
    function evaluate(x, p)
        values = NamedTuple{names}(Tuple(p))
        yt = yt_mode === :fixed ? FSS_YT_FIXED : values.yt
        result = Vector{eltype(p)}(undef, size(x, 1))
        for index in axes(x, 1)
            L = x[index, 1]
            u = x[index, 2] - values.hc
            Q = values.Qc + values.a1 * u * L^yt + values.b1 * L^FSS_YI_FIXED
            model === :M2 && (Q += values.a2 * u^2 * L^(2yt))
            model === :M3 && (Q += values.b2 * L^-2)
            result[index] = Q
        end
        return result
    end
    return evaluate
end

function _initial_parameters(model::Symbol, yt_mode::Symbol, x, y)
    h_low, h_high = extrema(@view x[:, 2])
    h_low < h_high || throw(ArgumentError("fit rows must contain multiple field anchors"))
    names = _parameter_names(model, yt_mode)
    initial_values = Dict{Symbol,Float64}(
        :hc => (h_low + h_high) / 2,
        :Qc => sum(y) / length(y),
        :a1 => -0.05,
        :a2 => 0.0,
        :b1 => -0.02,
        :b2 => 0.0,
        :yt => FSS_YT_FIXED,
    )
    return [initial_values[name] for name in names]
end

function _yt_strictly_interior(value::Float64)
    lower, upper = FSS_YT_BOUNDS
    scale = max(abs(value), abs(lower), abs(upper), 1.0)
    ulp = max(eps(value), eps(lower), eps(upper), eps(scale))
    margin = 1024ulp
    return value > lower + margin && value < upper - margin
end

"""Fit one pre-approved primary Binder window using exact row uncertainties."""
function fit_binder_window(
    points;
    model::Symbol,
    L_min::Integer,
    yt_mode::Symbol,
    covariance=nothing,
)
    names = _parameter_names(model, yt_mode)
    L_min_int = Int(L_min)
    L_min_int in FSS_L_MINS || throw(ArgumentError("unsupported FSS L_min: $L_min_int"))
    rows = _direct_rows(points, L_min_int)
    sizes = sort!(unique(Int(_point_value(row, :L)) for row in rows))
    length(sizes) >= 4 || throw(ArgumentError("fit window requires at least four distinct sizes"))

    x = Matrix{Float64}(undef, length(rows), 2)
    y = Vector{Float64}(undef, length(rows))
    sigma = Vector{Float64}(undef, length(rows))
    for (index, row) in enumerate(rows)
        x[index, 1] = Float64(_point_value(row, :L))
        x[index, 2] = Float64(_point_value(row, :h))
        y[index] = Float64(_point_value(row, :Q))
        sigma[index] = Float64(_point_value(row, :sigma))
    end
    initial = _initial_parameters(model, yt_mode, x, y)
    weights = if covariance === nothing
        LsqFit.PrecisionWeights(1.0 ./ sigma .^ 2)
    else
        matrix = Matrix{Float64}(covariance)
        size(matrix) == (length(rows), length(rows)) ||
            throw(ArgumentError("row covariance has the wrong dimensions"))
        all(isfinite, matrix) && issymmetric(matrix) && isposdef(Symmetric(matrix)) ||
            throw(ArgumentError("row covariance must be finite symmetric positive-definite"))
        LsqFit.PrecisionMatrix(inv(Symmetric(matrix)))
    end
    fit = try
        if yt_mode === :free
            lower = fill(-Inf, length(initial))
            upper = fill(Inf, length(initial))
            lower[end], upper[end] = FSS_YT_BOUNDS
            curve_fit(
                _fss_model(model, yt_mode), x, y, weights, initial;
                lower=lower, upper=upper, maxIter=10_000)
        else
            curve_fit(
                _fss_model(model, yt_mode), x, y, weights, initial; maxIter=10_000)
        end
    catch error
        error isa InterruptException && rethrow()
        nothing
    end
    values = fit === nothing ? copy(initial) : Float64.(coef(fit))
    parameters = NamedTuple{names}(Tuple(values))
    parameter_covariance = try
        fit === nothing && error("fit unavailable")
        raw = Matrix{Float64}(LsqFit.vcov(fit))
        (raw + raw') / 2
    catch
        fill(NaN, length(values), length(values))
    end
    dof_value = length(y) - length(values)
    chi2 = fit === nothing ? Inf : sum(abs2, fit.resid)
    reduced_chi2 = dof_value > 0 ? chi2 / dof_value : Inf
    reasons = String[]
    converged = fit !== nothing && fit.converged
    converged || push!(reasons, "optimizer did not converge")
    dof_value >= 2 || push!(reasons, "fewer than two degrees of freedom")
    covariance_eigenvalues = all(isfinite, parameter_covariance) && issymmetric(parameter_covariance) ?
                             eigvals(Symmetric(parameter_covariance)) : Float64[]
    covariance_ok = !isempty(covariance_eigenvalues) && all(isfinite, covariance_eigenvalues) &&
                    all(>(0), covariance_eigenvalues) && fit !== nothing &&
                    rank(fit.jacobian) == length(values)
    covariance_ok || push!(reasons, "parameter covariance is not finite symmetric positive-definite")
    reduced_chi2 <= 2.0 || push!(reasons, "reduced chi-square exceeds 2.0")
    yt_mode === :free && !_yt_strictly_interior(parameters.yt) &&
        push!(reasons, "free yt is at or numerically active on a frozen bound")
    return BinderFitResult(
        model,
        L_min_int,
        yt_mode,
        names,
        parameters,
        parameter_covariance,
        chi2,
        dof_value,
        reduced_chi2,
        converged,
        isempty(reasons),
        reasons,
        length(rows),
        sizes,
    )
end

"""Enumerate every frozen model, size window, and thermal-exponent mode."""
function enumerate_binder_fits(points)
    return [
        fit_binder_window(points; model=model, L_min=L_min, yt_mode=yt_mode)
        for model in FSS_MODELS for L_min in FSS_L_MINS for yt_mode in (:fixed, :free)
        if length(unique(Int(_point_value(point, :L)) for point in points
                         if Symbol(_point_value(point, :source)) === :direct &&
                            Int(_point_value(point, :L)) >= L_min)) >= 4
    ]
end

"""Parametric bootstrap used only to test synthetic critical-point recovery."""
function bootstrap_binder_window(
    points;
    model::Symbol,
    L_min::Integer,
    yt_mode::Symbol,
    seed::Integer,
    draws::Integer,
)
    draws > 1 || throw(ArgumentError("bootstrap draws must exceed one"))
    rng = Xoshiro(seed)
    samples = Float64[]
    sizehint!(samples, Int(draws))
    for _ in 1:Int(draws)
        perturbed = [
            merge(point, (Q=Float64(_point_value(point, :Q)) +
                             Float64(_point_value(point, :sigma)) * randn(rng),))
            for point in points
        ]
        fit = fit_binder_window(perturbed; model=model, L_min=L_min, yt_mode=yt_mode)
        fit.converged && isfinite(fit.parameters.hc) ||
            throw(ArgumentError("synthetic bootstrap fit failed to converge"))
        push!(samples, fit.parameters.hc)
    end
    return samples
end

_scientific_group(record::ReplicaBinderData) = (record.lattice, record.L, record.h, record.c)

function _replica_groups(records::AbstractVector{<:ReplicaBinderData})
    groups = Dict{Tuple{Symbol,Int,Float64,Float64},Vector{ReplicaBinderData}}()
    for record in records
        push!(get!(groups, _scientific_group(record), ReplicaBinderData[]), record)
    end
    for (key, group) in groups
        replicas = getfield.(group, :replica)
        length(unique(replicas)) == length(replicas) ||
            throw(ArgumentError("duplicate replicas in scientific group $key"))
        length(group) >= 2 || throw(ArgumentError("scientific group $key requires at least two replicas"))
        sort!(group; by=record -> record.replica)
    end
    return groups
end


function _binder_point(group::AbstractVector{<:ReplicaBinderData}; sigma::Union{Nothing,Float64}=nothing)
    first_record = first(group)
    pooled_m2 = reduce(vcat, getfield.(group, :m2_bins))
    pooled_m4 = reduce(vcat, getfield.(group, :m4_bins))
    estimate = binder_from_bins(pooled_m2, pooled_m4)
    Q = estimate.mean
    uncertainty = sigma === nothing ? estimate.stderr : sigma
    isfinite(uncertainty) && uncertainty > 0 ||
        throw(ArgumentError("paired-bin Binder uncertainty must be finite and positive"))
    return (
        lattice=first_record.lattice,
        L=first_record.L,
        h=first_record.h,
        c=first_record.c,
        Q=Q,
        sigma=uncertainty,
        source=:direct,
    )
end

function _binder_points(
    groups::Dict{Tuple{Symbol,Int,Float64,Float64},Vector{ReplicaBinderData}},
    lattice::Symbol,
    c::Float64;
    sigmas=nothing,
)
    keys_for_lattice = sort!(
        [key for key in keys(groups) if key[1] === lattice && key[4] == c];
        by=key -> (key[2], key[3]),
    )
    isempty(keys_for_lattice) && throw(ArgumentError("missing calibration groups for lattice=$lattice c=$c"))
    return [
        _binder_point(groups[key]; sigma=sigmas === nothing ? nothing : sigmas[key])
        for key in keys_for_lattice
    ]
end

function _resampled_primary_points(groups, lattice::Symbol, rng::AbstractRNG, sigmas)
    keys_for_lattice = sort!(
        [key for key in keys(groups) if key[1] === lattice && key[4] == 1.0];
        by=key -> (key[2], key[3]),
    )
    return [
        begin
            group = groups[key]
            selected = [group[rand(rng, eachindex(group))] for _ in eachindex(group)]
            _binder_point(selected; sigma=sigmas[key])
        end for key in keys_for_lattice
    ]
end

function _accepted_fit(points, model::Symbol, L_min::Int, yt_mode::Symbol, label::String)
    fit = fit_binder_window(points; model=model, L_min=L_min, yt_mode=yt_mode)
    fit.accepted || throw(ArgumentError("required accepted fit is absent for $label: $(join(fit.rejection_reasons, "; "))"))
    return fit
end

"""Jointly propagate the critical-field ratio by whole-replica group bootstrap."""
function bootstrap_critical_ratio(
    records::AbstractVector{<:ReplicaBinderData};
    model::Symbol=:M1,
    L_min::Integer=8,
    yt_mode::Symbol=:fixed,
    seed::Integer=FSS_BOOTSTRAP_SEED,
    draws::Integer=FSS_BOOTSTRAP_DRAWS,
)
    draws > 1 || throw(ArgumentError("bootstrap draws must exceed one"))
    groups = _replica_groups(records)
    primary_keys = [key for key in keys(groups) if key[4] == 1.0]
    sigmas = Dict(key => _binder_point(groups[key]).sigma for key in primary_keys)
    triangle_rng = Xoshiro(seed)
    honeycomb_rng = Xoshiro(seed + 1)
    samples = Float64[]
    sizehint!(samples, Int(draws))
    for draw in 1:Int(draws)
        triangle_points = _resampled_primary_points(groups, :triangle, triangle_rng, sigmas)
        honeycomb_points = _resampled_primary_points(groups, :honeycomb, honeycomb_rng, sigmas)
        triangle_fit = _accepted_fit(
            triangle_points, model, Int(L_min), yt_mode, "triangle bootstrap draw $draw")
        honeycomb_fit = _accepted_fit(
            honeycomb_points, model, Int(L_min), yt_mode, "honeycomb bootstrap draw $draw")
        push!(samples, triangle_fit.parameters.hc / honeycomb_fit.parameters.hc)
    end
    return RatioBootstrapResult(samples, Int(seed), Int(draws))
end

_fit_key(fit::BinderFitResult) = (fit.model, fit.L_min, fit.yt_mode)

function _paired_ratio(triangle_fits, honeycomb_fits, key)
    triangle_fit = get(triangle_fits, key, nothing)
    honeycomb_fit = get(honeycomb_fits, key, nothing)
    triangle_fit !== nothing && honeycomb_fit !== nothing &&
        triangle_fit.accepted && honeycomb_fit.accepted || return nothing
    return triangle_fit.parameters.hc / honeycomb_fit.parameters.hc
end

function _systematic_envelopes(triangle_fits, honeycomb_fits, central_ratio::Float64)
    baseline_ratios = Dict{Int,Float64}()
    for L_min in FSS_L_MINS
        ratio = _paired_ratio(triangle_fits, honeycomb_fits, (:M1, L_min, :fixed))
        ratio === nothing || (baseline_ratios[L_min] = ratio)
    end
    length(baseline_ratios) >= 2 ||
        throw(ArgumentError("required accepted fit-window comparisons are absent"))
    sigma_window = maximum(abs(ratio - central_ratio) for ratio in values(baseline_ratios))

    relative_shifts = Float64[]
    for L_min in FSS_L_MINS, model in FSS_MODELS, yt_mode in (:fixed, :free)
        model === :M1 && yt_mode === :fixed && continue
        ratio = _paired_ratio(triangle_fits, honeycomb_fits, (model, L_min, yt_mode))
        ratio === nothing && continue
        baseline = get(baseline_ratios, L_min, nothing)
        baseline === nothing && throw(ArgumentError(
            "accepted FSS comparison lacks an accepted M1/fixed baseline at L_min=$L_min"))
        push!(relative_shifts, abs(ratio - baseline))
    end
    isempty(relative_shifts) &&
        throw(ArgumentError("required accepted FSS comparisons are absent"))
    return (sigma_window=sigma_window, sigma_fss=maximum(relative_shifts))
end

function _binder_slope(fit::BinderFitResult, L::Int, h::Float64)
    yt = fit.yt_mode === :fixed ? FSS_YT_FIXED : fit.parameters.yt
    slope = fit.parameters.a1 * L^yt
    fit.model === :M2 &&
        (slope += 2fit.parameters.a2 * (h - fit.parameters.hc) * L^(2yt))
    isfinite(slope) && !iszero(slope) || throw(ArgumentError("fitted Binder slope is invalid"))
    return slope
end

function _thermal_scenario_points(groups, lattice::Symbol, L::Int, c::Float64)
    points = sort!(
        [point for point in _binder_points(groups, lattice, c) if point.L == L];
        by=point -> point.h,
    )
    length(points) == length(_FROZEN_X_ANCHORS) ||
        throw(ArgumentError("missing matched thermal calibration anchors for $lattice L=$L c=$c"))
    return points
end

function _thermal_ratio_envelope(
    groups,
    triangle_fit::BinderFitResult,
    honeycomb_fit::BinderFitResult,
    R::Float64,
)
    shifts = Float64[]
    triangle_primary = Dict(
        (point.L, point.h) => point for point in _binder_points(groups, :triangle, 1.0))
    honeycomb_primary = Dict(
        (point.L, point.h) => point for point in _binder_points(groups, :honeycomb, 1.0))
    honeycomb_hc = honeycomb_fit.parameters.hc
    for L in (24, 48), c in (1.5, 2.0)
        triangle_points = _thermal_scenario_points(groups, :triangle, L, c)
        honeycomb_points = _thermal_scenario_points(groups, :honeycomb, L, c)
        for anchor_index in eachindex(_FROZEN_X_ANCHORS)
            triangle_point = triangle_points[anchor_index]
            honeycomb_point = honeycomb_points[anchor_index]
            triangle_reference = get(triangle_primary, (L, triangle_point.h), nothing)
            honeycomb_reference = get(honeycomb_primary, (L, honeycomb_point.h), nothing)
            triangle_reference === nothing &&
                throw(ArgumentError("thermal calibration lacks a matching triangle primary anchor"))
            honeycomb_reference === nothing &&
                throw(ArgumentError("thermal calibration lacks a matching honeycomb primary anchor"))
            delta_triangle = (triangle_point.Q - triangle_reference.Q) /
                             _binder_slope(triangle_fit, L, triangle_point.h)
            delta_honeycomb = (honeycomb_point.Q - honeycomb_reference.Q) /
                              _binder_slope(honeycomb_fit, L, honeycomb_point.h)
            delta_R = delta_triangle / honeycomb_hc - R * delta_honeycomb / honeycomb_hc
            push!(shifts, abs(delta_R))
        end
    end
    return maximum(shifts)
end

"""Fit both lattices and report the frozen Route A preliminary error decomposition."""
function analyze_route_a_replicas(
    records::AbstractVector{<:ReplicaBinderData};
    seed::Integer=FSS_BOOTSTRAP_SEED,
    draws::Integer=FSS_BOOTSTRAP_DRAWS,
)
    groups = _replica_groups(records)
    triangle_points = _binder_points(groups, :triangle, 1.0)
    honeycomb_points = _binder_points(groups, :honeycomb, 1.0)
    triangle_all = enumerate_binder_fits(triangle_points)
    honeycomb_all = enumerate_binder_fits(honeycomb_points)
    length(triangle_all) == 24 && length(honeycomb_all) == 24 ||
        throw(ArgumentError("required frozen fit windows are absent"))
    triangle_fits = Dict(_fit_key(fit) => fit for fit in triangle_all)
    honeycomb_fits = Dict(_fit_key(fit) => fit for fit in honeycomb_all)
    central_key = (:M1, 8, :fixed)
    central_ratio = _paired_ratio(triangle_fits, honeycomb_fits, central_key)
    central_ratio === nothing && throw(ArgumentError("required accepted primary fit is absent"))
    triangle_central = triangle_fits[central_key]
    honeycomb_central = honeycomb_fits[central_key]

    systematic = _systematic_envelopes(triangle_fits, honeycomb_fits, central_ratio)
    sigma_window = systematic.sigma_window
    sigma_fss = systematic.sigma_fss

    bootstrap = bootstrap_critical_ratio(
        records; model=:M1, L_min=8, yt_mode=:fixed, seed=seed, draws=draws)
    sigma_stat = std(bootstrap.samples)
    sigma_c = _thermal_ratio_envelope(
        groups, triangle_central, honeycomb_central, central_ratio)
    sigma_total = sqrt(sigma_stat^2 + sigma_window^2 + sigma_fss^2 + sigma_c^2)
    return (
        status=ROUTE_A_PRELIMINARY_STATUS,
        R=central_ratio,
        Delta=central_ratio - sqrt(5),
        critical_points=(
            triangle=triangle_central.parameters.hc,
            honeycomb=honeycomb_central.parameters.hc,
        ),
        errors=(
            sigma_stat=sigma_stat,
            sigma_window=sigma_window,
            sigma_fss=sigma_fss,
            sigma_c=sigma_c,
            sigma_total_preliminary=sigma_total,
        ),
        bootstrap=(seed=Int(seed), draws=Int(draws)),
        fit_windows=vcat(triangle_all, honeycomb_all),
    )
end
