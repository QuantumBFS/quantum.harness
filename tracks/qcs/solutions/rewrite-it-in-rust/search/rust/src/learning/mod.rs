mod family;
mod inputs;
mod learner;
mod prediction;
mod report;

pub use family::{ArithmeticFamily, CandidateScore, score_candidates};
pub use inputs::{
    TestInputs, decode_lsb, encode_lsb, parse_commitment, parse_test_inputs,
    parse_test_inputs_with_limits,
};
pub use learner::{LearnRequest, LearnResult, infer_unique_family, learn_instance};
pub use prediction::{prediction_csv_from_circuit, sha256_hex};
pub use report::{
    LearningReport, Manifest, ManifestInstance, WrittenInstance, load_written_instance,
    write_instance_artifacts, write_manifest,
};
