mod abc_dont_care;
mod adapters;
mod bdd;
mod evolution;
mod learner;
mod memory;
mod process;
mod projection;
mod rss;
mod runner;
mod sampling;
mod sat_cegis;
mod tasks;
mod trial;

pub use abc_dont_care::{AbcDontCareLearner, render_partial_pla};
pub use adapters::default_adapters;
pub use bdd::{BddOrder, BddResult, RobddLearner, build_robdd};
pub use evolution::{
    EvolutionConfig, EvolutionResult, EvolutionTraceEntry, GrammarEvolutionLearner, evolve,
    evolve_with_budget,
};
pub use learner::{LearnedHypothesis, LearnerFailure, ResearchLearner, ResearchTools, TrialBudget};
pub use memory::MemorizationLearner;
pub use process::{run_isolated_experiment, run_measured_trial};
pub use projection::{
    SEMANTIC_PROJECTION_EXCLUDED_FIELDS, SemanticTrialRecord, render_semantic_jsonl,
    semantic_projection, write_semantic_jsonl,
};
pub use rss::peak_rss_bytes;
pub use runner::{run_experiment, run_trial, run_trial_with_tools};
pub use sampling::{Split, split_task};
pub use sat_cegis::SatCegisLearner;
pub use tasks::{
    ObservedTask, OracleTask, TaskClass, TaskManifest, official_and_synthetic_tasks, render_dataset,
};
pub use trial::{
    ExperimentConfig, ResearchMethod, TrialKey, TrialRecord, TrialStatus, expected_trial_keys,
    load_experiment_config,
};
