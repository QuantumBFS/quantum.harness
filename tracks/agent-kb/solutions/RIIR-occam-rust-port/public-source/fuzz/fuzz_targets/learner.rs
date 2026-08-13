#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::{DEFAULT_LIMITS, LearnRequest, learn_instance};

fuzz_target!(|data: &[u8]| {
    let mut parts = data.splitn(3, |byte| *byte == 0);
    let training = parts.next().and_then(|part| std::str::from_utf8(part).ok());
    let test_inputs = parts.next().and_then(|part| std::str::from_utf8(part).ok());
    let commitment = parts.next().and_then(|part| std::str::from_utf8(part).ok());
    let (Some(training_source), Some(test_inputs_source)) = (training, test_inputs) else {
        return;
    };

    let limits = occam71_rust::ResourceLimits {
        max_source_bytes: 16_384,
        max_inputs: 16,
        max_gates: 10_000,
        max_outputs: 16,
        max_samples: 256,
        max_input_width: 16,
        max_output_width: 16,
        max_dataset_bits: 65_536,
        max_packed_words: 8_192,
        max_generated_bytes: 65_536,
        ..DEFAULT_LIMITS
    };
    let _ = learn_instance(LearnRequest {
        instance: "fuzz",
        training_source,
        test_inputs_source,
        commitment_source: commitment.filter(|source| !source.is_empty()),
        limits: &limits,
    });
});
