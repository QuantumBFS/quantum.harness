using LinearAlgebra

function redfield_generator(model::SpinBosonModel)
    energies = [model.omega / 2, -model.omega / 2]
    coupling_energy_basis = ComplexF64[0 1; 1 0]
    H = Diagonal(energies)
    Γ = [bath_gamma(model, energies[a] - energies[b]) for a in 1:2, b in 1:2]
    A = [coupling_energy_basis[m, n] * Γ[n, m] for m in 1:2, n in 1:2]
    B = [coupling_energy_basis[m, n] * conj(Γ[m, n]) for m in 1:2, n in 1:2]
    SA, BS = coupling_energy_basis * A, B * coupling_energy_basis
    redfield = -kron(I(2), SA) + kron(transpose(coupling_energy_basis), A) +
               kron(transpose(B), coupling_energy_basis) - kron(transpose(BS), I(2))
    coherent = -im * (kron(I(2), H) - kron(transpose(H), I(2)))
    return Matrix(coherent + redfield)
end

"""Propagate ⟨σz⟩ with a single exp(LΔt) and recurrence, including t=0."""
function redfield_magnus!(values::AbstractVector{<:Real}, model::SpinBosonModel, dt::Real)
    dt > 0 || throw(ArgumentError("Redfield step must be positive"))
    state = ComplexF64[0.5, 0.5, 0.5, 0.5]  # vec(|↑z⟩⟨↑z|) in the σx energy basis
    step = exp(redfield_generator(model) * dt)
    observable = ComplexF64[0 1; 1 0]
    for i in eachindex(values)
        values[i] = real(tr(observable * reshape(state, 2, 2)))
        state = step * state
    end
    return values
end

"""Independent paper-formula fixture: exp(L t) at each output time."""
function redfield_magnus_paper_formula(model::SpinBosonModel, dt::Real, count::Integer)
    count > 0 || throw(ArgumentError("output count must be positive"))
    L = redfield_generator(model)
    initial = ComplexF64[0.5, 0.5, 0.5, 0.5]
    observable = ComplexF64[0 1; 1 0]
    return [real(tr(observable * reshape(exp(L * ((i - 1) * dt)) * initial, 2, 2)))
            for i in 1:count]
end
