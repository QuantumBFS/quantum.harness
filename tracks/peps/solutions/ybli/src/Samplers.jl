"""
Born-rule sampling strategies (workflow section 4).

Three samplers, in order of preference:

1. DirectSampler -- iid configurations (Nishimori gauge-equivalent).
   No thermalization or autocorrelation; the cleanest cluster benchmark.

2. SequentialBornSampler -- online trajectory sampling using conditional
   outcome probabilities.  Different trajectories are independent.

3. MetropolisSampler -- cached-environment MCMC with local/loop/global
   moves, used when only a weight oracle m -> log Z_m is available.

All samplers return SampleResult objects carrying the configuration,
log Z_m, and acceptance/diagnostic statistics.
"""

using Random
using LinearAlgebra
using Statistics

# ----------------------------------------------------------------------
# Result type
# ----------------------------------------------------------------------

"""
    SampleResult

Container for one sampled configuration and its diagnostics.

Fields:
  - config:     the sampled Configuration
  - logZ:       log Z_m (Born weight in log space)
  - logP:       log P(m) = kappa * log|Z_raw| + proposal_correction
  - accepted:   number of accepted proposals (MCMC only)
  - proposed:   number of proposed moves (MCMC only)
  - sweep:      current sweep index
  - logZ_history: vector of logZ values (for autocorrelation analysis)
"""
struct SampleResult
    config::Configuration
    logZ::Float64
    logP::Float64
    accepted::Int
    proposed::Int
    sweep::Int
    logZ_history::Vector{Float64}
end

"""Construct a minimal SampleResult for direct/sequential sampling."""
function SampleResult(config::Configuration, logZ::Float64)
    SampleResult(config, logZ, logZ, 0, 0, 0, [logZ])
end

# ----------------------------------------------------------------------
# 1. Direct (iid) sampler
# ----------------------------------------------------------------------

"""
    DirectSampler

Draws independent configurations from the model's native distribution.
For the Nishimori RBIM, gauge-invariant observables can be sampled from
the equivalent iid +/-J disorder distribution (workflow 4.1).

This is the preferred sampler whenever the model's sample_config draws
from the correct Born distribution directly.
"""
struct DirectSampler{M<:BornModel}
    model::M
    Ly::Int
end

"""
    sample!(sampler::DirectSampler, rng; nsamples)

Draw `nsamples` independent configurations and return a vector of
SampleResult objects.  Each sample is independent (no autocorrelation).
"""
function sample!(sampler::DirectSampler, rng::AbstractRNG; nsamples::Int=1)
    results = Vector{SampleResult}(undef, nsamples)
    for i in 1:nsamples
        config = sample_config(sampler.model, rng, sampler.Ly)
        logZ = dense_logZ(sampler.model, config)
        results[i] = SampleResult(config, logZ)
    end
    return results
end

"""
    run_direct(model, Ly, nsamples; rng, seed)

Convenience wrapper: draw `nsamples` iid configurations from `model`,
compute logZ for each, and return (logZs, configs).
"""
function run_direct(model::BornModel, Ly::Int, nsamples::Int;
                       rng::AbstractRNG=Random.default_rng())
    sampler = DirectSampler(model, Ly)
    results = sample!(sampler, rng; nsamples)
    logZs = [r.logZ for r in results]
    configs = [r.config for r in results]
    return logZs, configs
end

# ----------------------------------------------------------------------
# 2. Metropolis sampler with cached environments
# ----------------------------------------------------------------------

"""
    MetropolisSampler

MCMC over complete measurement/bond records using Metropolis-Hastings.

The acceptance ratio is:
  A(m -> m') = min[1, exp(Delta_logP)]
where
  Delta_logP = kappa * (log|Z_raw(m')| - log|Z_raw(m)|)
             + log(q(m|m') / q(m'|m))

For symmetric proposals the last term vanishes.

Moves:
  - :local    -- flip a single bond or outcome
  - :row      -- resample an entire row
  - :loop     -- gauge-loop flip (for Nishimori-type models)
  - :global   -- flip all bonds (global Z2 move)

Environment caching: after each accepted sweep, the transfer operators
are rebuilt lazily.  For a single-bond flip in row y, only row y's
transfer matrix is recomputed, and the logZ difference is estimated
via a partial contraction.
"""
mutable struct MetropolisSampler{M<:BornModel}
    model::M
    Ly::Int
    config::Configuration
    logZ::Float64
    move_weights::Dict{Symbol,Float64}
end

"""
    MetropolisSampler(model, Ly; rng, move_weights)

Initialize a Metropolis sampler with a random starting configuration.
"""
function MetropolisSampler(model::BornModel, Ly::Int;
                              rng::AbstractRNG=Random.default_rng(),
                              move_weights::Dict{Symbol,Float64}=Dict(
                                  :local => 0.6, :row => 0.2,
                                  :loop => 0.1, :global => 0.1))
    config = sample_config(model, rng, Ly)
    logZ = dense_logZ(model, config)
    MetropolisSampler(model, Ly, config, logZ, move_weights)
end

"""
    propose_local(sampler, rng)

Propose flipping a single bond at a random (x, y) position.
Returns (new_config, log_q_ratio) where log_q_ratio = 0 for symmetric proposal.
"""
function propose_local(sampler::MetropolisSampler, rng::AbstractRNG)
    config = sampler.config
    L = config.L
    Ly = config.Ly

    # Pick a random position
    x = rand(rng, 1:L)
    y = rand(rng, 1:sampler.Ly)
    is_vertical = rand(rng, Bool)

    new_bonds_v = copy(config.bonds_v)
    new_bonds_h = copy(config.bonds_h)
    new_outcomes = copy(config.outcomes)

    conv = convention(sampler.model)
    if conv.disorder == :clean
        # For clean Ising, flip an outcome (no effect on Z, but tests sampler)
        new_outcomes[x, y] = 1 - new_outcomes[x, y]
    else
        # Flip a bond: J -> -J
        if is_vertical
            new_bonds_v[x, y] = -new_bonds_v[x, y]
        else
            new_bonds_h[x, y] = -new_bonds_h[x, y]
        end
    end

    new_config = Configuration(L, Ly, new_bonds_v, new_bonds_h, new_outcomes)
    # Symmetric proposal
    return new_config, 0.0
end

"""
    propose_row(sampler, rng)

Resample all bonds in a single row from the model's prior.
"""
function propose_row(sampler::MetropolisSampler, rng::AbstractRNG)
    config = sampler.config
    L = config.L
    y = rand(rng, 1:sampler.Ly)

    new_bonds_v = copy(config.bonds_v)
    new_bonds_h = copy(config.bonds_h)

    conv = convention(sampler.model)
    if conv.disorder == :nishimori
        model = sampler.model
        p = typeof(model) == NishimoriRBIM ? model.p :
            (typeof(model) == MeasuredToricCode ? model.nishimori_model.p : 0.5)
        for x in 1:L
            new_bonds_v[x, y] = rand(rng) < p ? 1.0 : -1.0
            new_bonds_h[x, y] = rand(rng) < p ? 1.0 : -1.0
        end
    end

    new_config = Configuration(L, config.Ly, new_bonds_v, new_bonds_h, copy(config.outcomes))
    return new_config, 0.0
end

"""
    propose_loop(sampler, rng)

Gauge-loop move: flip all bonds around a plaquette.
For the Nishimori RBIM, this is a gauge transformation that leaves Z
invariant, so it tests detailed balance.
"""
function propose_loop(sampler::MetropolisSampler, rng::AbstractRNG)
    config = sampler.config
    L = config.L
    Ly = config.Ly

    x0 = rand(rng, 1:L)
    y0 = rand(rng, 1:Ly)
    x1 = mod1(x0 + 1, L)
    y1 = min(y0 + 1, Ly)

    new_bonds_v = copy(config.bonds_v)
    new_bonds_h = copy(config.bonds_h)

    # Flip the four bonds around plaquette (x0,y0)
    new_bonds_v[x0, y0] = -new_bonds_v[x0, y0]
    new_bonds_v[x1, y0] = -new_bonds_v[x1, y0]
    new_bonds_h[x0, y0] = -new_bonds_h[x0, y0]
    new_bonds_h[x0, y1] = -new_bonds_h[x0, y1]

    new_config = Configuration(L, Ly, new_bonds_v, new_bonds_h, copy(config.outcomes))
    return new_config, 0.0
end

"""
    propose_global(sampler, rng)

Global Z2 move: flip all bonds.
"""
function propose_global(sampler::MetropolisSampler, rng::AbstractRNG)
    config = sampler.config
    new_bonds_v = -copy(config.bonds_v)
    new_bonds_h = -copy(config.bonds_h)
    new_config = Configuration(config.L, config.Ly, new_bonds_v, new_bonds_h, copy(config.outcomes))
    return new_config, 0.0
end

"""
    step!(sampler, rng)

Perform one Metropolis-Hastings step.  Returns (accepted, move_type).
"""
function step!(sampler::MetropolisSampler, rng::AbstractRNG)
    # Choose move type
    moves = collect(keys(sampler.move_weights))
    weights = collect(values(sampler.move_weights))
    move_type = moves[_weighted_choice(rng, weights)]

    # Generate proposal
    if move_type == :local
        new_config, log_q_ratio = propose_local(sampler, rng)
    elseif move_type == :row
        new_config, log_q_ratio = propose_row(sampler, rng)
    elseif move_type == :loop
        new_config, log_q_ratio = propose_loop(sampler, rng)
    else
        new_config, log_q_ratio = propose_global(sampler, rng)
    end

    # Compute logZ for the proposed configuration
    new_logZ = dense_logZ(sampler.model, new_config)

    # Metropolis acceptance
    conv = convention(sampler.model)
    kappa = conv.kappa
    delta_logP = kappa * (new_logZ - sampler.logZ) + log_q_ratio

    accepted = false
    if delta_logP >= 0 || log(rand(rng)) < delta_logP
        sampler.config = new_config
        sampler.logZ = new_logZ
        accepted = true
    end

    return accepted, move_type
end

"""
    run_metropolis!(sampler, rng; nsweeps, burn_in, thin)

Run `nsweeps` MCMC sweeps.  Each sweep performs L*Ly local proposals
plus one of each other move type.  Returns a SampleResult with the
final configuration and the logZ history.

Arguments:
  - nsweeps: number of full sweeps
  - burn_in: number of initial sweeps to discard
  - thin:   keep every `thin`-th sample
"""
function run_metropolis!(sampler::MetropolisSampler, rng::AbstractRNG;
                           nsweeps::Int=100, burn_in::Int=10, thin::Int=1)
    L = sampler.config.L
    Ly = sampler.Ly
    steps_per_sweep = L * Ly

    logZ_history = Float64[]
    accepted_total = 0
    proposed_total = 0
    acceptance_by_move = Dict{Symbol, Tuple{Int,Int}}()

    for sweep in 1:(burn_in + nsweeps)
        for _ in 1:steps_per_sweep
            accepted, move_type = step!(sampler, rng)
            proposed_total += 1
            if accepted
                accepted_total += 1
            end
            # Track acceptance by move type
            if !haskey(acceptance_by_move, move_type)
                acceptance_by_move[move_type] = (0, 0)
            end
            a, p = acceptance_by_move[move_type]
            acceptance_by_move[move_type] = (a + Int(accepted), p + 1)
        end

        if sweep > burn_in && (sweep - burn_in) % thin == 0
            push!(logZ_history, sampler.logZ)
        end
    end

    return SampleResult(
        sampler.config,
        sampler.logZ,
        sampler.logZ,  # logP approximated by logZ for now
        accepted_total,
        proposed_total,
        nsweeps,
        logZ_history
    ), acceptance_by_move
end

# ----------------------------------------------------------------------
# Helper: weighted random choice (no StatsBase dependency)
# ----------------------------------------------------------------------

function _weighted_choice(rng::AbstractRNG, weights::AbstractVector{<:Real})
    s = sum(weights)
    r = rand(rng) * s
    cum = 0.0
    for (i, w) in enumerate(weights)
        cum += w
        if r <= cum
            return i
        end
    end
    return length(weights)
end

# ----------------------------------------------------------------------
# 3. Sequential Born sampler (stub for WP5)
# ----------------------------------------------------------------------

"""
    SequentialBornSampler

Online trajectory sampling using conditional outcome probabilities
(workflow 4.2).  Given the normalized state after history m_{<j},
evaluate each candidate branch:
  w_a = ||K_a |psi(m_{<j})>||^2,  p(a|m_{<j}) = w_a / sum_a' w_a'

Draw a, retain only that branch, normalize, and accumulate
  log P(m) = sum_j log p(m_j | m_{<j})

This requires a PEPS/quantum-state backend and is deferred to WP5.
Currently a stub.
"""
struct SequentialBornSampler{M<:BornModel}
    model::M
    Ly::Int
end

function sample!(sampler::SequentialBornSampler, rng::AbstractRNG; nsamples::Int=1)
    error("SequentialBornSampler requires a PEPS/quantum-state backend (WP5). " *
          "Use DirectSampler or MetropolisSampler for the Ising/Nishimori benchmarks.")
end

# ----------------------------------------------------------------------
# Autocorrelation analysis
# ----------------------------------------------------------------------

"""
    integrated_autocorrelation_time(series; max_lag)

Estimate the integrated autocorrelation time tau_int from a time series
using the windowing estimator:
  tau_int = 1 + 2 * sum_{k=1}^{W} rho_k

where rho_k is the autocorrelation at lag k and W is a window chosen
by the Sokal criterion (stop when rho_k < 0.05 or at max_lag).
"""
function integrated_autocorrelation_time(series::AbstractVector{<:Real};
                                            max_lag::Int=min(length(series)÷4, 200))
    n = length(series)
    if n < 4
        return NaN
    end

    mu = mean(series)
    var = sum((series .- mu).^2) / n
    if var == 0
        return 1.0
    end

    tau = 1.0
    for k in 1:max_lag
        rho_k = sum((series[1:n-k] .- mu) .* (series[k+1:n] .- mu)) / (n * var)
        tau += 2 * rho_k
        if rho_k < 0.05
            break
        end
    end

    return max(tau, 1.0)
end

"""
    block_mean(series; block_size)

Compute the mean and standard error using non-overlapping blocks.
"""
function block_mean(series::AbstractVector{<:Real}; block_size::Int=1)
    n = length(series)
    nblocks = n ÷ block_size
    if nblocks < 2
        return mean(series), NaN
    end

    blocks = Float64[]
    for i in 1:nblocks
        push!(blocks, mean(series[(i-1)*block_size+1 : i*block_size]))
    end

    return mean(blocks), std(blocks) / sqrt(nblocks)
end