using LinearAlgebra

"""Non-secular Redfield generator in the laboratory basis for a frozen H."""
function redfield_generator(model::SpinBosonModel, H::AbstractMatrix)
    spectral = eigen(Hermitian(H))
    energies, basis = spectral.values, spectral.vectors
    S = model.coupling_operator
    S_energy = basis' * S * basis
    Γ = [bath_gamma(model, energies[a] - energies[b]) for a in 1:2, b in 1:2]
    A_energy = [S_energy[m, n] * Γ[n, m] for m in 1:2, n in 1:2]
    B_energy = [S_energy[m, n] * conj(Γ[m, n]) for m in 1:2, n in 1:2]
    A, B = basis * A_energy * basis', basis * B_energy * basis'
    SA, BS = S * A, B * S
    redfield = -kron(I(2), SA) + kron(transpose(S), A) +
               kron(transpose(B), S) - kron(transpose(BS), I(2))
    coherent = -im * (kron(I(2), H) - kron(transpose(H), I(2)))
    return Matrix(coherent + redfield)
end

redfield_generator(model::SpinBosonModel) = redfield_generator(model, model.omega / 2 * SIGMA_X)

const REDFIELD_INITIAL_STATE = ComplexF64[1, 0, 0, 0] # vec(|↑z⟩⟨↑z|), lab basis

"""Static effective-Hamiltonian fixture with one exp(LΔt) and recurrence."""
function redfield_magnus!(values::AbstractVector{<:Real}, model::SpinBosonModel, dt::Real)
    dt > 0 || throw(ArgumentError("Redfield step must be positive"))
    state = copy(REDFIELD_INITIAL_STATE)
    step = exp(redfield_generator(model) * dt)
    for i in eachindex(values)
        values[i] = real(tr(SIGMA_Z * reshape(state, 2, 2)))
        state = step * state
    end
    return values
end

function period_redfield_steps(model::SpinBosonModel, ωd::Real, dt::Real)
    grid = period_grid(ωd, dt)
    isapprox(grid.dt, dt; atol=grid.tolerance, rtol=0) ||
        throw(ArgumentError("Redfield step must close one drive period exactly"))
    return [exp(redfield_generator(model,
                system_hamiltonian(model, (phase - 0.5) * grid.dt, ωd)) * grid.dt)
            for phase in 1:grid.M]
end

"""Period-resolved driven Redfield propagation, with one cached exp(LₘΔt) per phase."""
function redfield_magnus!(values::AbstractVector{<:Real}, model::SpinBosonModel,
                           ωd::Real, dt::Real)
    dt > 0 || throw(ArgumentError("Redfield step must be positive"))
    steps = period_redfield_steps(model, ωd, dt)
    state = copy(REDFIELD_INITIAL_STATE)
    for (index, i) in enumerate(eachindex(values))
        values[i] = real(tr(SIGMA_Z * reshape(state, 2, 2)))
        index == length(values) && break
        state = steps[mod1(index, length(steps))] * state
    end
    return values
end

"""Independent formula oracle: direct period-resolved exp(LₘΔt) products."""
function redfield_magnus_paper_formula(model::SpinBosonModel, ωd::Real,
                                       dt::Real, count::Integer)
    count > 0 || throw(ArgumentError("output count must be positive"))
    grid = period_grid(ωd, dt)
    isapprox(grid.dt, dt; atol=grid.tolerance, rtol=0) ||
        throw(ArgumentError("Redfield step must close one drive period exactly"))
    state = copy(REDFIELD_INITIAL_STATE)
    values = Vector{Float64}(undef, count)
    for index in 1:count
        values[index] = real(tr(SIGMA_Z * reshape(state, 2, 2)))
        index == count && break
        phase = mod1(index, grid.M)
        Hphase = system_hamiltonian(model, (phase - 0.5) * grid.dt, ωd)
        state = exp(redfield_generator(model, Hphase) * grid.dt) * state
    end
    return values
end

"""Legacy static formula fixture retained for the no-drive recurrence test."""
function redfield_magnus_paper_formula(model::SpinBosonModel, dt::Real, count::Integer)
    count > 0 || throw(ArgumentError("output count must be positive"))
    L = redfield_generator(model)
    return [real(tr(SIGMA_Z * reshape(exp(L * ((i - 1) * dt)) * REDFIELD_INITIAL_STATE, 2, 2)))
            for i in 1:count]
end
