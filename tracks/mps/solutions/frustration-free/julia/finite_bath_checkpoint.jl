module FiniteBathCheckpoint

using HDF5
using ITensors
using ITensorMPS
using JSON3
using SHA

const PARENT_MODULE = parentmodule(@__MODULE__)
isdefined(PARENT_MODULE, :FiniteBathPurification) ||
    Base.include(
        PARENT_MODULE, joinpath(@__DIR__, "finite_bath_purification.jl")
    )
using ..FiniteBathPurification:
    EvolutionResumeState,
    PurificationSpec,
    non_qn_purification

export CheckpointIdentity,
    CheckpointCursor,
    EvolutionResumeState,
    ObservableCursor,
    ObservableResumeState,
    write_checkpoint_generation,
    load_current_checkpoint

const SHA256_PATTERN = r"^[0-9a-f]{64}$"
const GENERATION_PATTERN = r"^checkpoint-[0-9a-f]{64}$"

struct ObservableCursor
    phase::Symbol
    tau_index::Int
    spin::Symbol
    insertion::Symbol
    segment::Symbol

    function ObservableCursor(phase, tau_index, spin, insertion, segment)
        phase isa Symbol ||
            throw(ArgumentError("observable cursor phase must be a symbol"))
        tau_index isa Integer && !(tau_index isa Bool) ||
            throw(ArgumentError("observable cursor tau_index must be an integer"))
        spin isa Symbol ||
            throw(ArgumentError("observable cursor spin must be a symbol"))
        insertion isa Symbol ||
            throw(ArgumentError("observable cursor insertion must be a symbol"))
        segment isa Symbol ||
            throw(ArgumentError("observable cursor segment must be a symbol"))
        if phase === :thermal || phase === :complete
            tau_index == 0 && spin === :none && insertion === :none &&
                segment === :none ||
                throw(ArgumentError("thermal and complete cursors have no branch coordinates"))
        elseif phase === :green
            tau_index > 0 ||
                throw(ArgumentError("green cursor tau_index must be positive"))
            spin in (:up, :dn) ||
                throw(ArgumentError("green cursor spin must be :up or :dn"))
            insertion in (:creation, :annihilation) ||
                throw(ArgumentError("green cursor insertion is invalid"))
            segment in (:before, :after, :terminal) ||
                throw(ArgumentError("green cursor segment is invalid"))
        else
            throw(ArgumentError("observable cursor phase is invalid"))
        end
        return new(phase, Int(tau_index), spin, insertion, segment)
    end
end

struct ObservableResumeState
    cursor::ObservableCursor
    evolution_state::Union{Nothing,EvolutionResumeState}
    thermal_psi::Union{Nothing,MPS}
    data::NamedTuple

    function ObservableResumeState(
        cursor,
        evolution_state,
        thermal_psi,
        data,
    )
        nameof(typeof(cursor)) == :ObservableCursor &&
            fieldnames(typeof(cursor)) == fieldnames(ObservableCursor) ||
            throw(ArgumentError("observable cursor is invalid"))
        normalized_cursor = ObservableCursor(
            cursor.phase,
            cursor.tau_index,
            cursor.spin,
            cursor.insertion,
            cursor.segment,
        )
        evolution_state === nothing ||
            (
                nameof(typeof(evolution_state)) == :EvolutionResumeState &&
                fieldnames(typeof(evolution_state)) ==
                fieldnames(EvolutionResumeState)
            ) ||
            throw(ArgumentError("observable evolution_state is invalid"))
        normalized_evolution =
            evolution_state === nothing ?
            nothing : EvolutionResumeState(;
                completed_steps = evolution_state.completed_steps,
                beta_endpoint = evolution_state.beta_endpoint,
                log_unnormalized_norm =
                    evolution_state.log_unnormalized_norm,
                maximum_link_dimensions_by_bond =
                    evolution_state.maximum_link_dimensions_by_bond,
                step_history = evolution_state.step_history,
                expansion_applied = evolution_state.expansion_applied,
            )
        thermal_psi === nothing || thermal_psi isa MPS ||
            throw(ArgumentError("observable thermal_psi is invalid"))
        data isa NamedTuple ||
            throw(ArgumentError("observable data must be a named tuple"))
        normalized_cursor.phase === :thermal && thermal_psi !== nothing &&
            throw(ArgumentError("thermal cursor cannot carry a completed thermal state"))
        normalized_cursor.phase !== :thermal && thermal_psi === nothing &&
            throw(ArgumentError("post-thermal cursor requires the thermal state"))
        return new(normalized_cursor, normalized_evolution, thermal_psi, data)
    end
end

struct CheckpointIdentity
    request_sha256::String
    input_payload_sha256::String
    bath_sha256::String
    bath_representation::String
    chain_mapping_sha256::Union{Nothing,String}
    solver_settings::Dict{String,Any}
    source_hashes::Dict{String,String}
    project_toml_sha256::String
    manifest_toml_sha256::String
    julia_version::String
    itensors_version::String
    itensormps_version::String
    hdf5_version::String
    checkpoint_schema::Int
    writer_version::String
end

Base.:(==)(left::CheckpointIdentity, right::CheckpointIdentity) =
    all(
        getfield(left, field) == getfield(right, field) for
        field in fieldnames(CheckpointIdentity)
    )

function CheckpointIdentity(;
    request_sha256,
    input_payload_sha256,
    bath_sha256,
    bath_representation = "direct_star",
    chain_mapping_sha256 = nothing,
    solver_settings,
    source_hashes,
    project_toml_sha256,
    manifest_toml_sha256,
    julia_version,
    itensors_version,
    itensormps_version,
    hdf5_version,
    checkpoint_schema,
    writer_version,
)
    hashes = Dict{String,String}()
    for (name, value) in pairs(source_hashes)
        hashes[String(name)] = _sha256(value, "source_hashes.$name")
    end
    isempty(hashes) &&
        throw(ArgumentError("source_hashes must not be empty"))
    settings = _json_object(solver_settings, "solver_settings")
    checkpoint_schema isa Integer && !(checkpoint_schema isa Bool) &&
        checkpoint_schema > 0 ||
        throw(ArgumentError("checkpoint_schema must be a positive integer"))
    bath_representation isa AbstractString ||
        throw(ArgumentError("bath_representation must be a string"))
    representation = String(bath_representation)
    representation in ("direct_star", "chain") ||
        throw(ArgumentError("bath_representation is unsupported"))
    if representation == "direct_star"
        chain_mapping_sha256 === nothing ||
            throw(ArgumentError("direct_star identity requires null chain_mapping_sha256"))
        mapping_sha256 = nothing
    else
        mapping_sha256 = _sha256(
            chain_mapping_sha256, "chain_mapping_sha256"
        )
    end
    return CheckpointIdentity(
        _sha256(request_sha256, "request_sha256"),
        _sha256(input_payload_sha256, "input_payload_sha256"),
        _sha256(bath_sha256, "bath_sha256"),
        representation,
        mapping_sha256,
        settings,
        hashes,
        _sha256(project_toml_sha256, "project_toml_sha256"),
        _sha256(manifest_toml_sha256, "manifest_toml_sha256"),
        _nonempty_string(julia_version, "julia_version"),
        _nonempty_string(itensors_version, "itensors_version"),
        _nonempty_string(itensormps_version, "itensormps_version"),
        _nonempty_string(hdf5_version, "hdf5_version"),
        Int(checkpoint_schema),
        _nonempty_string(writer_version, "writer_version"),
    )
end

struct CheckpointCursor
    completed_steps::Int
    generation::String
    metadata_sha256::String
    state_sha256::String
    completion_sha256::String
end

Base.:(==)(left::CheckpointCursor, right::CheckpointCursor) =
    all(
        getfield(left, field) == getfield(right, field) for
        field in fieldnames(CheckpointCursor)
    )

function CheckpointCursor(;
    completed_steps,
    generation = "",
    metadata_sha256 = "",
    state_sha256 = "",
    completion_sha256 = "",
)
    completed_steps isa Integer && !(completed_steps isa Bool) &&
        completed_steps >= 0 ||
        throw(ArgumentError("completed_steps must be a nonnegative integer"))
    values = (generation, metadata_sha256, state_sha256, completion_sha256)
    all_empty = all(isempty, values)
    all_bound = all(!isempty, values)
    all_empty || all_bound ||
        throw(ArgumentError("checkpoint cursor bindings must be all present or absent"))
    if all_bound
        occursin(GENERATION_PATTERN, generation) ||
            throw(ArgumentError("generation is invalid"))
        _sha256(metadata_sha256, "metadata_sha256")
        _sha256(state_sha256, "state_sha256")
        _sha256(completion_sha256, "completion_sha256")
        generation == "checkpoint-$metadata_sha256" ||
            throw(ArgumentError("generation does not bind metadata_sha256"))
    end
    return CheckpointCursor(
        Int(completed_steps),
        String(generation),
        String(metadata_sha256),
        String(state_sha256),
        String(completion_sha256),
    )
end

CheckpointCursor(completed_steps::Integer) =
    CheckpointCursor(; completed_steps)

function write_checkpoint_generation(
    root,
    identity::CheckpointIdentity,
    cursor,
    psi::Union{Nothing,MPS},
    resume_state,
    ;
    purification::PurificationSpec = non_qn_purification(),
)
    completed_steps =
        cursor isa CheckpointCursor ? cursor.completed_steps :
        cursor isa Integer && !(cursor isa Bool) ? Int(cursor) :
        throw(ArgumentError("cursor must be a CheckpointCursor or integer"))
    if nameof(typeof(resume_state)) == :ObservableResumeState &&
       fieldnames(typeof(resume_state)) == fieldnames(ObservableResumeState) &&
       !(resume_state isa ObservableResumeState)
        resume_state = ObservableResumeState(
            resume_state.cursor,
            resume_state.evolution_state,
            resume_state.thermal_psi,
            resume_state.data,
        )
    end
    _validate_resume_state(resume_state, completed_steps)
    _validate_observable_sector_contract(
        resume_state, psi, purification
    )
    terminal_zero =
        resume_state isa ObservableResumeState &&
        resume_state.cursor.segment === :terminal &&
        haskey(resume_state.data, :branch_status) &&
        resume_state.data.branch_status === :zero &&
        haskey(resume_state.data, :expected_sector)
    (psi !== nothing || terminal_zero) ||
        throw(ArgumentError("only zero terminal checkpoints may omit active MPS"))
    (psi === nothing || !terminal_zero) ||
        throw(ArgumentError("zero terminal checkpoint must omit active MPS"))
    root_path = abspath(String(root))
    _ensure_directory(root_path, "checkpoint root"; create = true)
    generations = joinpath(root_path, "generations")
    _ensure_directory(generations, "generations directory"; create = true)

    metadata = Dict{String,Any}(
        "checkpoint_schema" => identity.checkpoint_schema,
        "writer_version" => identity.writer_version,
        "identity" => _identity_dict(identity),
        "completed_steps" => completed_steps,
        "resume_state" => _resume_state_dict(resume_state),
    )
    metadata_bytes = _canonical_bytes(metadata)
    metadata_sha256 = _bytes_sha256(metadata_bytes)
    generation_name = "checkpoint-$metadata_sha256"
    stage = mktempdir(generations; prefix = ".stage-", cleanup = false)
    published = false
    try
        metadata_path = joinpath(stage, "metadata.json")
        _write_durable(metadata_path, metadata_bytes)

        state_path = joinpath(stage, "state.h5")
        try
            h5open(state_path, "w") do file
                psi !== nothing && write(file, "psi", psi)
                resume_state isa ObservableResumeState &&
                    resume_state.thermal_psi !== nothing &&
                    write(file, "thermal_psi", resume_state.thermal_psi)
            end
        catch error
            throw(ArgumentError("could not write checkpoint MPS: $(sprint(showerror, error))"))
        end
        _fsync_file(state_path)
        state_sha256 = _file_sha256(state_path)

        completion = Dict{String,Any}(
            "checkpoint_schema" => identity.checkpoint_schema,
            "writer_version" => identity.writer_version,
            "generation" => generation_name,
            "metadata_sha256" => metadata_sha256,
            "state_sha256" => state_sha256,
        )
        completion_bytes = _canonical_bytes(completion)
        completion_sha256 = _bytes_sha256(completion_bytes)
        _write_durable(joinpath(stage, "completion.json"), completion_bytes)
        _fsync_directory(stage)
        cursor_bound = CheckpointCursor(;
            completed_steps,
            generation = generation_name,
            metadata_sha256,
            state_sha256,
            completion_sha256,
        )

        _load_generation(
            stage, cursor_bound, identity, purification
        )
        destination = joinpath(generations, generation_name)
        if ispath(destination)
            _require_directory(destination, "generation")
            _load_generation(
                destination, cursor_bound, identity, purification
            )
            rm(stage; recursive = true)
        else
            Base.Filesystem.rename(stage, destination)
            _fsync_directory(generations)
        end
        _fsync_directory(root_path)

        pointer = _cursor_dict(cursor_bound, identity)
        _atomic_write_current(root_path, _canonical_bytes(pointer))
        published = true
        return cursor_bound
    finally
        !published && ispath(stage) && rm(stage; recursive = true, force = true)
    end
end

function load_current_checkpoint(
    root,
    expected_identity::CheckpointIdentity;
    purification::PurificationSpec = non_qn_purification(),
)
    root_path = abspath(String(root))
    _require_directory(root_path, "checkpoint root")
    generations = joinpath(root_path, "generations")
    _require_directory(generations, "generations directory")
    pointer_path = joinpath(root_path, "current.json")
    pointer = _read_canonical_json(pointer_path, "current pointer")
    _require_exact_keys(
        pointer,
        [
            "checkpoint_schema",
            "writer_version",
            "generation",
            "completed_steps",
            "metadata_sha256",
            "state_sha256",
            "completion_sha256",
        ],
        "current pointer",
    )
    pointer["checkpoint_schema"] == expected_identity.checkpoint_schema ||
        throw(ArgumentError("checkpoint schema mismatch"))
    pointer["writer_version"] == expected_identity.writer_version ||
        throw(ArgumentError("checkpoint writer version mismatch"))
    cursor = CheckpointCursor(;
        completed_steps = pointer["completed_steps"],
        generation = pointer["generation"],
        metadata_sha256 = pointer["metadata_sha256"],
        state_sha256 = pointer["state_sha256"],
        completion_sha256 = pointer["completion_sha256"],
    )
    generation = joinpath(generations, cursor.generation)
    return _load_generation(
        generation, cursor, expected_identity, purification
    )
end

function _load_generation(
    generation_path,
    cursor::CheckpointCursor,
    expected_identity::CheckpointIdentity,
    purification::PurificationSpec,
)
    _require_directory(generation_path, "generation")
    metadata_path = joinpath(generation_path, "metadata.json")
    state_path = joinpath(generation_path, "state.h5")
    completion_path = joinpath(generation_path, "completion.json")
    metadata = _read_canonical_json(metadata_path, "checkpoint metadata")
    completion = _read_canonical_json(completion_path, "checkpoint completion")
    _require_regular_file(state_path, "checkpoint state")
    _file_sha256(metadata_path) == cursor.metadata_sha256 ||
        throw(ArgumentError("checkpoint metadata hash mismatch"))
    _file_sha256(state_path) == cursor.state_sha256 ||
        throw(ArgumentError("checkpoint state hash mismatch"))
    _file_sha256(completion_path) == cursor.completion_sha256 ||
        throw(ArgumentError("checkpoint completion hash mismatch"))

    _require_exact_keys(
        metadata,
        [
            "checkpoint_schema",
            "writer_version",
            "identity",
            "completed_steps",
            "resume_state",
        ],
        "checkpoint metadata",
    )
    _require_exact_keys(
        completion,
        [
            "checkpoint_schema",
            "writer_version",
            "generation",
            "metadata_sha256",
            "state_sha256",
        ],
        "checkpoint completion",
    )
    completion == Dict{String,Any}(
        "checkpoint_schema" => expected_identity.checkpoint_schema,
        "writer_version" => expected_identity.writer_version,
        "generation" => cursor.generation,
        "metadata_sha256" => cursor.metadata_sha256,
        "state_sha256" => cursor.state_sha256,
    ) || throw(ArgumentError("checkpoint completion bindings mismatch"))
    metadata["checkpoint_schema"] == expected_identity.checkpoint_schema ||
        throw(ArgumentError("checkpoint schema mismatch"))
    metadata["writer_version"] == expected_identity.writer_version ||
        throw(ArgumentError("checkpoint writer version mismatch"))
    identity = _identity_from_dict(metadata["identity"])
    identity == expected_identity ||
        throw(ArgumentError("checkpoint identity mismatch"))
    metadata["completed_steps"] == cursor.completed_steps ||
        throw(ArgumentError("checkpoint cursor mismatch"))
    psi, thermal_psi = try
        h5open(state_path, "r") do file
            active =
                haskey(file, "psi") ? read(file, "psi", MPS) : nothing
            thermal =
                haskey(file, "thermal_psi") ?
                read(file, "thermal_psi", MPS) : nothing
            (active, thermal)
        end
    catch error
        error isa ArgumentError && rethrow()
        throw(ArgumentError("could not read checkpoint MPS: $(sprint(showerror, error))"))
    end
    resume_state =
        _resume_state_from_dict(metadata["resume_state"], thermal_psi)
    _validate_resume_state(resume_state, cursor.completed_steps)
    _validate_observable_sector_contract(
        resume_state, psi, purification
    )
    terminal_zero =
        resume_state isa ObservableResumeState &&
        resume_state.cursor.segment === :terminal &&
        haskey(resume_state.data, :branch_status) &&
        resume_state.data.branch_status === :zero &&
        haskey(resume_state.data, :expected_sector)
    (psi !== nothing || terminal_zero) ||
        throw(ArgumentError("checkpoint state does not contain psi"))
    (psi === nothing || !terminal_zero) ||
        throw(ArgumentError("zero terminal checkpoint contains active MPS"))
    return (; identity, cursor, psi, resume_state)
end

function _identity_dict(identity::CheckpointIdentity)
    return Dict{String,Any}(
        "request_sha256" => identity.request_sha256,
        "input_payload_sha256" => identity.input_payload_sha256,
        "bath_sha256" => identity.bath_sha256,
        "bath_representation" => identity.bath_representation,
        "chain_mapping_sha256" => identity.chain_mapping_sha256,
        "solver_settings" => identity.solver_settings,
        "source_hashes" => identity.source_hashes,
        "project_toml_sha256" => identity.project_toml_sha256,
        "manifest_toml_sha256" => identity.manifest_toml_sha256,
        "julia_version" => identity.julia_version,
        "itensors_version" => identity.itensors_version,
        "itensormps_version" => identity.itensormps_version,
        "hdf5_version" => identity.hdf5_version,
        "checkpoint_schema" => identity.checkpoint_schema,
        "writer_version" => identity.writer_version,
    )
end

function _identity_from_dict(value)
    _require_exact_keys(
        value,
        [
            "request_sha256",
            "input_payload_sha256",
            "bath_sha256",
            "bath_representation",
            "chain_mapping_sha256",
            "solver_settings",
            "source_hashes",
            "project_toml_sha256",
            "manifest_toml_sha256",
            "julia_version",
            "itensors_version",
            "itensormps_version",
            "hdf5_version",
            "checkpoint_schema",
            "writer_version",
        ],
        "checkpoint identity",
    )
    return CheckpointIdentity(;
        request_sha256 = value["request_sha256"],
        input_payload_sha256 = value["input_payload_sha256"],
        bath_sha256 = value["bath_sha256"],
        bath_representation = value["bath_representation"],
        chain_mapping_sha256 = value["chain_mapping_sha256"],
        solver_settings = value["solver_settings"],
        source_hashes = value["source_hashes"],
        project_toml_sha256 = value["project_toml_sha256"],
        manifest_toml_sha256 = value["manifest_toml_sha256"],
        julia_version = value["julia_version"],
        itensors_version = value["itensors_version"],
        itensormps_version = value["itensormps_version"],
        hdf5_version = value["hdf5_version"],
        checkpoint_schema = value["checkpoint_schema"],
        writer_version = value["writer_version"],
    )
end

function _resume_state_dict(state)
    if state isa ObservableResumeState
        return Dict{String,Any}(
            "kind" => "observable",
            "cursor" => Dict{String,Any}(
                "phase" => String(state.cursor.phase),
                "tau_index" => state.cursor.tau_index,
                "spin" => String(state.cursor.spin),
                "insertion" => String(state.cursor.insertion),
                "segment" => String(state.cursor.segment),
            ),
            "evolution_state" =>
                state.evolution_state === nothing ?
                nothing : _resume_state_dict(state.evolution_state),
            "thermal_psi" => state.thermal_psi !== nothing,
            "data" => _typed_json_value(state.data),
        )
    end
    history = [
        Dict{String,Any}(
            "keys" => String.(collect(keys(entry))),
            "values" => [_json_value(item, "step_history value") for item in values(entry)],
        ) for entry in state.step_history
    ]
    return Dict{String,Any}(
        "completed_steps" => state.completed_steps,
        "beta_endpoint" => state.beta_endpoint,
        "log_unnormalized_norm" => state.log_unnormalized_norm,
        "maximum_link_dimensions_by_bond" =>
            state.maximum_link_dimensions_by_bond,
        "step_history" => history,
        "expansion_applied" => state.expansion_applied,
    )
end

function _resume_state_from_dict(value, thermal_psi = nothing)
    if value isa AbstractDict && get(value, "kind", nothing) == "observable"
        _require_exact_keys(
            value,
            ["kind", "cursor", "evolution_state", "thermal_psi", "data"],
            "observable resume state",
        )
        cursor_value = value["cursor"]
        _require_exact_keys(
            cursor_value,
            ["phase", "tau_index", "spin", "insertion", "segment"],
            "observable cursor",
        )
        cursor = ObservableCursor(
            Symbol(cursor_value["phase"]),
            cursor_value["tau_index"],
            Symbol(cursor_value["spin"]),
            Symbol(cursor_value["insertion"]),
            Symbol(cursor_value["segment"]),
        )
        value["thermal_psi"] isa Bool ||
            throw(ArgumentError("observable thermal-state marker is invalid"))
        (thermal_psi !== nothing) == value["thermal_psi"] ||
            throw(ArgumentError("observable thermal-state binding mismatch"))
        evolution =
            value["evolution_state"] === nothing ?
            nothing : _resume_state_from_dict(value["evolution_state"])
        data = _typed_json_restore(value["data"])
        data isa NamedTuple ||
            throw(ArgumentError("observable checkpoint data is invalid"))
        return ObservableResumeState(cursor, evolution, thermal_psi, data)
    end
    _require_exact_keys(
        value,
        [
            "completed_steps",
            "beta_endpoint",
            "log_unnormalized_norm",
            "maximum_link_dimensions_by_bond",
            "step_history",
            "expansion_applied",
        ],
        "resume state",
    )
    history_value = value["step_history"]
    history_value isa AbstractVector ||
        throw(ArgumentError("resume state history must be an array"))
    history = NamedTuple[]
    for (index, entry) in enumerate(history_value)
        _require_exact_keys(entry, ["keys", "values"], "resume state history[$index]")
        entry["keys"] isa AbstractVector &&
            all(key -> key isa AbstractString, entry["keys"]) ||
            throw(ArgumentError("resume state history keys must be strings"))
        entry["values"] isa AbstractVector ||
            throw(ArgumentError("resume state history values must be an array"))
        length(entry["keys"]) == length(entry["values"]) ||
            throw(ArgumentError("resume state history key/value length mismatch"))
        symbols = Tuple(Symbol.(entry["keys"]))
        length(unique(symbols)) == length(symbols) ||
            throw(ArgumentError("resume state history contains duplicate keys"))
        push!(history, NamedTuple{symbols}(Tuple(entry["values"])))
    end
    return try
        EvolutionResumeState(;
            completed_steps = value["completed_steps"],
            beta_endpoint = value["beta_endpoint"],
            log_unnormalized_norm = value["log_unnormalized_norm"],
            maximum_link_dimensions_by_bond =
                value["maximum_link_dimensions_by_bond"],
            step_history = history,
            expansion_applied = value["expansion_applied"],
        )
    catch error
        throw(ArgumentError("invalid checkpoint resume state: $(sprint(showerror, error))"))
    end
end

function _operator_sector_coordinates(value, name)
    nameof(typeof(value)) == :OperatorSector &&
        fieldnames(typeof(value)) == (:insertion, :spin, :nf, :sz) ||
        throw(ArgumentError("$name is not an operator sector"))
    return (
        insertion = value.insertion,
        spin = value.spin,
        nf = value.nf,
        sz = value.sz,
    )
end

function _validate_observable_sector_contract(
    state,
    active::Union{Nothing,MPS},
    purification::PurificationSpec,
)
    state isa ObservableResumeState || return nothing
    cursor = state.cursor
    qn_enabled = purification.mode === :qn_dual
    base_flux =
        qn_enabled ?
        QN(
            ("Nf", purification.base_sector_nf, -1),
            ("Sz", purification.base_sector_sz),
        ) : nothing

    if state.thermal_psi !== nothing
        if qn_enabled
            flux(state.thermal_psi) == base_flux ||
                throw(ArgumentError(
                    "checkpoint thermal state has the wrong base sector"
                ))
        else
            all(!hasqns(site) for site in siteinds(state.thermal_psi)) ||
                throw(ArgumentError(
                    "non-QN checkpoint thermal state contains QNs"
                ))
        end
    end

    shifted =
        cursor.phase === :green &&
        cursor.segment in (:after, :terminal)
    reported_sector = get(state.data, :expected_sector, nothing)
    if shifted && qn_enabled
        delta_nf = cursor.insertion === :creation ? 1 : -1
        delta_sz =
            (cursor.insertion, cursor.spin) in
            ((:creation, :up), (:annihilation, :dn)) ? 1 : -1
        expected = (
            insertion = cursor.insertion,
            spin = cursor.spin,
            nf = purification.base_sector_nf + delta_nf,
            sz = delta_sz,
        )
        _operator_sector_coordinates(
            reported_sector, "checkpoint expected sector"
        ) == expected ||
            throw(ArgumentError(
                "checkpoint expected sector disagrees with purification"
            ))
    else
        reported_sector === nothing ||
            throw(ArgumentError(
                "checkpoint cannot claim an operator sector"
            ))
    end

    if cursor.segment === :terminal
        active === nothing ||
            throw(ArgumentError(
                "zero terminal checkpoint cannot contain active MPS"
            ))
        return nothing
    end

    active !== nothing ||
        throw(ArgumentError("checkpoint is missing active MPS"))
    if shifted && qn_enabled
        coordinates = _operator_sector_coordinates(
            reported_sector, "checkpoint expected sector"
        )
        flux(active) ==
            QN(
                ("Nf", coordinates.nf, -1),
                ("Sz", coordinates.sz),
            ) ||
            throw(ArgumentError(
                "checkpoint active state has the wrong operator sector"
            ))
    elseif qn_enabled
        flux(active) == base_flux ||
            throw(ArgumentError(
                "checkpoint active state has the wrong base sector"
            ))
    else
        all(!hasqns(site) for site in siteinds(active)) ||
            throw(ArgumentError(
                "non-QN checkpoint active state contains QNs"
            ))
    end
    return nothing
end

function _validate_resume_state(state, completed_steps)
    if state isa ObservableResumeState
        state_steps =
            state.evolution_state === nothing ?
            0 : state.evolution_state.completed_steps
        state_steps == completed_steps ||
            throw(ArgumentError("cursor does not match observable evolution state"))
        state.evolution_state === nothing ||
            _validate_resume_state(state.evolution_state, completed_steps)
        return nothing
    end
    nameof(typeof(state)) == :EvolutionResumeState &&
        fieldnames(typeof(state)) == fieldnames(EvolutionResumeState) ||
        throw(ArgumentError("resume_state must be an EvolutionResumeState"))
    state.completed_steps == completed_steps ||
        throw(ArgumentError("cursor does not match resume state"))
    completed_steps >= 0 ||
        throw(ArgumentError("completed_steps must be nonnegative"))
    length(state.step_history) == completed_steps ||
        throw(ArgumentError("resume state history length mismatch"))
    isfinite(state.beta_endpoint) && state.beta_endpoint >= 0 ||
        throw(ArgumentError("resume state beta endpoint is invalid"))
    isfinite(state.log_unnormalized_norm) ||
        throw(ArgumentError("resume state log norm is invalid"))
    all(dimension -> dimension >= 0, state.maximum_link_dimensions_by_bond) ||
        throw(ArgumentError("resume state link dimensions are invalid"))
    return nothing
end

function _typed_json_value(value)
    if value isa Symbol
        return Dict{String,Any}("__type__" => "symbol", "value" => String(value))
    elseif value isa NamedTuple
        return Dict{String,Any}(
            "__type__" => "named_tuple",
            "keys" => String.(collect(keys(value))),
            "values" => [_typed_json_value(item) for item in values(value)],
        )
    elseif nameof(typeof(value)) == :OperatorSector &&
           fieldnames(typeof(value)) == (:insertion, :spin, :nf, :sz)
        return Dict{String,Any}(
            "__type__" => "operator_sector",
            "insertion" => String(value.insertion),
            "spin" => String(value.spin),
            "nf" => value.nf,
            "sz" => value.sz,
        )
    elseif value isa Tuple
        return Dict{String,Any}(
            "__type__" => "tuple",
            "values" => [_typed_json_value(item) for item in value],
        )
    elseif value isa AbstractVector
        return [_typed_json_value(item) for item in value]
    elseif value isa AbstractFloat && !isfinite(value)
        return Dict{String,Any}(
            "__type__" => "nonfinite",
            "value" => isnan(value) ? "nan" : signbit(value) ? "-inf" : "inf",
        )
    elseif value === nothing || value isa Bool || value isa Integer ||
           value isa AbstractFloat || value isa AbstractString
        return value
    end
    throw(ArgumentError("observable checkpoint data contains unsupported value $(typeof(value))"))
end

function _typed_json_restore(value)
    if value isa AbstractVector
        return Any[_typed_json_restore(item) for item in value]
    elseif value isa AbstractDict && haskey(value, "__type__")
        kind = value["__type__"]
        if kind == "symbol"
            _require_exact_keys(value, ["__type__", "value"], "typed symbol")
            return Symbol(value["value"])
        elseif kind == "named_tuple"
            _require_exact_keys(
                value, ["__type__", "keys", "values"], "typed named tuple"
            )
            keys_value = Symbol.(value["keys"])
            length(keys_value) == length(value["values"]) ||
                throw(ArgumentError("typed named tuple length mismatch"))
            length(unique(keys_value)) == length(keys_value) ||
                throw(ArgumentError("typed named tuple contains duplicate keys"))
            return NamedTuple{Tuple(keys_value)}(
                Tuple(_typed_json_restore(item) for item in value["values"])
            )
        elseif kind == "tuple"
            _require_exact_keys(value, ["__type__", "values"], "typed tuple")
            return Tuple(_typed_json_restore(item) for item in value["values"])
        elseif kind == "nonfinite"
            _require_exact_keys(value, ["__type__", "value"], "typed nonfinite")
            value["value"] == "-inf" && return -Inf
            value["value"] == "inf" && return Inf
            value["value"] == "nan" && return NaN
            throw(ArgumentError("typed nonfinite value is invalid"))
        elseif kind == "operator_sector"
            _require_exact_keys(
                value,
                ["__type__", "insertion", "spin", "nf", "sz"],
                "typed operator sector",
            )
            isdefined(PARENT_MODULE, :FiniteBathObservables) ||
                throw(ArgumentError(
                    "operator sector type is unavailable"
                ))
            constructor = getfield(
                getfield(PARENT_MODULE, :FiniteBathObservables),
                :OperatorSector,
            )
            return constructor(
                Symbol(value["insertion"]),
                Symbol(value["spin"]),
                value["nf"],
                value["sz"],
            )
        end
        throw(ArgumentError("observable checkpoint data type is invalid"))
    elseif value === nothing || value isa Bool || value isa Integer ||
           value isa AbstractFloat || value isa AbstractString
        return value
    end
    throw(ArgumentError("observable checkpoint data is invalid"))
end

function _cursor_dict(cursor::CheckpointCursor, identity::CheckpointIdentity)
    return Dict{String,Any}(
        "checkpoint_schema" => identity.checkpoint_schema,
        "writer_version" => identity.writer_version,
        "generation" => cursor.generation,
        "completed_steps" => cursor.completed_steps,
        "metadata_sha256" => cursor.metadata_sha256,
        "state_sha256" => cursor.state_sha256,
        "completion_sha256" => cursor.completion_sha256,
    )
end

function _json_value(value, name)
    if value === nothing || value isa Bool || value isa Integer ||
       value isa AbstractString
        return value
    elseif value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("$name contains a nonfinite number"))
        return Float64(value)
    elseif value isa AbstractVector
        return [_json_value(item, name) for item in value]
    elseif value isa NamedTuple || value isa AbstractDict
        return _json_object(value, name)
    end
    throw(ArgumentError("$name contains unsupported value $(typeof(value))"))
end

function _json_object(value, name)
    value isa NamedTuple || value isa AbstractDict ||
        throw(ArgumentError("$name must be an object"))
    result = Dict{String,Any}()
    for (key, item) in pairs(value)
        string_key = String(key)
        haskey(result, string_key) &&
            throw(ArgumentError("$name contains duplicate key $string_key"))
        result[string_key] = _json_value(item, "$name.$string_key")
    end
    return result
end

function _canonical_json(value)
    if value === nothing || value isa Bool || value isa Integer ||
       value isa AbstractString
        return String(JSON3.write(value))
    elseif value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("canonical JSON contains a nonfinite number"))
        return String(JSON3.write(value))
    elseif value isa AbstractVector
        return "[" * join(_canonical_json.(value), ",") * "]"
    elseif value isa AbstractDict
        entries = String[]
        for key in sort!(String.(collect(keys(value))))
            push!(
                entries,
                _canonical_json(key) * ":" * _canonical_json(value[key]),
            )
        end
        return "{" * join(entries, ",") * "}"
    end
    throw(ArgumentError("canonical JSON contains unsupported value"))
end

_canonical_bytes(value) = Vector{UInt8}(codeunits(_canonical_json(value) * "\n"))

function _read_canonical_json(path, name)
    _require_regular_file(path, name)
    bytes = read(path)
    parsed = try
        JSON3.read(String(bytes), Dict{String,Any})
    catch error
        throw(ArgumentError("$name is malformed JSON: $(sprint(showerror, error))"))
    end
    normalized = _json_value(parsed, name)
    normalized isa Dict{String,Any} ||
        throw(ArgumentError("$name must be a JSON object"))
    return normalized
end

function _require_exact_keys(value, expected, name)
    value isa AbstractDict ||
        throw(ArgumentError("$name must be a JSON object"))
    Set(String.(keys(value))) == Set(expected) ||
        throw(ArgumentError("$name keys do not match the supported schema"))
    return nothing
end

function _sha256(value, name)
    value isa AbstractString && occursin(SHA256_PATTERN, value) ||
        throw(ArgumentError("$name must be a lowercase SHA256"))
    return String(value)
end

function _nonempty_string(value, name)
    value isa AbstractString && !isempty(value) ||
        throw(ArgumentError("$name must be a nonempty string"))
    return String(value)
end

_bytes_sha256(bytes) = bytes2hex(sha256(bytes))
_file_sha256(path) = open(path, "r") do io
    bytes2hex(sha256(io))
end

function _require_regular_file(path, name)
    ispath(path) || throw(ArgumentError("$name is missing"))
    islink(path) && throw(ArgumentError("$name must not be a symlink"))
    isfile(path) || throw(ArgumentError("$name must be a regular file"))
    return nothing
end

function _require_directory(path, name)
    ispath(path) || throw(ArgumentError("$name is missing"))
    islink(path) && throw(ArgumentError("$name must not be a symlink"))
    isdir(path) || throw(ArgumentError("$name must be a directory"))
    return nothing
end

function _ensure_directory(path, name; create)
    if ispath(path)
        _require_directory(path, name)
    elseif create
        mkpath(path)
        _require_directory(path, name)
        _fsync_directory(dirname(path))
    else
        throw(ArgumentError("$name is missing"))
    end
    return nothing
end

function _write_durable(path, bytes)
    open(path, "w") do io
        write(io, bytes)
        flush(io)
        _fsync(io, path)
    end
    return nothing
end

function _fsync_file(path)
    open(path, "r") do io
        _fsync(io, path)
    end
    return nothing
end

function _fsync(io, path)
    ccall(:fsync, Cint, (Cint,), fd(io)) == 0 ||
        error("fsync failed for $path")
end

function _fsync_directory(path)
    directory_fd = ccall(:open, Cint, (Cstring, Cint), path, 0)
    directory_fd >= 0 || error("cannot open directory for fsync: $path")
    try
        ccall(:fsync, Cint, (Cint,), directory_fd) == 0 ||
            error("fsync failed for directory: $path")
    finally
        ccall(:close, Cint, (Cint,), directory_fd)
    end
    return nothing
end

function _atomic_write_current(root, bytes)
    temporary, io = mktemp(root; cleanup = false)
    published = false
    try
        write(io, bytes)
        flush(io)
        _fsync(io, temporary)
        close(io)
        Base.Filesystem.rename(temporary, joinpath(root, "current.json"))
        _fsync_directory(root)
        published = true
    finally
        isopen(io) && close(io)
        !published && ispath(temporary) && rm(temporary; force = true)
    end
    return nothing
end

end
