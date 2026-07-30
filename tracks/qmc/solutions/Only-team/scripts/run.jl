using MPI
using MinimalTFIM

function main(args)::Int
    initialized_here = !MPI.Initialized()
    initialized_here && MPI.Init()
    exit_code = 0

    try
        length(args) == 1 ||
            throw(ArgumentError("expected exactly one TOML configuration path"))
        project_root = normpath(joinpath(@__DIR__, ".."))
        repo_root = normpath(joinpath(project_root, "..", "..", "..", ".."))
        config = MinimalTFIM.load_config(args[1]; repo_root)
        MinimalTFIM.run_simulation(config, MPI.COMM_WORLD)
    catch error
        if MPI.Comm_rank(MPI.COMM_WORLD) == 0
            showerror(stderr, error)
            println(stderr)
            flush(stderr)
        end
        exit_code = 1
    finally
        if initialized_here && !MPI.Finalized()
            MPI.Finalize()
        end
    end

    return exit_code
end

exit(main(ARGS))
