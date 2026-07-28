pub mod benchmark;
pub mod circuit;
pub mod compiled;
pub mod dataset;
mod dataset_scan;
pub mod error;
pub mod generate;
pub mod learning;
pub mod limits;
pub mod metrics;
pub mod netlist;
pub mod optimize;
pub mod packed;
pub mod reference;
pub mod scalar;
pub mod synthesis;

pub use benchmark::{BenchmarkBackend, BenchmarkReport, TimingStatistics, run_benchmark};
pub use circuit::{Circuit, Gate, GateOp, Operand, Source};
pub use compiled::{
    CompiledCircuit, verify_compiled_prepacked, verify_compiled_prepacked_with_limits,
};
pub use dataset::{Dataset, Sample, parse_dataset, parse_dataset_with_limits};
pub use error::OccamError;
pub use generate::{ArithmeticOperation, generate_dataset, generate_dataset_with_limits};
pub use learning::{
    ArithmeticFamily, CandidateScore, LearnRequest, LearnResult, LearningReport, Manifest,
    ManifestInstance, TestInputs, WrittenInstance, decode_lsb, encode_lsb, infer_unique_family,
    learn_instance, load_written_instance, parse_commitment, parse_test_inputs,
    parse_test_inputs_with_limits, prediction_csv_from_circuit, score_candidates, sha256_hex,
    write_instance_artifacts, write_manifest,
};
pub use limits::{DEFAULT_LIMITS, ResourceLimits};
pub use metrics::{VerificationMetrics, verify, verify_with_limits};
pub use netlist::{parse_netlist, parse_netlist_with_limits};
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
pub use scalar::{evaluate, evaluate_with_limits};
pub use synthesis::{
    AttemptStatus, SynthesisAttempt, SynthesisCertificate, SynthesisLimits, SynthesisProblem,
    SynthesisStatus, synthesize_minimal,
};
