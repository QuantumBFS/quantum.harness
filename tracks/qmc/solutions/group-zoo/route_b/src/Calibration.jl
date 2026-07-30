function calibration_grid(values)
    checked = sort!(unique(Float64.(collect(values))))
    isempty(checked) && throw(ArgumentError("calibration values must not be empty"))
    all(isfinite, checked) && all(>(0), checked) ||
        throw(ArgumentError("calibration values must be finite and positive"))
    return [(a, b, c) for a in checked for b in checked for c in checked]
end

function select_calibration(candidates::AbstractVector)
    isempty(candidates) && throw(ArgumentError("calibration candidate table is empty"))
    for candidate in candidates
        length(candidate.multipliers) == 3 ||
            throw(ArgumentError("calibration candidates require three multipliers"))
        all(isfinite, candidate.multipliers) && all(>(0), candidate.multipliers) ||
            throw(ArgumentError("calibration multipliers must be finite and positive"))
        isfinite(candidate.ess_per_second) && candidate.ess_per_second > 0 ||
            throw(ArgumentError("calibration efficiency must be finite and positive"))
    end
    accepted = [candidate for candidate in candidates if candidate.ergodic]
    isempty(accepted) && throw(ArgumentError("no ergodic calibration candidate"))
    best_efficiency = maximum(candidate.ess_per_second for candidate in accepted)
    tied = [
        candidate for candidate in accepted
        if candidate.ess_per_second >= 0.98best_efficiency
    ]
    sort!(tied; by=candidate -> (sum(candidate.multipliers), candidate.multipliers))
    return first(tied)
end

function make_regression_calibration_tasks(config::AbstractDict)
    grid = calibration_grid(config["multiplier_values"])
    replicas = Int(config["replicas"])
    replicas > 0 || throw(ArgumentError("calibration replicas must be positive"))
    tasks = TaskSpec[]
    for (system_index, lattice) in enumerate((:chain, :square))
        system = config["systems"][String(lattice)]
        for (candidate_index, multipliers) in enumerate(grid), replica in 1:replicas
            push!(tasks, TaskSpec(
                lattice=lattice,
                L=Int(system["L"]),
                J=Float64(config["J"]),
                h=Float64(system["h"]),
                beta_over_L=Float64(system["c"]),
                seed=14800000 + system_index * 100000 + candidate_index * 100 + replica,
                kernel=:huang,
                tau_multipliers=multipliers,
                warmup_bins=Int(config["warmup_bins"]),
                retained_bins=Int(config["retained_bins"]),
                visits_per_bin=Int(config["visits_per_bin"]),
                checkpoint_every=Int(config["checkpoint_every"]),
                purpose=:regression_calibration,
            ))
        end
    end
    return tasks
end

function make_universal_regression_tasks(config::AbstractDict)
    multipliers = Tuple(Float64.(config["selected_tau_multipliers"]))
    length(multipliers) == 3 || throw(ArgumentError("three selected tau multipliers required"))
    replicas = Int(config["replicas"])
    replicas > 0 || throw(ArgumentError("regression replicas must be positive"))
    anchors = Float64.(config["field_anchors"])
    isempty(anchors) && throw(ArgumentError("regression field anchors must not be empty"))
    tasks = TaskSpec[]
    for (system_index, lattice) in enumerate((:chain, :square))
        system = config["systems"][String(lattice)]
        yt = Float64(system["yt"])
        hc = Float64(system["hc_anchor"])
        for (size_index, L) in enumerate(Int.(system["sizes"]))
            for (anchor_index, anchor) in enumerate(anchors), replica in 1:replicas
                field = hc + anchor / L^yt
                push!(tasks, TaskSpec(
                    lattice=lattice,
                    L=L,
                    J=Float64(config["J"]),
                    h=field,
                    beta_over_L=1.0,
                    seed=14900000 + system_index * 1000000 + size_index * 10000 +
                         anchor_index * 100 + replica,
                    kernel=:huang,
                    tau_multipliers=multipliers,
                    warmup_bins=Int(config["warmup_bins"]),
                    retained_bins=Int(config["retained_bins"]),
                    visits_per_bin=Int(config["visits_per_bin"]),
                    checkpoint_every=Int(config["checkpoint_every"]),
                    purpose=:universal_regression,
                ))
            end
        end
    end
    return tasks
end
