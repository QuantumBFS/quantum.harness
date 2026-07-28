using SpecialFunctions

"""Zero-temperature Ohmic bath correlation α(t)=αωc²/(1+iωct)²."""
bath_correlation(model::SpinBosonModel, t::Real) =
    model.alpha * (model.omega_c / (1 + im * model.omega_c * t))^2

"""One-sided Fourier transform Γ(ω) used by the non-secular Redfield generator."""
function bath_gamma(model::SpinBosonModel, ω::Real)
    model.alpha == 0 && return 0.0 + 0.0im
    re = ω > 0 ? π * model.alpha * ω * exp(-ω / model.omega_c) : 0.0
    principal_value = if ω > 0
        exp(-ω / model.omega_c) * expinti(ω / model.omega_c)
    elseif ω < 0
        -exp(abs(ω) / model.omega_c) * expint(abs(ω) / model.omega_c)
    else
        0.0
    end
    return re + im * model.alpha * (-model.omega_c + ω * principal_value)
end
