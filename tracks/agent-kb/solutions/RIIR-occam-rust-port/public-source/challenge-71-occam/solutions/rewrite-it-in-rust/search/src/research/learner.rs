use std::{path::PathBuf, time::Duration};

use thiserror::Error;

use crate::Expr;

use super::{ObservedTask, ResearchMethod, TrialStatus};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TrialBudget {
    pub timeout: Duration,
    pub max_gates: usize,
    pub max_nodes: usize,
}

impl Default for TrialBudget {
    fn default() -> Self {
        Self {
            timeout: Duration::from_secs(30),
            max_gates: crate::DEFAULT_LIMITS.max_gates,
            max_nodes: 250_000,
        }
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ResearchTools {
    pub abc: Option<PathBuf>,
    pub espresso: Option<PathBuf>,
    pub yosys: Option<PathBuf>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum LearnedHypothesis {
    Expression {
        expression: Expr,
        minimum_unique: Option<bool>,
        detail: String,
    },
    Circuit {
        netlist: String,
        description_length: Option<usize>,
        minimum_unique: Option<bool>,
        detail: String,
    },
}

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum LearnerFailure {
    #[error("{0}")]
    NoHypothesis(String),
    #[error("{0}")]
    Unsupported(String),
    #[error("{0}")]
    Timeout(String),
    #[error("{0}")]
    ResourceLimit(String),
    #[error("{0}")]
    ToolError(String),
}

impl LearnerFailure {
    pub fn status(&self) -> TrialStatus {
        match self {
            Self::NoHypothesis(_) => TrialStatus::NoHypothesis,
            Self::Unsupported(_) => TrialStatus::Unsupported,
            Self::Timeout(_) => TrialStatus::Timeout,
            Self::ResourceLimit(_) => TrialStatus::ResourceLimit,
            Self::ToolError(_) => TrialStatus::Error,
        }
    }
}

pub trait ResearchLearner: Send + Sync {
    fn method(&self) -> ResearchMethod;

    fn fit(
        &self,
        observed: &ObservedTask,
        seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure>;
}
