using Test
using TOML
using Random
using StableRNGs
using MPI
import MinimalTFIM

const TEST_GROUP = get(ENV, "TFIM_TEST_GROUP", "all")
const PROJECT_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPO_ROOT = normpath(joinpath(PROJECT_ROOT, "..", "..", "..", ".."))
const RESULTS_ROOT = joinpath(REPO_ROOT, "tracks", "qmc", "results", "Only-team")
const BASELINE_PATH = joinpath(PROJECT_ROOT, "configs", "baseline-triangular.toml")

run_group(name) =
    TEST_GROUP == "all" ||
    TEST_GROUP == name ||
    (
        TEST_GROUP == "fast" &&
        name in (
            "config",
            "lattice",
            "weights",
            "cluster",
            "measurement",
            "statistics",
            "driver",
        )
    )

function load_with(; kwargs...)
    raw = TOML.parsefile(BASELINE_PATH)
    for (key, value) in kwargs
        raw[string(key)] = value
    end

    mkpath(RESULTS_ROOT)
    return mktemp(RESULTS_ROOT) do path, io
        TOML.print(io, raw)
        close(io)
        MinimalTFIM.load_config(path; repo_root = REPO_ROOT)
    end
end

if run_group("config")
    config_api_present =
        isdefined(MinimalTFIM, :SimulationConfig) &&
        isdefined(MinimalTFIM, :load_config) &&
        isdefined(MinimalTFIM, :validate_statistics_feasibility)

    @testset "configuration API" begin
        @test isdefined(MinimalTFIM, :SimulationConfig)
        @test isdefined(MinimalTFIM, :load_config)
        @test isdefined(MinimalTFIM, :validate_statistics_feasibility)
    end

    if config_api_present
        @testset "configuration parsing and derivation" begin
            cfg = MinimalTFIM.load_config(BASELINE_PATH; repo_root = REPO_ROOT)

            @test cfg.lattice == :triangular
            @test cfg.input_LTrot == 400
            @test cfg.LTrot == 300
            @test cfg.Dltau == 0.02
            @test cfg.FixedDltau == 0.02
            @test cfg.J1 == -1.0
            @test cfg.J2 == 0.0
            @test cfg.CpTau < 0
            @test cfg.K_space > 0
            @test cfg.K_tau > 0
            @test cfg.raw_input["LTrot"] == 400
            @test cfg.output_dir == joinpath(
                REPO_ROOT,
                "tracks",
                "qmc",
                "results",
                "Only-team",
                "baseline-triangular",
            )

            odd = load_with(IfSetDltau = false, LTrot = 5, NmMeaConfg = 5)
            @test odd.input_LTrot == 5
            @test odd.LTrot == 6
            @test odd.Dltau == 1.0

            @test_throws ArgumentError load_with(lattice = "square")
            @test_throws ArgumentError load_with(NumL1 = 2)
            @test_throws ArgumentError load_with(NumL2 = 2)
            @test_throws ArgumentError load_with(J1 = 0.0)
            @test_throws ArgumentError load_with(J1 = 1.0)
            @test_throws ArgumentError load_with(J2 = 0.1)
            @test_throws ArgumentError load_with(hTrfd = 0.0)
            @test_throws ArgumentError load_with(BetaT = 0.0)
            @test_throws ArgumentError load_with(FixedDltau = 0.0)
            @test_throws ArgumentError load_with(LTrot = 0)
            @test_throws ArgumentError load_with(nLocal = -1)
            @test_throws ArgumentError load_with(nWolff = -1)
            @test_throws ArgumentError load_with(nWarm = -1)
            @test_throws ArgumentError load_with(NmBin = -1)
            @test_throws ArgumentError load_with(NSwep = -1)
            @test_throws ArgumentError load_with(NmMeaConfg = 0)
            @test_throws ArgumentError load_with(
                IfSetDltau = false,
                LTrot = 5,
                NmMeaConfg = 7,
            )
            @test_throws ArgumentError load_with(discard_initial_bins = -1)
            @test_throws ArgumentError load_with(discard_initial_bins = 11)
            @test_throws ArgumentError load_with(statistics_mode = "jackknife")
            @test_throws ArgumentError load_with(initial_state = "zero")
            @test_throws ArgumentError load_with(seed = -1)
            @test_throws ArgumentError load_with(
                output_dir = joinpath(REPO_ROOT, "outside-results"),
            )
        end

        @testset "production statistics feasibility" begin
            @test isnothing(
                MinimalTFIM.validate_statistics_feasibility(load_with()),
            )
            @test isnothing(
                MinimalTFIM.validate_statistics_feasibility(
                    load_with(
                        trim_extrema = false,
                        NmBin = 3,
                        discard_initial_bins = 1,
                    ),
                ),
            )
            @test_throws ArgumentError MinimalTFIM.validate_statistics_feasibility(
                load_with(NSwep = 0),
            )
            @test_throws ArgumentError MinimalTFIM.validate_statistics_feasibility(
                load_with(NmBin = 4, discard_initial_bins = 1),
            )
            @test_throws ArgumentError MinimalTFIM.validate_statistics_feasibility(
                load_with(
                    trim_extrema = false,
                    NmBin = 2,
                    discard_initial_bins = 1,
                ),
            )
        end
    end
end

if run_group("lattice")
    lattice_api_present =
        isdefined(MinimalTFIM, :Lattice) &&
        isdefined(MinimalTFIM, :build_lattice) &&
        isdefined(MinimalTFIM, :validate_lattice)

    @testset "lattice API" begin
        @test isdefined(MinimalTFIM, :Lattice)
        @test isdefined(MinimalTFIM, :build_lattice)
        @test isdefined(MinimalTFIM, :validate_lattice)
    end

    if lattice_api_present
        function assert_invariants(lattice, expected_degree, expected_bonds)
            @test length(lattice.neighbors) == lattice.N
            @test all(length(neighbors) == expected_degree for neighbors in lattice.neighbors)
            @test all(
                length(neighbors) == length(unique(neighbors)) for
                neighbors in lattice.neighbors
            )
            @test all(
                site ∉ lattice.neighbors[site] for site in 1:lattice.N
            )
            @test all(
                1 <= neighbor <= lattice.N for
                neighbors in lattice.neighbors for neighbor in neighbors
            )
            @test all(
                site in lattice.neighbors[neighbor] for
                site in 1:lattice.N for neighbor in lattice.neighbors[site]
            )
            @test length(lattice.bonds) == expected_bonds
            @test length(lattice.bonds) == length(unique(lattice.bonds))
            @test all(first(bond) < last(bond) for bond in lattice.bonds)
            @test isnothing(MinimalTFIM.validate_lattice(lattice))
        end

        @testset "triangular invariants" begin
            for (L1, L2) in ((3, 3), (4, 5), (6, 6))
                lattice = MinimalTFIM.build_lattice(:triangular, L1, L2)
                @test lattice.kind == :triangular
                @test lattice.NumL1 == L1
                @test lattice.NumL2 == L2
                @test lattice.N == L1 * L2
                assert_invariants(lattice, 6, 3 * lattice.N)
            end
        end

        @testset "triangular origin neighbors" begin
            L1, L2 = 4, 5
            lattice = MinimalTFIM.build_lattice(:triangular, L1, L2)
            index(x, y) = mod(x, L1) + 1 + L1 * mod(y, L2)
            expected = Set(
                index(x, y) for
                (x, y) in ((-1, 0), (-1, 1), (0, 1), (1, 0), (1, -1), (0, -1))
            )
            @test Set(lattice.neighbors[index(0, 0)]) == expected
        end

        @testset "honeycomb invariants" begin
            for (L1, L2) in ((3, 3), (4, 5), (6, 6))
                lattice = MinimalTFIM.build_lattice(:honeycomb, L1, L2)
                @test lattice.kind == :honeycomb
                @test lattice.NumL1 == L1
                @test lattice.NumL2 == L2
                @test lattice.N == 2 * L1 * L2
                assert_invariants(lattice, 3, 3 * lattice.N ÷ 2)
            end
        end

        @testset "honeycomb origin neighbors" begin
            L1, L2 = 4, 5
            lattice = MinimalTFIM.build_lattice(:honeycomb, L1, L2)
            index(x, y, sub) =
                2 * (mod(x, L1) + L1 * mod(y, L2)) + (sub == :A ? 1 : 2)

            expected_A = Set(
                (
                    index(0, 0, :B),
                    index(-1, 0, :B),
                    index(0, -1, :B),
                ),
            )
            expected_B = Set(
                (
                    index(0, 0, :A),
                    index(1, 0, :A),
                    index(0, 1, :A),
                ),
            )
            @test Set(lattice.neighbors[index(0, 0, :A)]) == expected_A
            @test Set(lattice.neighbors[index(0, 0, :B)]) == expected_B
        end

        @testset "invalid lattice requests" begin
            @test_throws ArgumentError MinimalTFIM.build_lattice(:square, 4, 4)
            @test_throws ArgumentError MinimalTFIM.build_lattice(:triangular, 2, 4)
            @test_throws ArgumentError MinimalTFIM.build_lattice(:honeycomb, 4, 2)
        end
    end
end

if run_group("weights")
    weight_api_names = (
        :UpdateDiagnostics,
        :SimulationState,
        :tau_minus,
        :tau_plus,
        :initialize_state,
        :reset_diagnostics!,
        :total_log_weight,
        :local_terms,
        :local_sweep!,
    )
    weight_api_present = all(isdefined(MinimalTFIM, name) for name in weight_api_names)

    @testset "weight and local API" begin
        for name in weight_api_names
            @test isdefined(MinimalTFIM, name)
        end
    end

    if weight_api_present
        function compact_config(lattice::String; initial_state = "random")
            return load_with(
                lattice = lattice,
                NumL1 = 4,
                NumL2 = 4,
                BetaT = 0.12,
                IfSetDltau = false,
                FixedDltau = 0.02,
                LTrot = 6,
                NmMeaConfg = 3,
                initial_state = initial_state,
            )
        end

        @testset "periodic imaginary time" begin
            @test MinimalTFIM.tau_minus(1, 6) == 6
            @test MinimalTFIM.tau_minus(2, 6) == 1
            @test MinimalTFIM.tau_plus(5, 6) == 6
            @test MinimalTFIM.tau_plus(6, 6) == 1
        end

        @testset "state initialization and diagnostics" begin
            cfg_random = compact_config("triangular")
            lattice = MinimalTFIM.build_lattice(
                cfg_random.lattice,
                cfg_random.NumL1,
                cfg_random.NumL2,
            )
            state_a = MinimalTFIM.initialize_state(
                cfg_random,
                lattice,
                StableRNG(0x1234),
            )
            state_b = MinimalTFIM.initialize_state(
                cfg_random,
                lattice,
                StableRNG(0x1234),
            )

            @test state_a.spins isa Matrix{Int8}
            @test size(state_a.spins) == (lattice.N, cfg_random.LTrot)
            @test sort(unique(vec(state_a.spins))) == Int8[-1, 1]
            @test state_a.spins == state_b.spins
            @test state_a.diagnostics.local_attempts == 0
            @test state_a.diagnostics.local_accepts == 0
            @test state_a.diagnostics.cluster_size_sum == 0
            @test state_a.diagnostics.cluster_count == 0

            cfg_ordered = compact_config("honeycomb"; initial_state = "ordered")
            ordered_lattice = MinimalTFIM.build_lattice(
                cfg_ordered.lattice,
                cfg_ordered.NumL1,
                cfg_ordered.NumL2,
            )
            ordered_state = MinimalTFIM.initialize_state(
                cfg_ordered,
                ordered_lattice,
                StableRNG(0x5678),
            )
            @test all(==(Int8(1)), ordered_state.spins)
            @test size(ordered_state.spins) ==
                  (ordered_lattice.N, cfg_ordered.LTrot)

            diagnostics = MinimalTFIM.UpdateDiagnostics(1, 2, 3, 4)
            @test isnothing(MinimalTFIM.reset_diagnostics!(diagnostics))
            @test (
                diagnostics.local_attempts,
                diagnostics.local_accepts,
                diagnostics.cluster_size_sum,
                diagnostics.cluster_count,
            ) == (0, 0, 0, 0)
        end

        @testset "fixed coupling and local regressions" begin
            cfg = compact_config("triangular"; initial_state = "ordered")
            lattice = MinimalTFIM.build_lattice(
                cfg.lattice,
                cfg.NumL1,
                cfg.NumL2,
            )
            state = MinimalTFIM.initialize_state(cfg, lattice, StableRNG(1))

            @test isapprox(
                cfg.CpTau,
                -1.17656041848794;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                cfg.K_space,
                0.02000000000000;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                cfg.K_tau,
                1.17656041848794;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                cfg.p_space,
                0.0392105608476768;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                cfg.p_tau,
                0.904928005445148;
                rtol = 1e-13,
                atol = 1e-14,
            )

            IsSpin, Rtp0 = MinimalTFIM.local_terms(
                state.spins,
                1,
                1,
                lattice,
                cfg,
            )
            delta_log_weight = -2 * IsSpin * Rtp0
            weight_ratio = exp(delta_log_weight)
            @test IsSpin == Int8(1)
            @test isapprox(
                Rtp0,
                2.47312083697588;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                delta_log_weight,
                -4.94624167395176;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                weight_ratio,
                0.00711008077869917;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                min(1.0, weight_ratio),
                0.00711008077869917;
                rtol = 1e-13,
                atol = 1e-14,
            )

            state.spins[1, 1] = Int8(-1)
            negative_spin, negative_Rtp0 = MinimalTFIM.local_terms(
                state.spins,
                1,
                1,
                lattice,
                cfg,
            )
            negative_ratio = exp(-2 * negative_spin * negative_Rtp0)
            @test negative_spin == Int8(-1)
            @test isapprox(
                negative_Rtp0,
                2.47312083697588;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test isapprox(
                negative_ratio,
                140.645378178525;
                rtol = 1e-13,
                atol = 1e-14,
            )
            @test min(1.0, negative_ratio) == 1.0
        end

        @testset "total weight on aligned states" begin
            for kind in ("triangular", "honeycomb")
                cfg = compact_config(kind; initial_state = "ordered")
                lattice = MinimalTFIM.build_lattice(
                    cfg.lattice,
                    cfg.NumL1,
                    cfg.NumL2,
                )
                spins = fill(Int8(1), lattice.N, cfg.LTrot)
                expected =
                    cfg.K_space * length(lattice.bonds) * cfg.LTrot +
                    cfg.K_tau * lattice.N * cfg.LTrot
                @test isapprox(
                    MinimalTFIM.total_log_weight(spins, lattice, cfg),
                    expected;
                    rtol = 1e-14,
                    atol = 1e-14,
                )
            end
        end

        @testset "local formula equals complete weight difference" begin
            rng = StableRNG(0x829d)
            for kind in ("triangular", "honeycomb")
                cfg = compact_config(kind)
                lattice = MinimalTFIM.build_lattice(
                    cfg.lattice,
                    cfg.NumL1,
                    cfg.NumL2,
                )

                for _ in 1:20
                    spins = rand(
                        rng,
                        Int8[-1, 1],
                        lattice.N,
                        cfg.LTrot,
                    )
                    for _ in 1:20
                        site = rand(rng, 1:lattice.N)
                        tau = rand(rng, 1:cfg.LTrot)
                        before =
                            MinimalTFIM.total_log_weight(spins, lattice, cfg)
                        IsSpin, Rtp0 = MinimalTFIM.local_terms(
                            spins,
                            site,
                            tau,
                            lattice,
                            cfg,
                        )
                        spins[site, tau] = -spins[site, tau]
                        after =
                            MinimalTFIM.total_log_weight(spins, lattice, cfg)
                        @test isapprox(
                            after - before,
                            -2 * IsSpin * Rtp0;
                            rtol = 1e-13,
                            atol = 1e-14,
                        )
                        spins[site, tau] = -spins[site, tau]
                    end
                end
            end
        end

        @testset "local sweep attempts each spacetime spin" begin
            cfg = compact_config("honeycomb")
            lattice = MinimalTFIM.build_lattice(
                cfg.lattice,
                cfg.NumL1,
                cfg.NumL2,
            )
            state_a =
                MinimalTFIM.initialize_state(cfg, lattice, StableRNG(0x16))
            state_b =
                MinimalTFIM.initialize_state(cfg, lattice, StableRNG(0x16))
            rng_a = StableRNG(0x17)
            rng_b = StableRNG(0x17)

            @test isnothing(
                MinimalTFIM.local_sweep!(state_a, lattice, cfg, rng_a),
            )
            MinimalTFIM.local_sweep!(state_b, lattice, cfg, rng_b)

            @test state_a.diagnostics.local_attempts ==
                  lattice.N * cfg.LTrot
            @test 0 <= state_a.diagnostics.local_accepts <=
                  state_a.diagnostics.local_attempts
            @test all(spin in Int8[-1, 1] for spin in state_a.spins)
            @test state_a.spins == state_b.spins
            @test state_a.diagnostics.local_accepts ==
                  state_b.diagnostics.local_accepts
        end
    end
end

if run_group("cluster")
    cluster_api_names = (
        :should_add,
        :build_cluster,
        :wolff_update!,
        :update_cycle!,
    )
    cluster_api_present =
        all(isdefined(MinimalTFIM, name) for name in cluster_api_names)

    @testset "cluster API" begin
        for name in cluster_api_names
            @test isdefined(MinimalTFIM, name)
        end
    end

    if cluster_api_present
        function cluster_config(
            lattice::String;
            initial_state = "ordered",
            nLocal = 0,
            nWolff = 1,
        )
            return load_with(
                lattice = lattice,
                NumL1 = 4,
                NumL2 = 4,
                BetaT = 0.12,
                IfSetDltau = false,
                FixedDltau = 0.02,
                LTrot = 6,
                NmMeaConfg = 3,
                initial_state = initial_state,
                nLocal = nLocal,
                nWolff = nWolff,
            )
        end

        function replace_config(config; kwargs...)
            names = fieldnames(typeof(config))
            values = map(
                name ->
                    haskey(kwargs, name) ? kwargs[name] : getfield(config, name),
                names,
            )
            return typeof(config)(values...)
        end

        @testset "bond addition decision" begin
            @test !MinimalTFIM.should_add(
                Int8(1),
                Int8(-1),
                false,
                1.0,
                0.0,
            )
            @test !MinimalTFIM.should_add(
                Int8(1),
                Int8(1),
                true,
                1.0,
                0.0,
            )
            @test !MinimalTFIM.should_add(
                Int8(1),
                Int8(1),
                false,
                0.0,
                0.0,
            )
            @test MinimalTFIM.should_add(
                Int8(1),
                Int8(1),
                false,
                1.0,
                prevfloat(1.0),
            )
            @test !MinimalTFIM.should_add(
                Int8(-1),
                Int8(-1),
                false,
                0.25,
                0.25,
            )
            @test MinimalTFIM.should_add(
                Int8(-1),
                Int8(-1),
                false,
                0.25,
                prevfloat(0.25),
            )
        end

        @testset "cluster members are unique and legal" begin
            for kind in ("triangular", "honeycomb")
                cfg = cluster_config(kind; initial_state = "random")
                lattice = MinimalTFIM.build_lattice(
                    cfg.lattice,
                    cfg.NumL1,
                    cfg.NumL2,
                )
                state =
                    MinimalTFIM.initialize_state(cfg, lattice, StableRNG(81))
                before = copy(state.spins)

                for seed in UInt64.(91:100)
                    members = MinimalTFIM.build_cluster(
                        state,
                        lattice,
                        cfg,
                        StableRNG(seed),
                    )
                    @test !isempty(members)
                    @test length(members) == length(unique(members))
                    @test all(1 <= index <= length(state.spins) for index in members)
                    @test all(
                        state.spins[index] == state.spins[first(members)] for
                        index in members
                    )
                    @test state.spins == before
                end
            end
        end

        @testset "space and imaginary-time probability boundaries" begin
            for kind in ("triangular", "honeycomb")
                cfg = cluster_config(kind)
                lattice = MinimalTFIM.build_lattice(
                    cfg.lattice,
                    cfg.NumL1,
                    cfg.NumL2,
                )
                state =
                    MinimalTFIM.initialize_state(cfg, lattice, StableRNG(101))

                zero_probability =
                    replace_config(cfg; p_space = 0.0, p_tau = 0.0)
                zero_members = MinimalTFIM.build_cluster(
                    state,
                    lattice,
                    zero_probability,
                    StableRNG(102),
                )
                @test length(zero_members) == 1

                unit_probability =
                    replace_config(cfg; p_space = 1.0, p_tau = 1.0)
                unit_members = MinimalTFIM.build_cluster(
                    state,
                    lattice,
                    unit_probability,
                    StableRNG(103),
                )
                @test length(unit_members) == length(state.spins)
                @test length(unit_members) == length(unique(unit_members))

                space_only =
                    replace_config(cfg; p_space = 1.0, p_tau = 0.0)
                space_members = MinimalTFIM.build_cluster(
                    state,
                    lattice,
                    space_only,
                    StableRNG(104),
                )
                space_taus = Set(
                    fld(index - 1, lattice.N) + 1 for index in space_members
                )
                @test length(space_members) == lattice.N
                @test length(space_taus) == 1

                time_only =
                    replace_config(cfg; p_space = 0.0, p_tau = 1.0)
                time_members = MinimalTFIM.build_cluster(
                    state,
                    lattice,
                    time_only,
                    StableRNG(105),
                )
                time_sites = Set(mod1(index, lattice.N) for index in time_members)
                @test length(time_members) == cfg.LTrot
                @test length(time_sites) == 1
            end
        end

        @testset "Wolff flips exactly one completed cluster" begin
            for kind in ("triangular", "honeycomb")
                cfg = cluster_config(kind; initial_state = "random")
                lattice = MinimalTFIM.build_lattice(
                    cfg.lattice,
                    cfg.NumL1,
                    cfg.NumL2,
                )
                state = MinimalTFIM.initialize_state(
                    cfg,
                    lattice,
                    StableRNG(201),
                )
                before = copy(state.spins)
                expected_members = MinimalTFIM.build_cluster(
                    state,
                    lattice,
                    cfg,
                    StableRNG(202),
                )

                cluster_size = MinimalTFIM.wolff_update!(
                    state,
                    lattice,
                    cfg,
                    StableRNG(202),
                )

                expected = copy(before)
                expected[expected_members] .*= Int8(-1)
                @test cluster_size == length(expected_members)
                @test state.spins == expected
                @test state.diagnostics.cluster_count == 1
                @test state.diagnostics.cluster_size_sum == cluster_size
                @test state.diagnostics.local_attempts == 0
                @test state.diagnostics.local_accepts == 0
            end
        end

        @testset "update cycle counts and ordering" begin
            zero_cfg = cluster_config(
                "triangular";
                initial_state = "random",
                nLocal = 0,
                nWolff = 0,
            )
            zero_lattice = MinimalTFIM.build_lattice(
                zero_cfg.lattice,
                zero_cfg.NumL1,
                zero_cfg.NumL2,
            )
            zero_state = MinimalTFIM.initialize_state(
                zero_cfg,
                zero_lattice,
                StableRNG(301),
            )
            zero_before = copy(zero_state.spins)
            @test isnothing(
                MinimalTFIM.update_cycle!(
                    zero_state,
                    zero_lattice,
                    zero_cfg,
                    StableRNG(302),
                ),
            )
            @test zero_state.spins == zero_before
            @test zero_state.diagnostics.local_attempts == 0
            @test zero_state.diagnostics.cluster_count == 0

            cfg = cluster_config(
                "honeycomb";
                initial_state = "random",
                nLocal = 1,
                nWolff = 2,
            )
            lattice = MinimalTFIM.build_lattice(
                cfg.lattice,
                cfg.NumL1,
                cfg.NumL2,
            )
            state_cycle =
                MinimalTFIM.initialize_state(cfg, lattice, StableRNG(303))
            state_manual =
                MinimalTFIM.initialize_state(cfg, lattice, StableRNG(303))
            rng_cycle = StableRNG(304)
            rng_manual = StableRNG(304)

            MinimalTFIM.update_cycle!(state_cycle, lattice, cfg, rng_cycle)
            MinimalTFIM.local_sweep!(state_manual, lattice, cfg, rng_manual)
            for _ in 1:cfg.nWolff
                MinimalTFIM.wolff_update!(
                    state_manual,
                    lattice,
                    cfg,
                    rng_manual,
                )
            end

            @test state_cycle.spins == state_manual.spins
            @test state_cycle.diagnostics.local_attempts ==
                  lattice.N * cfg.LTrot
            @test state_cycle.diagnostics.local_accepts ==
                  state_manual.diagnostics.local_accepts
            @test state_cycle.diagnostics.cluster_count == cfg.nWolff
            @test state_cycle.diagnostics.cluster_size_sum ==
                  state_manual.diagnostics.cluster_size_sum
        end
    end
end

if run_group("measurement")
    measurement_api_names = (
        :BinAccumulator,
        :tau_segments,
        :sample_measurement_slices,
        :measure_at_slices,
        :measure!,
    )
    measurement_api_present =
        all(isdefined(MinimalTFIM, name) for name in measurement_api_names)

    @testset "measurement API" begin
        for name in measurement_api_names
            @test isdefined(MinimalTFIM, name)
        end
    end

    if measurement_api_present
        function assert_segment_partition(LTrot, count, expected_lengths)
            segments = MinimalTFIM.tau_segments(LTrot, count)
            @test length(segments) == count
            @test length.(segments) == expected_lengths
            @test collect(Iterators.flatten(segments)) == collect(1:LTrot)
            @test sum(length, segments) == LTrot
            @test all(!isempty, segments)
            return segments
        end

        @testset "imaginary-time segment partition" begin
            @test assert_segment_partition(10, 3, [4, 3, 3]) ==
                  UnitRange{Int}[1:4, 5:7, 8:10]
            @test assert_segment_partition(12, 4, [3, 3, 3, 3]) ==
                  UnitRange{Int}[1:3, 4:6, 7:9, 10:12]
            @test assert_segment_partition(7, 1, [7]) ==
                  UnitRange{Int}[1:7]
            @test assert_segment_partition(6, 6, ones(Int, 6)) ==
                  UnitRange{Int}[1:1, 2:2, 3:3, 4:4, 5:5, 6:6]

            @test_throws ArgumentError MinimalTFIM.tau_segments(0, 1)
            @test_throws ArgumentError MinimalTFIM.tau_segments(6, 0)
            @test_throws ArgumentError MinimalTFIM.tau_segments(6, 7)
        end

        @testset "one reproducible sample per segment" begin
            segments = MinimalTFIM.tau_segments(10, 3)
            rng_a = StableRNG(0x501)
            rng_b = StableRNG(0x501)

            for _ in 1:50
                slices_a =
                    MinimalTFIM.sample_measurement_slices(segments, rng_a)
                slices_b =
                    MinimalTFIM.sample_measurement_slices(segments, rng_b)
                @test slices_a == slices_b
                @test length(slices_a) == length(segments)
                @test all(
                    slices_a[index] in segments[index] for
                    index in eachindex(segments)
                )
            end
        end

        @testset "slice moments precede imaginary-time averaging" begin
            spins = Int8[
                1 -1 1
                1 -1 1
                1 -1 -1
                1 -1 -1
            ]
            slices = [1, 2, 3]
            before = copy(spins)
            m2, m4 = MinimalTFIM.measure_at_slices(spins, slices)

            magnetizations = [
                sum(spins[:, tau]) / size(spins, 1) for tau in slices
            ]
            expected_m2 = sum(value^2 for value in magnetizations) / length(slices)
            expected_m4 = sum(value^4 for value in magnetizations) / length(slices)
            time_averaged_square =
                (sum(magnetizations) / length(magnetizations))^2

            @test m2 == expected_m2 == 2 / 3
            @test m4 == expected_m4 == 2 / 3
            @test m2 != time_averaged_square
            @test time_averaged_square == 0.0
            @test spins == before
        end

        @testset "measurement accumulation" begin
            spins = Int8[
                1 1 -1 -1 1 1
                1 1 -1 -1 -1 -1
                1 -1 -1 1 1 -1
                1 -1 -1 1 -1 1
            ]
            state = MinimalTFIM.SimulationState(
                copy(spins),
                MinimalTFIM.UpdateDiagnostics(0, 0, 0, 0),
            )
            segments = MinimalTFIM.tau_segments(6, 3)
            accumulator = MinimalTFIM.BinAccumulator(0.0, 0.0, 0)
            rng_expected = StableRNG(0x601)
            rng_actual = StableRNG(0x601)

            expected_m2_sum = 0.0
            expected_m4_sum = 0.0
            for measurement_count in 1:2
                slices = MinimalTFIM.sample_measurement_slices(
                    segments,
                    rng_expected,
                )
                m2, m4 =
                    MinimalTFIM.measure_at_slices(state.spins, slices)
                expected_m2_sum += m2
                expected_m4_sum += m4

                @test isnothing(
                    MinimalTFIM.measure!(
                        accumulator,
                        state,
                        segments,
                        rng_actual,
                    ),
                )
                @test accumulator.measurement_count == measurement_count
                @test accumulator.m2_sum == expected_m2_sum
                @test accumulator.m4_sum == expected_m4_sum
            end
            @test state.spins == spins
            @test state.diagnostics.local_attempts == 0
            @test state.diagnostics.cluster_count == 0
        end
    end
end

if run_group("statistics")
    statistics_api_names = (
        :BinRecord,
        :bin_record,
        :bin_sem,
        :filter_series,
        :summarize_bins,
    )
    statistics_api_present =
        all(isdefined(MinimalTFIM, name) for name in statistics_api_names)

    @testset "statistics API" begin
        for name in statistics_api_names
            @test isdefined(MinimalTFIM, name)
        end
    end

    if statistics_api_present
        function record_from_m2_Q(bin, m2, Q)
            return MinimalTFIM.bin_record(bin, m2, m2^2 / Q)
        end

        @testset "per-bin Binder moment ratio" begin
            record = MinimalTFIM.bin_record(1, 0.25, 0.125)
            @test record.bin == 1
            @test record.m2 == 0.25
            @test record.m4 == 0.125
            @test record.Q == 0.5
            @test_throws ArgumentError MinimalTFIM.bin_record(0, 0.25, 0.125)
            @test_throws ArgumentError MinimalTFIM.bin_record(1, -0.25, 0.125)
            @test_throws ArgumentError MinimalTFIM.bin_record(1, 0.0, 0.0)
        end

        @testset "bin standard error" begin
            values = [1.0, 2.0, 4.0, 7.0]
            before = copy(values)
            result = MinimalTFIM.bin_sem(values)
            expected_mean = sum(values) / length(values)
            expected_error = sqrt(
                sum((value - expected_mean)^2 for value in values) /
                (length(values) * (length(values) - 1)),
            )
            @test result.mean == expected_mean
            @test result.error == expected_error
            @test result.n == length(values)
            @test values == before
            @test_throws ArgumentError MinimalTFIM.bin_sem([1.0])
            @test_throws ArgumentError MinimalTFIM.bin_sem([1.0, Inf])
        end

        @testset "initial removal and independent extrema" begin
            records = [
                record_from_m2_Q(1, 100.0, 1.0),
                record_from_m2_Q(2, 0.1, 0.5),
                record_from_m2_Q(3, 0.3, 0.1),
                record_from_m2_Q(4, 0.4, 0.4),
                record_from_m2_Q(5, 0.5, 0.9),
                record_from_m2_Q(6, 0.8, 0.6),
            ]
            before = copy(records)

            m2_filter =
                MinimalTFIM.filter_series(records, :m2, 1, true)
            Q_filter =
                MinimalTFIM.filter_series(records, :Q, 1, true)

            @test m2_filter.values == [0.3, 0.4, 0.5]
            @test m2_filter.retained_bins == [3, 4, 5]
            @test m2_filter.discarded_bins == [1]
            @test m2_filter.trimmed_bins == [2, 6]
            @test m2_filter.removed_bins == [1, 2, 6]

            @test Q_filter.values ≈ [0.4, 0.5, 0.6]
            @test Q_filter.retained_bins == [4, 2, 6]
            @test Q_filter.discarded_bins == [1]
            @test Q_filter.trimmed_bins == [3, 5]
            @test Q_filter.removed_bins == [1, 3, 5]

            @test m2_filter.number_before_filtering == 6
            @test m2_filter.number_after_discard == 5
            @test m2_filter.number_after_filtering == 3
            @test Q_filter.number_before_filtering == 6
            @test Q_filter.number_after_filtering == 3
            @test records == before

            untrimmed =
                MinimalTFIM.filter_series(records, :m2, 2, false)
            @test untrimmed.values == [0.3, 0.4, 0.5, 0.8]
            @test untrimmed.retained_bins == [3, 4, 5, 6]
            @test untrimmed.discarded_bins == [1, 2]
            @test isempty(untrimmed.trimmed_bins)
            @test untrimmed.removed_bins == [1, 2]

            @test_throws ArgumentError MinimalTFIM.filter_series(
                records,
                :m4,
                1,
                true,
            )
            @test_throws ArgumentError MinimalTFIM.filter_series(
                records,
                :m2,
                -1,
                true,
            )
            @test_throws ArgumentError MinimalTFIM.filter_series(
                records[1:3],
                :m2,
                0,
                true,
            )
        end

        @testset "bin summary keeps m2 and Q filters separate" begin
            records = [
                record_from_m2_Q(1, 100.0, 1.0),
                record_from_m2_Q(2, 0.1, 0.5),
                record_from_m2_Q(3, 0.3, 0.1),
                record_from_m2_Q(4, 0.4, 0.4),
                record_from_m2_Q(5, 0.5, 0.9),
                record_from_m2_Q(6, 0.8, 0.6),
            ]
            cfg = load_with(
                NmBin = 6,
                discard_initial_bins = 1,
                trim_extrema = true,
            )
            summary = MinimalTFIM.summarize_bins(records, cfg)
            expected_m2 = MinimalTFIM.bin_sem([0.3, 0.4, 0.5])
            expected_Q = MinimalTFIM.bin_sem([0.4, 0.5, 0.6])

            @test summary.m2 == expected_m2.mean
            @test summary.m2_error == expected_m2.error
            @test summary.binder_Q ≈ expected_Q.mean
            @test summary.binder_Q_error ≈ expected_Q.error
            @test summary.m2_filter.retained_bins == [3, 4, 5]
            @test summary.binder_Q_filter.retained_bins == [4, 2, 6]
            @test summary.statistics_mode == :bin_sem
            @test summary.discard_initial_bins == 1
            @test summary.trim_extrema
            @test summary.number_of_bins_before_filtering == 6
            @test summary.number_of_bins_after_filtering == 3

            wrong_count_cfg = load_with(
                NmBin = 7,
                discard_initial_bins = 1,
                trim_extrema = true,
            )
            @test_throws ArgumentError MinimalTFIM.summarize_bins(
                records,
                wrong_count_cfg,
            )
        end
    end
end

if run_group("driver")
    driver_api_names = (
        :deterministic_seed,
        :reduce_bin,
        :prepare_output_directory,
        :write_results,
        :run_simulation,
    )
    driver_api_present =
        all(isdefined(MinimalTFIM, name) for name in driver_api_names)
    run_script = joinpath(PROJECT_ROOT, "scripts", "run.jl")

    @testset "MPI driver API" begin
        for name in driver_api_names
            @test isdefined(MinimalTFIM, name)
        end
        @test isfile(run_script)
    end

    @testset "SCNet pilot validates rank seeds from metadata" begin
        pilot_script = read(
            joinpath(
                PROJECT_ROOT,
                "scripts",
                "scnet-pilot-honeycomb-L28.sbatch",
            ),
            String,
        )
        @test occursin(
            "metadata[\"runtime\"][\"rank_seeds\"]",
            pilot_script,
        )
        @test !occursin("\"rank_seeds.csv\"", pilot_script)
    end

    @testset "extreme scan cell preparation" begin
        helper = joinpath(
            PROJECT_ROOT,
            "scripts",
            "prepare_extreme_scan_cell.py",
        )
        runner = joinpath(
            PROJECT_ROOT,
            "scripts",
            "run_extreme_scan_cell.sh",
        )
        @test isfile(helper)
        @test isfile(runner)

        if isfile(helper) && isfile(runner)
            python = something(Sys.which("python3"), "")
            @test !isempty(python)
            mktempdir(RESULTS_ROOT) do run_dir
                run_spec = joinpath(run_dir, "run_spec.json")
                relative_run_dir = relpath(run_dir, REPO_ROOT)
                write(
                    run_spec,
                    """
                    {
                      "run_id": "test-extreme-min",
                      "run_dir": "$(replace(relative_run_dir, '\\' => '/'))",
                      "settings": {
                        "J1": -1.0,
                        "J2": 0.0,
                        "IfSetDltau": true,
                        "FixedDltau": 0.013,
                        "nLocal": 1,
                        "nWolff": 5,
                        "nWarm": 10000,
                        "NmBin": 32,
                        "NSwep": 2000,
                        "NmMeaConfg": 10,
                        "discard_initial_bins": 1,
                        "trim_extrema": true,
                        "statistics_mode": "bin_sem",
                        "base_seed": 20260729,
                        "initial_state": "random",
                        "nprocs": 32,
                        "sizes": {
                          "min": {"triangular": 8, "honeycomb": 10},
                          "max": {"triangular": 48, "honeycomb": 32}
                        },
                        "fields": {
                          "triangular": [4.76511, 4.76611, 4.76711, 4.76811, 4.76911, 4.77011, 4.77111],
                          "honeycomb": [2.1295, 2.1305, 2.1315, 2.1325, 2.1335, 2.1345, 2.1355]
                        }
                      },
                      "provenance": {},
                      "cells": [
                        {"cell_id": "cell-0001", "params": {"lattice": "triangular", "field_index": 1}},
                        {"cell_id": "cell-0008", "params": {"lattice": "honeycomb", "field_index": 1}}
                      ]
                    }
                    """,
                )

                prepare(index) = `$python $helper prepare --run-spec $run_spec --index $index --role min --repo-root $REPO_ROOT`
                context_triangular = readchomp(prepare(1))
                @test isfile(context_triangular)
                triangular_config = MinimalTFIM.load_config(
                    joinpath(dirname(context_triangular), "config.toml");
                    repo_root = REPO_ROOT,
                )
                @test triangular_config.lattice == :triangular
                @test triangular_config.NumL1 == 8
                @test triangular_config.NumL2 == 8
                @test triangular_config.hTrfd == 4.76511
                @test triangular_config.BetaT == 8 / 4.76511
                @test triangular_config.FixedDltau == 0.013
                @test triangular_config.nLocal == 1
                @test triangular_config.nWolff == 5
                @test triangular_config.nWarm == 10000
                @test triangular_config.NmBin == 32
                @test triangular_config.NSwep == 2000

                context_honeycomb = readchomp(prepare(2))
                @test isfile(context_honeycomb)
                honeycomb_config = MinimalTFIM.load_config(
                    joinpath(dirname(context_honeycomb), "config.toml");
                    repo_root = REPO_ROOT,
                )
                @test honeycomb_config.lattice == :honeycomb
                @test honeycomb_config.NumL1 == 10
                @test honeycomb_config.NumL2 == 10
                @test honeycomb_config.hTrfd == 2.1295
                @test honeycomb_config.BetaT == 10 / 2.1295
                @test triangular_config.seed != honeycomb_config.seed

                repeated = run(
                    pipeline(
                        ignorestatus(prepare(1));
                        stdout = devnull,
                        stderr = devnull,
                    ),
                )
                @test repeated.exitcode != 0
            end

            runner_source = read(runner, String)
            @test occursin("SLURM_ARRAY_TASK_ID", runner_source)
            @test occursin("prepare_extreme_scan_cell.py", runner_source)
            @test occursin(" finalize ", runner_source)
            @test occursin("mpiexecjl", runner_source)
        end
    end

    @testset "SCNet extreme scan array resources" begin
        for (role, walltime) in (("min", "01:00:00"), ("max", "06:00:00"))
            script = joinpath(
                PROJECT_ROOT,
                "scripts",
                "scnet-extremes-$role.sbatch",
            )
            @test isfile(script)
            if isfile(script)
                source = read(script, String)
                @test occursin("#SBATCH --partition=xhacnormalb", source)
                @test occursin("#SBATCH --nodes=1", source)
                @test occursin("#SBATCH --ntasks=32", source)
                @test occursin("#SBATCH --cpus-per-task=1", source)
                @test occursin("#SBATCH --mem=64G", source)
                @test occursin("#SBATCH --time=$walltime", source)
                @test occursin("#SBATCH --array=1-14%8", source)
                @test occursin("SIZE_ROLE=$role", source)
                @test occursin(
                    "challenge-extremes-$role-20260729/run_spec.json",
                    source,
                )
                @test !occursin("C:\\", source)
            end
        end
    end

    @testset "challenge production scan cell preparation" begin
        helper = joinpath(
            PROJECT_ROOT,
            "scripts",
            "prepare_extreme_scan_cell.py",
        )
        runner = joinpath(
            PROJECT_ROOT,
            "scripts",
            "run_challenge_scan_cell.sh",
        )
        @test isfile(helper)
        @test isfile(runner)

        if isfile(helper)
            python = something(Sys.which("python3"), "")
            @test !isempty(python)
            mktempdir(RESULTS_ROOT) do run_dir
                run_spec = joinpath(run_dir, "run_spec.json")
                relative_run_dir = relpath(run_dir, REPO_ROOT)
                write(
                    run_spec,
                    """
                    {
                      "run_id": "test-challenge-production",
                      "run_dir": "$(replace(relative_run_dir, '\\' => '/'))",
                      "settings": {
                        "J1": -1.0,
                        "J2": 0.0,
                        "IfSetDltau": true,
                        "FixedDltau": 0.013,
                        "nLocal": 1,
                        "nWolff": 5,
                        "nWarm": 10000,
                        "NmBin": 32,
                        "NSwep": 2000,
                        "NmMeaConfg": 10,
                        "discard_initial_bins": 1,
                        "trim_extrema": true,
                        "statistics_mode": "bin_sem",
                        "base_seed": 20260729,
                        "initial_state": "random",
                        "nprocs": 32
                      },
                      "provenance": {},
                      "cells": [
                        {
                          "cell_id": "cell-0001",
                          "params": {
                            "lattice": "triangular",
                            "L": 40,
                            "hTrfd": 4.76811,
                            "FixedDltau": 0.016,
                            "scan_kind": "dtau",
                            "seed": 20261001
                          }
                        },
                        {
                          "cell_id": "cell-0002",
                          "params": {
                            "lattice": "honeycomb",
                            "L": 24,
                            "hTrfd": 2.1325,
                            "FixedDltau": 0.02,
                            "scan_kind": "dtau",
                            "seed": 20262001
                          }
                        }
                      ]
                    }
                    """,
                )

                prepare(index) = `$python $helper prepare --run-spec $run_spec --index $index --role scan --repo-root $REPO_ROOT`
                triangular_context = readchomp(prepare(1))
                triangular_config = MinimalTFIM.load_config(
                    joinpath(dirname(triangular_context), "config.toml");
                    repo_root = REPO_ROOT,
                )
                @test triangular_config.lattice == :triangular
                @test triangular_config.NumL1 == 40
                @test triangular_config.hTrfd == 4.76811
                @test triangular_config.BetaT == 40 / 4.76811
                @test triangular_config.FixedDltau == 0.016
                @test triangular_config.seed == 20261001

                honeycomb_context = readchomp(prepare(2))
                honeycomb_config = MinimalTFIM.load_config(
                    joinpath(dirname(honeycomb_context), "config.toml");
                    repo_root = REPO_ROOT,
                )
                @test honeycomb_config.lattice == :honeycomb
                @test honeycomb_config.NumL1 == 24
                @test honeycomb_config.hTrfd == 2.1325
                @test honeycomb_config.BetaT == 24 / 2.1325
                @test honeycomb_config.FixedDltau == 0.02
                @test honeycomb_config.seed == 20262001
            end
        end
    end

    @testset "SCNet challenge production array resources" begin
        for (lattice, count) in (("triangular", 78), ("honeycomb", 71))
            script = joinpath(
                PROJECT_ROOT,
                "scripts",
                "scnet-challenge-$lattice.sbatch",
            )
            @test isfile(script)
            if isfile(script)
                source = read(script, String)
                @test occursin("#SBATCH --partition=xhacnormalb", source)
                @test occursin("#SBATCH --nodes=1", source)
                @test occursin("#SBATCH --ntasks=32", source)
                @test occursin("#SBATCH --cpus-per-task=1", source)
                @test occursin("#SBATCH --mem=64G", source)
                @test occursin("#SBATCH --time=05:00:00", source)
                @test occursin("#SBATCH --array=1-$count%8", source)
                @test occursin(
                    "challenge-production-$lattice-20260729/run_spec.json",
                    source,
                )
                @test occursin("run_challenge_scan_cell.sh", source)
                @test !occursin("C:\\", source)
            end
        end
    end

    @testset "honeycomb quota bundle covers every remaining cell once" begin
        runner = joinpath(
            PROJECT_ROOT,
            "scripts",
            "run_challenge_scan_bundle.sh",
        )
        script = joinpath(
            PROJECT_ROOT,
            "scripts",
            "scnet-challenge-honeycomb-bundle.sbatch",
        )
        @test isfile(runner)
        @test isfile(script)
        if isfile(runner)
            source = read(runner, String)
            @test occursin("START_INDEX=11", source)
            @test occursin("END_INDEX=71", source)
            @test occursin("BUNDLE_COUNT=8", source)
            @test occursin("run_challenge_scan_cell.sh", source)
        end
        if isfile(script)
            source = read(script, String)
            @test occursin("#SBATCH --partition=xhacnormalb", source)
            @test occursin("#SBATCH --ntasks=32", source)
            @test occursin("#SBATCH --mem=64G", source)
            @test occursin("#SBATCH --time=20:00:00", source)
            @test occursin("#SBATCH --array=1-8%8", source)
            @test occursin("run_challenge_scan_bundle.sh", source)
        end

        covered = Int[]
        for bundle_id in 1:8
            append!(covered, (10 + bundle_id):8:71)
        end
        @test sort(covered) == collect(11:71)
        @test length(covered) == length(unique(covered))
    end

    if driver_api_present && isfile(run_script)
        MPI.Initialized() || MPI.Init()

        function driver_config(output_dir)
            return load_with(
                lattice = "triangular",
                NumL1 = 3,
                NumL2 = 3,
                BetaT = 0.12,
                IfSetDltau = false,
                FixedDltau = 0.02,
                LTrot = 6,
                nLocal = 0,
                nWolff = 1,
                nWarm = 2,
                NmBin = 5,
                NSwep = 3,
                NmMeaConfg = 3,
                discard_initial_bins = 1,
                trim_extrema = true,
                seed = 20260728,
                initial_state = "ordered",
                output_dir = output_dir,
            )
        end

        @testset "deterministic rank seeds" begin
            base_seed = UInt64(20260728)
            seeds_a = [
                MinimalTFIM.deterministic_seed(base_seed, rank) for
                rank in 0:3
            ]
            seeds_b = [
                MinimalTFIM.deterministic_seed(base_seed, rank) for
                rank in 0:3
            ]
            @test seeds_a == seeds_b
            @test length(unique(seeds_a)) == 4
            @test all(seed isa UInt64 for seed in seeds_a)
            @test_throws ArgumentError MinimalTFIM.deterministic_seed(
                base_seed,
                -1,
            )
        end

        @testset "one-rank bin reduction" begin
            record = MinimalTFIM.reduce_bin(
                3,
                0.25,
                0.125,
                MPI.COMM_SELF,
            )
            @test record isa MinimalTFIM.BinRecord
            @test record.bin == 3
            @test record.m2 == 0.25
            @test record.m4 == 0.125
            @test record.Q == 0.5
        end

        @testset "serial driver output and repeatability" begin
            mktempdir(RESULTS_ROOT) do output_a
                mktempdir(RESULTS_ROOT) do output_b
                    cfg_a = driver_config(output_a)
                    cfg_b = driver_config(output_b)
                    result_a = MinimalTFIM.run_simulation(
                        cfg_a,
                        MPI.COMM_SELF,
                    )
                    result_b = MinimalTFIM.run_simulation(
                        cfg_b,
                        MPI.COMM_SELF,
                    )

                    @test !isnothing(result_a)
                    @test !isnothing(result_b)
                    @test sort(readdir(output_a)) ==
                          ["bins.csv", "metadata.toml", "results.csv"]
                    @test sort(readdir(output_b)) ==
                          ["bins.csv", "metadata.toml", "results.csv"]
                    @test read(joinpath(output_a, "bins.csv"), String) ==
                          read(joinpath(output_b, "bins.csv"), String)
                    @test read(joinpath(output_a, "results.csv"), String) ==
                          read(joinpath(output_b, "results.csv"), String)

                    results_lines = readlines(
                        joinpath(output_a, "results.csv"),
                    )
                    @test results_lines[1] ==
                          "lattice,NumL1,NumL2,NumNS,J1,J2,hTrfd,BetaT,LTrot,Dltau,nprocs,total_measurements,m2,m2_error,binder_Q,binder_Q_error,statistics_mode"
                    @test length(results_lines) == 2
                    results_fields = split(results_lines[2], ",")
                    @test length(results_fields) == 17
                    @test results_fields[1] == "triangular"
                    @test results_fields[5] == "-1.0"
                    @test results_fields[11] == "1"
                    @test results_fields[12] == "15"
                    @test results_fields[17] == "bin_sem"

                    bins_lines =
                        readlines(joinpath(output_a, "bins.csv"))
                    @test bins_lines[1] == "bin,m2_bin,m4_bin,Q_bin"
                    @test length(bins_lines) == cfg_a.NmBin + 1
                    for line in bins_lines[2:end]
                        fields = split(line, ",")
                        m2 = parse(Float64, fields[2])
                        m4 = parse(Float64, fields[3])
                        Q = parse(Float64, fields[4])
                        @test Q == m2^2 / m4
                    end

                    metadata = TOML.parsefile(
                        joinpath(output_a, "metadata.toml"),
                    )
                    @test all(
                        haskey(metadata, key) for key in (
                            "raw_input",
                            "actual_parameters",
                            "derived_couplings",
                            "runtime",
                            "sampling",
                            "statistics",
                            "diagnostics",
                        )
                    )
                    @test metadata["actual_parameters"]["input_LTrot"] == 6
                    @test metadata["actual_parameters"]["LTrot"] == 6
                    @test metadata["actual_parameters"]["FixedDltau"] == 0.02
                    @test metadata["actual_parameters"]["Dltau"] == 0.02
                    @test metadata["runtime"]["mpi_size"] == 1
                    @test metadata["runtime"]["rank_seeds"] == [
                        string(
                            MinimalTFIM.deterministic_seed(
                                cfg_a.seed,
                                0,
                            ),
                        ),
                    ]
                    @test metadata["sampling"]["nWarm"] == 2
                    @test metadata["sampling"]["NmBin"] == 5
                    @test metadata["sampling"]["NSwep"] == 3
                    @test metadata["sampling"]["NmMeaConfg"] == 3
                    @test metadata["statistics"]["statistics_mode"] ==
                          "bin_sem"
                    @test metadata["statistics"]["discard_initial_bins"] == 1
                    @test metadata["statistics"]["trim_extrema"]
                    @test metadata["statistics"]["number_of_bins_before_filtering"] ==
                          5
                    @test metadata["statistics"]["number_of_bins_after_filtering"] ==
                          2
                    @test metadata["diagnostics"]["local_attempts"] == 0
                    @test metadata["diagnostics"]["local_accepts"] == 0
                    @test metadata["diagnostics"]["local_acceptance"] ==
                          "not_applicable"
                    @test metadata["diagnostics"]["cluster_count"] == 15
                    @test metadata["diagnostics"]["mean_cluster_size"] isa
                          AbstractFloat
                    @test metadata["diagnostics"]["mean_cluster_fraction"] isa
                          AbstractFloat
                    @test metadata["runtime"]["wall_time_seconds"] >= 0
                end
            end
        end

        @testset "nonempty output directory is rejected" begin
            mktempdir(RESULTS_ROOT) do output_dir
                sentinel = joinpath(output_dir, "keep.txt")
                write(sentinel, "keep")
                cfg = driver_config(output_dir)
                error = try
                    MinimalTFIM.run_simulation(cfg, MPI.COMM_SELF)
                    nothing
                catch caught
                    caught
                end
                @test error isa ArgumentError
                @test occursin("nonempty", sprint(showerror, error))
                @test readdir(output_dir) == ["keep.txt"]
                @test read(sentinel, String) == "keep"
            end
        end

        @testset "command entry point requires one configuration" begin
            command = `$(Base.julia_cmd()) --project=$(PROJECT_ROOT) $(run_script)`
            process = run(
                pipeline(ignorestatus(command); stdout = devnull, stderr = devnull),
            )
            @test process.exitcode != 0
        end
    end
end

if run_group("mpi")
    @testset "MPI launcher smoke run" begin
        nprocs = parse(Int, get(ENV, "JULIA_MPI_TEST_NPROCS", "1"))
        @test nprocs in (1, 2)
        launcher = get(
            ENV,
            "JULIA_MPI_TEST_LAUNCHER",
            joinpath(first(DEPOT_PATH), "bin", "mpiexecjl"),
        )
        @test isfile(launcher)

        if nprocs in (1, 2) && isfile(launcher)
            mkpath(RESULTS_ROOT)
            mktempdir(RESULTS_ROOT) do test_root
                output_dir = joinpath(test_root, "output")
                config_path = joinpath(test_root, "smoke.toml")
                log_path = joinpath(test_root, "run.log")
                raw = TOML.parsefile(
                    joinpath(
                        PROJECT_ROOT,
                        "configs",
                        "smoke-triangular.toml",
                    ),
                )
                raw["output_dir"] = relpath(output_dir, REPO_ROOT)
                open(config_path, "w") do io
                    TOML.print(io, raw)
                end

                julia = joinpath(Sys.BINDIR, Base.julia_exename())
                run_script = joinpath(PROJECT_ROOT, "scripts", "run.jl")
                command = `$launcher -n $nprocs $julia --project=$PROJECT_ROOT $run_script $config_path`
                process = open(log_path, "w") do log
                    run(
                        pipeline(
                            ignorestatus(command);
                            stdout = log,
                            stderr = log,
                        ),
                    )
                end
                if !success(process)
                    println(read(log_path, String))
                end
                @test success(process)

                if success(process)
                    @test sort(readdir(output_dir)) ==
                          ["bins.csv", "metadata.toml", "results.csv"]
                    metadata = TOML.parsefile(
                        joinpath(output_dir, "metadata.toml"),
                    )
                    @test metadata["runtime"]["mpi_size"] == nprocs
                    @test length(metadata["runtime"]["rank_seeds"]) ==
                          nprocs
                    @test length(unique(metadata["runtime"]["rank_seeds"])) ==
                          nprocs

                    bins_lines =
                        readlines(joinpath(output_dir, "bins.csv"))
                    @test length(bins_lines) == raw["NmBin"] + 1

                    results_lines =
                        readlines(joinpath(output_dir, "results.csv"))
                    header = split(results_lines[1], ",")
                    values = split(results_lines[2], ",")
                    results = Dict(zip(header, values))
                    @test parse(Int, results["nprocs"]) == nprocs
                    @test parse(Int, results["total_measurements"]) ==
                          nprocs * raw["NmBin"] * raw["NSwep"]

                    all_files = String[]
                    for (root, _, files) in walkdir(test_root)
                        append!(
                            all_files,
                            joinpath.(Ref(root), files),
                        )
                    end
                    for common_output in (
                        "bins.csv",
                        "metadata.toml",
                        "results.csv",
                    )
                        @test count(
                            path -> basename(path) == common_output,
                            all_files,
                        ) == 1
                    end
                end
            end
        end
    end
end
