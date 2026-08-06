#![no_main]

use libfuzzer_sys::fuzz_target;
use occam71_rust::{parse_mapped_blif, parse_netlist};

fuzz_target!(|data: &[u8]| {
    if data.len() > 1024 * 1024 {
        return;
    }
    let Ok(source) = std::str::from_utf8(data) else {
        return;
    };
    if let Ok(mapped) = parse_mapped_blif(source)
        && let Ok(netlist) = mapped.into_official_netlist()
    {
        let reparsed = parse_netlist(&netlist).expect("mapped importer emitted invalid netlist");
        assert!(!reparsed.outputs.is_empty());
    }
});
