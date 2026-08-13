#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum GateOp {
    And,
    Or,
    Xor,
    Nand,
    Nor,
    Xnor,
}

impl GateOp {
    pub fn apply(self, lhs: bool, rhs: bool) -> bool {
        match self {
            Self::And => lhs & rhs,
            Self::Or => lhs | rhs,
            Self::Xor => lhs ^ rhs,
            Self::Nand => !(lhs & rhs),
            Self::Nor => !(lhs | rhs),
            Self::Xnor => !(lhs ^ rhs),
        }
    }

    pub fn apply_word(self, lhs: u64, rhs: u64) -> u64 {
        match self {
            Self::And => lhs & rhs,
            Self::Or => lhs | rhs,
            Self::Xor => lhs ^ rhs,
            Self::Nand => !(lhs & rhs),
            Self::Nor => !(lhs | rhs),
            Self::Xnor => !(lhs ^ rhs),
        }
    }
}

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
pub enum Source {
    Input(usize),
    Wire(usize),
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
pub struct Operand {
    pub source: Source,
    pub inverted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Gate {
    pub output: usize,
    pub op: GateOp,
    pub lhs: Operand,
    pub rhs: Operand,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Circuit {
    pub input_count: usize,
    pub wire_count: usize,
    pub gates: Vec<Gate>,
    pub outputs: Vec<Operand>,
}
