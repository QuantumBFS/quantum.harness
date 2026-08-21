mutable struct CounterRNG
    state::UInt64
end

CounterRNG(seed::Integer) = CounterRNG(UInt64(seed))

function rand_u64!(rng::CounterRNG)
    rng.state += 0x9e3779b97f4a7c15
    value = rng.state
    value = (value ⊻ (value >> 30)) * 0xbf58476d1ce4e5b9
    value = (value ⊻ (value >> 27)) * 0x94d049bb133111eb
    return value ⊻ (value >> 31)
end

rand_float!(rng::CounterRNG) = Float64(rand_u64!(rng) >> 11) * 0x1.0p-53

function rand_int!(rng::CounterRNG, upper::Integer)
    upper > 0 || throw(ArgumentError("upper must be positive"))
    bound = UInt64(upper)
    threshold = mod(typemax(UInt64) - bound + UInt64(1), bound)
    while true
        value = rand_u64!(rng)
        value >= threshold && return Int(mod(value, bound)) + 1
    end
end
