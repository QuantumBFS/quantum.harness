"""Immutable sampled controls and composable command-to-field transfers.

The sample convention is zero-order hold: each sample describes one interval
of length ``dt_us``.  Analytic waveforms are sampled at interval midpoints.
Hardware transforms are causal and may append samples for delay or ringdown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Protocol, Tuple

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class SampledWaveform:
    """Amplitude, phase, and detuning samples for one named control channel."""

    dt_us: float
    amplitude_rad_per_us: Tuple[float, ...]
    phase_rad: Tuple[float, ...]
    detuning_rad_per_us: Tuple[float, ...]

    def __post_init__(self) -> None:
        if self.dt_us <= 0 or not math.isfinite(self.dt_us):
            raise ValueError("dt_us must be finite and positive")
        length = len(self.amplitude_rad_per_us)
        if length == 0:
            raise ValueError("a sampled waveform requires at least one sample")
        if len(self.phase_rad) != length or len(self.detuning_rad_per_us) != length:
            raise ValueError("amplitude, phase, and detuning lengths must match")
        arrays = (
            self.amplitude_rad_per_us,
            self.phase_rad,
            self.detuning_rad_per_us,
        )
        if not all(math.isfinite(value) for array in arrays for value in array):
            raise ValueError("all waveform samples must be finite")
        if any(value < 0 for value in self.amplitude_rad_per_us):
            raise ValueError("waveform amplitudes must be non-negative")

    @classmethod
    def from_amplitude(
        cls,
        *,
        dt_us: float,
        amplitude_rad_per_us: Tuple[float, ...],
        phase_rad: float = 0.0,
        detuning_rad_per_us: float = 0.0,
    ) -> "SampledWaveform":
        """Construct a waveform with constant phase and detuning."""

        length = len(amplitude_rad_per_us)
        return cls(
            dt_us,
            tuple(amplitude_rad_per_us),
            (phase_rad,) * length,
            (detuning_rad_per_us,) * length,
        )

    @property
    def n_samples(self) -> int:
        return len(self.amplitude_rad_per_us)

    @property
    def duration_us(self) -> float:
        return self.n_samples * self.dt_us

    def scale_amplitude(self, factor: float) -> "SampledWaveform":
        if factor < 0 or not math.isfinite(factor):
            raise ValueError("amplitude scale must be finite and non-negative")
        return SampledWaveform(
            self.dt_us,
            tuple(factor * value for value in self.amplitude_rad_per_us),
            self.phase_rad,
            self.detuning_rad_per_us,
        )

    def pad_right(self, n_samples: int) -> "SampledWaveform":
        if n_samples < 0:
            raise ValueError("padding must be non-negative")
        if n_samples == 0:
            return self
        return SampledWaveform(
            self.dt_us,
            self.amplitude_rad_per_us + (0.0,) * n_samples,
            self.phase_rad + (0.0,) * n_samples,
            self.detuning_rad_per_us + (0.0,) * n_samples,
        )


@dataclass(frozen=True)
class AnalyticWaveform:
    """An analytic control envelope sampled at zero-order-hold midpoints."""

    duration_us: float
    amplitude: Callable[[float], float]
    phase: Callable[[float], float] = lambda _: 0.0
    detuning: Callable[[float], float] = lambda _: 0.0

    def sample(self, *, dt_us: float) -> SampledWaveform:
        if self.duration_us <= 0:
            raise ValueError("duration_us must be positive")
        if dt_us <= 0:
            raise ValueError("dt_us must be positive")
        ratio = self.duration_us / dt_us
        n_samples = int(round(ratio))
        if n_samples <= 0 or not math.isclose(
            n_samples * dt_us,
            self.duration_us,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("duration_us must be an integer multiple of dt_us")
        times = tuple((index + 0.5) * dt_us for index in range(n_samples))
        return SampledWaveform(
            dt_us,
            tuple(float(self.amplitude(time)) for time in times),
            tuple(float(self.phase(time)) for time in times),
            tuple(float(self.detuning(time)) for time in times),
        )


class WaveformTransfer(Protocol):
    """One deterministic command-to-field transformation."""

    def apply(self, waveform: SampledWaveform) -> SampledWaveform:
        ...


@dataclass(frozen=True)
class GainOffsetTransfer:
    """Static calibration from command units to field-control units."""

    amplitude_gain: float = 1.0
    amplitude_offset_rad_per_us: float = 0.0
    phase_offset_rad: float = 0.0
    detuning_gain: float = 1.0
    detuning_offset_rad_per_us: float = 0.0

    def apply(self, waveform: SampledWaveform) -> SampledWaveform:
        amplitudes = tuple(
            self.amplitude_gain * value + self.amplitude_offset_rad_per_us
            for value in waveform.amplitude_rad_per_us
        )
        if any(value < 0 for value in amplitudes):
            raise ValueError("gain/offset transfer produced negative amplitude")
        return SampledWaveform(
            waveform.dt_us,
            amplitudes,
            tuple(value + self.phase_offset_rad for value in waveform.phase_rad),
            tuple(
                self.detuning_gain * value + self.detuning_offset_rad_per_us
                for value in waveform.detuning_rad_per_us
            ),
        )


@dataclass(frozen=True)
class PureDelayTransfer:
    """Causal integer-sample hardware delay."""

    delay_us: float

    def apply(self, waveform: SampledWaveform) -> SampledWaveform:
        if self.delay_us < 0:
            raise ValueError("delay_us must be non-negative")
        ratio = self.delay_us / waveform.dt_us
        n_delay = int(round(ratio))
        if not math.isclose(
            n_delay * waveform.dt_us,
            self.delay_us,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("delay_us must be an integer multiple of dt_us")
        if n_delay == 0:
            return waveform
        return SampledWaveform(
            waveform.dt_us,
            (0.0,) * n_delay + waveform.amplitude_rad_per_us,
            (0.0,) * n_delay + waveform.phase_rad,
            (0.0,) * n_delay + waveform.detuning_rad_per_us,
        )


@dataclass(frozen=True)
class FirstOrderLowPassTransfer:
    """Causal one-pole low-pass applied to the complex field envelope.

    The pole is discretized exactly under zero-order hold.  ``bandwidth_mhz`` is
    the conventional -3 dB bandwidth, and MHz is numerically inverse
    microseconds.
    """

    bandwidth_mhz: float
    ringdown_time_constants: float = 0.0
    filter_detuning: bool = True

    @property
    def time_constant_us(self) -> float:
        if self.bandwidth_mhz <= 0:
            raise ValueError("bandwidth_mhz must be positive")
        return 1.0 / (2.0 * math.pi * self.bandwidth_mhz)

    @property
    def rise_time_10_90_us(self) -> float:
        return math.log(9.0) * self.time_constant_us

    def apply(self, waveform: SampledWaveform) -> SampledWaveform:
        if self.ringdown_time_constants < 0:
            raise ValueError("ringdown_time_constants must be non-negative")
        tau = self.time_constant_us
        n_ringdown = int(
            math.ceil(self.ringdown_time_constants * tau / waveform.dt_us)
        )
        complex_input = np.asarray(waveform.amplitude_rad_per_us) * np.exp(
            1j * np.asarray(waveform.phase_rad)
        )
        complex_input = np.pad(complex_input, (0, n_ringdown))
        alpha = math.exp(-waveform.dt_us / tau)
        field = signal.lfilter([1.0 - alpha], [1.0, -alpha], complex_input)
        amplitude = np.abs(field)
        phase = np.angle(field)

        detuning_input = np.asarray(waveform.detuning_rad_per_us)
        detuning_input = np.pad(detuning_input, (0, n_ringdown))
        if self.filter_detuning:
            detuning = signal.lfilter(
                [1.0 - alpha],
                [1.0, -alpha],
                detuning_input,
            )
        else:
            detuning = detuning_input
        return SampledWaveform(
            waveform.dt_us,
            tuple(float(value) for value in amplitude),
            tuple(float(value) for value in phase),
            tuple(float(value) for value in detuning),
        )


@dataclass(frozen=True)
class CompositeTransfer:
    """Apply transfer stages in declared physical order."""

    stages: Tuple[WaveformTransfer, ...]

    def apply(self, waveform: SampledWaveform) -> SampledWaveform:
        output = waveform
        for stage in self.stages:
            output = stage.apply(output)
        return output


@dataclass(frozen=True)
class HardwareTransferGraph:
    """Per-channel command-to-field transfer chains."""

    channel_transfers: Mapping[str, CompositeTransfer]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "channel_transfers",
            MappingProxyType(dict(self.channel_transfers)),
        )

    def apply(
        self,
        commands: Mapping[str, SampledWaveform],
    ) -> Mapping[str, SampledWaveform]:
        if not commands:
            raise ValueError("at least one command waveform is required")
        dt_values = {waveform.dt_us for waveform in commands.values()}
        if len(dt_values) != 1:
            raise ValueError("all command waveforms must use the same dt_us")
        outputs = {
            channel: self.channel_transfers.get(
                channel,
                CompositeTransfer(()),
            ).apply(waveform)
            for channel, waveform in commands.items()
        }
        max_samples = max(waveform.n_samples for waveform in outputs.values())
        return MappingProxyType(
            {
                channel: waveform.pad_right(max_samples - waveform.n_samples)
                for channel, waveform in outputs.items()
            }
        )
