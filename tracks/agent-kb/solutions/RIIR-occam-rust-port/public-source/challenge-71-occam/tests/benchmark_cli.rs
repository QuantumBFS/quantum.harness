use std::{fs, path::PathBuf, process::Command};

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

#[test]
fn writes_complete_benchmark_json() {
    for backend in ["scalar", "packed", "compiled"] {
        let json = std::env::temp_dir().join(format!(
            "occam71-benchmark-{}-{backend}.json",
            std::process::id()
        ));
        let output = Command::new(env!("CARGO_BIN_EXE_occam71_rust"))
            .args([
                "benchmark",
                "--backend",
                backend,
                "--circuit",
                fixture("add-n2.txt").to_str().unwrap(),
                "--dataset",
                fixture("add-n2.csv").to_str().unwrap(),
                "--warmup",
                "2",
                "--iterations",
                "5",
                "--json",
                json.to_str().unwrap(),
            ])
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let report: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&json).unwrap()).unwrap();
        assert_eq!(report["backend"], backend);
        assert_eq!(report["samples"], 16);
        assert_eq!(report["gates"], 7);
        assert_eq!(report["schema_version"], 3);
        assert_eq!(report["measured_iterations"], 5);
        assert_eq!(report["batch_count"], 5);
        assert_eq!(report["raw_iterations_ns"].as_array().unwrap().len(), 25);
        assert_eq!(report["batch_medians_ns"].as_array().unwrap().len(), 5);
        assert!(report["evaluation"]["median_ns"].as_u64().unwrap() > 0);
        assert!(report["circuit_parse_ns"].as_u64().is_some());
        assert!(report["scalar_dataset_parse_ns"].as_u64().unwrap() > 0);
        assert!(report["legacy_pack_ns"].as_u64().unwrap() > 0);
        assert!(report["direct_packed_parse_ns"].as_u64().unwrap() > 0);
        assert!(report["compilation_ns"].as_u64().unwrap() > 0);
        assert!(report["one_shot_ns"].as_u64().unwrap() > 0);
        for field in [
            "scalar_dataset_parse_iterations_ns",
            "legacy_pack_iterations_ns",
            "direct_packed_parse_iterations_ns",
            "compilation_iterations_ns",
        ] {
            assert_eq!(report[field].as_array().unwrap().len(), 5);
        }
        assert!(report["direct_packed_parse"]["median_ns"].as_u64().unwrap() > 0);
        assert!(
            report["evaluation"]["standard_deviation_ns"]
                .as_f64()
                .unwrap()
                >= 0.0
        );
        assert!(report["samples_per_second_at_median"].as_f64().unwrap() > 0.0);
        fs::remove_file(json).unwrap();
    }
}
