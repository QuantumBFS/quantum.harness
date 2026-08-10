//! Generic-angle Born circuit construction and one-period sampling.

use crate::angles::GateCouplings;
use crate::gaussian::{InvariantErrors, MajoranaState, MeasurementGate};
use anyhow::{bail, Result};
use nalgebra::DMatrix;
use num_complex::Complex64;
use rand_xoshiro::rand_core::Rng;
use rand_xoshiro::Xoshiro256PlusPlus;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BoundarySector {
    pub wilson_loop: i8,
    pub fermion_parity: i8,
}

impl BoundarySector {
    pub const fn vacuum() -> Self {
        Self {
            wilson_loop: 1,
            fermion_parity: 1,
        }
    }

    fn validate(self) -> Result<()> {
        if !matches!(self.wilson_loop, -1 | 1) || !matches!(self.fermion_parity, -1 | 1) {
            bail!("boundary-sector quantum numbers must be +1 or -1");
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SamplingMode {
    Born,
    IidDiagnostic,
}

impl SamplingMode {
    pub const fn is_physical(self) -> bool {
        matches!(self, Self::Born)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct ConditionalGate {
    pub measurement: MeasurementGate,
    pub positive_rotation: f64,
    pub negative_rotation: f64,
}

impl ConditionalGate {
    pub fn rotation_for(self, outcome: i8) -> Result<f64> {
        match outcome {
            1 => Ok(self.positive_rotation),
            -1 => Ok(self.negative_rotation),
            _ => bail!("gate outcome must be +1 or -1"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub struct AppliedGate {
    pub measurement: MeasurementGate,
    pub outcome: i8,
    pub probability: f64,
    pub conditional_entropy: f64,
    pub rotation: f64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct PeriodSample {
    pub onsite: Vec<i8>,
    pub bond: Vec<i8>,
    pub applied_gates: Vec<AppliedGate>,
    pub conditional_entropy: f64,
    pub conditional_entropy_terms: usize,
    pub min_probability: f64,
    pub invariant_errors: InvariantErrors,
}

#[derive(Clone, Debug)]
pub struct GenericCircuit {
    width: usize,
    sector: BoundarySector,
    onsite: Vec<ConditionalGate>,
    bond: Vec<ConditionalGate>,
}

impl GenericCircuit {
    pub fn new(width: usize, couplings: GateCouplings, sector: BoundarySector) -> Result<Self> {
        if width < 2 || width % 2 != 0 {
            bail!("generic circuit width must be even and at least 2");
        }
        sector.validate()?;

        let onsite = (0..width)
            .map(|site| {
                conditional_gate(
                    2 * site,
                    2 * site + 1,
                    1,
                    couplings.j_dual,
                    couplings.phi_dual,
                )
            })
            .collect::<Result<Vec<_>>>()?;
        let bond = (0..width)
            .map(|site| {
                let wraps = site + 1 == width;
                let sign = if wraps {
                    -sector.wilson_loop * sector.fermion_parity
                } else {
                    1
                };
                conditional_gate(
                    2 * site + 1,
                    2 * ((site + 1) % width),
                    sign,
                    couplings.j,
                    couplings.phi,
                )
            })
            .collect::<Result<Vec<_>>>()?;

        Ok(Self {
            width,
            sector,
            onsite,
            bond,
        })
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn sector(&self) -> BoundarySector {
        self.sector
    }

    pub fn onsite_gates(&self) -> &[ConditionalGate] {
        &self.onsite
    }

    pub fn bond_gates(&self) -> &[ConditionalGate] {
        &self.bond
    }

    pub fn sample_period(
        &self,
        state: &mut MajoranaState,
        rng: &mut Xoshiro256PlusPlus,
        mode: SamplingMode,
    ) -> Result<PeriodSample> {
        if state.width() != self.width {
            bail!("circuit and covariance widths differ");
        }

        let mut onsite = Vec::with_capacity(self.width);
        let mut bond = Vec::with_capacity(self.width);
        let mut applied_gates = Vec::with_capacity(2 * self.width);
        let mut conditional_entropy = 0.0;
        let mut min_probability = 1.0_f64;
        let mut invariant_errors = InvariantErrors {
            antisymmetry: 0.0,
            purity: 0.0,
        };

        for (gates, outcomes) in [
            (self.onsite.as_slice(), &mut onsite),
            (self.bond.as_slice(), &mut bond),
        ] {
            for &gate in gates {
                let plus_probability = state.outcome_probability(gate.measurement, 1)?;
                let outcome = draw_outcome(rng, plus_probability, mode);
                let applied = apply_forced_gate(state, gate, outcome)?;

                outcomes.push(outcome);
                conditional_entropy += applied.conditional_entropy;
                min_probability = min_probability.min(applied.probability);
                let errors = state.invariant_errors();
                invariant_errors.antisymmetry =
                    invariant_errors.antisymmetry.max(errors.antisymmetry);
                invariant_errors.purity = invariant_errors.purity.max(errors.purity);
                applied_gates.push(applied);
            }
        }
        state.recondition_pure()?;

        Ok(PeriodSample {
            onsite,
            bond,
            applied_gates,
            conditional_entropy,
            conditional_entropy_terms: 2 * self.width,
            min_probability,
            invariant_errors,
        })
    }
}

pub fn apply_forced_gate(
    state: &mut MajoranaState,
    gate: ConditionalGate,
    outcome: i8,
) -> Result<AppliedGate> {
    let plus_probability = state.outcome_probability(gate.measurement, 1)?;
    let conditional_entropy = binary_entropy(plus_probability)?;
    let stats = state.apply_measurement(gate.measurement, outcome)?;
    let rotation = gate.rotation_for(outcome)?;
    state.apply_rotation(gate.measurement.a, gate.measurement.b, rotation)?;
    Ok(AppliedGate {
        measurement: gate.measurement,
        outcome,
        probability: stats.probability,
        conditional_entropy,
        rotation,
    })
}

fn conditional_gate(
    a: usize,
    b: usize,
    observable_sign: i8,
    strength: f64,
    phase: f64,
) -> Result<ConditionalGate> {
    if !strength.is_finite() || strength < 0.0 || !phase.is_finite() {
        bail!("conditional gate parameters must be finite with non-negative strength");
    }
    let sign = observable_sign as f64;
    Ok(ConditionalGate {
        measurement: MeasurementGate {
            a,
            b,
            observable_sign,
            strength,
        },
        positive_rotation: sign * phase,
        negative_rotation: sign * phase,
    })
}

fn draw_outcome(rng: &mut Xoshiro256PlusPlus, plus_probability: f64, mode: SamplingMode) -> i8 {
    match mode {
        SamplingMode::Born => {
            let uniform = ((rng.next_u64() >> 11) as f64) * (1.0 / ((1_u64 << 53) as f64));
            if uniform < plus_probability {
                1
            } else {
                -1
            }
        }
        SamplingMode::IidDiagnostic => {
            if rng.next_u64() & 1 == 0 {
                1
            } else {
                -1
            }
        }
    }
}

pub fn binary_entropy(probability: f64) -> Result<f64> {
    if !probability.is_finite() || !(0.0..=1.0).contains(&probability) {
        bail!("binary-entropy probability must lie in [0,1]");
    }
    let term = |value: f64| {
        if value == 0.0 {
            0.0
        } else {
            -value * value.ln()
        }
    };
    Ok(term(probability) + term(1.0 - probability))
}

/// Complex-orthogonal single-particle transfer matrix for a forced gate.
pub fn single_particle_gate(dimension: usize, applied: &AppliedGate) -> Result<DMatrix<Complex64>> {
    if dimension == 0
        || applied.measurement.a >= dimension
        || applied.measurement.b >= dimension
        || applied.measurement.a == applied.measurement.b
    {
        bail!("forced gate indices are invalid for the transfer dimension");
    }
    if !matches!(applied.outcome, -1 | 1)
        || !applied.measurement.strength.is_finite()
        || !applied.rotation.is_finite()
    {
        bail!("forced gate parameters are invalid");
    }

    let real = applied.outcome as f64
        * applied.measurement.observable_sign as f64
        * applied.measurement.strength;
    let parameter = Complex64::new(real, applied.rotation);
    let cosine = parameter.cosh();
    let sine = Complex64::i() * parameter.sinh();
    let mut gate = DMatrix::<Complex64>::identity(dimension, dimension);
    let a = applied.measurement.a;
    let b = applied.measurement.b;
    gate[(a, a)] = cosine;
    gate[(a, b)] = sine;
    gate[(b, a)] = -sine;
    gate[(b, b)] = cosine;
    Ok(gate)
}

/// Product of the disjoint forced gates in one circuit row.
pub fn single_particle_row(
    dimension: usize,
    applied: &[AppliedGate],
) -> Result<DMatrix<Complex64>> {
    let mut row = DMatrix::<Complex64>::identity(dimension, dimension);
    for gate in applied {
        row = single_particle_gate(dimension, gate)? * row;
    }
    Ok(row)
}
