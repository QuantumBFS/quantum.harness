"""METTS status codes (B 角色, §7.1 of the task spec).

Every per-sample trace carries one of these as ``status_code``. The driver
never silently continues past a bad sample: a non-``OK`` sample is recorded in
full (with its intermediate state) and excluded from the production statistics.
"""
from __future__ import annotations

OK = "OK"
INVALID_CONFIG = "INVALID_CONFIG"
INIT_STATE_ERROR = "INIT_STATE_ERROR"
EVOLUTION_NAN = "EVOLUTION_NAN"
NORM_ERROR = "NORM_ERROR"
ENERGY_ERROR = "ENERGY_ERROR"
PROBABILITY_ERROR = "PROBABILITY_ERROR"
COLLAPSE_ERROR = "COLLAPSE_ERROR"
TRUNCATION_EXCEEDED = "TRUNCATION_EXCEEDED"
MEMORY_LIMIT = "MEMORY_LIMIT"
TIMEOUT = "TIMEOUT"
CHECKPOINT_ERROR = "CHECKPOINT_ERROR"
UNKNOWN_ERROR = "UNKNOWN_ERROR"

# Samples with any of these codes are excluded from the thermodynamic average.
FAILURE_CODES = frozenset(
    {
        INVALID_CONFIG, INIT_STATE_ERROR, EVOLUTION_NAN, NORM_ERROR,
        ENERGY_ERROR, PROBABILITY_ERROR, COLLAPSE_ERROR, TRUNCATION_EXCEEDED,
        MEMORY_LIMIT, TIMEOUT, CHECKPOINT_ERROR, UNKNOWN_ERROR,
    }
)


def is_failure(code: str) -> bool:
    return code in FAILURE_CODES
