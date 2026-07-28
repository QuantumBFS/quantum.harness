mod equivalence;
mod peephole;
mod report;
mod rewrite;
mod window;

pub use peephole::{PeepholeConfig, optimize_peepholes};
pub use report::{
    PeepholeAttemptReport, PeepholeBoundReport, PeepholeOptimizationReport,
    PeepholeOptimizationResult,
};
pub use rewrite::rewrite_with_candidate;
pub use window::{CircuitWindow, WindowConfig, extract_windows};
