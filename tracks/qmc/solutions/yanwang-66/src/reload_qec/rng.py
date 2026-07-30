"""Counter-addressed deterministic random streams."""

from __future__ import annotations

from enum import IntEnum


MASK64 = (1 << 64) - 1
UINT53_SCALE = 1.0 / (1 << 53)


class EventType(IntEnum):
    DATA_PAULI = 1
    MEASUREMENT_FLIP = 2
    LOSS = 3
    LOSS_COMPONENT = 4
    RELOAD_RESET = 5
    RELOAD_SUCCESS = 6


def splitmix64(value: int) -> int:
    """Return one fixed-width SplitMix64 permutation."""

    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def counter_u64(
    master_seed: int,
    shot_id: int,
    round_index: int,
    site_id: int,
    event_type: EventType,
    subindex: int = 0,
) -> int:
    """Map an event address to a uint64 without mutable RNG state."""

    values = (
        master_seed,
        shot_id,
        round_index,
        site_id,
        int(event_type),
        subindex,
    )
    state = 0xD1B54A32D192ED03
    for position, value in enumerate(values):
        if value < 0:
            raise ValueError("counter coordinates must be non-negative")
        state = splitmix64(state ^ splitmix64(value + position * 0x9E3779B9))
    return state


def uniform01(
    master_seed: int,
    shot_id: int,
    round_index: int,
    site_id: int,
    event_type: EventType,
    subindex: int = 0,
) -> float:
    value = counter_u64(
        master_seed,
        shot_id,
        round_index,
        site_id,
        event_type,
        subindex,
    )
    return (value >> 11) * UINT53_SCALE


def bernoulli(
    probability: float,
    master_seed: int,
    shot_id: int,
    round_index: int,
    site_id: int,
    event_type: EventType,
    subindex: int = 0,
) -> bool:
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability outside [0,1]: {probability}")
    if probability == 0.0:
        return False
    if probability == 1.0:
        return True
    return uniform01(
        master_seed,
        shot_id,
        round_index,
        site_id,
        event_type,
        subindex,
    ) < probability


def data_pauli_kind(
    master_seed: int, shot_id: int, round_index: int, site_id: int
) -> int:
    """Return 0, 1, or 2 for X, Y, or Z after occurrence is sampled."""

    value = counter_u64(
        master_seed,
        shot_id,
        round_index,
        site_id,
        EventType.DATA_PAULI,
        subindex=1,
    )
    return value % 3
