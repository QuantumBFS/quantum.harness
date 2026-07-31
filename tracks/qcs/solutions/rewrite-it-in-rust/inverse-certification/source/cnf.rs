use crate::{GateOp, OccamError, RelationProblem, Source};
use varisat::{CnfFormula, ExtendFormula, Lit};

use super::{SynthesisLimits, SynthesisProblem};

pub(crate) const GATE_OPERATIONS: [GateOp; 6] = [
    GateOp::And,
    GateOp::Or,
    GateOp::Xor,
    GateOp::Nand,
    GateOp::Nor,
    GateOp::Xnor,
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct LiteralCandidate {
    pub source: Source,
    pub inverted: bool,
}

pub(crate) struct GateEncoding {
    pub operations: Vec<Lit>,
    pub lhs_selectors: Vec<Lit>,
    pub rhs_selectors: Vec<Lit>,
    pub candidates: Vec<LiteralCandidate>,
    pub values: Vec<Lit>,
}

pub(crate) struct OutputEncoding {
    pub selectors: Vec<Lit>,
    pub candidates: Vec<LiteralCandidate>,
    pub values: Vec<Lit>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EncodingStatistics {
    pub variables: usize,
    pub clauses: usize,
    pub literals: usize,
}

pub(crate) struct EncodedSynthesis {
    pub formula: CnfFormula,
    pub gates: Vec<GateEncoding>,
    pub outputs: Vec<OutputEncoding>,
    pub statistics: EncodingStatistics,
}

struct FormulaBuilder<'a> {
    formula: CnfFormula,
    limits: &'a SynthesisLimits,
    literal_count: usize,
}

impl<'a> FormulaBuilder<'a> {
    fn new(limits: &'a SynthesisLimits) -> Self {
        Self {
            formula: CnfFormula::new(),
            limits,
            literal_count: 0,
        }
    }

    fn new_lit(&mut self) -> Result<Lit, OccamError> {
        let requested =
            self.formula
                .var_count()
                .checked_add(1)
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "synthesis CNF variable count",
                })?;
        require(
            "synthesis CNF variables",
            requested,
            self.limits.max_cnf_variables,
        )?;
        Ok(self.formula.new_lit())
    }

    fn new_lits(&mut self, count: usize) -> Result<Vec<Lit>, OccamError> {
        (0..count).map(|_| self.new_lit()).collect()
    }

    fn add_clause(&mut self, clause: &[Lit]) -> Result<(), OccamError> {
        let clause_count =
            self.formula
                .len()
                .checked_add(1)
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "synthesis CNF clause count",
                })?;
        require(
            "synthesis CNF clauses",
            clause_count,
            self.limits.max_cnf_clauses,
        )?;
        self.literal_count =
            self.literal_count
                .checked_add(clause.len())
                .ok_or(OccamError::ArithmeticOverflow {
                    context: "synthesis CNF literal count",
                })?;
        require(
            "synthesis CNF literals",
            self.literal_count,
            self.limits.max_cnf_literals,
        )?;
        self.formula.add_clause(clause);
        Ok(())
    }

    fn exactly_one(&mut self, selectors: &[Lit]) -> Result<(), OccamError> {
        self.add_clause(selectors)?;
        for left in 0..selectors.len() {
            for right in (left + 1)..selectors.len() {
                self.add_clause(&[!selectors[left], !selectors[right]])?;
            }
        }
        Ok(())
    }

    fn ordered_commutative_pair(
        &mut self,
        lhs_selectors: &[Lit],
        rhs_selectors: &[Lit],
    ) -> Result<(), OccamError> {
        if lhs_selectors.len() != rhs_selectors.len() {
            return Err(OccamError::Validation(
                "commutative selector groups must have equal length".into(),
            ));
        }
        for (lhs_index, lhs_selector) in lhs_selectors.iter().enumerate() {
            for rhs_selector in rhs_selectors.iter().take(lhs_index) {
                self.add_clause(&[!*lhs_selector, !*rhs_selector])?;
            }
        }
        Ok(())
    }

    fn statistics(&self) -> EncodingStatistics {
        EncodingStatistics {
            variables: self.formula.var_count(),
            clauses: self.formula.len(),
            literals: self.literal_count,
        }
    }
}

pub(crate) fn encode(
    problem: &SynthesisProblem,
    gate_bound: usize,
    limits: &SynthesisLimits,
) -> Result<EncodedSynthesis, OccamError> {
    require("synthesis gates", gate_bound, limits.max_gates)?;
    let mut builder = FormulaBuilder::new(limits);
    let mut gates = Vec::with_capacity(gate_bound);

    for gate_index in 0..gate_bound {
        let candidates = literal_candidates(problem.input_width, gate_index);
        let operations = builder.new_lits(GATE_OPERATIONS.len())?;
        let lhs_selectors = builder.new_lits(candidates.len())?;
        let rhs_selectors = builder.new_lits(candidates.len())?;
        let lhs_values = builder.new_lits(problem.rows.len())?;
        let rhs_values = builder.new_lits(problem.rows.len())?;
        let values = builder.new_lits(problem.rows.len())?;
        builder.exactly_one(&operations)?;
        builder.exactly_one(&lhs_selectors)?;
        builder.exactly_one(&rhs_selectors)?;
        builder.ordered_commutative_pair(&lhs_selectors, &rhs_selectors)?;

        for (row_index, row) in problem.rows.iter().enumerate() {
            for (selector, candidate) in lhs_selectors.iter().zip(&candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, lhs_values[row_index], source)?;
            }
            for (selector, candidate) in rhs_selectors.iter().zip(&candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, rhs_values[row_index], source)?;
            }
            for (operation_index, operation) in GATE_OPERATIONS.iter().enumerate() {
                encode_operation(
                    &mut builder,
                    operations[operation_index],
                    lhs_values[row_index],
                    rhs_values[row_index],
                    values[row_index],
                    *operation,
                )?;
            }
        }

        gates.push(GateEncoding {
            operations,
            lhs_selectors,
            rhs_selectors,
            candidates,
            values,
        });
    }

    let output_candidates = literal_candidates(problem.input_width, gate_bound);
    let mut outputs = Vec::with_capacity(problem.output_width);
    for output_index in 0..problem.output_width {
        let selectors = builder.new_lits(output_candidates.len())?;
        let values = builder.new_lits(problem.rows.len())?;
        builder.exactly_one(&selectors)?;
        for (row_index, row) in problem.rows.iter().enumerate() {
            for (selector, candidate) in selectors.iter().zip(&output_candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, values[row_index], source)?;
            }
            builder.add_clause(&[if row.expected[output_index] {
                values[row_index]
            } else {
                !values[row_index]
            }])?;
        }
        outputs.push(OutputEncoding {
            selectors,
            candidates: output_candidates.clone(),
            values,
        });
    }

    let statistics = builder.statistics();
    Ok(EncodedSynthesis {
        formula: builder.formula,
        gates,
        outputs,
        statistics,
    })
}

pub(crate) fn encode_relation(
    problem: &RelationProblem,
    gate_bound: usize,
    limits: &SynthesisLimits,
) -> Result<EncodedSynthesis, OccamError> {
    require("synthesis gates", gate_bound, limits.max_gates)?;
    let mut builder = FormulaBuilder::new(limits);
    let mut gates = Vec::with_capacity(gate_bound);

    for gate_index in 0..gate_bound {
        let candidates = literal_candidates(problem.input_width, gate_index);
        let operations = builder.new_lits(GATE_OPERATIONS.len())?;
        let lhs_selectors = builder.new_lits(candidates.len())?;
        let rhs_selectors = builder.new_lits(candidates.len())?;
        let lhs_values = builder.new_lits(problem.rows.len())?;
        let rhs_values = builder.new_lits(problem.rows.len())?;
        let values = builder.new_lits(problem.rows.len())?;
        builder.exactly_one(&operations)?;
        builder.exactly_one(&lhs_selectors)?;
        builder.exactly_one(&rhs_selectors)?;
        builder.ordered_commutative_pair(&lhs_selectors, &rhs_selectors)?;

        for (row_index, row) in problem.rows.iter().enumerate() {
            for (selector, candidate) in lhs_selectors.iter().zip(&candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, lhs_values[row_index], source)?;
            }
            for (selector, candidate) in rhs_selectors.iter().zip(&candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, rhs_values[row_index], source)?;
            }
            for (operation_index, operation) in GATE_OPERATIONS.iter().enumerate() {
                encode_operation(
                    &mut builder,
                    operations[operation_index],
                    lhs_values[row_index],
                    rhs_values[row_index],
                    values[row_index],
                    *operation,
                )?;
            }
        }

        gates.push(GateEncoding {
            operations,
            lhs_selectors,
            rhs_selectors,
            candidates,
            values,
        });
    }

    let output_candidates = literal_candidates(problem.input_width, gate_bound);
    let mut outputs = Vec::with_capacity(problem.output_width);
    for _ in 0..problem.output_width {
        let selectors = builder.new_lits(output_candidates.len())?;
        let values = builder.new_lits(problem.rows.len())?;
        builder.exactly_one(&selectors)?;
        for (row_index, row) in problem.rows.iter().enumerate() {
            for (selector, candidate) in selectors.iter().zip(&output_candidates) {
                let source = source_value(*candidate, row_index, &row.input, &gates)?;
                imply_equality(&mut builder, *selector, values[row_index], source)?;
            }
        }
        outputs.push(OutputEncoding {
            selectors,
            candidates: output_candidates.clone(),
            values,
        });
    }

    let shift =
        u32::try_from(problem.output_width).map_err(|_| OccamError::ArithmeticOverflow {
            context: "inverse relation output tuple count",
        })?;
    let tuple_count = 1usize
        .checked_shl(shift)
        .ok_or(OccamError::ArithmeticOverflow {
            context: "inverse relation output tuple count",
        })?;
    for (row_index, row) in problem.rows.iter().enumerate() {
        for tuple in 0..tuple_count {
            let forbidden = (0..problem.output_width)
                .map(|bit| tuple & (1usize << bit) != 0)
                .collect::<Vec<_>>();
            if row.accepted_outputs.contains(&forbidden) {
                continue;
            }
            let clause = outputs
                .iter()
                .enumerate()
                .map(|(bit, output)| {
                    let value = output.values[row_index];
                    if forbidden[bit] { !value } else { value }
                })
                .collect::<Vec<_>>();
            builder.add_clause(&clause)?;
        }
    }

    let statistics = builder.statistics();
    Ok(EncodedSynthesis {
        formula: builder.formula,
        gates,
        outputs,
        statistics,
    })
}

fn literal_candidates(input_width: usize, wire_count: usize) -> Vec<LiteralCandidate> {
    let sources = (0..input_width)
        .map(Source::Input)
        .chain((0..wire_count).map(Source::Wire));
    sources
        .flat_map(|source| {
            [
                LiteralCandidate {
                    source,
                    inverted: false,
                },
                LiteralCandidate {
                    source,
                    inverted: true,
                },
            ]
        })
        .collect()
}

#[derive(Clone, Copy)]
enum SemanticValue {
    Constant(bool),
    Literal(Lit),
}

fn source_value(
    candidate: LiteralCandidate,
    row_index: usize,
    input: &[bool],
    gates: &[GateEncoding],
) -> Result<SemanticValue, OccamError> {
    match candidate.source {
        Source::Input(index) => input
            .get(index)
            .copied()
            .map(|value| SemanticValue::Constant(value ^ candidate.inverted))
            .ok_or_else(|| {
                OccamError::Validation(format!("synthesis input source {index} is out of range"))
            }),
        Source::Wire(index) => gates
            .get(index)
            .and_then(|gate| gate.values.get(row_index))
            .copied()
            .map(|value| SemanticValue::Literal(if candidate.inverted { !value } else { value }))
            .ok_or_else(|| {
                OccamError::Validation(format!("synthesis wire source {index} is unavailable"))
            }),
    }
}

fn imply_equality(
    builder: &mut FormulaBuilder<'_>,
    selector: Lit,
    value: Lit,
    source: SemanticValue,
) -> Result<(), OccamError> {
    match source {
        SemanticValue::Constant(true) => builder.add_clause(&[!selector, value]),
        SemanticValue::Constant(false) => builder.add_clause(&[!selector, !value]),
        SemanticValue::Literal(source) => {
            builder.add_clause(&[!selector, !value, source])?;
            builder.add_clause(&[!selector, value, !source])
        }
    }
}

fn encode_operation(
    builder: &mut FormulaBuilder<'_>,
    selector: Lit,
    lhs: Lit,
    rhs: Lit,
    output: Lit,
    operation: GateOp,
) -> Result<(), OccamError> {
    for lhs_value in [false, true] {
        for rhs_value in [false, true] {
            let expected = operation.apply(lhs_value, rhs_value);
            builder.add_clause(&[
                !selector,
                if lhs_value { !lhs } else { lhs },
                if rhs_value { !rhs } else { rhs },
                if expected { output } else { !output },
            ])?;
        }
    }
    Ok(())
}

fn require(resource: &'static str, requested: usize, limit: usize) -> Result<(), OccamError> {
    if requested > limit {
        return Err(OccamError::ResourceLimit {
            resource,
            requested,
            limit,
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use crate::{ArithmeticFamily, InverseSpec, build_relation_problem};
    use varisat::Solver;

    use super::*;

    fn solve(formula: &CnfFormula) -> bool {
        let mut solver = Solver::new();
        solver.add_formula(formula);
        solver.solve().unwrap()
    }

    #[test]
    fn exactly_one_handles_zero_one_and_multiple_selectors() {
        let limits = SynthesisLimits::default();

        let mut zero = FormulaBuilder::new(&limits);
        zero.exactly_one(&[]).unwrap();
        assert!(!solve(&zero.formula));

        let mut one = FormulaBuilder::new(&limits);
        let selector = one.new_lit().unwrap();
        one.exactly_one(&[selector]).unwrap();
        assert!(solve(&one.formula));

        let mut multiple = FormulaBuilder::new(&limits);
        let left = multiple.new_lit().unwrap();
        let right = multiple.new_lit().unwrap();
        multiple.exactly_one(&[left, right]).unwrap();
        multiple.add_clause(&[left]).unwrap();
        multiple.add_clause(&[right]).unwrap();
        assert!(!solve(&multiple.formula));
    }

    #[test]
    fn commutative_operand_order_removes_only_swapped_selector_models() {
        fn constrained_pair(lhs_index: usize, rhs_index: usize) -> CnfFormula {
            let limits = SynthesisLimits::default();
            let mut builder = FormulaBuilder::new(&limits);
            let lhs = builder.new_lits(3).unwrap();
            let rhs = builder.new_lits(3).unwrap();
            builder.exactly_one(&lhs).unwrap();
            builder.exactly_one(&rhs).unwrap();
            builder.ordered_commutative_pair(&lhs, &rhs).unwrap();
            builder.add_clause(&[lhs[lhs_index]]).unwrap();
            builder.add_clause(&[rhs[rhs_index]]).unwrap();
            builder.formula
        }

        let ordered = constrained_pair(0, 2);
        assert!(solve(&ordered));
        let swapped = constrained_pair(2, 0);
        assert!(!solve(&swapped));
    }

    #[test]
    fn respects_cnf_resource_limits() {
        let limits = SynthesisLimits {
            max_cnf_variables: 0,
            ..SynthesisLimits::default()
        };
        let mut builder = FormulaBuilder::new(&limits);
        assert!(matches!(
            builder.new_lit(),
            Err(OccamError::ResourceLimit {
                resource: "synthesis CNF variables",
                ..
            })
        ));
    }

    #[test]
    fn impossible_relation_row_is_unsatisfiable() {
        let spec = InverseSpec::new(ArithmeticFamily::Add, 1).unwrap();
        let mut problem = build_relation_problem(spec).unwrap();
        problem.rows[0].accepted_outputs.clear();
        let encoded = encode_relation(&problem, 2, &SynthesisLimits::default()).unwrap();
        assert!(!solve(&encoded.formula));
    }
}
