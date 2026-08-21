function make_ed_validation_tasks(config::AbstractDict, rows::AbstractVector)
    Int(config["schema"]) == 1 || throw(ArgumentError("unsupported ED config schema"))
    get(config, "production_authorized", true) == false ||
        throw(ArgumentError("ED validation config must forbid production"))
    replicas = Int(config["replicas"])
    replicas > 0 || throw(ArgumentError("ED replicas must be positive"))
    multipliers = Float64.(config["tau_multipliers"])
    tasks = TaskSpec[]
    for (row_index, row) in enumerate(rows)
        lattice = Symbol(row["lattice"])
        system = config["systems"][String(lattice)]
        Int(system["L"]) == Int(row["L"]) ||
            throw(ArgumentError("ED row L disagrees with config"))
        Float64(system["h"]) == Float64(row["h"]) ||
            throw(ArgumentError("ED row h disagrees with config"))
        for replica in 1:replicas
            push!(tasks, TaskSpec(
                lattice=lattice,
                L=Int(row["L"]),
                J=Float64(config["J"]),
                h=Float64(row["h"]),
                beta_over_L=Float64(row["c"]),
                seed=148000 + (row_index - 1) * 100 + replica,
                kernel=:huang,
                tau_multipliers=multipliers,
                warmup_bins=Int(config["warmup_bins"]),
                retained_bins=Int(config["retained_bins"]),
                visits_per_bin=Int(config["visits_per_bin"]),
                checkpoint_every=Int(config["checkpoint_every"]),
                purpose=:ed_validation,
            ))
        end
    end
    return tasks
end
