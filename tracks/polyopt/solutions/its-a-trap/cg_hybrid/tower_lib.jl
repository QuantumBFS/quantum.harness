# tower_lib.jl — shared numerics for the ω-tower (used by tower.jl gates and
# tower_gen.jl generator). Extracted verbatim from the gate-validated tower.jl.
using LinearAlgebra

const σI = ComplexF64[1 0; 0 1]
const σx = ComplexF64[0 1; 1 0]
const σy = ComplexF64[0 -im; im 0]
const σz = ComplexF64[1 0; 0 -1]
const h2 = 0.25 * (kron(σx, σx) + kron(σy, σy) + kron(σz, σz))  # per-bond, per-site objective uses tr(h ρ2)

newmodel() = begin
    m = Model(optimizer_with_attributes(Mosek.Optimizer,
        "MSK_DPAR_INTPNT_CO_TOL_PFEAS" => 1e-8, "MSK_DPAR_INTPNT_CO_TOL_DFEAS" => 1e-8,
        "MSK_DPAR_INTPNT_CO_TOL_REL_GAP" => 1e-8, "MSK_IPAR_NUM_THREADS" => 2))
    set_silent(m); m
end

ceq!(m, A, B) = begin  # complex elementwise equality
    @constraint(m, real.(A) .== real.(B))
    @constraint(m, imag.(A) .== imag.(B))
end

# partial traces over FIRST/LAST factor of dims (2, dr) / (dl, 2)
ptr_first(X, dr) = [sum(X[(s-1)*dr+i, (s-1)*dr+j] for s in 1:2) for i in 1:dr, j in 1:dr]
ptr_last(X, dl)  = [sum(X[(i-1)*2+s, (j-1)*2+s] for s in 1:2) for i in 1:dl, j in 1:dl]
# trace out an arbitrary middle factor: dims (da, dt, db), trace dt.
# Output ordering MUST stay b-fastest ((a-1)*db + b) to match ptr_first/ptr_last;
# the first version of this function used a-fastest and scrambled the T2 links
# (caught by the G4/validity gates — E_cg exceeded E0).
function ptr_mid(X, da, dt, db)
    lin(a, t, b) = ((a - 1) * dt + (t - 1)) * db + b
    n = da * db
    ai(p) = div(p - 1, db) + 1
    bi(p) = mod(p - 1, db) + 1
    [sum(X[lin(ai(p), t, bi(p)), lin(ai(q), t, bi(q))] for t in 1:dt)
     for p in 1:n, q in 1:n]
end

# ---------------------------------------------------------------- maps ------
# uMPS tensor B: A[μ] = m×m; chain map W_k: (C^2)^k -> C^m ⊗ C^m,
# (W_k)_{(I,J),(μ1..μk)} = (A^{μ1}···A^{μk})_{IJ}
function chainmap(A::Vector{Matrix{ComplexF64}}, k::Int)
    m = size(A[1], 1)
    W = zeros(ComplexF64, m * m, 2^k)
    for μs in Iterators.product(fill(1:2, k)...)
        P = foldl(*, (A[μ] for μ in μs))
        col = 1 + sum((μs[t] - 1) * 2^(k - t) for t in 1:k)
        for I in 1:m, J in 1:m
            W[(I-1)*m+J, col] = P[I, J]
        end
    end
    return W
end

# 𝒞_M: ρ_M (2^M) -> ω_M on (2, m, m, 2); X = I2 ⊗ W_{M-2} ⊗ I2 as a matrix
cmat(W, m) = kron(σI, W, σI)   # (2·m²·2) × (2·2^{M-2}·2 = 2^M)

# right link map on ω legs (2, m, m, 2): apply Bmat: (J,μ)->K on last two legs, trace K
# Bmat[(K),(J,μ)] = A^μ[J,K]  (m × 2m)
function bmat(A::Vector{Matrix{ComplexF64}})
    m = size(A[1], 1)
    Bm = zeros(ComplexF64, m, m * 2)
    for μ in 1:2, J in 1:m, K in 1:m
        Bm[K, (J-1)*2+μ] = A[μ][J, K]
    end
    return Bm
end
# mirror: left link, apply B̃: (μ,I)->K' on FIRST two legs, trace; B̃[(K),(μ,I)] = A^μ[K,I]
function bmat_left(A::Vector{Matrix{ComplexF64}})
    m = size(A[1], 1)
    Bm = zeros(ComplexF64, m, 2 * m)
    for μ in 1:2, I in 1:m, K in 1:m
        Bm[K, (μ-1)*m+I] = A[μ][K, I]
    end
    return Bm
end


# leg-order helpers (dims annotated at call sites)
ptr_mid_wrap(X, da, dt, db) = ptr_mid(X, da, dt, db)     # alias, clarity
ptr_mid_left(X, da, dt, db) = ptr_mid(X, da, dt, db)
ptr_first_m(X, dt, dr) = [sum(X[(t-1)*dr+i, (t-1)*dr+j] for t in 1:dt) for i in 1:dr, j in 1:dr]
ptr_last_m(X, dl, dt)  = [sum(X[(i-1)*dt+t, (j-1)*dt+t] for t in 1:dt) for i in 1:dl, j in 1:dl]

function random_left_canonical(mm)
    # random isometry V: C^{2m} -> C^m  =>  Σ_μ A_μ† A_μ = I (left canonical)
    Q = Matrix(qr(randn(ComplexF64, 2 * mm, mm)).Q)[:, 1:mm]     # (2m)×m isometry, Q†Q = I
    A = [Matrix{ComplexF64}(undef, mm, mm) for _ in 1:2]
    for μ in 1:2, i in 1:mm, k in 1:mm
        A[μ][i, k] = Q[(μ-1)*mm+i, k]                            # A^μ[i,k] = Q[(μ,i),k]
    end
    return A
end

# marginal of M consecutive sites starting at `pos` (0-based) from state ψ on N qubits
function window_marginal(ψ::Vector{Float64}, N::Int, pos::Int, M::Int)
    ρ = zeros(ComplexF64, 2^M, 2^M)
    mask_bits = [(pos + t) % N for t in 0:(M-1)]
    rest = setdiff(0:(N-1), mask_bits)
    for a in 0:(2^M-1), b in 0:(2^M-1)
        acc = 0.0
        for r in 0:(2^(N-M)-1)
            s1 = 0; s2 = 0
            for (t, bit) in enumerate(mask_bits)
                s1 |= ((a >> (M - t)) & 1) << bit
                s2 |= ((b >> (M - t)) & 1) << bit
            end
            # NOTE index order: bit t of the window = qubit mask_bits[t]; use big-endian within window
            for (t, bit) in enumerate(rest)
                s1 |= ((r >> (t - 1)) & 1) << bit
                s2 |= ((r >> (t - 1)) & 1) << bit
            end
            acc += ψ[s1+1] * ψ[s2+1]
        end
        ρ[a+1, b+1] = acc
    end
    return ρ
end
