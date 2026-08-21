function _finite_float(name::AbstractString, value::Real)
    converted = Float64(value)
    isfinite(converted) || throw(ArgumentError("$name must be finite"))
    return converted
end

function _positive_coupling(J::Real)
    coupling = _finite_float("J", J)
    coupling > 0 || throw(ArgumentError("J must be positive"))
    return coupling
end

function log_weight(
    J::Real,
    h::Real,
    hopping_kinks::Integer,
    pairing_kinks::Integer,
    spin_time::Real,
)
    coupling = _positive_coupling(J)
    field = _finite_float("h", h)
    integrated_spin = _finite_float("spin_time", spin_time)
    hopping_kinks >= 0 || throw(ArgumentError("hopping_kinks must be nonnegative"))
    pairing_kinks >= 0 || throw(ArgumentError("pairing_kinks must be nonnegative"))

    return (hopping_kinks + pairing_kinks) * log(coupling) +
           field * integrated_spin
end

function log_ratio(
    J::Real;
    delta_kinks::Integer,
    h::Real,
    delta_spin_time::Real,
)
    coupling = _positive_coupling(J)
    field = _finite_float("h", h)
    integrated_spin_change = _finite_float("delta_spin_time", delta_spin_time)
    return delta_kinks * log(coupling) + field * integrated_spin_change
end

function metropolis_from_logratio(logratio::Real)
    ratio = _finite_float("logratio", logratio)
    return ratio >= 0 ? 1.0 : exp(ratio)
end
