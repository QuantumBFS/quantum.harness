using Graft
using Graft.TestUtils
using GraftImpurity
using Graft.Backend: dim, domain
using LinearAlgebra
using Printf
using SHA

length(ARGS) == 5 || error(
    "usage: graft_solve_tdvp_beta16.jl METHOD CHI RESOLUTION PROFILE OUTPUT_DIR",
)

const METHOD = ARGS[1]
const CHI = parse(Int, ARGS[2])
const RESOLUTION = parse(Int, ARGS[3])
const PROFILE = ARGS[4]
const OUTPUT_DIR = abspath(ARGS[5])
const NBATH = parse(Int, get(ENV, "TEAMC_NBATH", PROFILE == "smoke" ? "1" : "2"))
const BETA = 16.0
const NTAU = parse(Int, get(ENV, "TEAMC_NTAU", PROFILE == "smoke" ? "5" : "65"))
const NIW = parse(Int, get(ENV, "TEAMC_NIW", PROFILE == "smoke" ? "4" : "16"))
const BATH_CSV = get(ENV, "TEAMC_BATH_CSV", "")
const BATH_METHOD = get(ENV, "TEAMC_BATH_METHOD", "unspecified")
const BATH_MIN_COUPLING =
    parse(Float64, get(ENV, "TEAMC_BATH_MIN_COUPLING", "0.0"))
const MODEL_US = (2.0, 8.0)
const DENSE_REFERENCE = get(
    ENV,
    "TEAMC_DENSE_REFERENCE",
    isempty(BATH_CSV) ? "1" : "0",
) == "1"
const TDVP_DT = parse(
    Float64,
    get(ENV, "TEAMC_TDVP_DT", PROFILE == "smoke" ? "0.0" : "0.25"),
)
const TDVP_TRUNC_ATOL =
    parse(Float64, get(ENV, "TEAMC_TDVP_TRUNC_ATOL", "1e-12"))
const PH_SYMMETRY = get(ENV, "TEAMC_PH_SYMMETRY", "0") == "1"
const TAU_THREADED = get(ENV, "TEAMC_TAU_THREADED", "0") == "1"
const TAU_FIRST = parse(Float64, get(ENV, "TEAMC_TAU_FIRST", "0.01"))
const BOOTSTRAP_PASSES = parse(Int, get(
    ENV, "TEAMC_BOOTSTRAP_PASSES", PROFILE == "smoke" ? "1" : "3"))
const PREP_CHI = parse(Int, get(ENV, "TEAMC_PREP_CHI", string(CHI)))
const IMPLICIT_KRYLOVDIM = parse(Int, get(
    ENV, "TEAMC_IMPLICIT_KRYLOVDIM", PROFILE == "smoke" ? "12" : "10"))
const IMPLICIT_MAXITER = parse(Int, get(
    ENV, "TEAMC_IMPLICIT_MAXITER", PROFILE == "smoke" ? "4" : "1"))
const IMPLICIT_TOL = parse(Float64, get(
    ENV, "TEAMC_IMPLICIT_TOL", "1e-8"))
const IMPLICIT_FIT_NSWEEPS = parse(Int, get(
    ENV, "TEAMC_IMPLICIT_FIT_NSWEEPS", PROFILE == "smoke" ? "4" : "1"))
const IMPLICIT_FIT_TOL = parse(Float64, get(
    ENV, "TEAMC_IMPLICIT_FIT_TOL", PROFILE == "smoke" ? "1e-10" : "1e-8"))
const GRAFT_COMMIT = get(ENV, "TEAMC_GRAFT_COMMIT", "unknown")
const GRAFTIMPURITY_COMMIT = get(ENV, "TEAMC_GRAFTIMPURITY_COMMIT", "unknown")
const GREENFUNC_COMMIT = get(ENV, "TEAMC_GREENFUNC_COMMIT", "unknown")

METHOD in ("tdvp2", "implicit") || error("METHOD must be tdvp2 or implicit")
CHI >= 2 || error("CHI must be at least 2")
RESOLUTION >= 1 || error("RESOLUTION must be positive")
BETA > 0 || error("BETA must be positive")
NTAU >= 3 || error("NTAU must be at least 3")
NIW >= 1 || error("NIW must be positive")
TDVP_DT >= 0 || error("TEAMC_TDVP_DT must be nonnegative")
TDVP_TRUNC_ATOL >= 0 || error("TEAMC_TDVP_TRUNC_ATOL must be nonnegative")
BATH_MIN_COUPLING >= 0 || error("TEAMC_BATH_MIN_COUPLING must be nonnegative")
PH_SYMMETRY && !isodd(NTAU) &&
    error("particle-hole symmetry requires an odd NTAU")

mkpath(OUTPUT_DIR)

csv_value(x) = begin
    s = string(x)
    (occursin(',', s) || occursin('"', s) || occursin('\n', s)) ?
        "\"" * replace(s, "\"" => "\"\"") * "\"" : s
end

function write_namedtuple(path, row)
    open(path, "w") do io
        println(io, join(string.(keys(row)), ','))
        println(io, join(csv_value.(values(row)), ','))
    end
end

function write_rows(path, rows)
    open(path, "w") do io
        println(io, join(string.(keys(first(rows))), ','))
        for row in rows
            println(io, join(csv_value.(values(row)), ','))
        end
    end
end

function read_bath_csv(path::AbstractString)
    lines = readlines(path)
    length(lines) >= 2 || error("bath CSV is empty: $path")
    headers = split(first(lines), ',')
    energy_column = findfirst(==("energy"), headers)
    coupling_column = findfirst(==("coupling"), headers)
    energy_column === nothing && error("bath CSV has no energy column")
    coupling_column === nothing && error("bath CSV has no coupling column")
    energies = Float64[]
    couplings = ComplexF64[]
    for (offset, line) in enumerate(Iterators.drop(lines, 1))
        isempty(strip(line)) && continue
        fields = split(line, ',')
        length(fields) == length(headers) ||
            error("bath CSV field count mismatch at line $(offset + 1)")
        push!(energies, parse(Float64, fields[energy_column]))
        push!(couplings, parse(Float64, fields[coupling_column]))
    end
    return energies, couplings
end

function semicircular_anderson(nbath::Int, U::Float64)
    energies, couplings = if isempty(BATH_CSV)
        gauss_semicircular_bath(nbath)
    else
        read_bath_csv(BATH_CSV)
    end
    length(energies) == nbath || error(
        "bath CSV has $(length(energies)) modes but TEAMC_NBATH=$nbath",
    )
    minimum(abs, couplings) >= BATH_MIN_COUPLING || error(
        "bath CSV contains an inactive coupling below TEAMC_BATH_MIN_COUPLING; " *
        "minimum=$(minimum(abs, couplings))",
    )
    F = fermion_ops_z2()
    bath_up = [Symbol(:bath_up_, j) for j in 1:nbath]
    bath_down = [Symbol(:bath_down_, j) for j in 1:nbath]
    sites = [:d_up; bath_up; :d_down; bath_down]
    topo = TreeTopology(
        first(sites),
        [sites[j] => sites[j + 1] for j in 1:(length(sites) - 1)],
    )
    phys = Dict(site => F.P for site in sites)
    H = OpSum() +
        Term(U, SiteOp(:d_up, :N, F.N), SiteOp(:d_down, :N, F.N)) +
        Term(-U / 2, SiteOp(:d_up, :N, F.N)) +
        Term(-U / 2, SiteOp(:d_down, :N, F.N))
    for (impurity, bath) in ((:d_up, bath_up), (:d_down, bath_down))
        for j in eachindex(bath)
            H += Term(energies[j], SiteOp(bath[j], :N, F.N))
            H += Term(
                couplings[j],
                SiteOp(impurity, :Cd, F.Cd),
                SiteOp(bath[j], :C, F.C),
            )
            H += Term(
                conj(couplings[j]),
                SiteOp(impurity, :C, F.C),
                SiteOp(bath[j], :Cd, F.Cd),
            )
        end
    end
    return (; H, F, topo, phys)
end

function max_bond_dimension(psi)
    topo = topology(psi)
    ds = [
        dim(domain(psi.tensors[n])[1])
        for n in 1:nnodes(topo) if topo.parent[n] != 0
    ]
    return isempty(ds) ? 1 : maximum(ds)
end

function bond_dimensions(psi)
    topo = topology(psi)
    return [
        dim(domain(psi.tensors[n])[1])
        for n in 1:nnodes(topo) if topo.parent[n] != 0
    ]
end

function dense_local_operator(topo, phys, site::Symbol, op)
    sites = [n for n in 1:nnodes(topo) if haskey(phys, nodeid(topo, n))]
    dims = [dim(phys[nodeid(topo, n)]) for n in sites]
    mats = [Matrix{ComplexF64}(I, d, d) for d in dims]
    position = findfirst(==(nodeindex(topo, site)), sites)
    position === nothing && error("site $site has no physical leg")
    d = dims[position]
    array = reshape(convert(Array, op), d, d, :)
    size(array, 3) == 1 ||
        error("local operator charge leg is not one-dimensional")
    mats[position] = array[:, :, 1]
    return reduce(kron, reverse(mats))
end

function krylov_bootstrap(
    psi, K, chi::Int, passes::Int;
    charge_op=nothing,
    charge_site::Union{Nothing,Symbol}=nothing,
)
    reference = to_dense(psi)
    topo = topology(psi)
    initial_bonds = bond_dimensions(psi)
    completed = 0
    preservation = 0.0
    for pass in 1:passes
        before = bond_dimensions(psi)
        for child in 1:nnodes(topo)
            parent = topo.parent[child]
            parent == 0 && continue
            expand!(
                psi,
                K,
                (child, parent);
                scheme=:exact,
                trunc=TruncationScheme(maxdim=chi),
                max_add=min(8, chi),
                mixing=1.0,
                enr_rtol=1e-12,
                enr_atol=1e-14,
            )
        end
        completed = pass
        after = bond_dimensions(psi)
        preservation = norm(to_dense(psi) - reference) / norm(reference)
        preservation <= 1e-10 || error(
            "edge expansion changed represented state: $preservation",
        )
        maximum(after; init=1) >= chi && break
        after == before && break
    end
    println(
        "TEAMC_BOOTSTRAP chi=", chi,
        " passes=", passes,
        " charged=", charge_op !== nothing,
        " implementation=EdgeExactExpansion",
        " preservation=", preservation,
        " initial_bonds=", initial_bonds,
        " final_bonds=", bond_dimensions(psi),
    )
    flush(stdout)
    preservation <= 1e-8 || error(
        "edge expansion changed represented state: $preservation",
    )
    return psi, (; completed, worst_preservation=preservation)
end

tdvp2_evolver() = TDVP2(
    order=2,
    trunc=TruncationScheme(maxdim=CHI, atol=TDVP_TRUNC_ATOL),
    krylovdim=24,
    tol=1e-10,
    verbose=false,
)

implicit_evolver() = ImplicitLogTime(
    scheme=LogTrapezoid(),
    krylovdim=IMPLICIT_KRYLOVDIM,
    maxiter=IMPLICIT_MAXITER,
    tol=IMPLICIT_TOL,
    fit_nsweeps=IMPLICIT_FIT_NSWEEPS,
    fit_tol=IMPLICIT_FIT_TOL,
    normalize=false,
    energy_shift=true,
)

fresh_evolver() = METHOD == "tdvp2" ? tdvp2_evolver() : implicit_evolver()

function base_grid(tmax::Float64)
    tmax == 0 && return [0.0]
    if METHOD == "tdvp2"
        steps = TDVP_DT > 0 ? ceil(Int, tmax / TDVP_DT) : RESOLUTION
        return collect(range(0.0, tmax; length=steps + 1))
    end
    first_step = min(TAU_FIRST, tmax)
    return logarithmic_time_grid(
        first_step, tmax; nsteps_per_panel=RESOLUTION)
end

function propagate!(psi, K, grid, log_amp::Float64)
    ev = fresh_evolver()
    maxchi = max_bond_dimension(psi)
    worst_residual = 0.0
    all_converged = true
    for (a, b) in zip(grid[1:end-1], grid[2:end])
        step!(ev, psi, K, -(b - a))
        if METHOD == "implicit"
            info = ev.last_info
            all_converged &= info.converged == 1
            worst_residual = max(worst_residual, info.normres)
            info.converged == 1 || error(
                "implicit solve failed on [$a,$b]: $(repr(info)); " *
                "rhs_fit_error=$(repr(ev.last_fit_error))",
            )
        end
        nrm = norm(psi)
        isfinite(nrm) && nrm > 0 || error("invalid propagated norm $nrm")
        Graft.normalize!(psi)
        log_amp += log(nrm)
        maxchi = max(maxchi, max_bond_dimension(psi))
    end
    return (; log_amp, maxchi, worst_residual, all_converged)
end

function exact_gtau_and_iw(Hd, Cd, Cdd, beta, taus, frequencies)
    F = eigen(Hermitian(Matrix{ComplexF64}(Hd)))
    energies = real.(F.values)
    e0 = minimum(energies)
    shifted = energies .- e0
    weights = exp.(-beta .* shifted)
    Z = sum(weights)
    C = F.vectors' * Cd * F.vectors
    Cdag = F.vectors' * Cdd * F.vectors

    gtau = ComplexF64[]
    for tau in taus
        value = zero(ComplexF64)
        for m in eachindex(shifted), n in eachindex(shifted)
            value += exp(-(beta - tau) * shifted[m]) *
                C[m, n] * exp(-tau * shifted[n]) * Cdag[n, m]
        end
        push!(gtau, -value / Z)
    end

    giw = ComplexF64[]
    for omega in frequencies
        value = zero(ComplexF64)
        for m in eachindex(shifted), n in eachindex(shifted)
            numerator = weights[m] + weights[n]
            value += numerator * C[m, n] * Cdag[n, m] /
                (im * omega + shifted[m] - shifted[n])
        end
        push!(giw, value / Z)
    end
    return gtau, giw
end

function main(U::Float64)
    u_label = replace(@sprintf("%.6g", U), "." => "p")
    output_dir = joinpath(OUTPUT_DIR, "u" * u_label)
    mkpath(output_dir)
    tag = @sprintf(
        "gtau_iw_%s_nb%d_beta%s_chi%d_r%d_%s",
        METHOD, NBATH, replace(@sprintf("%.6g", BETA), "." => "p"),
        CHI, RESOLUTION, PROFILE,
    )
    summary_path = joinpath(output_dir, tag * "_summary.csv")
    tau_path = joinpath(output_dir, tag * "_tau.csv")
    iw_path = joinpath(output_dir, tag * "_iw.csv")
    println(
        "TEAMC_GTAU_PHASE start tag=", tag,
        " model_u=", U,
        " julia=", VERSION,
    )
    flush(stdout)

    parallel_runtime = Graft.configure_parallel_runtime!(
        blas_threads=1,
        strided_threads=1,
    )
    tau_threaded = TAU_THREADED && Threads.nthreads() > 1
    println(
        "TEAMC_GTAU_PARALLEL tau_threaded=", tau_threaded,
        " runtime=", parallel_runtime,
    )
    flush(stdout)

    model_started = time_ns()
    model = semicircular_anderson(NBATH, U)
    problem = purification_problem(
        model.H, model.topo, model.phys; hermitian=true)
    taus = collect(range(0.0, BETA; length=NTAU))
    frequencies = [(2n + 1) * pi / BETA for n in 0:(NIW - 1)]
    gtau_reference, giw_reference = if DENSE_REFERENCE
        Hd = dense_hamiltonian(model.H, model.topo, model.phys)
        Cd = dense_local_operator(model.topo, model.phys, :d_up, model.F.C)
        Cdd = dense_local_operator(model.topo, model.phys, :d_up, model.F.Cd)
        exact_gtau_and_iw(Hd, Cd, Cdd, BETA, taus, frequencies)
    else
        fill(ComplexF64(NaN, NaN), NTAU),
        fill(ComplexF64(NaN, NaN), NIW)
    end
    reference_seconds = (time_ns() - model_started) / 1e9
    println(
        "TEAMC_GTAU_PHASE model_ready sites=", nnodes(model.topo),
        " doubled_sites=", nnodes(problem.topo_doubled),
        " dense_reference=", DENSE_REFERENCE,
        " seconds=", reference_seconds,
    )
    flush(stdout)

    # Compile one representative step outside the formal timer.
    warmup_started = time_ns()
    warm = infinite_temperature_state(problem).psi
    if METHOD == "implicit"
        warm, _ = krylov_bootstrap(
            warm, problem.K, PREP_CHI, 1)
    end
    warm_grid = [0.0, min(BETA / 1000, 1e-4)]
    propagate!(warm, problem.K, warm_grid, 0.0)
    warmup_seconds = (time_ns() - warmup_started) / 1e9
    println("TEAMC_GTAU_PHASE warmup_complete seconds=", warmup_seconds)
    flush(stdout)

    formal_started = time_ns()
    state0 = infinite_temperature_state(problem)
    psi = copy(state0.psi)
    bootstrap_calls = 0
    bootstrap_passes = 0
    bootstrap_error = 0.0
    if METHOD == "implicit"
        psi, boot = krylov_bootstrap(
            psi, problem.K, PREP_CHI, BOOTSTRAP_PASSES)
        bootstrap_calls += 1
        bootstrap_passes += boot.completed
        bootstrap_error = max(bootstrap_error, boot.worst_preservation)
    end

    computed_indices = PH_SYMMETRY ?
        findall(tau -> tau <= BETA / 2 + 10eps(BETA), taus) :
        collect(eachindex(taus))
    targets = (BETA .- taus[computed_indices]) ./ 2
    prep_grid = sort!(unique(vcat(base_grid(BETA / 2), targets)))
    checkpoints = Dict{Float64,Tuple{Any,Float64}}()
    checkpoints[0.0] = (copy(psi), 0.0)
    log_amp = 0.0
    actual_max_chi = max_bond_dimension(psi)
    maximum_linear_residual = 0.0
    all_linear_solves_converged = true
    ev = fresh_evolver()
    for (a, b) in zip(prep_grid[1:end-1], prep_grid[2:end])
        step!(ev, psi, problem.K, -(b - a))
        if METHOD == "implicit"
            info = ev.last_info
            all_linear_solves_converged &= info.converged == 1
            maximum_linear_residual = max(maximum_linear_residual, info.normres)
            info.converged == 1 || error(
                "implicit preparation solve failed on [$a,$b]: $(repr(info)); " *
                "rhs_fit_error=$(repr(ev.last_fit_error))",
            )
        end
        nrm = norm(psi)
        Graft.normalize!(psi)
        log_amp += log(nrm)
        actual_max_chi = max(actual_max_chi, max_bond_dimension(psi))
        checkpoints[b] = (copy(psi), log_amp)
    end
    l_beta = checkpoints[BETA / 2][2]

    gtau = fill(ComplexF64(NaN, NaN), NTAU)
    charged_max_chi = ones(Int, NTAU)
    charged_worst_residual = zeros(Float64, NTAU)
    charged_all_converged = trues(NTAU)
    charged_bootstrap_calls = zeros(Int, NTAU)
    charged_bootstrap_passes = zeros(Int, NTAU)
    charged_bootstrap_error = zeros(Float64, NTAU)
    Graft.threaded_foreach(computed_indices; threaded=tau_threaded, minbatch=2) do i
        tau = taus[i]
        state_b, l_b = checkpoints[(BETA - tau) / 2]
        bra = apply_local(state_b, adjoint(model.F.C), :d_up)
        ket = apply_local(state_b, model.F.Cd, :d_up)
        n_ket = norm(ket)
        if iszero(n_ket)
            gtau[i] = 0
        else
            Graft.normalize!(ket)
            l_k = log(n_ket)
            println(
                "TEAMC_GTAU_CHARGED tau=", tau,
                " initial_chi=", max_bond_dimension(ket),
            )
            flush(stdout)
            if METHOD == "implicit" && tau > 0
                ket, boot = krylov_bootstrap(
                    ket, problem.K, CHI, BOOTSTRAP_PASSES;
                    charge_op=model.F.Cd,
                    charge_site=:d_up,
                )
                charged_bootstrap_calls[i] = 1
                charged_bootstrap_passes[i] = boot.completed
                charged_bootstrap_error[i] = boot.worst_preservation
            end
            if tau > 0
                result = propagate!(ket, problem.K, base_grid(tau), l_k)
                l_k = result.log_amp
                charged_max_chi[i] = result.maxchi
                charged_worst_residual[i] = result.worst_residual
                charged_all_converged[i] = result.all_converged
            else
                charged_max_chi[i] = max_bond_dimension(ket)
            end
            gtau[i] = -exp(2l_b + l_k - 2l_beta) * inner(bra, ket)
        end
    end
    actual_max_chi = max(actual_max_chi, maximum(charged_max_chi))
    maximum_linear_residual = max(
        maximum_linear_residual,
        maximum(charged_worst_residual),
    )
    all_linear_solves_converged &= all(charged_all_converged)
    bootstrap_calls += sum(charged_bootstrap_calls)
    bootstrap_passes += sum(charged_bootstrap_passes)
    bootstrap_error = max(bootstrap_error, maximum(charged_bootstrap_error))
    if PH_SYMMETRY
        for i in eachindex(taus)
            mirror = NTAU + 1 - i
            if !isfinite(real(gtau[i]))
                gtau[i] = gtau[mirror]
            end
        end
    end

    series = CorrelatorSeries(taus, gtau, (; beta=BETA))
    iw_series = matsubara_transform(
        series; statistics=:fermionic, indices=0:(NIW - 1))
    giw = iw_series.values
    measured_wall_seconds = (time_ns() - formal_started) / 1e9

    tau_abs_errors = DENSE_REFERENCE ?
        abs.(gtau .- gtau_reference) : fill(NaN, NTAU)
    iw_abs_errors = DENSE_REFERENCE ?
        abs.(giw .- giw_reference) : fill(NaN, NIW)
    tau_l2_relative_error = DENSE_REFERENCE ?
        norm(gtau - gtau_reference) / norm(gtau_reference) : NaN
    iw_l2_relative_error = DENSE_REFERENCE ?
        norm(giw - giw_reference) / norm(giw_reference) : NaN

    tau_rows = [
        (;
            tau=taus[i],
            value_real=real(gtau[i]),
            value_imag=imag(gtau[i]),
            reference_real=real(gtau_reference[i]),
            reference_imag=imag(gtau_reference[i]),
            absolute_error=tau_abs_errors[i],
        )
        for i in eachindex(taus)
    ]
    iw_rows = [
        (;
            index=i - 1,
            omega=frequencies[i],
            value_real=real(giw[i]),
            value_imag=imag(giw[i]),
            reference_real=real(giw_reference[i]),
            reference_imag=imag(giw_reference[i]),
            absolute_error=iw_abs_errors[i],
        )
        for i in eachindex(frequencies)
    ]
    summary = (;
        tag,
        method=METHOD,
        profile=PROFILE,
        bath_source=isempty(BATH_CSV) ? "gauss_semicircular" : abspath(BATH_CSV),
        bath_method=BATH_METHOD,
        bath_sha256=isempty(BATH_CSV) ? "" : bytes2hex(sha256(read(BATH_CSV))),
        bath_minimum_coupling=isempty(BATH_CSV) ? NaN :
            minimum(abs, last(read_bath_csv(BATH_CSV))),
        nbath_per_spin=NBATH,
        physical_sites=2 + 2NBATH,
        doubled_sites=2 * (2 + 2NBATH),
        beta=BETA,
        ntau=NTAU,
        niw=NIW,
        resolution=RESOLUTION,
        tdvp_dt=TDVP_DT,
        tdvp_trunc_atol=TDVP_TRUNC_ATOL,
        particle_hole_symmetry=PH_SYMMETRY,
        tau_threaded,
        dense_reference=DENSE_REFERENCE,
        model_u=U,
        requested_chi=CHI,
        preparation_chi=PREP_CHI,
        actual_max_chi,
        bootstrap_calls,
        bootstrap_passes,
        bootstrap_strategy="EdgeExactExpansion",
        bootstrap_state_error=bootstrap_error,
        reference_seconds,
        warmup_seconds,
        measured_wall_seconds,
        peak_rss_bytes=Sys.maxrss(),
        tau_max_absolute_error=DENSE_REFERENCE ? maximum(tau_abs_errors) : NaN,
        tau_l2_relative_error,
        iw_max_absolute_error=DENSE_REFERENCE ? maximum(iw_abs_errors) : NaN,
        iw_l2_relative_error,
        all_finite=all(isfinite, vcat(
            real.(gtau), imag.(gtau), real.(giw), imag.(giw))),
        all_linear_solves_converged,
        maximum_linear_residual,
        julia_version=VERSION,
        graft_commit=GRAFT_COMMIT,
        graftimpurity_commit=GRAFTIMPURITY_COMMIT,
        greenfunc_commit=GREENFUNC_COMMIT,
        julia_threads=Threads.nthreads(),
        blas_threads=BLAS.get_num_threads(),
    )

    write_rows(tau_path, tau_rows)
    write_rows(iw_path, iw_rows)
    write_namedtuple(summary_path, summary)
    println("TEAMC_GTAU_SUMMARY ", summary)
    println("SUMMARY_PATH=", summary_path)
    println("TAU_PATH=", tau_path)
    println("IW_PATH=", iw_path)
end

for U in MODEL_US
    main(U)
end
