use std::collections::HashMap;

use crate::{GateOp, OccamError, ResourceLimits};

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
enum Node {
    Input(usize),
    Gate(usize),
    Zero,
}

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Signal {
    node: Node,
    inverted: bool,
}

impl Signal {
    pub fn input(index: usize) -> Self {
        Self {
            node: Node::Input(index),
            inverted: false,
        }
    }

    pub fn inverted(self) -> Self {
        Self {
            inverted: !self.inverted,
            ..self
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SynthesizedCircuit {
    pub netlist: String,
    pub gate_count: usize,
}

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
struct GateKey {
    op: GateOp,
    lhs: Signal,
    rhs: Signal,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct CanonicalGate {
    op: GateOp,
    lhs: Signal,
    rhs: Signal,
}

pub struct CircuitBuilder<'a> {
    input_count: usize,
    limits: &'a ResourceLimits,
    gates: Vec<CanonicalGate>,
    interned: HashMap<GateKey, Signal>,
}

impl<'a> CircuitBuilder<'a> {
    pub fn new(input_count: usize, limits: &'a ResourceLimits) -> Result<Self, OccamError> {
        if input_count == 0 {
            return Err(OccamError::Validation(
                "circuit builder input count must be positive".into(),
            ));
        }
        limits.require("circuit inputs", input_count, limits.max_inputs)?;
        Ok(Self {
            input_count,
            limits,
            gates: Vec::new(),
            interned: HashMap::new(),
        })
    }

    pub fn zero(&self) -> Result<Signal, OccamError> {
        Ok(Signal {
            node: Node::Zero,
            inverted: false,
        })
    }

    pub fn one(&self) -> Result<Signal, OccamError> {
        Ok(self.zero()?.inverted())
    }

    pub fn binary(&mut self, op: GateOp, lhs: Signal, rhs: Signal) -> Result<Signal, OccamError> {
        self.validate_signal(lhs)?;
        self.validate_signal(rhs)?;
        match op {
            GateOp::Nand => {
                return Ok(self.binary(GateOp::And, lhs, rhs)?.inverted());
            }
            GateOp::Nor => {
                return Ok(self.binary(GateOp::Or, lhs, rhs)?.inverted());
            }
            GateOp::Xnor => {
                return Ok(self.binary(GateOp::Xor, lhs, rhs)?.inverted());
            }
            GateOp::And | GateOp::Or | GateOp::Xor => {}
        }
        if let Some(result) = self.simplify(op, lhs, rhs)? {
            return Ok(result);
        }
        let (lhs, rhs) = if lhs <= rhs { (lhs, rhs) } else { (rhs, lhs) };
        let key = GateKey { op, lhs, rhs };
        if let Some(signal) = self.interned.get(&key) {
            return Ok(*signal);
        }
        let next_count = self
            .gates
            .len()
            .checked_add(1)
            .ok_or(OccamError::ArithmeticOverflow {
                context: "optimized circuit gate count",
            })?;
        self.limits
            .require("circuit gates", next_count, self.limits.max_gates)?;
        let signal = Signal {
            node: Node::Gate(self.gates.len()),
            inverted: false,
        };
        self.gates.push(CanonicalGate { op, lhs, rhs });
        self.interned.insert(key, signal);
        Ok(signal)
    }

    pub fn finish(self, outputs: &[Signal]) -> Result<SynthesizedCircuit, OccamError> {
        if outputs.is_empty() {
            return Err(OccamError::Validation(
                "optimized circuit must have at least one output".into(),
            ));
        }
        self.limits
            .require("circuit outputs", outputs.len(), self.limits.max_outputs)?;
        for output in outputs {
            self.validate_signal(*output)?;
        }

        let mut reachable = vec![false; self.gates.len()];
        for output in outputs {
            mark_reachable(*output, &self.gates, &mut reachable);
        }
        let constant_required = outputs
            .iter()
            .any(|signal| matches!(signal.node, Node::Zero))
            || self.gates.iter().zip(&reachable).any(|(gate, keep)| {
                *keep
                    && (matches!(gate.lhs.node, Node::Zero) || matches!(gate.rhs.node, Node::Zero))
            });
        let reachable_count = reachable.iter().filter(|keep| **keep).count();
        let gate_count = reachable_count
            .checked_add(usize::from(constant_required))
            .ok_or(OccamError::ArithmeticOverflow {
                context: "serialized circuit gate count",
            })?;
        self.limits
            .require("circuit gates", gate_count, self.limits.max_gates)?;

        let mut dense_wires = vec![None; self.gates.len()];
        let zero_wire = constant_required.then_some(1usize);
        let mut next_wire = 1 + usize::from(constant_required);
        for (index, keep) in reachable.iter().enumerate() {
            if *keep {
                dense_wires[index] = Some(next_wire);
                next_wire += 1;
            }
        }

        let mut lines = Vec::with_capacity(gate_count + 2);
        lines.push(format!("INPUTS {}", self.input_count));
        if let Some(wire) = zero_wire {
            lines.push(format!("w{wire} = XOR x1 x1"));
        }
        for (index, gate) in self.gates.iter().enumerate() {
            let Some(wire) = dense_wires[index] else {
                continue;
            };
            let lhs = render_signal(gate.lhs, &dense_wires, zero_wire)?;
            let rhs = render_signal(gate.rhs, &dense_wires, zero_wire)?;
            lines.push(format!("w{wire} = {} {lhs} {rhs}", operation_name(gate.op)));
        }
        let rendered_outputs = outputs
            .iter()
            .map(|signal| render_signal(*signal, &dense_wires, zero_wire))
            .collect::<Result<Vec<_>, _>>()?;
        lines.push(format!("OUTPUTS {}", rendered_outputs.join(" ")));
        let netlist = format!("{}\n", lines.join("\n"));
        let max_bytes = self
            .limits
            .max_generated_bytes
            .min(self.limits.max_source_bytes);
        self.limits
            .require("generated bytes", netlist.len(), max_bytes)?;
        Ok(SynthesizedCircuit {
            netlist,
            gate_count,
        })
    }

    fn simplify(&self, op: GateOp, lhs: Signal, rhs: Signal) -> Result<Option<Signal>, OccamError> {
        debug_assert!(matches!(op, GateOp::And | GateOp::Or | GateOp::Xor));
        if lhs == rhs {
            return Ok(Some(match op {
                GateOp::And | GateOp::Or => lhs,
                GateOp::Xor => self.zero()?,
                _ => unreachable!(),
            }));
        }
        if lhs == rhs.inverted() {
            return Ok(Some(match op {
                GateOp::And => self.zero()?,
                GateOp::Or | GateOp::Xor => self.one()?,
                _ => unreachable!(),
            }));
        }
        match (constant_value(lhs), constant_value(rhs)) {
            (Some(lhs), Some(rhs)) => {
                let value = op.apply(lhs, rhs);
                Ok(Some(if value { self.one()? } else { self.zero()? }))
            }
            (Some(constant), None) => Ok(Some(simplify_one_constant(op, constant, rhs, self)?)),
            (None, Some(constant)) => Ok(Some(simplify_one_constant(op, constant, lhs, self)?)),
            (None, None) => Ok(None),
        }
    }

    fn validate_signal(&self, signal: Signal) -> Result<(), OccamError> {
        match signal.node {
            Node::Input(index) if index < self.input_count => Ok(()),
            Node::Input(index) => Err(OccamError::Validation(format!(
                "builder input index {index} is out of range for {} inputs",
                self.input_count
            ))),
            Node::Gate(index) if index < self.gates.len() => Ok(()),
            Node::Gate(index) => Err(OccamError::Validation(format!(
                "builder gate index {index} is unavailable"
            ))),
            Node::Zero => Ok(()),
        }
    }
}

fn simplify_one_constant(
    op: GateOp,
    constant: bool,
    signal: Signal,
    builder: &CircuitBuilder<'_>,
) -> Result<Signal, OccamError> {
    Ok(match (op, constant) {
        (GateOp::And, false) => builder.zero()?,
        (GateOp::And, true) | (GateOp::Or, false) | (GateOp::Xor, false) => signal,
        (GateOp::Or, true) => builder.one()?,
        (GateOp::Xor, true) => signal.inverted(),
        _ => unreachable!(),
    })
}

fn constant_value(signal: Signal) -> Option<bool> {
    matches!(signal.node, Node::Zero).then_some(signal.inverted)
}

fn mark_reachable(signal: Signal, gates: &[CanonicalGate], reachable: &mut [bool]) {
    let Node::Gate(index) = signal.node else {
        return;
    };
    if reachable[index] {
        return;
    }
    reachable[index] = true;
    mark_reachable(gates[index].lhs, gates, reachable);
    mark_reachable(gates[index].rhs, gates, reachable);
}

fn render_signal(
    signal: Signal,
    dense_wires: &[Option<usize>],
    zero_wire: Option<usize>,
) -> Result<String, OccamError> {
    let name = match signal.node {
        Node::Input(index) => format!("x{}", index + 1),
        Node::Gate(index) => format!(
            "w{}",
            dense_wires
                .get(index)
                .and_then(|wire| *wire)
                .ok_or_else(|| OccamError::Validation(format!(
                    "reachable gate {index} has no serialized wire"
                )))?
        ),
        Node::Zero => format!(
            "w{}",
            zero_wire.ok_or_else(|| {
                OccamError::Validation("constant output has no serialized zero wire".into())
            })?
        ),
    };
    Ok(if signal.inverted {
        format!("~{name}")
    } else {
        name
    })
}

fn operation_name(op: GateOp) -> &'static str {
    match op {
        GateOp::And => "AND",
        GateOp::Or => "OR",
        GateOp::Xor => "XOR",
        GateOp::Nand => "NAND",
        GateOp::Nor => "NOR",
        GateOp::Xnor => "XNOR",
    }
}

#[cfg(test)]
mod tests {
    use crate::{DEFAULT_LIMITS, evaluate, parse_netlist};

    use super::*;

    #[test]
    fn serializes_constant_outputs_with_one_shared_gate() {
        let builder = CircuitBuilder::new(1, &DEFAULT_LIMITS).unwrap();
        let zero = builder.zero().unwrap();
        let one = builder.one().unwrap();
        let synthesized = builder.finish(&[zero, one]).unwrap();
        assert_eq!(synthesized.gate_count, 1);
        let circuit = parse_netlist(&synthesized.netlist).unwrap();
        assert_eq!(evaluate(&circuit, &[false]).unwrap(), vec![false, true]);
        assert_eq!(evaluate(&circuit, &[true]).unwrap(), vec![false, true]);
    }
}
