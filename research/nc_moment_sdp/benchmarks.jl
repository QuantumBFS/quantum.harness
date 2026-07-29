function chsh_z2(; order::Integer=2)
    names = [:A0, :A1, :B0, :B1]
    commuting = [(alice, bob) for alice in (:A0, :A1) for bob in (:B0, :B1)]
    backend = LegacyInvolutionBackend(names; commuting_pairs=commuting)
    objective = polynomial(backend, Dict(
        (:A0, :B0) => 1.0,
        (:A0, :B1) => 1.0,
        (:A1, :B0) => 1.0,
        (:A1, :B1) => -1.0,
    ))
    return NCProblem("CHSH / Z2", backend; objective=objective,
                     generator_characters=[0x1, 0x1, 0x1, 0x1],
                     group_rank=1, order=order, sense=:Max)
end

function pauli_z2xz2(; order::Integer=2)
    backend = PauliBackend([
        (:X1, 1, :X), (:Y1, 1, :Y), (:Z1, 1, :Z),
        (:X2, 2, :X), (:Y2, 2, :Y), (:Z2, 2, :Z),
    ])
    objective = polynomial(backend, Dict((:X1, :X2) => 1.0, (:Z1, :Z2) => 1.0))
    return NCProblem("two-site Pauli / Z2xZ2", backend; objective=objective,
                     generator_characters=[0x1, 0x3, 0x2, 0x1, 0x3, 0x2],
                     group_rank=2, order=order, sense=:Max)
end

function complex_pauli_benchmark(; order::Integer=1)
    backend = PauliBackend([(:X, 1, :X), (:Y, 1, :Y), (:Z, 1, :Z)])
    objective = polynomial(backend, Dict((:Z,) => 1.0))
    return NCProblem("complex Pauli imaginary moment", backend;
                     objective=objective, order=order, sense=:Max)
end

function equality_localizer_benchmark(; order::Integer=2)
    backend = LegacyInvolutionBackend([:A, :B]; commuting_pairs=[(:A, :B)])
    objective = polynomial(backend, Dict((:B,) => 1.0))
    equality = polynomial(backend, Dict((:A,) => 1.0, (:B,) => -1.0))
    inequality = polynomial(backend, Dict(() => 1.0, (:A,) => 1.0))
    return NCProblem("equality and localizer", backend; objective=objective,
                     equalities=[equality], inequalities=[inequality],
                     order=order, sense=:Max)
end
