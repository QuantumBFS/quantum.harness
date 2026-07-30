struct ScalingFit
    status::Symbol
    hc::Float64
    stderr_hc::Float64
    Rc::Float64
    coefficients::Vector{Float64}
    chi2::Float64
    dof::Int
    pvalue::Float64
    covariance_condition::Float64
    Lmin::Int
    corrections::Int
    yt::Float64
    yi::Float64
end

struct RatioBootstrap
    mean::Float64
    stderr::Float64
    n_success::Int
    n_failed::Int
end

struct ScalingBootstrap
    mean_hc::Float64
    stderr_hc::Float64
    n_success::Int
    n_failed::Int
end

function _normal_ccdf(z::Float64)
    x = abs(z)
    t = 1 / (1 + 0.2316419x)
    density = exp(-0.5x^2) / sqrt(2pi)
    tail = density * t * (
        0.319381530 + t * (-0.356563782 + t * (1.781477937 +
        t * (-1.821255978 + t * 1.330274429)))
    )
    return z >= 0 ? tail : 1 - tail
end

function _chisq_pvalue(chi2::Float64, dof::Int)
    dof > 0 || return 0.0
    chi2 >= 0 || return 0.0
    z = ((chi2 / dof)^(1 / 3) - (1 - 2 / (9dof))) / sqrt(2 / (9dof))
    return clamp(_normal_ccdf(z), 0.0, 1.0)
end

function _design_matrix(rows, hc::Float64, yt::Float64, yi::Float64, corrections::Int)
    columns = corrections == 1 ? 4 : 3
    matrix = Matrix{Float64}(undef, length(rows), columns)
    for (index, row) in enumerate(rows)
        L = Float64(row.L)
        delta = Float64(row.h) - hc
        matrix[index, 1] = 1.0
        matrix[index, 2] = delta * L^yt
        matrix[index, 3] = delta^2 * L^(2yt)
        corrections == 1 && (matrix[index, 4] = L^yi)
    end
    return matrix
end

function _profile_fit(rows, hc::Float64, yt::Float64, yi::Float64, corrections::Int)
    design = _design_matrix(rows, hc, yt, yi, corrections)
    values = Float64[row.value for row in rows]
    inverse_sigma = Float64[1 / row.stderr for row in rows]
    weighted_design = design .* inverse_sigma
    weighted_values = values .* inverse_sigma
    coefficients = weighted_design \ weighted_values
    residuals = (values - design * coefficients) .* inverse_sigma
    return sum(abs2, residuals), coefficients, design
end

function _golden_minimum(objective, lower::Float64, upper::Float64)
    ratio = (sqrt(5.0) - 1) / 2
    left = upper - ratio * (upper - lower)
    right = lower + ratio * (upper - lower)
    fleft, fright = objective(left), objective(right)
    for _ in 1:120
        if fleft <= fright
            upper, right, fright = right, left, fleft
            left = upper - ratio * (upper - lower)
            fleft = objective(left)
        else
            lower, left, fleft = left, right, fright
            right = lower + ratio * (upper - lower)
            fright = objective(right)
        end
        upper - lower <= 2e-13 * max(1.0, abs(lower), abs(upper)) && break
    end
    return (lower + upper) / 2
end

function fit_wrapping_scaling(
    data::AbstractVector;
    Lmin::Integer,
    corrections::Integer,
    yt::Real,
    yi::Real,
    hc_bounds,
)
    isempty(data) && throw(ArgumentError("wrapping data must not be empty"))
    corrections in (0, 1) || throw(ArgumentError("corrections must be zero or one"))
    checked_yt = Float64(yt)
    checked_yi = Float64(yi)
    isfinite(checked_yt) && checked_yt > 0 || throw(ArgumentError("yt must be positive"))
    isfinite(checked_yi) && checked_yi < 0 || throw(ArgumentError("yi must be negative"))
    length(hc_bounds) == 2 || throw(ArgumentError("hc_bounds requires two values"))
    lower, upper = Float64(hc_bounds[1]), Float64(hc_bounds[2])
    isfinite(lower) && isfinite(upper) && lower < upper ||
        throw(ArgumentError("invalid hc bounds"))
    for row in data
        row.L > 0 || throw(ArgumentError("L must be positive"))
        all(isfinite, (Float64(row.h), Float64(row.value), Float64(row.stderr))) ||
            throw(ArgumentError("wrapping rows must be finite"))
        row.stderr > 0 || throw(ArgumentError("wrapping stderr must be positive"))
    end
    rows = [row for row in data if row.L >= Lmin]
    nparameters = 4 + corrections
    length(rows) > nparameters || throw(ArgumentError("insufficient rows for scaling fit"))

    objective(hc) = first(_profile_fit(rows, hc, checked_yt, checked_yi, corrections))
    hc = _golden_minimum(objective, lower, upper)
    chi2, coefficients, design = _profile_fit(rows, hc, checked_yt, checked_yi, corrections)
    derivative_hc = Float64[
        -coefficients[2] * row.L^checked_yt -
        2coefficients[3] * (row.h - hc) * row.L^(2checked_yt)
        for row in rows
    ]
    jacobian = hcat(design, derivative_hc)
    inverse_sigma = Float64[1 / row.stderr for row in rows]
    weighted_jacobian = jacobian .* inverse_sigma
    normal = transpose(weighted_jacobian) * weighted_jacobian
    condition = cond(normal)
    isfinite(condition) && condition < 1e14 ||
        throw(ArgumentError("scaling covariance is singular or ill-conditioned"))
    covariance = inv(normal)
    stderr_hc = sqrt(max(0.0, covariance[end, end]))
    dof = length(rows) - nparameters
    pvalue = _chisq_pvalue(chi2, dof)
    return ScalingFit(
        :pass, hc, stderr_hc, coefficients[1], coefficients, chi2, dof, pvalue,
        condition, Int(Lmin), Int(corrections), checked_yt, checked_yi,
    )
end

function fit_window_record(data::AbstractVector; Lmin::Integer, corrections::Integer, options...)
    try
        fit = fit_wrapping_scaling(
            data; Lmin=Lmin, corrections=corrections, options...,
        )
        return (
            status="pass",
            error=nothing,
            hc=fit.hc,
            stderr_hc=fit.stderr_hc,
            Rc=fit.Rc,
            coefficients=fit.coefficients,
            chi2=fit.chi2,
            dof=fit.dof,
            pvalue=fit.pvalue,
            covariance_condition=fit.covariance_condition,
            Lmin=fit.Lmin,
            corrections=fit.corrections,
            yt=fit.yt,
            yi=fit.yi,
        )
    catch error
        error isa ArgumentError || rethrow()
        return (
            status="fail",
            error=sprint(showerror, error),
            hc=nothing,
            stderr_hc=nothing,
            Rc=nothing,
            coefficients=Float64[],
            chi2=nothing,
            dof=nothing,
            pvalue=nothing,
            covariance_condition=nothing,
            Lmin=Int(Lmin),
            corrections=Int(corrections),
            yt=Float64(get(options, :yt, NaN)),
            yi=Float64(get(options, :yi, NaN)),
        )
    end
end

_window_value(window, name::Symbol) =
    window isa AbstractDict ? window[String(name)] : getproperty(window, name)

function evaluate_regression_gate(
    windows::AbstractVector;
    reference::Real,
    absolute_tolerance::Real,
    sigma_multiplier::Real,
    declared_systematic::Real,
)
    isempty(windows) && throw(ArgumentError("regression gate requires fit windows"))
    checked_reference = Float64(reference)
    checked_tolerance = Float64(absolute_tolerance)
    checked_multiplier = Float64(sigma_multiplier)
    checked_systematic = Float64(declared_systematic)
    all(isfinite, (checked_reference, checked_tolerance, checked_multiplier, checked_systematic)) ||
        throw(ArgumentError("regression gate inputs must be finite"))
    checked_tolerance >= 0 && checked_multiplier >= 0 && checked_systematic >= 0 ||
        throw(ArgumentError("regression gate tolerances must be nonnegative"))

    passed = [window for window in windows if _window_value(window, :status) == "pass"]
    failed_windows = length(windows) - length(passed)
    isempty(passed) && throw(ArgumentError("regression gate has no successful fit"))
    primary = first(passed)
    primary_hc = Float64(_window_value(primary, :hc))
    statistical = Float64(_window_value(primary, :stderr_hc))
    isfinite(primary_hc) && isfinite(statistical) && statistical >= 0 ||
        throw(ArgumentError("primary fit has invalid uncertainty"))
    shifts = Float64[abs(Float64(_window_value(window, :hc)) - primary_hc) for window in passed]
    observed_shift = maximum(shifts)
    window_stable = observed_shift <= checked_systematic + 16eps(max(1.0, observed_shift))
    combined = hypot(statistical, checked_systematic)
    threshold = max(checked_tolerance, checked_multiplier * combined)
    reference_difference = abs(primary_hc - checked_reference)
    reasons = String[]
    failed_windows == 0 || push!(reasons, "failed_fit_window")
    window_stable || push!(reasons, "window_shift_exceeds_declared_systematic")
    reference_difference <= threshold || push!(reasons, "critical_point_outside_gate")
    return (
        status=isempty(reasons) ? "pass" : "fail",
        reasons=reasons,
        primary_hc=primary_hc,
        reference=checked_reference,
        reference_difference=reference_difference,
        statistical_stderr=statistical,
        declared_systematic=checked_systematic,
        observed_window_shift=observed_shift,
        combined_stderr=combined,
        acceptance_threshold=threshold,
        window_stable=window_stable,
        failed_windows=failed_windows,
    )
end

function _normal_draw!(rng::CounterRNG)
    u1 = max(rand_float!(rng), eps(Float64))
    u2 = rand_float!(rng)
    return sqrt(-2log(u1)) * cos(2pi * u2)
end

function bootstrap_ratio(fits::AbstractVector{ScalingFit}; replicas::Integer, seed::Integer)
    length(fits) == 2 || throw(ArgumentError("ratio bootstrap requires two fits"))
    replicas > 1 || throw(ArgumentError("at least two bootstrap replicas are required"))
    all(fit.status == :pass && fit.stderr_hc > 0 for fit in fits) ||
        throw(ArgumentError("ratio bootstrap requires valid fits"))
    rng = CounterRNG(seed)
    ratios = Float64[]
    failed = 0
    for _ in 1:replicas
        numerator = fits[1].hc + fits[1].stderr_hc * _normal_draw!(rng)
        denominator = fits[2].hc + fits[2].stderr_hc * _normal_draw!(rng)
        if isfinite(numerator) && isfinite(denominator) && denominator != 0
            push!(ratios, numerator / denominator)
        else
            failed += 1
        end
    end
    length(ratios) >= 2 || throw(ArgumentError("ratio bootstrap produced too few replicas"))
    return RatioBootstrap(mean(ratios), std(ratios), length(ratios), failed)
end

function bootstrap_scaling(
    data::AbstractVector;
    replicas::Integer,
    seed::Integer,
    fit_options...,
)
    replicas > 1 || throw(ArgumentError("at least two bootstrap replicas are required"))
    isempty(data) && throw(ArgumentError("wrapping data must not be empty"))
    point_keys = sort!(unique((Int(row.L), Float64(row.h)) for row in data))
    by_point = Dict(key => [row for row in data if (Int(row.L), Float64(row.h)) == key]
                    for key in point_keys)
    all(length(rows) >= 2 for rows in values(by_point)) ||
        throw(ArgumentError("whole-replica bootstrap needs two chains per point"))
    rng = CounterRNG(seed)
    estimates = Float64[]
    failed = 0
    for _ in 1:replicas
        sample = NamedTuple[]
        for key in point_keys
            chains = by_point[key]
            for _ in eachindex(chains)
                push!(sample, chains[rand_int!(rng, length(chains))])
            end
        end
        try
            fit = fit_wrapping_scaling(sample; fit_options...)
            isfinite(fit.hc) ? push!(estimates, fit.hc) : (failed += 1)
        catch error
            error isa ArgumentError || rethrow()
            failed += 1
        end
    end
    length(estimates) >= 2 || throw(ArgumentError("too few successful scaling bootstraps"))
    return ScalingBootstrap(mean(estimates), std(estimates), length(estimates), failed)
end
