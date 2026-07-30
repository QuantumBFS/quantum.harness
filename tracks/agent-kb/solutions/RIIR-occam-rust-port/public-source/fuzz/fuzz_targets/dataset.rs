#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::parse_dataset;

fuzz_target!(|data: &[u8]| {
    if let Ok(source) = std::str::from_utf8(data)
        && let Ok(dataset) = parse_dataset(source)
    {
        assert!(!dataset.samples.is_empty());
        assert!(dataset.input_width > 0);
        assert!(dataset.output_width > 0);
        for sample in dataset.samples {
            assert_eq!(sample.input.len(), dataset.input_width);
            assert_eq!(sample.expected.len(), dataset.output_width);
        }
    }
});
