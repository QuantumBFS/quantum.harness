module LongRangeIsingClock

using Random, Statistics, LinearAlgebra

export ClockKernel, build_kernel, clock_attempt!, direct_attempt!,
       validate_clock, run_clock

struct ClockKernel
    L::Int
    dx::Vector{Int}
    dy::Vector{Int}
    coupling::Vector{Float64}
    cumulative_hazard::Vector{Float64}
end

function build_kernel(L::Int, sigma::Real, beta::Real)
    L >= 2 || error("L must be >= 2")
    raw = Float64[]
    dx = Int[]
    dy = Int[]
    for y in 0:L-1, x in 0:L-1
        x == 0 && y == 0 && continue
        mx = min(x, L-x)
        my = min(y, L-y)
        push!(dx, x)
        push!(dy, y)
        push!(raw, (mx*mx + my*my)^(-(2+sigma)/2))
    end
    coupling = 4 .* raw ./ sum(raw)
    order = sortperm(coupling; rev=true)
    coupling = coupling[order]
    ClockKernel(L, dx[order], dy[order], coupling,
                cumsum(2 .* beta .* coupling))
end

@inline function next_candidate(k::ClockKernel, start::Int, rng)
    start > length(k.coupling) && return length(k.coupling)+1
    previous = start == 1 ? 0.0 : k.cumulative_hazard[start-1]
    searchsortedfirst(k.cumulative_hazard, previous-log(rand(rng)))
end

@inline function clock_attempt!(spins, site::Int, k::ClockKernel, rng)
    L = k.L
    x = (site-1) % L + 1
    y = (site-1) ÷ L + 1
    si = spins[site]
    bond = next_candidate(k, 1, rng)
    while bond <= length(k.coupling)
        xj = mod1(x+k.dx[bond], L)
        yj = mod1(y+k.dy[bond], L)
        if spins[xj+(yj-1)*L] == si
            return false
        end
        bond = next_candidate(k, bond+1, rng)
    end
    spins[site] = -si
    true
end

@inline function direct_attempt!(spins, site::Int, k::ClockKernel, beta, rng)
    L = k.L
    x = (site-1) % L + 1
    y = (site-1) ÷ L + 1
    si = spins[site]
    for bond in eachindex(k.coupling)
        xj = mod1(x+k.dx[bond], L)
        yj = mod1(y+k.dy[bond], L)
        if spins[xj+(yj-1)*L] == si &&
           rand(rng) < -expm1(-2beta*k.coupling[bond])
            return false
        end
    end
    spins[site] = -si
    true
end

function validate_clock(; trials=200_000, seed=1905)
    L, sigma, beta = 4, 1.875, 0.336985
    k = build_kernel(L, sigma, beta)
    base = Int8[1,-1,1,1,-1,1,-1,1,1,1,-1,-1,-1,-1,1,-1]
    rc = MersenneTwister(seed)
    rd = MersenneTwister(seed+1)
    ac = sum(clock_attempt!(copy(base), 6, k, rc) for _ in 1:trials)/trials
    ad = sum(direct_attempt!(copy(base), 6, k, beta, rd) for _ in 1:trials)/trials
    tolerance = 6sqrt(max(ac*(1-ac), ad*(1-ad))/trials)
    abs(ac-ad) <= tolerance ||
        error("Clock/direct mismatch: $ac versus $ad (tol=$tolerance)")
    (; clock_acceptance=ac, direct_acceptance=ad, tolerance)
end

function sweep!(spins, k, rng)
    accepted = 0
    for _ in eachindex(spins)
        accepted += clock_attempt!(spins, rand(rng, eachindex(spins)), k, rng)
    end
    accepted/length(spins)
end

function block_means(v, nblocks)
    blocksize = length(v) ÷ nblocks
    [mean(@view v[(i-1)*blocksize+1:i*blocksize]) for i in 1:nblocks]
end

function tau_int(v, nblocks)
    z = v .- mean(v)
    denom = sum(abs2, z)
    denom == 0 && return 0.5
    tau = 0.5
    for lag in 1:min(200, length(v) ÷ 10)
        rho = dot(@view(z[1:end-lag]), @view(z[1+lag:end]))/denom
        rho <= 0 && break
        tau += rho
    end
    bm = block_means(v, nblocks)
    blocksize = length(v) ÷ nblocks
    tau_batch = 0.5*blocksize*var(bm)/var(v)
    max(tau, tau_batch)
end

function run_clock(; L, sigma, beta, seed, therm, meas, sample_every=1,
                   nblocks=50)
    rng = MersenneTwister(seed)
    k = build_kernel(L, sigma, beta)
    spins = rand(rng, Int8[-1,1], L^2)
    for _ in 1:therm
        sweep!(spins, k, rng)
    end
    m2 = Float64[]
    m4 = Float64[]
    acceptance = 0.0
    started = time()
    for sweep in 1:meas
        acceptance += sweep!(spins, k, rng)
        if sweep % sample_every == 0
            m = sum(spins)/length(spins)
            push!(m2, m*m)
            push!(m4, m^4)
        end
    end
    nsamples = length(m2)
    nblocks = min(nblocks, max(2, nsamples ÷ 20))
    bm2 = block_means(m2, nblocks)
    bm4 = block_means(m4, nblocks)
    mean2, mean4 = mean(m2), mean(m4)
    summary = (L=L, sigma=Float64(sigma), beta=Float64(beta), seed=seed,
      therm=therm, meas=meas, sample_every=sample_every, nsamples=nsamples,
      mean_m2=mean2, mean_m4=mean4, Qm=mean2^2/mean4,
      chi=L^2*mean2, acceptance=acceptance/meas, tau_m2=tau_int(m2,nblocks),
      blocks=nblocks, runtime_s=time()-started, sumJ=sum(k.coupling))
    (; summary, block_m2=bm2, block_m4=bm4)
end

end
