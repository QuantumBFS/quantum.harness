#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::{pack_dataset, parse_dataset, parse_packed_dataset};

fuzz_target!(|data: &[u8]| {
    let direct = parse_packed_dataset(data);
    if let Ok(source) = std::str::from_utf8(data) {
        let scalar = parse_dataset(source);
        match (scalar, direct) {
            (Ok(scalar), Ok(direct)) => {
                assert_eq!(pack_dataset(&scalar).unwrap(), direct);
            }
            (Err(scalar), Err(direct)) => {
                assert_eq!(scalar.to_string(), direct.to_string());
            }
            (scalar, direct) => {
                panic!("parser outcome mismatch: scalar={scalar:?}, direct={direct:?}");
            }
        }
    } else {
        assert!(direct.is_err(), "non-UTF-8 dataset was accepted");
    }
});
