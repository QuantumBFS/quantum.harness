use std::{collections::HashMap, time::Instant};

use crate::{CircuitBuilder, DEFAULT_LIMITS, GateOp, ResourceLimits, Signal};

use super::{
    LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, ResearchMethod, TrialBudget,
};

type NodeId = usize;
type Row = (Vec<bool>, Vec<bool>);

#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
enum Node {
    False,
    True,
    Branch {
        variable: usize,
        low: NodeId,
        high: NodeId,
    },
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum BddOrder {
    File,
    Interleaved,
    YThenX,
    Reverse,
}

impl BddOrder {
    pub const ALL: [Self; 4] = [Self::File, Self::Interleaved, Self::YThenX, Self::Reverse];

    fn name(self) -> &'static str {
        match self {
            Self::File => "file",
            Self::Interleaved => "interleaved",
            Self::YThenX => "y-then-x",
            Self::Reverse => "reverse",
        }
    }

    fn variables(self, input_width: usize) -> Vec<usize> {
        match self {
            Self::File => (0..input_width).collect(),
            Self::Reverse => (0..input_width).rev().collect(),
            Self::YThenX => {
                let midpoint = input_width / 2;
                (midpoint..input_width).chain(0..midpoint).collect()
            }
            Self::Interleaved => {
                let midpoint = input_width / 2;
                let mut variables = Vec::with_capacity(input_width);
                for offset in 0..midpoint {
                    variables.push(offset);
                    if midpoint + offset < input_width {
                        variables.push(midpoint + offset);
                    }
                }
                if !input_width.is_multiple_of(2) {
                    variables.push(input_width - 1);
                }
                variables
            }
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BddResult {
    pub netlist: String,
    pub node_count: usize,
    pub gate_count: usize,
    pub order: BddOrder,
}

pub struct RobddLearner;

impl ResearchLearner for RobddLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::Robdd
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let mut candidates = BddOrder::ALL
            .into_iter()
            .map(|order| build_robdd(observed, order, budget))
            .collect::<Result<Vec<_>, _>>()?;
        candidates.sort_by_key(|result| (result.node_count, result.gate_count, result.order));
        let best = candidates
            .into_iter()
            .next()
            .ok_or_else(|| LearnerFailure::NoHypothesis("ROBDD produced no ordering".into()))?;
        Ok(LearnedHypothesis::Circuit {
            netlist: best.netlist,
            description_length: Some(best.node_count),
            minimum_unique: None,
            detail: format!(
                "reduced ordered BDD using {} order ({} nonterminal nodes)",
                best.order.name(),
                best.node_count
            ),
        })
    }
}

pub fn build_robdd(
    observed: &ObservedTask,
    order: BddOrder,
    budget: &TrialBudget,
) -> Result<BddResult, LearnerFailure> {
    let rows = normalized_rows(observed)?;
    let variables = order.variables(observed.input_width);
    let deadline = Instant::now() + budget.timeout;
    let mut manager = BddManager::new(budget.max_nodes, deadline);
    let row_refs = rows.iter().collect::<Vec<_>>();
    let roots = (0..observed.output_width)
        .map(|output| manager.build(&row_refs, &variables, 0, output))
        .collect::<Result<Vec<_>, _>>()?;
    let node_count = manager.nodes.len().saturating_sub(2);
    let limits = ResourceLimits {
        max_gates: budget.max_gates,
        ..DEFAULT_LIMITS
    };
    let mut builder =
        CircuitBuilder::new(observed.input_width, &limits).map_err(classify_builder_failure)?;
    let mut compiled = HashMap::new();
    let outputs = roots
        .iter()
        .map(|root| compile_node(*root, &manager.nodes, &mut compiled, &mut builder))
        .collect::<Result<Vec<_>, _>>()?;
    let circuit = builder.finish(&outputs).map_err(classify_builder_failure)?;
    Ok(BddResult {
        netlist: circuit.netlist,
        node_count,
        gate_count: circuit.gate_count,
        order,
    })
}

struct BddManager {
    nodes: Vec<Node>,
    unique: HashMap<(usize, NodeId, NodeId), NodeId>,
    max_nodes: usize,
    deadline: Instant,
}

impl BddManager {
    fn new(max_nodes: usize, deadline: Instant) -> Self {
        Self {
            nodes: vec![Node::False, Node::True],
            unique: HashMap::new(),
            max_nodes,
            deadline,
        }
    }

    fn build(
        &mut self,
        rows: &[&Row],
        variables: &[usize],
        depth: usize,
        output: usize,
    ) -> Result<NodeId, LearnerFailure> {
        self.check_deadline("ROBDD construction")?;
        if rows.is_empty() {
            return Ok(0);
        }
        let first = rows[0].1[output];
        if rows.iter().all(|row| row.1[output] == first) {
            return Ok(usize::from(first));
        }
        let Some(variable) = variables.get(depth).copied() else {
            return Err(LearnerFailure::NoHypothesis(
                "identical observed inputs have conflicting outputs".into(),
            ));
        };
        let mut low = Vec::new();
        let mut high = Vec::new();
        for row in rows {
            if row.0[variable] {
                high.push(*row);
            } else {
                low.push(*row);
            }
        }

        let low = (!low.is_empty())
            .then(|| self.build(&low, variables, depth + 1, output))
            .transpose()?;
        let high = (!high.is_empty())
            .then(|| self.build(&high, variables, depth + 1, output))
            .transpose()?;
        match (low, high) {
            (Some(low), Some(high)) => self.branch(variable, low, high),
            (Some(populated), None) | (None, Some(populated)) => Ok(populated),
            (None, None) => Ok(0),
        }
    }

    fn branch(
        &mut self,
        variable: usize,
        low: NodeId,
        high: NodeId,
    ) -> Result<NodeId, LearnerFailure> {
        if low == high {
            return Ok(low);
        }
        let key = (variable, low, high);
        if let Some(node) = self.unique.get(&key) {
            return Ok(*node);
        }
        let next_node_count = self.nodes.len().saturating_sub(1);
        if next_node_count > self.max_nodes {
            return Err(LearnerFailure::ResourceLimit(format!(
                "ROBDD node limit {} exceeded",
                self.max_nodes
            )));
        }
        let id = self.nodes.len();
        self.nodes.push(Node::Branch {
            variable,
            low,
            high,
        });
        self.unique.insert(key, id);
        Ok(id)
    }

    fn check_deadline(&self, label: &str) -> Result<(), LearnerFailure> {
        if Instant::now() >= self.deadline {
            Err(LearnerFailure::Timeout(format!(
                "{label} exceeded the trial timeout"
            )))
        } else {
            Ok(())
        }
    }
}

fn compile_node(
    id: NodeId,
    nodes: &[Node],
    compiled: &mut HashMap<NodeId, Signal>,
    builder: &mut CircuitBuilder<'_>,
) -> Result<Signal, LearnerFailure> {
    if let Some(signal) = compiled.get(&id) {
        return Ok(*signal);
    }
    let signal = match nodes[id] {
        Node::False => builder.zero().map_err(classify_builder_failure)?,
        Node::True => builder.one().map_err(classify_builder_failure)?,
        Node::Branch {
            variable,
            low,
            high,
        } => {
            let low = compile_node(low, nodes, compiled, builder)?;
            let high = compile_node(high, nodes, compiled, builder)?;
            let variable = Signal::input(variable);
            let when_high = builder
                .binary(GateOp::And, variable, high)
                .map_err(classify_builder_failure)?;
            let when_low = builder
                .binary(GateOp::And, variable.inverted(), low)
                .map_err(classify_builder_failure)?;
            builder
                .binary(GateOp::Or, when_high, when_low)
                .map_err(classify_builder_failure)?
        }
    };
    compiled.insert(id, signal);
    Ok(signal)
}

fn normalized_rows(observed: &ObservedTask) -> Result<Vec<Row>, LearnerFailure> {
    if observed.input_width == 0 || observed.output_width == 0 || observed.samples.is_empty() {
        return Err(LearnerFailure::NoHypothesis(
            "ROBDD requires non-empty, positive-width observations".into(),
        ));
    }
    let mut rows = observed
        .samples
        .iter()
        .map(|sample| {
            if sample.input.len() != observed.input_width
                || sample.expected.len() != observed.output_width
            {
                return Err(LearnerFailure::ToolError(
                    "observed row width does not match the task".into(),
                ));
            }
            Ok((sample.input.clone(), sample.expected.clone()))
        })
        .collect::<Result<Vec<_>, _>>()?;
    rows.sort();
    let mut unique = Vec::<Row>::with_capacity(rows.len());
    for row in rows {
        if let Some(previous) = unique.last()
            && previous.0 == row.0
        {
            if previous.1 != row.1 {
                return Err(LearnerFailure::NoHypothesis(
                    "duplicate observed input has conflicting outputs".into(),
                ));
            }
            continue;
        }
        unique.push(row);
    }
    Ok(unique)
}

fn classify_builder_failure(error: crate::OccamError) -> LearnerFailure {
    match error {
        crate::OccamError::ResourceLimit { .. } | crate::OccamError::ArithmeticOverflow { .. } => {
            LearnerFailure::ResourceLimit(error.to_string())
        }
        _ => LearnerFailure::ToolError(error.to_string()),
    }
}
