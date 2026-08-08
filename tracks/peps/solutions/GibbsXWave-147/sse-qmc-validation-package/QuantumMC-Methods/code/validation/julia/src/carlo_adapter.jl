"""
    TFIMSSECarlo(params)

`Carlo.AbstractMC` adapter for the transparent TFIM SSE kernel.

Required task parameters are `:Lx`, `:Ly`, `:J`, `:h`, and `:beta`. Carlo
itself consumes `:thermalization`, `:binsize`, and optionally `:seed`.
"""
mutable struct TFIMSSECarlo <: Carlo.AbstractMC
    model::SquareLatticeTFIM
    beta::Float64
    requested_cutoff::Union{Nothing,Int}
    validate_every::Int
    state::Union{Nothing,SSEState}
end

function TFIMSSECarlo(params::AbstractDict)
    model = SquareLatticeTFIM(
        Int(params[:Lx]),
        Int(get(params, :Ly, params[:Lx]));
        J=Float64(params[:J]),
        h=Float64(params[:h]),
    )
    beta = Float64(params[:beta])
    beta > 0 || throw(ArgumentError("SSE requires beta > 0"))
    requested_cutoff =
        haskey(params, :cutoff) ? Int(params[:cutoff]) : nothing
    validate_every = Int(get(params, :validate_every, 0))
    return TFIMSSECarlo(model, beta, requested_cutoff, validate_every, nothing)
end

function _initialized_state(mc::TFIMSSECarlo)
    isnothing(mc.state) && error("TFIMSSECarlo has not been initialized")
    return mc.state::SSEState
end

function Carlo.init!(mc::TFIMSSECarlo, ctx::Carlo.MCContext,
                     params::AbstractDict)
    mc.state = initialize_sse(mc.model, mc.beta, ctx.rng;
                              cutoff=mc.requested_cutoff)
    return nothing
end

function Carlo.sweep!(mc::TFIMSSECarlo, ctx::Carlo.MCContext)
    state = _initialized_state(mc)

    # MCContext.sweeps is incremented by Carlo after this callback. The first
    # measured sweep starts when it equals thermalization_sweeps.
    if ctx.sweeps == ctx.thermalization_sweeps
        state.max_n_observed = state.n
        state.cutoff_touched = state.n == length(state.operators)
    end

    sweep!(state, mc.model, mc.beta, ctx.rng)

    if ctx.sweeps < ctx.thermalization_sweeps &&
       4state.n > 3length(state.operators)
        grow_cutoff!(state)
    end

    if mc.validate_every > 0 &&
       (ctx.sweeps + 1) % mc.validate_every == 0
        validate_configuration(state, mc.model)
    end
    return nothing
end

function Carlo.measure!(mc::TFIMSSECarlo, ctx::Carlo.MCContext)
    state = _initialized_state(mc)
    measurement = raw_measurement(state, mc.model)
    N = nsites(mc.model)
    Nb = nbonds(mc.model)
    deflated_shift = mc.model.J * Nb

    Carlo.measure!(ctx, :ExpansionOrder, Float64(measurement.n))
    Carlo.measure!(ctx, :ExpansionOrder2, Float64(measurement.n2))
    Carlo.measure!(ctx, :DeflatedExpansionOrder, Float64(measurement.m))
    Carlo.measure!(ctx, :DeflatedExpansionOrder2, Float64(measurement.m2))
    Carlo.measure!(ctx, :BondOperatorCount, Float64(measurement.nJ))
    Carlo.measure!(ctx, :SiteOperatorCount, Float64(measurement.nh))
    Carlo.measure!(ctx, :SiteConstantCount, Float64(measurement.n0))
    Carlo.measure!(ctx, :SiteFlipCount, Float64(measurement.nflip))
    Carlo.measure!(ctx, :EnergyDensity,
                   (deflated_shift - measurement.m / mc.beta) / N)
    Carlo.measure!(ctx, :MagnetizationZ2, measurement.mz2)
    Carlo.measure!(ctx, :Cutoff, Float64(length(state.operators)))
    Carlo.measure!(ctx, :CutoffTouched, state.cutoff_touched ? 1.0 : 0.0)

    if !iszero(mc.model.h)
        Carlo.measure!(
            ctx,
            :TransverseMagnetization,
            measurement.nflip / (mc.beta * mc.model.h * N),
        )
    end
    if !iszero(mc.model.J) && !iszero(Nb)
        Carlo.measure!(
            ctx,
            :BondCorrelation,
            -1 + measurement.nJ / (mc.beta * mc.model.J * Nb),
        )
    end
    return nothing
end

function Carlo.register_evaluables(::Type{TFIMSSECarlo},
                                   evaluator::Carlo.AbstractEvaluator,
                                   params::AbstractDict)
    N = Int(params[:Lx]) * Int(get(params, :Ly, params[:Lx]))
    Carlo.evaluate!(
        (mean_m, mean_m2) -> (mean_m2 - mean_m^2 - mean_m) / N,
        evaluator,
        :HeatCapacityDensity,
        (:DeflatedExpansionOrder, :DeflatedExpansionOrder2),
    )
    return nothing
end

# Carlo stores the context, RNG, and accumulated bins. These callbacks store
# only the scientific configuration required to resume the Markov chain.
function Carlo.write_checkpoint(mc::TFIMSSECarlo, out::HDF5.Group)
    state = _initialized_state(mc)
    out["spins"] = state.spins
    out["operator_kinds"] = [operator.kind for operator in state.operators]
    out["operator_targets"] = [operator.target for operator in state.operators]
    out["expansion_order"] = state.n
    out["max_expansion_order"] = state.max_n_observed
    out["cutoff_touched"] = state.cutoff_touched ? 1 : 0
    return nothing
end

function Carlo.read_checkpoint!(mc::TFIMSSECarlo, input::HDF5.Group)
    spins = Int8.(read(input["spins"]))
    kinds = UInt8.(read(input["operator_kinds"]))
    targets = Int.(read(input["operator_targets"]))
    length(kinds) == length(targets) ||
        error("checkpoint operator arrays have different lengths")
    operators = [SSEOperator(kind, target) for (kind, target) in zip(kinds, targets)]
    mc.state = SSEState(
        spins,
        operators,
        Int(read(input["expansion_order"])),
        Int(read(input["max_expansion_order"])),
        !iszero(read(input["cutoff_touched"])),
    )
    validate_configuration(_initialized_state(mc), mc.model)
    return nothing
end
