const SIGMA_X = ComplexF64[0 1; 1 0]
const SIGMA_Z = ComplexF64[1 0; 0 -1]

"""The driven spin coupled through σz to an Ohmic zero-temperature bath."""
Base.@kwdef struct SpinBosonModel
    omega::Float64 = 1.0
    epsilon_d::Float64 = 1.0
    alpha::Float64 = 0.05
    omega_c::Float64 = 2.5
    drive::Symbol = :transversal
    coupling_operator::Matrix{ComplexF64} = SIGMA_Z

    function SpinBosonModel(omega::Float64, epsilon_d::Float64, alpha::Float64,
                            omega_c::Float64, drive::Symbol,
                            coupling_operator::Matrix{ComplexF64})
        drive in (:longitudinal, :transversal) ||
            throw(ArgumentError("drive must be :longitudinal or :transversal"))
        omega > 0 && omega_c > 0 && alpha >= 0 ||
            throw(ArgumentError("omega and omega_c must be positive and alpha nonnegative"))
        coupling_operator == SIGMA_Z ||
            throw(ArgumentError("fixed Fig. 2 coupling operator is σz"))
        new(omega, epsilon_d, alpha, omega_c, drive, coupling_operator)
    end
end

function drive_hamiltonian(model::SpinBosonModel, t::Real, ωd::Real=1.0)
    axis = model.drive === :longitudinal ? SIGMA_X : SIGMA_Z
    return model.epsilon_d * cos(ωd * t) * axis
end

system_hamiltonian(model::SpinBosonModel, t::Real, ωd::Real=1.0) =
    model.omega / 2 * SIGMA_X + drive_hamiltonian(model, t, ωd)
