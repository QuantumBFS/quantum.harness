"""Spawned-process transport for the public closed-loop ask/tell protocol.

Only bounded UTF-8 JSON bytes cross the duplex pipe.  In particular, this
module never calls ``Connection.send`` or ``Connection.recv`` and therefore
never unpickles controller-provided payloads.  The live executor, program
factory, backend, seed tree, and validation oracle remain in the parent.

This is a process-memory and live-capability boundary for honest or buggy
controllers.  It is not a sandbox for malicious code running as the same
Windows user: such code may still read files, access the network, inspect
other processes, consume resources, or create descendant processes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import json
import math
import multiprocessing
from multiprocessing.connection import Connection, wait
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid
from typing import Any

from .closed_loop import (
    CandidatePoint,
    CandidateRequest,
    ClosedLoopProblemDescriptor,
    ControllerRecommendation,
    KLLUCBController,
    PhysicalParameterSpec,
    PublicBatchObservation,
    PublicBudgetView,
    SuccessiveHalvingController,
    UniformRepeatedController,
)


WIRE_PROTOCOL = "cs-closed-loop"
WIRE_VERSION = 1
DEFAULT_MAX_FRAME_BYTES = 65_536
_SESSION_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class StrictJSONError(ValueError):
    """A frame is not strict RFC-8259-compatible JSON."""


class ControllerProcessError(RuntimeError):
    """Sanitized parent-side controller transport failure."""

    def __init__(
        self,
        public_code: str,
        message: str,
        *,
        exitcode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.public_code = public_code
        self.exitcode = exitcode


@dataclass(frozen=True)
class _NonFiniteJSON:
    spelling: str


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_nonfinite(spelling: str) -> _NonFiniteJSON:
    return _NonFiniteJSON(spelling)


def _exact_keys(
    payload: object,
    expected: set[str],
    *,
    label: str,
) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != expected:
        raise StrictJSONError(f"{label} has an invalid schema")
    return payload


def encode_wire_frame(
    *,
    session_id: str,
    seq: int,
    message_type: str,
    payload: dict[str, object],
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> bytes:
    """Encode one exact-schema frame and enforce the byte limit."""

    frame = {
        "protocol": WIRE_PROTOCOL,
        "version": WIRE_VERSION,
        "session_id": session_id,
        "seq": seq,
        "type": message_type,
        "payload": payload,
    }
    try:
        encoded = json.dumps(
            frame,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StrictJSONError("frame cannot be encoded as strict JSON") from exc
    if len(encoded) > max_frame_bytes:
        raise StrictJSONError("frame exceeds the configured byte limit")
    return encoded


def decode_wire_frame(
    data: bytes,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> dict[str, object]:
    """Decode strict JSON while retaining non-finite candidate sentinels.

    Python's default decoder accepts duplicate keys and JavaScript-style
    ``NaN``/``Infinity``.  We retain the latter only as typed sentinels so the
    parent can first identify a valid candidate envelope, charge its token,
    and then reject the parameter.  They are never re-encoded.
    """

    if not isinstance(data, bytes) or len(data) > max_frame_bytes:
        raise StrictJSONError("frame exceeds the configured byte limit")
    try:
        text = data.decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_parse_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StrictJSONError("frame is not valid strict UTF-8 JSON") from exc
    envelope = _exact_keys(
        parsed,
        {"protocol", "version", "session_id", "seq", "type", "payload"},
        label="wire envelope",
    )
    if envelope["protocol"] != WIRE_PROTOCOL:
        raise StrictJSONError("wire protocol does not match")
    if (
        type(envelope["version"]) is not int
        or envelope["version"] != WIRE_VERSION
    ):
        raise StrictJSONError("wire version does not match")
    session_id = envelope["session_id"]
    if (
        not isinstance(session_id, str)
        or _SESSION_PATTERN.fullmatch(session_id) is None
    ):
        raise StrictJSONError("wire session_id is invalid")
    if type(envelope["seq"]) is not int or envelope["seq"] < 0:
        raise StrictJSONError("wire sequence is invalid")
    if not isinstance(envelope["type"], str) or not envelope["type"]:
        raise StrictJSONError("wire message type is invalid")
    if not isinstance(envelope["payload"], dict):
        raise StrictJSONError("wire payload must be an object")
    return envelope


def _finite_float(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value, (int, float, Decimal)
    ):
        raise StrictJSONError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise StrictJSONError(f"{label} must be finite")
    return result


def _strict_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise StrictJSONError(f"{label} must be an integer >= {minimum}")
    return value


def _candidate_value(value: object) -> object:
    """Convert wire numbers while preserving invalid values for paid rejection."""

    if isinstance(value, _NonFiniteJSON):
        if value.spelling == "NaN":
            return float("nan")
        if value.spelling == "-Infinity":
            return float("-inf")
        return float("inf")
    if isinstance(value, Decimal):
        converted = float(value)
        return converted
    return value


def _problem_to_payload(
    problem: ClosedLoopProblemDescriptor,
) -> dict[str, object]:
    return {
        "name": problem.name,
        "parameters": [asdict(parameter) for parameter in problem.parameters],
        "expected_outcome": problem.expected_outcome,
        "batch_shots": problem.batch_shots,
        "max_tokens": problem.max_tokens,
        "reserved_sequence_time_per_shot_us": (
            problem.reserved_sequence_time_per_shot_us
        ),
        "candidates": [asdict(candidate) for candidate in problem.candidates],
        "candidate_policy": problem.candidate_policy,
        "recommendation_policy": problem.recommendation_policy,
    }


def _problem_from_payload(payload: object) -> ClosedLoopProblemDescriptor:
    data = _exact_keys(
        payload,
        {
            "name",
            "parameters",
            "expected_outcome",
            "batch_shots",
            "max_tokens",
            "reserved_sequence_time_per_shot_us",
            "candidates",
            "candidate_policy",
            "recommendation_policy",
        },
        label="problem descriptor",
    )
    if (
        not isinstance(data["name"], str)
        or not isinstance(data["expected_outcome"], str)
        or not isinstance(data["parameters"], list)
        or not isinstance(data["candidates"], list)
        or not isinstance(data["candidate_policy"], str)
        or not isinstance(data["recommendation_policy"], str)
    ):
        raise StrictJSONError("problem descriptor field types are invalid")
    parameters: list[PhysicalParameterSpec] = []
    for item in data["parameters"]:
        spec = _exact_keys(
            item,
            {
                "name",
                "unit",
                "lower",
                "upper",
                "initial",
                "period",
                "quantum",
            },
            label="physical parameter",
        )
        if not isinstance(spec["name"], str) or not isinstance(
            spec["unit"], str
        ):
            raise StrictJSONError("physical parameter text fields are invalid")
        period = (
            None
            if spec["period"] is None
            else _finite_float(spec["period"], label="parameter period")
        )
        quantum = (
            None
            if spec["quantum"] is None
            else _finite_float(spec["quantum"], label="parameter quantum")
        )
        parameters.append(
            PhysicalParameterSpec(
                name=spec["name"],
                unit=spec["unit"],
                lower=_finite_float(spec["lower"], label="parameter lower"),
                upper=_finite_float(spec["upper"], label="parameter upper"),
                initial=_finite_float(
                    spec["initial"], label="parameter initial"
                ),
                period=period,
                quantum=quantum,
            )
        )
    candidates: list[CandidatePoint] = []
    for item in data["candidates"]:
        point = _exact_keys(
            item, {"candidate_id", "values"}, label="candidate point"
        )
        if not isinstance(point["candidate_id"], str) or not isinstance(
            point["values"], list
        ):
            raise StrictJSONError("candidate point field types are invalid")
        candidates.append(
            CandidatePoint(
                point["candidate_id"],
                tuple(
                    _finite_float(value, label="catalog candidate value")
                    for value in point["values"]
                ),
            )
        )
    return ClosedLoopProblemDescriptor(
        name=data["name"],
        parameters=tuple(parameters),
        expected_outcome=data["expected_outcome"],
        batch_shots=_strict_int(
            data["batch_shots"], label="batch_shots", minimum=1
        ),
        max_tokens=_strict_int(
            data["max_tokens"], label="max_tokens", minimum=1
        ),
        reserved_sequence_time_per_shot_us=_finite_float(
            data["reserved_sequence_time_per_shot_us"],
            label="reserved sequence time",
        ),
        candidates=tuple(candidates),
        candidate_policy=data["candidate_policy"],
        recommendation_policy=data["recommendation_policy"],
    )


def _budget_to_payload(budget: PublicBudgetView) -> dict[str, object]:
    return asdict(budget)


def _budget_from_payload(payload: object) -> PublicBudgetView:
    data = _exact_keys(
        payload,
        {
            "tokens_remaining",
            "reserved_shots_remaining",
            "reserved_scheduler_time_remaining_us",
        },
        label="budget",
    )
    return PublicBudgetView(
        tokens_remaining=_strict_int(
            data["tokens_remaining"], label="tokens_remaining"
        ),
        reserved_shots_remaining=_strict_int(
            data["reserved_shots_remaining"],
            label="reserved_shots_remaining",
        ),
        reserved_scheduler_time_remaining_us=_finite_float(
            data["reserved_scheduler_time_remaining_us"],
            label="reserved_scheduler_time_remaining_us",
        ),
    )


def _observation_to_payload(
    observation: PublicBatchObservation,
) -> dict[str, object]:
    payload = asdict(observation)
    payload["requested_values"] = list(observation.requested_values)
    payload["canonical_values"] = list(observation.canonical_values)
    payload["counts"] = [list(item) for item in observation.counts]
    return payload


def _observation_from_payload(payload: object) -> PublicBatchObservation:
    keys = set(PublicBatchObservation.__dataclass_fields__)
    data = _exact_keys(payload, keys, label="public observation")
    if (
        not isinstance(data["candidate_id"], str)
        or not isinstance(data["requested_values"], list)
        or not isinstance(data["canonical_values"], list)
        or not isinstance(data["canonical_parameter_sha256"], str)
        or not isinstance(data["program_sha256"], str)
        or not isinstance(data["status"], str)
        or not isinstance(data["failure_reason"], str)
        or not isinstance(data["execution_id"], str)
        or not isinstance(data["expected_outcome"], str)
        or not isinstance(data["counts"], list)
        or not isinstance(data["request_frame_sha256"], str)
    ):
        raise StrictJSONError("public observation field types are invalid")
    counts: list[tuple[str, int]] = []
    for item in data["counts"]:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
        ):
            raise StrictJSONError("public counts are invalid")
        counts.append(
            (item[0], _strict_int(item[1], label="public count"))
        )
    retained = data["retained_shots"]
    if retained is not None:
        retained = _strict_int(retained, label="retained_shots")
    return PublicBatchObservation(
        token_index=_strict_int(
            data["token_index"], label="token_index", minimum=1
        ),
        candidate_id=data["candidate_id"],
        requested_values=tuple(
            _finite_float(value, label="requested value")
            for value in data["requested_values"]
        ),
        canonical_values=tuple(
            _finite_float(value, label="canonical value")
            for value in data["canonical_values"]
        ),
        canonical_parameter_sha256=data["canonical_parameter_sha256"],
        program_sha256=data["program_sha256"],
        status=data["status"],
        failure_reason=data["failure_reason"],
        execution_id=data["execution_id"],
        expected_outcome=data["expected_outcome"],
        successes=_strict_int(data["successes"], label="successes"),
        attempted_shots=_strict_int(
            data["attempted_shots"], label="attempted_shots"
        ),
        valid_shots=_strict_int(
            data["valid_shots"], label="valid_shots"
        ),
        retained_shots=retained,
        counts=tuple(counts),
        active_sequence_time_us=_finite_float(
            data["active_sequence_time_us"],
            label="active_sequence_time_us",
        ),
        reserved_scheduler_time_us=_finite_float(
            data["reserved_scheduler_time_us"],
            label="reserved_scheduler_time_us",
        ),
        request_frame_sha256=data["request_frame_sha256"],
    )


@dataclass(frozen=True)
class ProcessControllerSpec:
    """A JSON-safe identifier and options for a child-side allowlisted controller."""

    controller_id: str
    options: tuple[tuple[str, object], ...] = ()

    @classmethod
    def uniform(cls, *, repeats: int) -> "ProcessControllerSpec":
        return cls("uniform", (("repeats", repeats),))

    @classmethod
    def successive_halving(cls) -> "ProcessControllerSpec":
        return cls("successive_halving")

    @classmethod
    def kl_lucb(
        cls, *, delta: float, epsilon: float
    ) -> "ProcessControllerSpec":
        return cls(
            "kl_lucb", (("delta", delta), ("epsilon", epsilon))
        )


def _spec_to_bytes(
    spec: ProcessControllerSpec,
    *,
    max_frame_bytes: int,
) -> bytes:
    if not isinstance(spec.controller_id, str) or not spec.controller_id:
        raise ValueError("controller_id must be non-empty")
    options = dict(spec.options)
    if len(options) != len(spec.options):
        raise ValueError("controller options must have unique keys")
    return encode_wire_frame(
        session_id="0" * 32,
        seq=0,
        message_type="controller_spec",
        payload={"controller_id": spec.controller_id, "options": options},
        max_frame_bytes=max_frame_bytes,
    )


def _spec_from_bytes(
    data: bytes,
    *,
    max_frame_bytes: int,
) -> tuple[str, dict[str, object]]:
    frame = decode_wire_frame(data, max_frame_bytes=max_frame_bytes)
    if frame["type"] != "controller_spec":
        raise StrictJSONError("spawn controller spec has the wrong type")
    payload = _exact_keys(
        frame["payload"],
        {"controller_id", "options"},
        label="controller spec",
    )
    if not isinstance(payload["controller_id"], str) or not isinstance(
        payload["options"], dict
    ):
        raise StrictJSONError("controller spec field types are invalid")
    return payload["controller_id"], payload["options"]


def _build_controller(
    controller_id: str,
    options: dict[str, object],
    problem: ClosedLoopProblemDescriptor,
    *,
    allow_test_controller: bool,
):
    if controller_id == "uniform":
        _exact_keys(options, {"repeats"}, label="uniform options")
        return UniformRepeatedController(
            problem.candidates,
            repeats=_strict_int(options["repeats"], label="repeats", minimum=1),
        )
    if controller_id == "successive_halving":
        _exact_keys(options, set(), label="successive-halving options")
        return SuccessiveHalvingController(problem.candidates)
    if controller_id == "kl_lucb":
        _exact_keys(options, {"delta", "epsilon"}, label="KL-LUCB options")
        return KLLUCBController(
            problem.candidates,
            delta=_finite_float(options["delta"], label="delta"),
            epsilon=_finite_float(options["epsilon"], label="epsilon"),
        )
    if controller_id == "__test_fault__" and allow_test_controller:
        _exact_keys(
            options, {"stage", "action"}, label="test fault options"
        )
        if options["stage"] not in {
            "startup",
            "ask",
            "tell",
            "recommend",
        } or options["action"] not in {
            "hang",
            "crash",
            "invalid_utf8",
            "oversized",
            "wrong_seq",
            "unknown_candidate_field",
            "nan_candidate",
            "infinity_candidate",
            "negative_infinity_candidate",
            "huge_candidate",
            "bool_candidate",
        }:
            raise StrictJSONError("test fault option is invalid")
        return UniformRepeatedController(
            problem.candidates[:1], repeats=1
        )
    raise StrictJSONError("controller_id is not in the allowlist")


def _fault_response_type(stage: str) -> str:
    return {
        "startup": "ready",
        "ask": "candidate",
        "tell": "ack",
        "recommend": "recommendation",
    }[stage]


def _inject_worker_fault(
    *,
    stage: str,
    controller_id: str,
    options: dict[str, object],
    connection: Connection,
    session_id: str,
    seq: int,
    max_frame_bytes: int,
    candidate_id: str = "fault-candidate",
) -> str:
    """Return ``none``, ``sent``, or never return for a frozen test fault."""

    if (
        controller_id != "__test_fault__"
        or options.get("stage") != stage
    ):
        return "none"
    action = options["action"]
    if action == "hang":
        while True:
            time.sleep(60.0)
    if action == "crash":
        os._exit(17)
    if action == "invalid_utf8":
        connection.send_bytes(b"\xff")
        return "sent"
    if action == "oversized":
        connection.send_bytes(b"x" * (max_frame_bytes + 1))
        return "sent"
    response_type = _fault_response_type(stage)
    if action == "wrong_seq":
        _worker_send(
            connection,
            session_id=session_id,
            seq=seq + 1,
            message_type=response_type,
            payload={},
            max_frame_bytes=max_frame_bytes,
        )
        return "sent"
    if action == "unknown_candidate_field" and stage == "ask":
        _worker_send(
            connection,
            session_id=session_id,
            seq=seq,
            message_type="candidate",
            payload={
                "candidate_id": candidate_id,
                "requested_values": [0.5],
                "program": "forbidden",
            },
            max_frame_bytes=max_frame_bytes,
        )
        return "sent"
    if action in {
        "nan_candidate",
        "infinity_candidate",
        "negative_infinity_candidate",
        "huge_candidate",
        "bool_candidate",
    } and stage == "ask":
        spelling = {
            "nan_candidate": "NaN",
            "infinity_candidate": "Infinity",
            "negative_infinity_candidate": "-Infinity",
            "huge_candidate": "1e9999",
            "bool_candidate": "true",
        }[action]
        raw = (
            '{"payload":{"candidate_id":'
            + json.dumps(candidate_id)
            + ',"requested_values":['
            + spelling
            + ']},"protocol":"'
            + WIRE_PROTOCOL
            + '","seq":'
            + str(seq)
            + ',"session_id":"'
            + session_id
            + '","type":"candidate","version":1}'
        ).encode("utf-8")
        connection.send_bytes(raw)
        return "sent"
    raise StrictJSONError("test fault is not valid for this stage")


def _send_bytes_with_deadline(
    connection: Connection,
    data: bytes,
    timeout_s: float,
) -> None:
    completed = threading.Event()
    error: list[BaseException] = []

    def writer() -> None:
        try:
            connection.send_bytes(data)
        except BaseException as exc:  # captured and re-raised in owner thread
            error.append(exc)
        finally:
            completed.set()

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    if not completed.wait(timeout_s):
        raise TimeoutError("controller pipe write timed out")
    if error:
        raise OSError("controller pipe write failed") from error[0]


def _worker_recv(
    connection: Connection,
    *,
    max_frame_bytes: int,
) -> dict[str, object]:
    return decode_wire_frame(
        connection.recv_bytes(maxlength=max_frame_bytes),
        max_frame_bytes=max_frame_bytes,
    )


def _worker_send(
    connection: Connection,
    *,
    session_id: str,
    seq: int,
    message_type: str,
    payload: dict[str, object],
    max_frame_bytes: int,
) -> None:
    connection.send_bytes(
        encode_wire_frame(
            session_id=session_id,
            seq=seq,
            message_type=message_type,
            payload=payload,
            max_frame_bytes=max_frame_bytes,
        )
    )


def _scrub_child_environment() -> None:
    sensitive_fragments = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "CREDENTIAL",
        "OPENAI",
        "GITHUB",
        "AWS_",
        "AZURE_",
    )
    for key in tuple(os.environ):
        upper = key.upper()
        if any(fragment in upper for fragment in sensitive_fragments):
            os.environ.pop(key, None)


def _controller_worker(
    connection: Connection,
    controller_spec_bytes: bytes,
    max_frame_bytes: int,
    allow_test_controller: bool,
) -> None:
    """Top-level spawn target.  All controller decisions stay in this process."""

    _scrub_child_environment()
    original_cwd = os.getcwd()
    try:
        temp_dir = tempfile.mkdtemp(prefix="cs-controller-")
        try:
            os.chdir(temp_dir)
            controller_id, options = _spec_from_bytes(
                controller_spec_bytes,
                max_frame_bytes=max_frame_bytes,
            )
            init = _worker_recv(
                connection, max_frame_bytes=max_frame_bytes
            )
            if init["type"] != "init" or init["seq"] != 0:
                raise StrictJSONError("worker expected init at sequence zero")
            session_id = init["session_id"]
            init_payload = _exact_keys(
                init["payload"], {"problem"}, label="init payload"
            )
            problem = _problem_from_payload(init_payload["problem"])
            controller = _build_controller(
                controller_id,
                options,
                problem,
                allow_test_controller=allow_test_controller,
            )
            if (
                _inject_worker_fault(
                    stage="startup",
                    controller_id=controller_id,
                    options=options,
                    connection=connection,
                    session_id=session_id,
                    seq=0,
                    max_frame_bytes=max_frame_bytes,
                )
                == "sent"
            ):
                return
            _worker_send(
                connection,
                session_id=session_id,
                seq=0,
                message_type="ready",
                payload={"pid": os.getpid()},
                max_frame_bytes=max_frame_bytes,
            )
            expected_seq = 1
            pending = False
            stopped = False
            while True:
                frame = _worker_recv(
                    connection, max_frame_bytes=max_frame_bytes
                )
                if (
                    frame["session_id"] != session_id
                    or frame["seq"] != expected_seq
                ):
                    raise StrictJSONError("worker session or sequence mismatch")
                message_type = frame["type"]
                if message_type == "ask" and not pending and not stopped:
                    payload = _exact_keys(
                        frame["payload"], {"budget"}, label="ask payload"
                    )
                    request = controller.ask(
                        problem, _budget_from_payload(payload["budget"])
                    )
                    if request is None:
                        stopped = True
                        response_type = "stop"
                        response_payload: dict[str, object] = {}
                    else:
                        pending = True
                        if (
                            _inject_worker_fault(
                                stage="ask",
                                controller_id=controller_id,
                                options=options,
                                connection=connection,
                                session_id=session_id,
                                seq=expected_seq,
                                max_frame_bytes=max_frame_bytes,
                                candidate_id=request.candidate_id,
                            )
                            == "sent"
                        ):
                            if str(options.get("action")).endswith(
                                "_candidate"
                            ):
                                expected_seq += 1
                                continue
                            return
                        response_type = "candidate"
                        response_payload = {
                            "candidate_id": request.candidate_id,
                            "requested_values": list(
                                request.requested_values
                            ),
                        }
                elif message_type == "tell" and pending and not stopped:
                    if (
                        _inject_worker_fault(
                            stage="tell",
                            controller_id=controller_id,
                            options=options,
                            connection=connection,
                            session_id=session_id,
                            seq=expected_seq,
                            max_frame_bytes=max_frame_bytes,
                        )
                        == "sent"
                    ):
                        return
                    payload = _exact_keys(
                        frame["payload"],
                        {"observation"},
                        label="tell payload",
                    )
                    controller.tell(
                        _observation_from_payload(payload["observation"])
                    )
                    pending = False
                    response_type = "ack"
                    response_payload = {}
                elif message_type == "recommend" and not pending:
                    if (
                        _inject_worker_fault(
                            stage="recommend",
                            controller_id=controller_id,
                            options=options,
                            connection=connection,
                            session_id=session_id,
                            seq=expected_seq,
                            max_frame_bytes=max_frame_bytes,
                        )
                        == "sent"
                    ):
                        return
                    _exact_keys(
                        frame["payload"], set(), label="recommend payload"
                    )
                    recommendation = controller.recommend()
                    response_type = "recommendation"
                    response_payload = {
                        "candidate_id": recommendation.candidate_id,
                        "canonical_values": list(
                            recommendation.canonical_values
                        ),
                        "decision_status": recommendation.decision_status,
                        "detail": recommendation.detail,
                    }
                elif message_type == "shutdown" and not pending:
                    _exact_keys(
                        frame["payload"], set(), label="shutdown payload"
                    )
                    _worker_send(
                        connection,
                        session_id=session_id,
                        seq=expected_seq,
                        message_type="bye",
                        payload={},
                        max_frame_bytes=max_frame_bytes,
                    )
                    return
                else:
                    raise StrictJSONError("worker state transition is invalid")
                _worker_send(
                    connection,
                    session_id=session_id,
                    seq=expected_seq,
                    message_type=response_type,
                    payload=response_payload,
                    max_frame_bytes=max_frame_bytes,
                )
                expected_seq += 1
        finally:
            os.chdir(original_cwd)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
    finally:
        connection.close()


class ProcessControllerProxy:
    """Parent-side AskTellController proxy backed by one spawned process."""

    def __init__(
        self,
        spec: ProcessControllerSpec,
        *,
        startup_timeout_s: float = 30.0,
        rpc_timeout_s: float = 300.0,
        shutdown_timeout_s: float = 5.0,
        join_timeout_s: float = 5.0,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        enable_test_controller: bool = False,
    ) -> None:
        timeouts = (
            startup_timeout_s,
            rpc_timeout_s,
            shutdown_timeout_s,
            join_timeout_s,
        )
        if (
            not all(math.isfinite(value) and value > 0.0 for value in timeouts)
            or type(max_frame_bytes) is not int
            or max_frame_bytes <= 0
            or max_frame_bytes > DEFAULT_MAX_FRAME_BYTES
        ):
            raise ValueError("process controller transport limits are invalid")
        self._spec = spec
        self._startup_timeout_s = float(startup_timeout_s)
        self._rpc_timeout_s = float(rpc_timeout_s)
        self._shutdown_timeout_s = float(shutdown_timeout_s)
        self._join_timeout_s = float(join_timeout_s)
        self._max_frame_bytes = max_frame_bytes
        self._enable_test_controller = bool(enable_test_controller)
        self._session_id = uuid.uuid4().hex
        self._seq = 0
        self._connection: Connection | None = None
        self._process: multiprocessing.Process | None = None
        self._state = "new"
        self._controller_pid: int | None = None
        self._exitcode: int | None = None

    @property
    def controller_pid(self) -> int | None:
        return self._controller_pid

    @property
    def exitcode(self) -> int | None:
        process = self._process
        if process is not None and process.exitcode is not None:
            return process.exitcode
        return self._exitcode

    @property
    def session_id(self) -> str:
        return self._session_id

    def _start(self, problem: ClosedLoopProblemDescriptor) -> None:
        if self._state != "new":
            return
        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=True)
        spec_bytes = _spec_to_bytes(
            self._spec, max_frame_bytes=self._max_frame_bytes
        )
        process = context.Process(
            target=_controller_worker,
            args=(
                child_connection,
                spec_bytes,
                self._max_frame_bytes,
                self._enable_test_controller,
            ),
            name=f"cs-controller-{self._session_id[:8]}",
            daemon=False,
        )
        self._connection = parent_connection
        self._process = process
        try:
            process.start()
        finally:
            child_connection.close()
        self._state = "starting"
        response = self._rpc(
            "init",
            {"problem": _problem_to_payload(problem)},
            expected_types={"ready"},
            timeout_s=self._startup_timeout_s,
        )
        try:
            ready = _exact_keys(
                response["payload"], {"pid"}, label="ready payload"
            )
            self._controller_pid = _strict_int(
                ready["pid"], label="controller pid", minimum=1
            )
        except StrictJSONError as exc:
            self._protocol_failure(exc)
        self._state = "idle"

    def _abort(self) -> None:
        process = self._process
        connection = self._connection
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(self._join_timeout_s)
            if process.is_alive():
                process.kill()
                process.join(self._join_timeout_s)
            self._exitcode = process.exitcode
            try:
                process.close()
            except ValueError:
                pass
        self._connection = None
        self._process = None
        self._state = "failed"

    def _protocol_failure(self, exc: BaseException) -> None:
        exitcode = self.exitcode
        self._abort()
        raise ControllerProcessError(
            "controller_protocol_failed",
            "controller response payload is invalid",
            exitcode=exitcode if exitcode is not None else self._exitcode,
        ) from exc

    def _rpc(
        self,
        message_type: str,
        payload: dict[str, object],
        *,
        expected_types: set[str],
        timeout_s: float,
    ) -> dict[str, object]:
        connection = self._connection
        process = self._process
        if connection is None or process is None:
            raise ControllerProcessError(
                "controller_transport_failed",
                "controller process is not available",
                exitcode=self.exitcode,
            )
        seq = self._seq
        try:
            encoded = encode_wire_frame(
                session_id=self._session_id,
                seq=seq,
                message_type=message_type,
                payload=payload,
                max_frame_bytes=self._max_frame_bytes,
            )
            _send_bytes_with_deadline(connection, encoded, timeout_s)
            ready = wait([connection, process.sentinel], timeout_s)
            if connection not in ready:
                if process.sentinel in ready:
                    process.join(0)
                    raise ControllerProcessError(
                        "controller_crashed",
                        "controller process exited before responding",
                        exitcode=process.exitcode,
                    )
                raise ControllerProcessError(
                    "controller_timeout",
                    "controller response timed out",
                    exitcode=process.exitcode,
                )
            raw = connection.recv_bytes(maxlength=self._max_frame_bytes)
            response = decode_wire_frame(
                raw, max_frame_bytes=self._max_frame_bytes
            )
            if (
                response["session_id"] != self._session_id
                or response["seq"] != seq
                or response["type"] not in expected_types
            ):
                raise StrictJSONError(
                    "controller response session, sequence, or type is invalid"
                )
            self._seq += 1
            return response
        except ControllerProcessError:
            self._abort()
            raise
        except TimeoutError as exc:
            exitcode = process.exitcode
            self._abort()
            raise ControllerProcessError(
                "controller_timeout",
                "controller pipe write timed out",
                exitcode=exitcode,
            ) from exc
        except (EOFError, OSError, StrictJSONError) as exc:
            exitcode = process.exitcode
            self._abort()
            code = (
                "controller_crashed"
                if exitcode not in (None, 0)
                else "controller_protocol_failed"
            )
            raise ControllerProcessError(
                code,
                "controller transport or protocol failed",
                exitcode=exitcode,
            ) from exc

    def ask(
        self,
        problem: ClosedLoopProblemDescriptor,
        budget: PublicBudgetView,
    ) -> CandidateRequest | None:
        if self._state == "new":
            self._start(problem)
        if self._state != "idle":
            raise ControllerProcessError(
                "controller_protocol_failed",
                "ask is invalid in the current proxy state",
                exitcode=self.exitcode,
            )
        response = self._rpc(
            "ask",
            {"budget": _budget_to_payload(budget)},
            expected_types={"candidate", "stop"},
            timeout_s=self._rpc_timeout_s,
        )
        if response["type"] == "stop":
            try:
                _exact_keys(
                    response["payload"], set(), label="stop payload"
                )
            except StrictJSONError as exc:
                self._protocol_failure(exc)
            self._state = "stopped"
            return None
        try:
            payload = _exact_keys(
                response["payload"],
                {"candidate_id", "requested_values"},
                label="candidate payload",
            )
            if not isinstance(payload["requested_values"], list):
                raise StrictJSONError(
                    "candidate requested_values is not an array"
                )
        except StrictJSONError as exc:
            self._protocol_failure(exc)
        request = CandidateRequest(
            payload["candidate_id"],
            tuple(_candidate_value(value) for value in payload["requested_values"]),
        )
        self._state = "pending"
        return request

    def tell(self, observation: PublicBatchObservation) -> None:
        if self._state != "pending":
            raise ControllerProcessError(
                "controller_protocol_failed",
                "tell is invalid in the current proxy state",
                exitcode=self.exitcode,
            )
        response = self._rpc(
            "tell",
            {"observation": _observation_to_payload(observation)},
            expected_types={"ack"},
            timeout_s=self._rpc_timeout_s,
        )
        try:
            _exact_keys(response["payload"], set(), label="ack payload")
        except StrictJSONError as exc:
            self._protocol_failure(exc)
        self._state = "idle"

    def recommend(self) -> ControllerRecommendation:
        if self._state not in {"idle", "stopped"}:
            raise ControllerProcessError(
                "controller_protocol_failed",
                "recommend is invalid in the current proxy state",
                exitcode=self.exitcode,
            )
        response = self._rpc(
            "recommend",
            {},
            expected_types={"recommendation"},
            timeout_s=self._rpc_timeout_s,
        )
        try:
            payload = _exact_keys(
                response["payload"],
                {
                    "candidate_id",
                    "canonical_values",
                    "decision_status",
                    "detail",
                },
                label="recommendation payload",
            )
            if not isinstance(payload["canonical_values"], list):
                raise StrictJSONError(
                    "recommendation values are not an array"
                )
        except StrictJSONError as exc:
            self._protocol_failure(exc)
        recommendation = ControllerRecommendation(
            candidate_id=payload["candidate_id"],
            canonical_values=tuple(
                _candidate_value(value)
                for value in payload["canonical_values"]
            ),
            decision_status=payload["decision_status"],
            detail=payload["detail"],
        )
        self._state = "recommended"
        self.close()
        return recommendation

    def close(self) -> None:
        if self._state in {"closed", "failed", "new"}:
            self._state = "closed" if self._state == "new" else self._state
            return
        try:
            response = self._rpc(
                "shutdown",
                {},
                expected_types={"bye"},
                timeout_s=self._shutdown_timeout_s,
            )
            try:
                _exact_keys(
                    response["payload"], set(), label="bye payload"
                )
            except StrictJSONError as exc:
                self._protocol_failure(exc)
            process = self._process
            if process is not None:
                process.join(self._join_timeout_s)
                if process.is_alive():
                    raise ControllerProcessError(
                        "controller_timeout",
                        "controller did not exit after shutdown",
                        exitcode=process.exitcode,
                    )
                self._exitcode = process.exitcode
                process.close()
            if self._connection is not None:
                self._connection.close()
            self._connection = None
            self._process = None
            self._state = "closed"
        except Exception:
            self._abort()
            raise

    def __enter__(self) -> "ProcessControllerProxy":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        if self._state not in {"closed", "failed"}:
            try:
                self.close()
            except ControllerProcessError:
                pass


def process_transport_manifest() -> dict[str, object]:
    """Public, serializable defaults for immutable benchmark manifests."""

    return {
        "protocol": WIRE_PROTOCOL,
        "version": WIRE_VERSION,
        "start_method": "spawn",
        "transport": "multiprocessing.Pipe.send_bytes/recv_bytes",
        "max_frame_bytes": DEFAULT_MAX_FRAME_BYTES,
        "default_timeouts_s": {
            "startup": 30.0,
            "rpc": 300.0,
            "shutdown": 5.0,
            "join": 5.0,
        },
        "security_claim": (
            "process-memory and live-capability separation; "
            "not a same-user malicious-code sandbox"
        ),
        "worker_module": str(Path(__file__).name),
    }
