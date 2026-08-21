struct TaskSpec
    schema::Int
    lattice::Symbol
    L::Int
    J::Float64
    h::Float64
    beta_over_L::Float64
    beta::Float64
    seed::UInt64
    kernel::Symbol
    tau_multipliers::NTuple{3,Float64}
    warmup_bins::Int
    retained_bins::Int
    visits_per_bin::Int
    checkpoint_every::Int
    purpose::Symbol
end

function TaskSpec(
    ; lattice::Symbol,
    L::Integer,
    J::Real,
    h::Real,
    beta_over_L::Real,
    seed::Integer,
    kernel::Symbol,
    tau_multipliers,
    warmup_bins::Integer,
    retained_bins::Integer,
    visits_per_bin::Integer,
    checkpoint_every::Integer,
    purpose::Symbol,
)
    L >= 2 || throw(ArgumentError("L must be at least two"))
    lattice in (:chain, :square, :honeycomb, :triangle) ||
        throw(ArgumentError("unsupported task lattice"))
    kernel == :huang || throw(ArgumentError("Route B task kernel must be :huang"))
    purpose != :production || throw(ArgumentError("production tasks require a later gate"))
    coupling = _positive_coupling(J)
    field = _finite_float("h", h)
    aspect = _finite_float("beta_over_L", beta_over_L)
    aspect > 0 || throw(ArgumentError("beta_over_L must be positive"))
    length(tau_multipliers) == 3 || throw(ArgumentError("three tau multipliers are required"))
    multipliers = ntuple(index -> begin
        value = _finite_float("tau multiplier", tau_multipliers[index])
        value > 0 || throw(ArgumentError("tau multipliers must be positive"))
        value
    end, 3)
    warmup_bins >= 0 || throw(ArgumentError("warmup_bins must be nonnegative"))
    retained_bins > 0 || throw(ArgumentError("retained_bins must be positive"))
    visits_per_bin > 0 || throw(ArgumentError("visits_per_bin must be positive"))
    checkpoint_every > 0 || throw(ArgumentError("checkpoint_every must be positive"))
    return TaskSpec(
        1,
        lattice,
        Int(L),
        coupling,
        field,
        aspect,
        aspect * L,
        UInt64(seed),
        kernel,
        multipliers,
        Int(warmup_bins),
        Int(retained_bins),
        Int(visits_per_bin),
        Int(checkpoint_every),
        purpose,
    )
end

function _task_record(task::TaskSpec)
    return (
        schema=task.schema,
        lattice=String(task.lattice),
        L=task.L,
        J=task.J,
        h=task.h,
        beta_over_L=task.beta_over_L,
        beta=task.beta,
        seed=string(task.seed),
        kernel=String(task.kernel),
        tau_multipliers=collect(task.tau_multipliers),
        warmup_bins=task.warmup_bins,
        retained_bins=task.retained_bins,
        visits_per_bin=task.visits_per_bin,
        checkpoint_every=task.checkpoint_every,
        purpose=String(task.purpose),
    )
end

canonical_task_json(task::TaskSpec) = JSON.json(_task_record(task))

function parse_task(encoded::AbstractString)
    data = JSON.parse(encoded)
    Int(data["schema"]) == 1 || throw(ArgumentError("unsupported task schema"))
    return TaskSpec(
        lattice=Symbol(data["lattice"]),
        L=Int(data["L"]),
        J=Float64(data["J"]),
        h=Float64(data["h"]),
        beta_over_L=Float64(data["beta_over_L"]),
        seed=parse(UInt64, data["seed"]),
        kernel=Symbol(data["kernel"]),
        tau_multipliers=Float64.(data["tau_multipliers"]),
        warmup_bins=Int(data["warmup_bins"]),
        retained_bins=Int(data["retained_bins"]),
        visits_per_bin=Int(data["visits_per_bin"]),
        checkpoint_every=Int(data["checkpoint_every"]),
        purpose=Symbol(data["purpose"]),
    )
end

task_hash(task::TaskSpec) = bytes2hex(SHA.sha256(codeunits(canonical_task_json(task))))
