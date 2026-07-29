struct AffineForm
    constant::ComplexF64
    terms::Tuple{Vararg{Tuple{Int,ComplexF64}}}
end
AffineForm() = AffineForm(0.0 + 0.0im, ())

struct LocalizingIR
    polynomial_index::Int
    basis::Tuple{Vararg{NCWord}}
    pencil::Tuple
end

struct CompiledDenseIR{P<:NCProblem}
    problem::P
    basis::Tuple{Vararg{NCWord}}
    coordinate_count::Int
    moment_words::Tuple{Vararg{NCWord}}
    moment_forms::Tuple{Vararg{AffineForm}}
    moment_matrix::Tuple
    equalities::Tuple{Vararg{AffineForm}}
    localizers::Tuple{Vararg{LocalizingIR}}
    objective::AffineForm
end

function _word_linear(backend, left::NCWord, poly::NCPolynomial, right::NCWord)
    output = Dict{NCWord,ComplexF64}()
    left_star = star_word(backend, left)
    for (word, coefficient) in poly.terms
        first_product = _multiply(backend, left_star.word, word)
        second_product = _multiply(backend, first_product.word, right)
        factor = left_star.phase * first_product.phase * second_product.phase * coefficient
        output[second_product.word] = get(output, second_product.word, 0.0 + 0.0im) + factor
    end
    filter!(pair -> abs(last(pair)) > 1.0e-14, output)
    return output
end

function _moment_entry(backend, left::NCWord, right::NCWord)
    return _word_linear(backend, left,
                        NCPolynomial(Dict(NCWord() => 1.0 + 0.0im)), right)
end

function _coordinate_forms(backend, requested_words)
    closure = Set{NCWord}(requested_words)
    for word in collect(closure)
        push!(closure, star_word(backend, word).word)
    end
    ordered = sort!(collect(closure); lt=_word_less)
    forms = Dict{NCWord,AffineForm}()
    coordinate = 0
    for word in ordered
        haskey(forms, word) && continue
        adjoint = star_word(backend, word)
        other, phase = adjoint.word, adjoint.phase
        if other == word
            coordinate += 1
            alpha = ComplexF64(sqrt(conj(phase)))
            abs(phase * alpha - conj(alpha)) <= 1.0e-10 ||
                error("failed to real-parameterize a self-adjoint moment orbit")
            forms[word] = AffineForm(0.0 + 0.0im, ((coordinate, alpha),))
        else
            real_coordinate = coordinate + 1
            imaginary_coordinate = coordinate + 2
            coordinate += 2
            forms[word] = AffineForm(0.0 + 0.0im,
                                     ((real_coordinate, 1.0 + 0.0im),
                                      (imaginary_coordinate, 0.0 + 1.0im)))
            factor = conj(phase)
            forms[other] = AffineForm(0.0 + 0.0im,
                                      ((real_coordinate, factor),
                                       (imaginary_coordinate, -im * factor)))
        end
    end
    return ordered, forms, coordinate
end

function _convert_word_linear(linear, forms)
    coefficients = Dict{Int,ComplexF64}()
    constant = 0.0 + 0.0im
    for (word, factor) in linear
        form = forms[word]
        constant += factor * form.constant
        for (index, coefficient) in form.terms
            coefficients[index] = get(coefficients, index, 0.0 + 0.0im) + factor * coefficient
        end
    end
    terms = Tuple((index, coefficients[index]) for index in sort!(collect(keys(coefficients)))
                  if abs(coefficients[index]) > 1.0e-14)
    return AffineForm(ComplexF64(constant), terms)
end

function compile_dense(problem::NCProblem)
    basis = enumerate_words(problem)
    backend = problem.backend
    moment_linears = [_moment_entry(backend, left, right) for left in basis, right in basis]

    equality_linears = Dict{NCWord,ComplexF64}[]
    for equality in problem.equalities
        degree = _polynomial_degree(equality)
        for left in basis, right in basis
            length(left) + degree + length(right) <= 2problem.order || continue
            push!(equality_linears, _word_linear(backend, left, equality, right))
        end
    end
    push!(equality_linears,
          Dict(NCWord() => 1.0 + 0.0im)) # converted below, then shifted to y₁ - 1

    localizer_data = Tuple[]
    for (index, inequality) in enumerate(problem.inequalities)
        radius = fld(2problem.order - _polynomial_degree(inequality), 2)
        radius >= 0 || throw(ArgumentError("inequality has no degree-admissible localizer"))
        local_basis = Tuple(enumerate_words(backend, radius))
        pencil = Tuple(Tuple(_word_linear(backend, left, inequality, right)
                             for right in local_basis) for left in local_basis)
        push!(localizer_data, (index, local_basis, pencil))
    end

    objective_linear = Dict(problem.objective.terms)
    all_linears = Any[vec(moment_linears)..., equality_linears..., objective_linear]
    for (_, _, pencil) in localizer_data, row in pencil, linear in row
        push!(all_linears, linear)
    end
    requested = Set{NCWord}()
    for linear in all_linears, word in keys(linear)
        push!(requested, word)
    end
    moment_words, forms, coordinate_count = _coordinate_forms(backend, requested)

    matrix = Tuple(Tuple(_convert_word_linear(moment_linears[i, j], forms)
                         for j in axes(moment_linears, 2)) for i in axes(moment_linears, 1))
    equalities = AffineForm[_convert_word_linear(linear, forms) for linear in equality_linears]
    normalization = pop!(equalities)
    push!(equalities, AffineForm(normalization.constant - (1.0 + 0.0im), normalization.terms))
    localizers = Tuple(LocalizingIR(index, local_basis,
        Tuple(Tuple(_convert_word_linear(linear, forms) for linear in row) for row in pencil))
        for (index, local_basis, pencil) in localizer_data)
    objective = _convert_word_linear(objective_linear, forms)

    ir = CompiledDenseIR(problem, Tuple(basis), coordinate_count, Tuple(moment_words),
                         Tuple(forms[word] for word in moment_words), matrix,
                         Tuple(equalities), localizers, objective)
    _validate_compiled(ir)
    return ir
end

function _conjugate_form(form::AffineForm)
    return AffineForm(conj(form.constant), Tuple((i, conj(c)) for (i, c) in form.terms))
end

function _form_difference_norm(left::AffineForm, right::AffineForm)
    coefficients = Dict{Int,ComplexF64}()
    for (i, c) in left.terms
        coefficients[i] = get(coefficients, i, 0.0 + 0.0im) + c
    end
    for (i, c) in right.terms
        coefficients[i] = get(coefficients, i, 0.0 + 0.0im) - c
    end
    return max(abs(left.constant - right.constant),
               maximum(abs.(collect(values(coefficients))); init=0.0))
end

function _validate_hermitian_pencil(pencil, label)
    n = length(pencil)
    all(length(row) == n for row in pencil) || throw(ArgumentError("$label is not square"))
    for i in 1:n, j in 1:n
        _form_difference_norm(pencil[i][j], _conjugate_form(pencil[j][i])) <= 1.0e-11 ||
            throw(ArgumentError("$label is not Hermitian at ($i, $j)"))
    end
end

function _validate_compiled(ir::CompiledDenseIR)
    _validate_hermitian_pencil(ir.moment_matrix, "moment matrix")
    for localizer in ir.localizers
        _validate_hermitian_pencil(localizer.pencil, "localizer $(localizer.polynomial_index)")
    end
    abs(imag(ir.objective.constant)) <= 1.0e-11 ||
        throw(ArgumentError("objective has a non-real constant in real coordinates"))
    all(abs(imag(c)) <= 1.0e-11 for (_, c) in ir.objective.terms) ||
        throw(ArgumentError("objective has non-real coefficients in real coordinates"))
    return ir
end
