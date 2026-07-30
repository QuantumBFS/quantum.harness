using Test
using LinearAlgebra
using OnlineStats
using Random
using SHA
using Challenge148LTFIM
using QMC

const C = Challenge148LTFIM

forced_openat2_enosys(args...) = throw(SystemError("forced openat2", Libc.ENOSYS))

mutable struct ForcedBoolRNG{R<:AbstractRNG} <: AbstractRNG
    inner::R
    forced::Bool
    bool_draws::Vector{Bool}
end

Random.rand(rng::ForcedBoolRNG) = rand(rng.inner)
Random.rand(rng::ForcedBoolRNG, ::Type{Bool}) = begin
    push!(rng.bool_draws, rng.forced)
    rng.forced
end
Random.rand(rng::ForcedBoolRNG, sampler::QMC.OperatorSampler) =
    rand(rng.inner, sampler)

@testset "independent seed namespace" begin
    a = C.derive_seed(0x0000000000000094)
    b = C.derive_seed(0x0000000000000095)
    @test length(a) == 32
    @test a != b
    @test bytes2hex(a) ==
          bytes2hex(sha256(vcat(Vector{UInt8}(codeunits("qmc-ltfim-seed-v1")), zeros(UInt8, 7), UInt8[0x94])))
    @test C.SEED_DERIVATION == "sha256:qmc-ltfim-seed-v1||u64be"
    @test !occursin("qmc-sse", lowercase(C.SEED_NAMESPACE))
end

@testset "secure openat2 ENOSYS fallback" begin
    mktempdir() do root
        write(joinpath(root, "value"), "retained")
        mkdir(joinpath(root, "directory"))
        mkdir(joinpath(root, "parent"))
        write(joinpath(root, "parent", "value"), "descriptor-retained")
        symlink("value", joinpath(root, "link"))
        root_fd = ccall(
            :open,
            Cint,
            (Cstring, Cint),
            root,
            C.O_RDONLY | C.O_DIRECTORY | C.O_CLOEXEC,
        )
        directory = C._secure_dir(root_fd, "fallback test root")
        try
            value_fd = C._secure_openat(
                directory.fd,
                "value",
                C.O_RDONLY;
                openat2_call=forced_openat2_enosys,
            )
            value_io = Base.fdio(value_fd, true)
            try
                @test read(value_io, String) == "retained"
            finally
                close(value_io)
            end

            child_fd = C._secure_openat(
                directory.fd,
                "directory",
                C.O_RDONLY | C.O_DIRECTORY;
                openat2_call=forced_openat2_enosys,
            )
            @test isdir(stat(child_fd))
            ccall(:close, Cint, (Cint,), child_fd)

            parent_fd = C._secure_openat(
                directory.fd,
                "parent",
                C.O_RDONLY | C.O_DIRECTORY;
                openat2_call=forced_openat2_enosys,
            )
            parent = C._secure_dir(parent_fd, "retained parent")
            try
                mv(joinpath(root, "parent"), joinpath(root, "parent-moved"))
                mkdir(joinpath(root, "parent"))
                write(joinpath(root, "parent", "value"), "replacement")
                retained_fd = C._secure_openat(
                    parent.fd,
                    "value",
                    C.O_RDONLY;
                    openat2_call=forced_openat2_enosys,
                )
                retained_io = Base.fdio(retained_fd, true)
                try
                    @test read(retained_io, String) == "descriptor-retained"
                finally
                    close(retained_io)
                end
            finally
                close(parent)
            end

            created_fd = C._secure_openat(
                directory.fd,
                "created",
                C.O_RDWR | C.O_CREAT | C.O_EXCL;
                mode=0o600,
                openat2_call=forced_openat2_enosys,
            )
            @test stat(created_fd).mode & 0o777 == 0o600
            ccall(:close, Cint, (Cint,), created_fd)

            symlink_error = try
                C._secure_openat(
                    directory.fd,
                    "link",
                    C.O_RDONLY;
                    openat2_call=forced_openat2_enosys,
                )
                nothing
            catch error
                error
            end
            @test symlink_error isa SystemError
            @test symlink_error.errnum == Libc.ELOOP

            for invalid in ("", ".", "..", "../value", "directory/value")
                @test_throws ArgumentError C._secure_openat(
                    directory.fd,
                    invalid,
                    C.O_RDONLY;
                    openat2_call=forced_openat2_enosys,
                )
            end

            denied = try
                C._secure_openat(
                    directory.fd,
                    "value",
                    C.O_RDONLY;
                    openat2_call=(args...) ->
                        throw(SystemError("forced denial", Libc.EACCES)),
                )
                nothing
            catch error
                error
            end
            @test denied isa SystemError
            @test denied.errnum == Libc.EACCES
        finally
            close(directory)
        end
    end
end

@testset "durable canonical anchor inode pin" begin
    mktempdir() do root
        anchor_sha = "a"^64
        anchor_name = "$anchor_sha.json"
        pin_name = "$anchor_sha.pin"
        anchor_path = joinpath(root, anchor_name)
        write(anchor_path, "anchor\n")
        root_fd = ccall(
            :open,
            Cint,
            (Cstring, Cint),
            root,
            C.O_RDONLY | C.O_DIRECTORY | C.O_CLOEXEC,
        )
        directory = C._secure_dir(root_fd, "anchor pin test root")
        try
            original_identity = C._ensure_anchor_pin(directory, anchor_sha; create=true)
            @test C._entries(directory) == [anchor_name, pin_name]
            @test C._file_identity(directory, anchor_name) == original_identity
            @test C._file_identity(directory, pin_name) == original_identity
            rm(anchor_path)
            write(anchor_path, "anchor\n")
            @test C._file_identity(directory, anchor_name) != original_identity
            @test_throws ArgumentError C._ensure_anchor_pin(
                directory, anchor_sha; create=false
            )
            @test C._file_identity(directory, pin_name) == original_identity
        finally
            close(directory)
        end
    end
end

@testset "direct pinned QMC_LTFIM thermal API and signs" begin
    bonds = [(0, 1), (1, 2)]
    J = C.coupling_matrix(3, bonds, 1.25)
    @test J == [0.0 -1.25 0.0; 0.0 0.0 -1.25; 0.0 0.0 0.0]
    H = C.build_model(3, bonds, 1.25, 0.7)
    @test H isa QMC.TFIM
    @test Matrix(H.J) == J
    @test H.hx == fill(0.7, 3)
    state = BinaryThermalState(H, 32)
    diagnostics = Diagnostics(RunStats(), NoTransitionMatrix())
    @test state isa BinaryThermalState
    @test diagnostics.runstats isa RunStats
    observed = Ref(false)
    measure!(cluster_list_size, qmc_state, model) = (observed[] = true)
    num_ops = mc_step_beta!(
        measure!, C.rng_from_seed(148), state, H, 0.5, diagnostics; eq=true, p=1.0
    )
    @test observed[]
    @test num_ops isa Int

    dense = C.dense_pauli_hamiltonian(3, bonds, 1.25, 0.7)
    z = [1.0 0.0; 0.0 -1.0]
    x = [0.0 1.0; 1.0 0.0]
    I2 = Matrix{Float64}(I, 2, 2)
    kron3(a, b, c) = kron(kron(a, b), c)
    expected = -1.25 .* (kron3(z, z, I2) + kron3(I2, z, z))
    expected .-= 0.7 .* (kron3(x, I2, I2) + kron3(I2, x, I2) + kron3(I2, I2, x))
    @test dense ≈ expected atol = 1e-14 rtol = 0
end

@testset "pinned multibranch and callback source contracts" begin
    source = dirname(pathof(QMC))
    mixed = read(joinpath(source, "ising", "mixedstate.jl"), String)
    ground = read(joinpath(source, "ising", "groundstate.jl"), String)
    multibranch = read(joinpath(source, "ising", "multibranch.jl"), String)
    runstats_source = read(joinpath(source, "diagnostics", "runstats.jl"), String)
    @test bytes2hex(sha256(codeunits(multibranch))) ==
          "15d18064b81adaa84e66c2f90418b56bcd5243f80ad1dace9c2da3b490d0492a"
    @test bytes2hex(sha256(codeunits(ground))) ==
          "a7c742e15ff44e3e25c681b4929d2c9a24ca42322c3e1c8f826bb8bd17b66675"
    @test bytes2hex(sha256(codeunits(mixed))) ==
          "2ebbd4204d7b5a2f9bc02242ca5b66c00596faac86634eb8ff917193b968fa59"
    @test bytes2hex(sha256(codeunits(runstats_source))) ==
          "ba892e5d6492b1406c5ec0ea97e90cfa210097afb289e132e067b9239327e0b4"
    @test all(
        Meta.parseall(text) isa Expr
        for text in (mixed, ground, multibranch, runstats_source)
    )
    @test occursin("cluster_update!(rng, qmc_state, H, d; kw...)", mixed)
    @test first(findfirst("cluster_update!(rng, qmc_state, H, d; kw...)", mixed)) <
          first(findfirst("f(lsize, qmc_state, H)", mixed))
    @test occursin("if rand(rng) < p", ground)
    @test occursin("multibranch_update!(rng, qmc_state, H, d)", ground)
    @test occursin("line_update!(rng, qmc_state, H, d)", ground)
    @test occursin("flip = rand(rng, Bool)", multibranch)
    tfim_start = first(findfirst(
        "function multibranch_cluster_update!(rng::AbstractRNG, lsize::Int, qmc_state::BinaryQMCState, H::AbstractTFIM",
        multibranch,
    ))
    tfim_contract = multibranch[tfim_start:end]
    @test first(findfirst("flip = rand(rng, Bool)", tfim_contract)) <
          first(findfirst("ocount = _map_back_basis_states!", tfim_contract))

    H = C.build_model(2, [(0, 1)], 1.0, 0.5)
    state = BinaryThermalState(H, 32)
    diagnostics = Diagnostics(RunStats(), NoTransitionMatrix())
    rng = C.rng_from_seed(148)
    callback_moments = Ref{Any}(nothing)
    callback_state = Ref{Any}(nothing)
    function probe!(cluster_list_size, qmc_state, model)
        callback_moments[] = C.longitudinal_moments(qmc_state, model)
        callback_state[] = (
            copy(qmc_state.left_config),
            copy(qmc_state.right_config),
            copy(qmc_state.operator_list),
        )
    end
    # p=1.0 deterministically chooses the multibranch arm and this TFIM call
    # completes without entering the pinned line-update zero-index defect.
    attempted = 0
    for _ in 1:20
        before = C._stats_total(diagnostics.runstats.cluster_count)
        empty!(rng.bool_draws)
        mc_step_beta!(probe!, rng, state, H, 0.5, diagnostics; eq=true, p=1.0)
        attempted = round(Int, C._stats_total(diagnostics.runstats.cluster_count) - before)
        attempted > 0 && break
    end
    @test attempted > 0
    @test length(rng.bool_draws) >= attempted
    @test callback_moments[] == C.longitudinal_moments(state, H)
    @test callback_state[] == (
        state.left_config,
        state.right_config,
        state.operator_list,
    )
    mc_method = which(
        QMC.mc_step_beta!,
        Tuple{
            typeof(probe!),
            typeof(rng),
            typeof(state),
            typeof(H),
            Float64,
            typeof(diagnostics),
        },
    )
    branch_method = which(
        QMC.cluster_update!,
        Tuple{typeof(rng),typeof(state),typeof(H),typeof(diagnostics)},
    )
    multibranch_method = which(
        QMC.multibranch_cluster_update!,
        Tuple{typeof(rng),Int,typeof(state),typeof(H),typeof(diagnostics)},
    )
    @test Base.functionloc(mc_method)[2] == 4
    @test endswith(Base.functionloc(mc_method)[1], "/ising/mixedstate.jl")
    @test Base.functionloc(branch_method)[2] == 2
    @test endswith(Base.functionloc(branch_method)[1], "/ising/groundstate.jl")
    @test Base.functionloc(multibranch_method)[2] == 364
    @test endswith(Base.functionloc(multibranch_method)[1], "/ising/multibranch.jl")
end

@testset "pinned TFIM accepted-flip trace is exact" begin
    function controlled_update(forced::Bool)
        H = C.build_model(2, [(0, 1)], 1.0, 1.5)
        state = BinaryThermalState(H, 64)
        diagnostics = Diagnostics(RunStats(), NoTransitionMatrix())
        rng = ForcedBoolRNG(C.rng_from_seed(forced ? 149 : 150).inner, forced, Bool[])
        callback_snapshot = Ref{Any}(nothing)
        attempted = 0
        for _ in 1:100
            before = C._stats_total(diagnostics.runstats.cluster_count)
            empty!(rng.bool_draws)
            function capture!(cluster_list_size, qmc_state, model)
                m = QMC.magnetization(qmc_state.left_config)
                callback_snapshot[] = (
                    copy(qmc_state.left_config),
                    copy(qmc_state.right_config),
                    copy(qmc_state.operator_list),
                    (m^2, m^4),
                    C.longitudinal_moments(qmc_state, model),
                )
            end
            mc_step_beta!(
                capture!, rng, state, H, 5.0, diagnostics; eq=true, p=1.0
            )
            attempted = round(
                Int,
                C._stats_total(diagnostics.runstats.cluster_count) - before,
            )
            attempted > 0 && length(rng.bool_draws) == attempted && break
        end
        return H, state, diagnostics, rng, callback_snapshot[], attempted
    end

    for forced in (false, true)
        H, state, diagnostics, rng, snapshot, attempted =
            controlled_update(forced)
        @test attempted > 0
        @test length(rng.bool_draws) == attempted
        @test all(==(forced), rng.bool_draws)
        @test count(identity, rng.bool_draws) == (forced ? attempted : 0)
        @test OnlineStats.nobs(diagnostics.runstats.accepted_cluster_count) == 0
        @test OnlineStats.nobs(diagnostics.runstats.rejected_cluster_count) == 0
        @test C._stats_total(diagnostics.runstats.cluster_update_accept) ==
              0.5 * C._stats_total(diagnostics.runstats.cluster_count)
        @test snapshot[1] == state.left_config
        @test snapshot[2] == state.right_config
        @test snapshot[3] == state.operator_list
        @test snapshot[4] == snapshot[5] == C.longitudinal_moments(state, H)
    end
end

@testset "Pauli estimators use current state conventions" begin
    H = C.build_model(2, [(0, 1)], 1.0, 0.5)
    state = BinaryThermalState(H, 8)
    state.left_config .= Bool[true, false]
    state.right_config .= state.left_config
    @test QMC.magnetization(state.left_config) == 0.0
    @test C.longitudinal_moments(state, H) == (0.0, 0.0)
    @test C.energy_estimator(state, H, 2.0, 3) == H.energy_shift - 1.5
    @test C.transverse_estimator(H, 2.0, 3) == 3 / (2.0 * sum(H.hx)) - 1
end

@testset "graph contract negatives" begin
    valid_tri = Dict(
        "lattice" => "triangular",
        "length" => 3,
        "site_count" => 9,
        "bonds" => C.triangular_reference_bonds(3),
    )
    valid_honey = Dict(
        "lattice" => "honeycomb",
        "length" => 2,
        "site_count" => 8,
        "bonds" => C.honeycomb_reference_bonds(2),
    )
    @test C.validate_graph_payload(valid_tri).site_count == 9
    @test C.validate_graph_payload(valid_honey).site_count == 8

    bad = [
        merge(valid_tri, Dict("length" => 2)),
        merge(valid_tri, Dict("site_count" => 8)),
        merge(valid_tri, Dict("bonds" => valid_tri["bonds"][1:end-1])),
        merge(valid_tri, Dict("bonds" => reverse(valid_tri["bonds"]))),
        merge(valid_tri, Dict("bonds" => vcat([(0, 0)], valid_tri["bonds"][2:end]))),
        merge(valid_tri, Dict("bonds" => vcat([(0, 9)], valid_tri["bonds"][2:end]))),
        merge(valid_tri, Dict("bonds" => vcat([valid_tri["bonds"][1]], valid_tri["bonds"][1:end-1]))),
        merge(valid_honey, Dict("length" => 1)),
        merge(valid_honey, Dict("site_count" => 7)),
        merge(valid_honey, Dict("bonds" => valid_honey["bonds"][1:end-1])),
    ]
    for graph in bad
        @test_throws ArgumentError C.validate_graph_payload(graph)
    end
end

@testset "canonical JSON and checkpoint contracts" begin
    @test C.canonical_json(Dict("b" => 1, "a" => 2)) == "{\"a\":2,\"b\":1}\n"
    @test C.validate_pointer(Dict(
        "schema_version" => "qmc-current-generation-v2",
        "anchor_sha256" => "a"^64,
        "generation_sha256" => "b"^64,
        "path" => "generations/" * "b"^64,
    )) !== nothing
    for pointer in [
        Dict("schema_version" => "qmc-current-generation-v1"),
        Dict(
            "schema_version" => "qmc-current-generation-v2",
            "generation_sha256" => "b"^64,
            "path" => "generations/" * "b"^64,
        ),
    ]
        @test_throws ArgumentError C.validate_pointer(pointer)
    end
end
