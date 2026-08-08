@inline _basis_spin(state::Integer, site::Integer) =
    iszero((state >> (site - 1)) & 1) ? 1.0 : -1.0

@inline function _log_two_cosh(x::Real)
    ax = abs(Float64(x))
    return ax + log1p(exp(-2ax))
end

@inline function _sech2(x::Real)
    tail = exp(-2abs(Float64(x)))
    return 4tail / (1 + tail)^2
end

"""
    dense_hamiltonian(model; max_sites=10)

Construct an independent dense reference Hamiltonian in the σᶻ product basis.
The basis integer uses bit `0` for σᶻ=+1 and bit `1` for σᶻ=-1.
"""
function dense_hamiltonian(model::SquareLatticeTFIM; max_sites::Integer=10)
    N = nsites(model)
    N <= max_sites ||
        throw(ArgumentError("dense ED limited to N ≤ $max_sites (requested N=$N)"))

    dim = 1 << N
    H = zeros(Float64, dim, dim)

    for basis in 0:(dim - 1)
        col = basis + 1
        diagonal = 0.0
        for (i, j) in model.bonds
            diagonal -= model.J * _basis_spin(basis, i) * _basis_spin(basis, j)
        end
        H[col, col] = diagonal

        for i in 1:N
            row = (basis ⊻ (1 << (i - 1))) + 1
            H[row, col] -= model.h
        end
    end

    return Hermitian(H)
end

exact_spectrum(model::SquareLatticeTFIM; kwargs...) =
    eigvals(dense_hamiltonian(model; kwargs...))

"""
    independent_spin_observables(N, h, beta)

Closed-form thermodynamics for `J=0`. Energy and heat capacity are per site.
"""
function independent_spin_observables(N::Integer, h::Real, beta::Real)
    N > 0 || throw(ArgumentError("N must be positive"))
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))

    x = Float64(beta * h)
    mx = tanh(x)
    u = -Float64(h) * mx
    c = x^2 / cosh(x)^2
    logZ = Int(N) * _log_two_cosh(x)
    free_energy = iszero(beta) ? -Inf : -logZ / Float64(beta)

    return (; logZ, free_energy, u, c, mx, mz2=1 / Float64(N))
end

"""
    classical_enumeration(model, beta)

Complete σᶻ-basis enumeration for the `h=0` classical limit.
"""
function classical_enumeration(model::SquareLatticeTFIM, beta::Real)
    iszero(model.h) || throw(ArgumentError("classical enumeration requires h=0"))
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))

    N = nsites(model)
    N <= 24 || throw(ArgumentError("classical enumeration limited to N ≤ 24"))
    dim = 1 << N
    energies = Vector{Float64}(undef, dim)
    mz2_basis = Vector{Float64}(undef, dim)

    for basis in 0:(dim - 1)
        E = 0.0
        magnetization = 0.0
        for i in 1:N
            magnetization += _basis_spin(basis, i)
        end
        for (i, j) in model.bonds
            E -= model.J * _basis_spin(basis, i) * _basis_spin(basis, j)
        end
        energies[basis + 1] = E
        mz2_basis[basis + 1] = (magnetization / N)^2
    end

    Emin = minimum(energies)
    weights = exp.(-Float64(beta) .* (energies .- Emin))
    normalization = sum(weights)
    probabilities = weights ./ normalization
    energy_total = dot(probabilities, energies)
    energy2 = dot(probabilities, energies .^ 2)
    logZ = -Float64(beta) * Emin + log(normalization)
    free_energy = iszero(beta) ? -Inf : -logZ / Float64(beta)

    return (; logZ,
            free_energy,
            energy_total,
            u=energy_total / N,
            c=Float64(beta)^2 * (energy2 - energy_total^2) / N,
            mx=0.0,
            mz2=dot(probabilities, mz2_basis))
end

"""
    exact_thermal_observables(model, beta; max_sites=10)

Dense finite-temperature reference calculation. Returned `u` and `c` are per
site; `mx` is `N⁻¹Σᵢ⟨σˣᵢ⟩`.
"""
function exact_thermal_observables(model::SquareLatticeTFIM, beta::Real;
                                   max_sites::Integer=10)
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))
    N = nsites(model)
    decomposition = eigen(dense_hamiltonian(model; max_sites))
    energies = decomposition.values
    vectors = decomposition.vectors

    Emin = minimum(energies)
    weights = exp.(-Float64(beta) .* (energies .- Emin))
    normalization = sum(weights)
    probabilities = weights ./ normalization
    energy_total = dot(probabilities, energies)
    energy2 = dot(probabilities, energies .^ 2)

    dim = length(energies)
    mx_eigenstate = zeros(Float64, dim)
    mz2_eigenstate = zeros(Float64, dim)
    mz2_basis = Vector{Float64}(undef, dim)

    for basis in 0:(dim - 1)
        magnetization = 0.0
        for site in 1:N
            magnetization += _basis_spin(basis, site)
        end
        mz2_basis[basis + 1] = (magnetization / N)^2
    end

    for eigenstate in 1:dim
        vector = view(vectors, :, eigenstate)
        mx_sum = 0.0
        for site in 1:N, basis in 0:(dim - 1)
            flipped = basis ⊻ (1 << (site - 1))
            mx_sum += vector[basis + 1] * vector[flipped + 1]
        end
        mx_eigenstate[eigenstate] = mx_sum / N
        mz2_eigenstate[eigenstate] =
            sum(abs2(vector[basis]) * mz2_basis[basis] for basis in 1:dim)
    end

    logZ = -Float64(beta) * Emin + log(normalization)
    free_energy = iszero(beta) ? -Inf : -logZ / Float64(beta)

    return (; logZ,
            free_energy,
            energy_total,
            u=energy_total / N,
            c=Float64(beta)^2 * (energy2 - energy_total^2) / N,
            mx=dot(probabilities, mx_eigenstate),
            mz2=dot(probabilities, mz2_eigenstate))
end

"""
    exact_open_chain_observables(model, beta)

Exact finite-temperature thermodynamics of the one-dimensional open-boundary
TFIM, obtained from its Jordan-Wigner free-fermion representation. The model
must have `Ly == 1`. Returned `u`, `c`, and `mx` are per site, while `logZ` and
`free_energy` are total quantities.

For
`H = -J Σᵢ σᶻᵢσᶻᵢ₊₁ - h Σᵢ σˣᵢ`,
the positive one-particle energies are twice the singular values of the
lower-bidiagonal matrix with diagonal `h` and subdiagonal `J`.
"""
function exact_open_chain_observables(model::SquareLatticeTFIM, beta::Real)
    model.Ly == 1 ||
        throw(ArgumentError("open-chain free-fermion reference requires Ly=1"))
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))

    L = model.Lx
    bidiagonal = zeros(Float64, L, L)
    for site in 1:L
        bidiagonal[site, site] = model.h
    end
    for site in 1:(L - 1)
        bidiagonal[site + 1, site] = model.J
    end

    decomposition = svd(bidiagonal)
    modes = decomposition.S
    beta_f = Float64(beta)
    scaled_modes = beta_f .* modes
    occupations = tanh.(scaled_modes)

    logZ = sum(_log_two_cosh(value) for value in scaled_modes)
    energy_total = -dot(modes, occupations)
    free_energy = iszero(beta_f) ? -Inf : -logZ / beta_f
    c = sum(value^2 * _sech2(value) for value in scaled_modes) / L

    # Hellmann-Feynman derivative ds_k/dh = u_k'v_k. At h=0 the finite-chain
    # transverse magnetization vanishes by symmetry, and handling it explicitly
    # avoids choosing a basis inside degenerate singular subspaces.
    mx = if iszero(model.h)
        0.0
    else
        sum(
            occupations[mode] *
            dot(view(decomposition.U, :, mode),
                view(decomposition.V, :, mode))
            for mode in eachindex(modes)
        ) / L
    end

    return (; logZ,
            free_energy,
            energy_total,
            u=energy_total / L,
            c,
            mx,
            mode_energies=2 .* modes)
end

function _gauss_legendre(order::Integer)
    order >= 2 || throw(ArgumentError("quadrature order must be at least 2"))
    n = Int(order)
    off_diagonal = Float64[
        index / sqrt(4index^2 - 1)
        for index in 1:(n - 1)
    ]
    decomposition = eigen(SymTridiagonal(zeros(n), off_diagonal))
    return decomposition.values, 2 .* decomposition.vectors[1, :] .^ 2
end

"""
    exact_infinite_chain_observables(J, h, beta; quadrature_order=256)

Thermodynamic-limit analytic solution of the one-dimensional TFIM. The exact
Jordan-Wigner result is evaluated as a Gauss-Legendre quadrature of the
Brillouin-zone integrals. Returned thermodynamic quantities are per site.
`logZ_density` means `lim(L→∞) log(Z)/L`.
"""
function exact_infinite_chain_observables(
    J::Real,
    h::Real,
    beta::Real;
    quadrature_order::Integer=256,
)
    J >= 0 || throw(ArgumentError("J must be nonnegative"))
    h >= 0 || throw(ArgumentError("h must be nonnegative"))
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))

    nodes, weights = _gauss_legendre(quadrature_order)
    beta_f = Float64(beta)
    J_f = Float64(J)
    h_f = Float64(h)
    logZ_integral = 0.0
    energy_integral = 0.0
    heat_integral = 0.0
    magnetization_integral = 0.0

    # Map Gauss-Legendre nodes from [-1,1] to k∈[0,π]. The factor 1/π
    # in the analytic formula and the interval Jacobian combine to 1/2.
    for (node, weight) in zip(nodes, weights)
        momentum = (node + 1) * (π / 2)
        mode = sqrt(J_f^2 + h_f^2 - 2J_f * h_f * cos(momentum))
        scaled_mode = beta_f * mode
        occupation = tanh(scaled_mode)
        half_weight = weight / 2

        logZ_integral += half_weight * _log_two_cosh(scaled_mode)
        energy_integral -= half_weight * mode * occupation
        heat_integral += half_weight * scaled_mode^2 * _sech2(scaled_mode)
        if !iszero(mode)
            magnetization_integral +=
                half_weight * occupation *
                (h_f - J_f * cos(momentum)) / mode
        end
    end

    free_energy_density =
        iszero(beta_f) ? -Inf : -logZ_integral / beta_f
    return (; logZ_density=logZ_integral,
            free_energy_density,
            u=energy_integral,
            c=heat_integral,
            mx=magnetization_integral)
end

"""
    exact_expansion_order_moments(model, beta;
                                  deflate_site_constant=false,
                                  max_sites=10)

Dense-ED oracle for the first four raw moments of the SSE expansion order.
With `deflate_site_constant=true`, the exactly factorizable `h*N*I` operator
count is removed and the returned order is `m = n - n0`.

The factorial-moment identity is
`E[(m)_r] = beta^r * <K^r>`, where
`K = shift*I - H` and `shift=J*Nb` for the deflated representation. The
returned `heat_influence_variance` is the independent-sample variance of the
delta-method heat-capacity influence value per site. It predicts the
irreducible count noise before Markov-chain autocorrelation is included.
"""
function exact_expansion_order_moments(
    model::SquareLatticeTFIM,
    beta::Real;
    deflate_site_constant::Bool=false,
    max_sites::Integer=10,
)
    beta > 0 || throw(ArgumentError("expansion-order moments require beta > 0"))
    N = nsites(model)
    energies = exact_spectrum(model; max_sites)
    minimum_energy = minimum(energies)
    weights = exp.(-Float64(beta) .* (energies .- minimum_energy))
    probabilities = weights ./ sum(weights)
    shift = model.J * nbonds(model) +
            (deflate_site_constant ? 0.0 : model.h * N)
    generator_eigenvalues = shift .- energies
    factorial = [
        Float64(beta)^order *
        dot(probabilities, generator_eigenvalues .^ order)
        for order in 1:4
    ]

    raw1 = factorial[1]
    raw2 = factorial[2] + factorial[1]
    raw3 = factorial[3] + 3factorial[2] + factorial[1]
    raw4 =
        factorial[4] + 6factorial[3] + 7factorial[2] + factorial[1]
    heat_capacity = (raw2 - raw1^2 - raw1) / N
    coefficient = -2raw1 - 1
    heat_influence_variance = (
        raw4 + 2coefficient * raw3 + coefficient^2 * raw2 -
        (raw2 + coefficient * raw1)^2
    ) / N^2
    energy_density = (shift - raw1 / Float64(beta)) / N

    return (; mean=raw1,
            second_moment=raw2,
            third_moment=raw3,
            fourth_moment=raw4,
            energy_density,
            heat_capacity,
            heat_influence_variance,
            deflate_site_constant)
end
