use crate::{
    ArithmeticFamily, BinaryOp, Expr, MdlSearchConfig, OccamError, SearchTermination,
    score_candidates, search_mdl,
};

use super::{
    AbcDontCareLearner, GrammarEvolutionLearner, LearnedHypothesis, LearnerFailure,
    MemorizationLearner, ObservedTask, ResearchLearner, ResearchMethod, ResearchTools,
    RobddLearner, SatCegisLearner, TrialBudget,
};

pub fn default_adapters(tools: ResearchTools) -> Vec<Box<dyn ResearchLearner>> {
    vec![
        Box::new(LegacyRegistryLearner),
        Box::new(MdlEnumeratorLearner),
        Box::new(AbcDontCareLearner::new(tools.abc)),
        Box::new(RobddLearner),
        Box::new(SatCegisLearner),
        Box::new(GrammarEvolutionLearner::default()),
        Box::new(MemorizationLearner),
    ]
}

struct LegacyRegistryLearner;

impl ResearchLearner for LegacyRegistryLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::LegacyRegistry
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        _budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let scores = score_candidates(&observed.dataset())
            .map_err(|error| LearnerFailure::NoHypothesis(error.to_string()))?;
        let perfect = scores
            .iter()
            .filter(|score| score.mismatches == 0)
            .map(|score| score.family)
            .collect::<Vec<_>>();
        let [family] = perfect.as_slice() else {
            return Err(LearnerFailure::NoHypothesis(
                "legacy registry has no unique training-consistent family".into(),
            ));
        };
        Ok(LearnedHypothesis::Expression {
            expression: family_expression(*family),
            minimum_unique: Some(true),
            detail: "legacy four-family registry baseline".into(),
        })
    }
}

struct MdlEnumeratorLearner;

impl ResearchLearner for MdlEnumeratorLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::MdlEnumerator
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        _seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let timeout_millis = budget.timeout.as_millis().try_into().unwrap_or(u64::MAX);
        let config = MdlSearchConfig {
            max_description_cost: 8,
            max_generated_expressions: 500_000,
            max_semantic_classes: budget.max_nodes.min(100_000),
            timeout_millis,
            ..MdlSearchConfig::default()
        };
        let result = search_mdl(&observed.dataset(), &config).map_err(classify_occam_failure)?;
        let expression = match result.report.termination {
            SearchTermination::Found => result.expression.ok_or_else(|| {
                LearnerFailure::NoHypothesis(
                    "MDL search reported success without an expression".into(),
                )
            })?,
            SearchTermination::CostExhausted => {
                return Err(LearnerFailure::NoHypothesis(
                    "MDL search exhausted its description-cost bound".into(),
                ));
            }
            SearchTermination::ExpressionLimit | SearchTermination::SemanticClassLimit => {
                return Err(LearnerFailure::ResourceLimit(format!(
                    "MDL search stopped at {:?}",
                    result.report.termination
                )));
            }
            SearchTermination::Timeout => {
                return Err(LearnerFailure::Timeout(
                    "MDL search exceeded the trial timeout".into(),
                ));
            }
        };
        Ok(LearnedHypothesis::Expression {
            expression,
            minimum_unique: result.report.minimum_unique,
            detail: "cost-ordered generic MDL enumeration".into(),
        })
    }
}

fn classify_occam_failure(error: OccamError) -> LearnerFailure {
    match error {
        OccamError::ResourceLimit { .. } | OccamError::ArithmeticOverflow { .. } => {
            LearnerFailure::ResourceLimit(error.to_string())
        }
        _ => LearnerFailure::ToolError(error.to_string()),
    }
}

fn family_expression(family: ArithmeticFamily) -> Expr {
    match family {
        ArithmeticFamily::Add => Expr::binary(BinaryOp::Add, Expr::x(), Expr::y()),
        ArithmeticFamily::AbsDiff => Expr::abs_diff(Expr::x(), Expr::y()),
        ArithmeticFamily::Multiply => Expr::binary(BinaryOp::Multiply, Expr::x(), Expr::y()),
        ArithmeticFamily::SumOfSquares => Expr::binary(
            BinaryOp::Add,
            Expr::square(Expr::x()),
            Expr::square(Expr::y()),
        ),
    }
}
