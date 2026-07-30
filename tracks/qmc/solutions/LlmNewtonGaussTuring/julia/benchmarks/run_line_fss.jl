# Independent bounded FSS pilot for the color-parallel line update.
# Usage: julia -t 4 benchmarks/run_line_fss.jl triangular|honeycomb [output-dir]

include(joinpath(@__DIR__, "..", "src", "TIM_lattice_observables.jl"))

using Dates
using Printf
using SHA

const DEFAULT_RUN_ID = "tfim-lineupdate-julia-fss-pilot-20260730"
const HEADER = ["run_id", "lattice", "L", "N", "Nb", "h", "beta", "c_tau",
                "epsilon", "seed", "start", "bin", "n_thermal", "n_bins",
                "sweeps_per_bin", "line_threads", "E", "spacetime_m2",
                "spacetime_m4", "S0", "Sq", "equal_m4", "q_norm", "q_count",
                "acceptance", "config_checked", "bin_seconds"]

envint(name, default) = parse(Int, get(ENV, name, string(default)))
envfloat(name, default) = parse(Float64, get(ENV, name, string(default)))
envlist(name, default, parser) = [parser(strip(value)) for value in
                                  split(get(ENV, name, default), ',')]

function grow_operator_window_fss!(s::Sim)
    target = floor(Int, 1.25 * s.nh)
    if target > s.lm
        target <= s.ll || error("operator list overflow: target=$target capacity=$(s.ll)")
        s.lm = target
    end
end

function chain_seed(lattice, L, field_index, start_index, replica)
    lattice_offset = Symbol(lattice) == :triangular ? 10_000_000 : 20_000_000
    return 202607300000 + lattice_offset + 100_000L + 1_000field_index +
           100start_index + replica
end

function write_metadata(path, run_id, lattice, sizes, fields, c_tau, epsilon,
                        thermal, bins, sweeps_per_bin, line_threads, replicas, raw_path)
    project = joinpath(@__DIR__, "..")
    commit = readchomp(`git -C $project rev-parse HEAD`)
    source_files = (joinpath(project, "src", "TIM_lattice_QMC.jl"),
                    joinpath(project, "src", "TIM_lattice_line.jl"),
                    joinpath(project, "src", "TIM_lattice_observables.jl"),
                    joinpath(project, "src", "lattice_coloring.jl"),
                    abspath(@__FILE__))
    command = join(vcat([Base.julia_cmd().exec[1], abspath(PROGRAM_FILE)], Base.ARGS), ' ')
    timestamp = Dates.format(now(), dateformat"yyyy-mm-ddTHH:MM:SS")
    open(path, "w") do io
        println(io, "run_id=$run_id")
        println(io, "timestamp=$timestamp")
        println(io, "source_commit=$commit")
        println(io, "julia_version=$(VERSION)")
        println(io, "julia_threads=$(Threads.nthreads())")
        println(io, "command=$command")
        println(io, "lattice=$lattice")
        println(io, "sizes=$(join(sizes, ','))")
        println(io, "fields=$(join(fields, ','))")
        println(io, "c_tau=$c_tau")
        println(io, "epsilon=$epsilon")
        println(io, "thermalization_sweeps=$thermal")
        println(io, "bins=$bins")
        println(io, "sweeps_per_bin=$sweeps_per_bin")
        println(io, "line_threads=$line_threads")
        println(io, "replicas_per_start=$replicas")
        for source in source_files
            println(io, "source_sha256.$(basename(source))=$(bytes2hex(sha256(read(source))))")
        end
        println(io, "raw_sha256=$(bytes2hex(sha256(read(raw_path))))")
    end
end

function main()
    isempty(ARGS) && error("lattice required: triangular or honeycomb")
    lattice = Symbol(ARGS[1])
    lattice in (:triangular, :honeycomb) || error("unsupported lattice: $lattice")
    output_dir = length(ARGS) >= 2 ? abspath(ARGS[2]) :
                 abspath(joinpath(@__DIR__, "..", "data", "processed", DEFAULT_RUN_ID))
    mkpath(output_dir)

    run_id = get(ENV, "TFIM_FSS_RUN_ID", DEFAULT_RUN_ID)
    occursin(r"^[a-z0-9][a-z0-9._-]*$", run_id) || error("invalid run ID: $run_id")
    sizes = envlist("TFIM_FSS_SIZES", "12,24,48", x -> parse(Int, x))
    default_fields = lattice == :triangular ? "4.74,4.76811,4.80" : "2.11,2.1325,2.15"
    fields = envlist("TFIM_FSS_FIELDS", default_fields, x -> parse(Float64, x))
    c_tau = envfloat("TFIM_FSS_C_TAU", 1.0)
    epsilon = envfloat("TFIM_FSS_EPSILON", recommended_line_epsilon(lattice))
    thermal = envint("TFIM_FSS_THERM", 1000)
    bins = envint("TFIM_FSS_BINS", 100)
    sweeps_per_bin = envint("TFIM_FSS_SWEEPS_PER_BIN", 20)
    replicas = envint("TFIM_FSS_REPLICAS", 1)
    line_threads = envint("TFIM_FSS_LINE_THREADS", min(4, Threads.nthreads()))
    line_threads <= Threads.nthreads() || error("line threads exceed Julia threads")
    all(size -> size > 1, sizes) || error("all sizes must exceed one")
    all(field -> field > 0, fields) || error("all fields must be positive")
    c_tau > 0 && epsilon > 0 || error("c_tau and epsilon must be positive")
    thermal >= 0 && bins > 0 && sweeps_per_bin > 0 && replicas > 0 ||
        error("invalid sampling budget")

    raw_path = joinpath(output_dir, "$(lattice)_bins.csv")
    ispath(raw_path) && error("refusing to overwrite existing pilot data: $raw_path")
    starts = (:random, :ordered)
    total_chains = length(sizes) * length(fields) * length(starts) * replicas
    completed = 0
    open(raw_path, "w") do io
        println(io, join(HEADER, ','))
        flush(io)
        for L in sizes, (field_index, field) in enumerate(fields),
            (start_index, start) in enumerate(starts), replica in 1:replicas
            seed = chain_seed(lattice, L, field_index, start_index, replica)
            beta = c_tau * L / field
            s = Sim(lattice, L, L, -1.0, 0.0, field, beta, seed)
            set_bond_epsilon!(s, epsilon)
            start == :ordered && fill!(s.conf, 1)
            _, classes = color_lattice(lattice, L, L, s.N, s.bond)
            scratch = LineScratch(s.N, line_threads, seed)
            phases = build_fss_phases(lattice, L, L)

            for _ in 1:thermal
                dupdate!(s)
                line_sweep!(s, scratch, classes; nt = line_threads)
                grow_operator_window_fss!(s)
            end
            check_config(s) || error("configuration failed after thermalization")

            for bin in 0:bins-1
                sums = zeros(6)
                accepted = 0
                proposed = 0
                bin_start = time_ns()
                for sweep in 1:sweeps_per_bin
                    dupdate!(s)
                    a, p = line_sweep!(s, scratch, classes; nt = line_threads)
                    grow_operator_window_fss!(s)
                    observable = measure_fss(s, phases;
                                             check_periodicity = sweep == sweeps_per_bin)
                    sums .+= (observable.E, observable.spacetime_m2,
                              observable.spacetime_m4, observable.S0,
                              observable.Sq, observable.equal_m4)
                    accepted += a
                    proposed += p
                end
                config_checked = check_config(s)
                config_checked || error("configuration failed in bin $bin")
                bin_seconds = (time_ns() - bin_start) / 1e9
                sums ./= sweeps_per_bin
                row = Any[run_id, lattice, L, s.N, s.Nb, field, beta, c_tau, epsilon,
                          seed, start, bin, thermal, bins, sweeps_per_bin, line_threads,
                          sums[1], sums[2], sums[3], sums[4], sums[5], sums[6],
                          phases.q_norm, size(phases.cosq, 1), accepted / max(proposed, 1),
                          Int(config_checked), bin_seconds]
                println(io, join(row, ','))
                flush(io)
            end
            completed += 1
            @printf("completed=%d/%d lattice=%s L=%d h=%.5f start=%s seed=%d\n",
                    completed, total_chains, string(lattice), L, field, string(start), seed)
            flush(stdout)
        end
    end
    metadata_path = joinpath(output_dir, "metadata-$(lattice).txt")
    write_metadata(metadata_path, run_id, lattice, sizes, fields, c_tau, epsilon,
                   thermal, bins, sweeps_per_bin, line_threads, replicas, raw_path)
    println("raw=$raw_path")
    println("metadata=$metadata_path")
end

main()
