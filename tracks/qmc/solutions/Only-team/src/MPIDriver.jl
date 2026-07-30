using MPI
using StableRNGs
using TOML

function deterministic_seed(
    base_seed::UInt64,
    rank::Integer,
)::UInt64
    rank >= 0 || throw(ArgumentError("rank must be nonnegative"))
    value =
        base_seed +
        0x9e3779b97f4a7c15 * (UInt64(rank) + UInt64(1))
    value = (value ⊻ (value >> 30)) * 0xbf58476d1ce4e5b9
    value = (value ⊻ (value >> 27)) * 0x94d049bb133111eb
    return value ⊻ (value >> 31)
end

function reduce_bin(
    bin::Int,
    m2_rank::Float64,
    m4_rank::Float64,
    comm,
)::Union{Nothing,BinRecord}
    rank = MPI.Comm_rank(comm)
    nprocs = MPI.Comm_size(comm)
    send_buffer = Float64[m2_rank, m4_rank]
    receive_buffer = zeros(Float64, 2)
    MPI.Reduce!(send_buffer, receive_buffer, +, comm; root = 0)

    record = nothing
    status = Int32[1]
    if rank == 0
        try
            record = bin_record(
                bin,
                receive_buffer[1] / nprocs,
                receive_buffer[2] / nprocs,
            )
        catch
            status[1] = 0
        end
    end
    MPI.Bcast!(status, comm; root = 0)
    status[1] == 1 ||
        throw(ArgumentError("reduced bin moments cannot define a finite Binder Q"))
    return record
end

function prepare_output_directory(
    path::AbstractString,
    comm,
)::Nothing
    rank = MPI.Comm_rank(comm)
    status = Int32[1]

    if rank == 0
        try
            if ispath(path)
                if !isdir(path) || !isempty(readdir(path))
                    status[1] = 0
                end
            else
                mkpath(path)
            end
        catch
            status[1] = 0
        end
    end

    MPI.Bcast!(status, comm; root = 0)
    status[1] == 1 ||
        throw(
            ArgumentError(
                "output directory is nonempty or cannot be prepared: $path",
            ),
        )
    return nothing
end

function _reduce_diagnostics(
    diagnostics::UpdateDiagnostics,
    comm,
)
    rank = MPI.Comm_rank(comm)
    send_buffer = Int64[
        diagnostics.local_attempts,
        diagnostics.local_accepts,
        diagnostics.cluster_size_sum,
        diagnostics.cluster_count,
    ]
    receive_buffer = zeros(Int64, 4)
    MPI.Reduce!(send_buffer, receive_buffer, +, comm; root = 0)
    return rank == 0 ? receive_buffer : nothing
end

function _reduce_wall_time(elapsed::Float64, comm)
    rank = MPI.Comm_rank(comm)
    send_buffer = Float64[elapsed]
    receive_buffer = zeros(Float64, 1)
    MPI.Reduce!(
        send_buffer,
        receive_buffer,
        MPI.MAX,
        comm;
        root = 0,
    )
    return rank == 0 ? receive_buffer[1] : nothing
end

function _safe_git_commit(config::SimulationConfig)
    repo_root = config.output_dir
    for _ in 1:5
        repo_root = dirname(repo_root)
    end

    try
        commit = readchomp(
            pipeline(
                `git -C $repo_root rev-parse HEAD`;
                stderr = devnull,
            ),
        )
        return isempty(commit) ? nothing : commit
    catch
        return nothing
    end
end

function _site_count(config::SimulationConfig)
    cells = config.NumL1 * config.NumL2
    return config.lattice === :triangular ? cells : 2 * cells
end

function write_results(
    path,
    config,
    summary,
    records,
    diagnostics,
    seeds,
    wall_time,
)::Nothing
    NumNS = _site_count(config)
    nprocs = length(seeds)
    total_measurements = nprocs * config.NmBin * config.NSwep

    open(joinpath(path, "results.csv"), "w") do io
        println(
            io,
            "lattice,NumL1,NumL2,NumNS,J1,J2,hTrfd,BetaT,LTrot,Dltau,nprocs,total_measurements,m2,m2_error,binder_Q,binder_Q_error,statistics_mode",
        )
        println(
            io,
            join(
                (
                    string(config.lattice),
                    config.NumL1,
                    config.NumL2,
                    NumNS,
                    config.J1,
                    config.J2,
                    config.hTrfd,
                    config.BetaT,
                    config.LTrot,
                    config.Dltau,
                    nprocs,
                    total_measurements,
                    summary.m2,
                    summary.m2_error,
                    summary.binder_Q,
                    summary.binder_Q_error,
                    string(config.statistics_mode),
                ),
                ",",
            ),
        )
    end

    open(joinpath(path, "bins.csv"), "w") do io
        println(io, "bin,m2_bin,m4_bin,Q_bin")
        for record in records
            println(
                io,
                join((record.bin, record.m2, record.m4, record.Q), ","),
            )
        end
    end

    runtime = Dict{String,Any}(
        "julia_version" => string(VERSION),
        "mpi_size" => nprocs,
        "rank_seeds" => string.(seeds),
        "wall_time_seconds" => wall_time,
    )
    git_commit = _safe_git_commit(config)
    isnothing(git_commit) || (runtime["git_commit"] = git_commit)

    metadata = Dict{String,Any}(
        "raw_input" => deepcopy(config.raw_input),
        "actual_parameters" => Dict{String,Any}(
            "lattice" => string(config.lattice),
            "NumL1" => config.NumL1,
            "NumL2" => config.NumL2,
            "NumNS" => NumNS,
            "J1" => config.J1,
            "J2" => config.J2,
            "hTrfd" => config.hTrfd,
            "BetaT" => config.BetaT,
            "IfSetDltau" => config.IfSetDltau,
            "FixedDltau" => config.FixedDltau,
            "input_LTrot" => config.input_LTrot,
            "LTrot" => config.LTrot,
            "Dltau" => config.Dltau,
            "nLocal" => config.nLocal,
            "nWolff" => config.nWolff,
            "seed" => string(config.seed),
            "initial_state" => string(config.initial_state),
        ),
        "derived_couplings" => Dict{String,Any}(
            "CpTau" => config.CpTau,
            "K_space" => config.K_space,
            "K_tau" => config.K_tau,
            "p_space" => config.p_space,
            "p_tau" => config.p_tau,
        ),
        "runtime" => runtime,
        "sampling" => Dict{String,Any}(
            "nWarm" => config.nWarm,
            "NmBin" => config.NmBin,
            "NSwep" => config.NSwep,
            "NmMeaConfg" => config.NmMeaConfg,
            "total_measurements" => total_measurements,
        ),
        "statistics" => Dict{String,Any}(
            "statistics_mode" => string(summary.statistics_mode),
            "discard_initial_bins" => summary.discard_initial_bins,
            "trim_extrema" => summary.trim_extrema,
            "number_of_bins_before_filtering" =>
                summary.number_of_bins_before_filtering,
            "number_of_bins_after_filtering" =>
                summary.number_of_bins_after_filtering,
            "m2_retained_bins" => summary.m2_filter.retained_bins,
            "m2_removed_bins" => summary.m2_filter.removed_bins,
            "binder_Q_retained_bins" =>
                summary.binder_Q_filter.retained_bins,
            "binder_Q_removed_bins" =>
                summary.binder_Q_filter.removed_bins,
        ),
        "diagnostics" => Dict{String,Any}(
            "local_attempts" => diagnostics.local_attempts,
            "local_accepts" => diagnostics.local_accepts,
            "local_acceptance" => diagnostics.local_acceptance,
            "cluster_size_sum" => diagnostics.cluster_size_sum,
            "cluster_count" => diagnostics.cluster_count,
            "mean_cluster_size" => diagnostics.mean_cluster_size,
            "mean_cluster_fraction" => diagnostics.mean_cluster_fraction,
        ),
    )

    open(joinpath(path, "metadata.toml"), "w") do io
        TOML.print(io, metadata; sorted = true)
    end
    return nothing
end

function run_simulation(
    config::SimulationConfig,
    comm = MPI.COMM_WORLD,
)::Union{Nothing,NamedTuple}
    validate_statistics_feasibility(config)
    prepare_output_directory(config.output_dir, comm)

    rank = MPI.Comm_rank(comm)
    nprocs = MPI.Comm_size(comm)
    started_at = time()
    lattice = build_lattice(config.lattice, config.NumL1, config.NumL2)
    segments = tau_segments(config.LTrot, config.NmMeaConfg)
    rank_seed = deterministic_seed(config.seed, rank)
    rng = StableRNG(rank_seed)
    state = initialize_state(config, lattice, rng)

    warm_progress = max(1, cld(max(config.nWarm, 1), 10))
    for warm_step in 1:config.nWarm
        update_cycle!(state, lattice, config, rng)
        if rank == 0 &&
           (warm_step % warm_progress == 0 || warm_step == config.nWarm)
            println("warmup $warm_step / $(config.nWarm)")
            flush(stdout)
        end
    end

    records = BinRecord[]
    diagnostic_totals = zeros(Int64, 4)
    for bin in 1:config.NmBin
        reset_diagnostics!(state.diagnostics)
        accumulator = BinAccumulator(0.0, 0.0, 0)

        for _ in 1:config.NSwep
            update_cycle!(state, lattice, config, rng)
            measure!(accumulator, state, segments, rng)
        end

        accumulator.measurement_count == config.NSwep ||
            error("measurement count does not equal NSwep")
        m2_rank = accumulator.m2_sum / accumulator.measurement_count
        m4_rank = accumulator.m4_sum / accumulator.measurement_count
        record = reduce_bin(bin, m2_rank, m4_rank, comm)
        reduced_diagnostics = _reduce_diagnostics(state.diagnostics, comm)

        if rank == 0
            push!(records, record)
            diagnostic_totals .+= reduced_diagnostics
            println("completed bin $bin / $(config.NmBin)")
            flush(stdout)
        end
    end

    elapsed = time() - started_at
    wall_time = _reduce_wall_time(elapsed, comm)
    seeds = MPI.Gather(rank_seed, comm; root = 0)

    if rank != 0
        return nothing
    end

    summary = summarize_bins(records, config)
    local_attempts = diagnostic_totals[1]
    local_accepts = diagnostic_totals[2]
    cluster_size_sum = diagnostic_totals[3]
    cluster_count = diagnostic_totals[4]
    diagnostics = (;
        local_attempts,
        local_accepts,
        local_acceptance = local_attempts == 0 ?
                           "not_applicable" :
                           local_accepts / local_attempts,
        cluster_size_sum,
        cluster_count,
        mean_cluster_size = cluster_count == 0 ?
                            "not_applicable" :
                            cluster_size_sum / cluster_count,
        mean_cluster_fraction = cluster_count == 0 ?
                                "not_applicable" :
                                cluster_size_sum /
                                (
                                    cluster_count *
                                    lattice.N *
                                    config.LTrot
                                ),
    )
    write_results(
        config.output_dir,
        config,
        summary,
        records,
        diagnostics,
        seeds,
        wall_time,
    )
    return (; summary, records, diagnostics, seeds, wall_time, nprocs)
end
