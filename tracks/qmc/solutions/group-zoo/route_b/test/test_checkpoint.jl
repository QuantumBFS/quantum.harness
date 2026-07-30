@testset "checkpoint checksum and atomic round trip" begin
    task = tiny_task()
    state = WorldlineState(build_lattice(:chain, 3), task.beta; initial_spins=fill(Int8(1), 3))
    rng = CounterRNG(task.seed)
    path = joinpath(mktempdir(), "state.checkpoint")
    write_checkpoint(path, task, state, rng, 2, [0.1, 0.2])
    loaded = read_checkpoint(path, task)
    @test loaded.bin_index == 2
    @test loaded.raw_bins == [0.1, 0.2]
    @test loaded.rng_state == rng.state
    @test validate_state(loaded.state)

    bytes = read(path)
    open(path, "w") do io
        write(io, bytes[1:end-1])
        write(io, xor(bytes[end], 0x01))
    end
    @test_throws ArgumentError read_checkpoint(path, task)
end
