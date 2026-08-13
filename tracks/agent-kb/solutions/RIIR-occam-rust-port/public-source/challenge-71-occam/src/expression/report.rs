use serde::{Deserialize, Serialize};

use crate::{BinaryOp, Expr};

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MdlSearchConfig {
    pub max_description_cost: usize,
    pub max_generated_expressions: usize,
    pub max_semantic_classes: usize,
    pub max_alternatives_per_class: usize,
    pub timeout_millis: u64,
    pub shift_amounts: Vec<u8>,
    pub enabled_binary_ops: Vec<BinaryOp>,
    pub enable_square: bool,
}

impl Default for MdlSearchConfig {
    fn default() -> Self {
        Self {
            max_description_cost: 8,
            max_generated_expressions: 2_000_000,
            max_semantic_classes: 250_000,
            max_alternatives_per_class: 8,
            timeout_millis: 30_000,
            shift_amounts: vec![1, 2, 3],
            enabled_binary_ops: vec![
                BinaryOp::Add,
                BinaryOp::Subtract,
                BinaryOp::AbsDiff,
                BinaryOp::Multiply,
                BinaryOp::BitXor,
                BinaryOp::BitAnd,
                BinaryOp::BitOr,
                BinaryOp::Min,
                BinaryOp::Max,
            ],
            enable_square: true,
        }
    }
}

impl MdlSearchConfig {
    pub fn for_tests() -> Self {
        Self {
            max_description_cost: 6,
            max_generated_expressions: 100_000,
            max_semantic_classes: 20_000,
            max_alternatives_per_class: 4,
            timeout_millis: 5_000,
            ..Self::default()
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SearchTermination {
    Found,
    CostExhausted,
    ExpressionLimit,
    SemanticClassLimit,
    Timeout,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CostSearchStats {
    pub description_cost: usize,
    pub generated_expressions: usize,
    pub evaluated_expressions: usize,
    pub retained_semantic_classes: usize,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MdlSearchReport {
    pub schema_version: u32,
    pub config: MdlSearchConfig,
    pub termination: SearchTermination,
    pub costs: Vec<CostSearchStats>,
    pub generated_expressions: usize,
    pub evaluated_expressions: usize,
    pub retained_semantic_classes: usize,
    pub description_cost: Option<usize>,
    pub minimum_unique: Option<bool>,
    pub equal_cost_expression_count: Option<usize>,
    pub alternatives: Vec<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MdlSearchResult {
    pub expression: Option<Expr>,
    pub report: MdlSearchReport,
}
