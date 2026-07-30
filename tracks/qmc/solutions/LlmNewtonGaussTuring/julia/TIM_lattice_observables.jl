# Finite-size-scaling observables for the line-update SSE implementation.
isdefined(Main, :Sim) || include(joinpath(@__DIR__, "TIM_lattice_line.jl"))

struct FSSPhases
    cosq::Matrix{Float64}
    sinq::Matrix{Float64}
    q_norm::Float64
end

@inline function fss_mode_power(q_re, q_im, normalization)
    power = 0.0
    @inbounds @simd for qindex in eachindex(q_re, q_im)
        power += q_re[qindex]^2 + q_im[qindex]^2
    end
    return power / normalization
end

function fss_site_coordinates(lattice, Lx::Int, Ly::Int)
    lat = Symbol(lattice)
    sqrt3 = sqrt(3.0)
    if lat == :triangular
        coordinates = Matrix{Float64}(undef, 2, Lx * Ly)
        for y in 0:Ly-1, x in 0:Lx-1
            site = x + y * Lx + 1
            coordinates[:, site] .= (x + 0.5y, 0.5sqrt3 * y)
        end
    elseif lat == :honeycomb
        coordinates = Matrix{Float64}(undef, 2, 2Lx * Ly)
        for y in 0:Ly-1, x in 0:Lx-1
            a = 2 * (x + y * Lx) + 1
            rx = 0.5x - 0.5y
            ry = 0.5sqrt3 * (x + y)
            coordinates[:, a] .= (rx, ry)
            coordinates[:, a + 1] .= (rx, ry + 1 / sqrt3)
        end
    else
        error("unsupported FSS lattice: $lattice")
    end
    return coordinates
end

function build_fss_phases(lattice, Lx::Int, Ly::Int)
    Lx == Ly || throw(ArgumentError("FSS pilot requires square unit-cell tori"))
    sqrt3 = sqrt(3.0)
    lat = Symbol(lattice)
    if lat == :triangular
        b1 = (2pi, -2pi / sqrt3)
        b2 = (0.0, 4pi / sqrt3)
    elseif lat == :honeycomb
        b1 = (2pi, 2pi / sqrt3)
        b2 = (-2pi, 2pi / sqrt3)
    else
        error("unsupported FSS lattice: $lattice")
    end
    coefficients = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1))
    qvectors = [(n1 * b1[1] / Lx + n2 * b2[1] / Ly,
                 n1 * b1[2] / Lx + n2 * b2[2] / Ly)
                for (n1, n2) in coefficients]
    norms = [hypot(q...) for q in qvectors]
    all(isapprox(norm, norms[1]; rtol = 1e-12) for norm in norms) ||
        error("shortest momentum vectors are not degenerate")
    coordinates = fss_site_coordinates(lat, Lx, Ly)
    cosq = Matrix{Float64}(undef, length(qvectors), size(coordinates, 2))
    sinq = similar(cosq)
    for (qindex, q) in enumerate(qvectors), site in axes(coordinates, 2)
        phase = q[1] * coordinates[1, site] + q[2] * coordinates[2, site]
        cosq[qindex, site] = cos(phase)
        sinq[qindex, site] = sin(phase)
    end
    return FSSPhases(cosq, sinq, norms[1])
end

function measure_fss(s::Sim, phases::FSSPhases; check_periodicity::Bool = false)
    size(phases.cosq, 2) == s.N || throw(ArgumentError("phase table site count mismatch"))
    spins = 2 .* s.conf .- 1
    initial = check_periodicity ? copy(spins) : Int[]
    magnetization = sum(spins)
    q_re = phases.cosq * spins
    q_im = phases.sinq * spins

    normalization = size(phases.cosq, 1) * s.N^2
    m = magnetization / s.N
    m2 = m^2
    m3 = m2 * m
    m4 = m2^2
    mode_power = fss_mode_power(q_re, q_im, normalization)
    p1 = 0.0
    p2 = 0.0
    p3 = 0.0
    p4 = 0.0
    interval_count = 1
    run_weight = 1
    equal_sq = 0.0

    @inbounds for position in 1:s.lm
        operator_type = s.opl[1, position]
        operator_type == 0 && continue

        if operator_type == 6 || operator_type == 7
            weight = Float64(run_weight)
            p1 += weight * m
            p2 += weight * m2
            p3 += weight * m3
            p4 += weight * m4
            equal_sq += weight * mode_power

            site = s.opl[2, position]
            delta = -2 * spins[site]
            spins[site] = -spins[site]
            magnetization += delta
            for qindex in axes(phases.cosq, 1)
                q_re[qindex] += delta * phases.cosq[qindex, site]
                q_im[qindex] += delta * phases.sinq[qindex, site]
            end
            m = magnetization / s.N
            m2 = m^2
            m3 = m2 * m
            m4 = m2^2
            mode_power = fss_mode_power(q_re, q_im, normalization)
            run_weight = 1
        else
            run_weight += 1
        end
        interval_count += 1
    end

    check_periodicity && spins != initial && error("worldline did not close during FSS measurement")
    weight = Float64(run_weight)
    p1 += weight * m
    p2 += weight * m2
    p3 += weight * m3
    p4 += weight * m4
    equal_sq += weight * mode_power

    K = Float64(interval_count)
    equal_m2 = p2 / K
    equal_m4 = p4 / K
    equal_sq /= K
    spacetime_m2 = (p1^2 + p2) / (K * (K + 1))
    spacetime_m4 = (p1^4 + 6p1^2 * p2 + 3p2^2 + 8p1 * p3 + 6p4) /
                   (K * (K + 1) * (K + 2) * (K + 3))
    interval_m2 = p2 / K
    interval_m4 = p4 / K
    spacetime_m2 <= interval_m2 + 1e-12 || error("Dirichlet m2 violates convexity")
    spacetime_m4 <= interval_m4 + 1e-12 || error("Dirichlet m4 violates convexity")

    energy = (-s.nh / s.beta + s.Nb * s.Cb + s.Gamma * s.N) / s.N
    return (E = energy, spacetime_m2 = spacetime_m2,
            spacetime_m4 = spacetime_m4, S0 = equal_m2, Sq = equal_sq,
            equal_m4 = equal_m4, q_norm = phases.q_norm,
            q_count = size(phases.cosq, 1))
end
