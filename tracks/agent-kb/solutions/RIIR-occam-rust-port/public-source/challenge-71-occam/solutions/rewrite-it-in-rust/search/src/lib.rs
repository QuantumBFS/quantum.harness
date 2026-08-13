pub mod benchmark;
pub mod circuit;
pub mod compiled;
pub mod dataset;
mod dataset_scan;
pub mod error;
pub mod expression;
pub mod generate;
pub mod learning;
pub mod limits;
pub mod logic;
pub mod metrics;
pub mod netlist;
pub mod optimization;
pub mod optimize;
pub mod packed;
pub mod reference;
pub mod research;
pub mod scalar;
pub mod synthesis;

pub use benchmark::{BenchmarkBackend, BenchmarkReport, TimingStatistics, run_benchmark};
pub use circuit::{Circuit, Gate, GateOp, Operand, Source};
pub use compiled::{
    CompiledCircuit, verify_compiled_prepacked, verify_compiled_prepacked_with_limits,
};
pub use dataset::{Dataset, Sample, parse_dataset, parse_dataset_with_limits};
pub use error::OccamError;
pub use expression::{
    BinaryOp, CostSearchStats, Expr, ExprSemantics, MdlSearchConfig, MdlSearchReport,
    MdlSearchResult, SearchTermination, SemanticKey, compile_expression, evaluate_rows,
    parse_expression, search_mdl,
};
pub use generate::{ArithmeticOperation, generate_dataset, generate_dataset_with_limits};
pub use learning::{
    AnySolutionManifest, ArithmeticFamily, CandidateScore, LearnRequest, LearnResult,
    LearningReport, Manifest, ManifestInstance, MdlLearnRequest, MdlLearnResult, MdlLearningReport,
    ResearchSolutionManifest, TestInputs, WrittenInstance, decode_lsb, encode_lsb,
    infer_unique_family, learn_instance, learn_mdl, load_written_instance, parse_commitment,
    parse_test_inputs, parse_test_inputs_with_limits, prediction_csv_from_circuit,
    score_candidates, sha256_hex, write_instance_artifacts, write_manifest,
};
pub use limits::{DEFAULT_LIMITS, ResourceLimits};
pub use logic::{
    AbcCandidate, AbcFlowReport, AbcOptimizationConfig, AbcOptimizationResult, AbcPortfolioReport,
    ExternalCommandLimits, MappedNetwork, circuit_to_blif, compare_circuits_exhaustively,
    optimize_with_abc, parse_mapped_blif,
};
pub use metrics::{VerificationMetrics, verify, verify_with_limits};
pub use netlist::{parse_netlist, parse_netlist_with_limits};
pub use optimization::{
    CircuitWindow, PeepholeAttemptReport, PeepholeBoundReport, PeepholeConfig,
    PeepholeOptimizationReport, PeepholeOptimizationResult, WindowConfig, extract_windows,
    optimize_peepholes, rewrite_with_candidate,
};
pub use optimize::{CircuitBuilder, Signal, SynthesizedCircuit};
pub use packed::{
    PackedDataset, pack_dataset, pack_dataset_with_limits, parse_packed_dataset,
    parse_packed_dataset_with_limits, verify_packed, verify_prepacked,
    verify_prepacked_interpreted, verify_prepacked_interpreted_with_limits,
    verify_prepacked_reference, verify_prepacked_with_limits,
};
pub use reference::{
    ripple_carry_adder, ripple_carry_adder_with_limits, shift_add_multiplier,
    shift_add_multiplier_with_limits, synthesize_family, synthesize_family_with_limits,
};
pub use research::{
    AbcDontCareLearner, BddOrder, BddResult, EvolutionConfig, EvolutionResult, EvolutionTraceEntry,
    ExperimentConfig, GrammarEvolutionLearner, LearnedHypothesis, LearnerFailure,
    MemorizationLearner, ObservedTask, OracleTask, ResearchLearner, ResearchMethod, ResearchTools,
    RobddLearner, SEMANTIC_PROJECTION_EXCLUDED_FIELDS, SatCegisLearner, SemanticTrialRecord, Split,
    TaskClass, TaskManifest, TrialBudget, TrialKey, TrialRecord, TrialStatus, build_robdd,
    default_adapters, evolve, evolve_with_budget, expected_trial_keys, load_experiment_config,
    official_and_synthetic_tasks, peak_rss_bytes, render_dataset, render_partial_pla,
    render_semantic_jsonl, run_experiment, run_isolated_experiment, run_measured_trial, run_trial,
    run_trial_with_tools, semantic_projection, split_task, write_semantic_jsonl,
};
pub use scalar::{evaluate, evaluate_with_limits};
pub use synthesis::{
    AttemptStatus, SynthesisAttempt, SynthesisCertificate, SynthesisLimits, SynthesisProblem,
    SynthesisStatus, synthesize_minimal,
};
