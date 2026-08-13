#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::parse_test_inputs;

fuzz_target!(|data: &[u8]| {
    if let Ok(source) = std::str::from_utf8(data) {
        let _ = parse_test_inputs(source);
    }
});
