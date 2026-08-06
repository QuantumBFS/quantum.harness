use std::{fs, path::PathBuf};

use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Audit {
    schema_version: u32,
    tools: Vec<ToolRecord>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ToolRecord {
    tool: String,
    version_output: String,
    executable_sha256: String,
    command: Vec<String>,
    input_sha256: String,
    output_sha256: String,
    output_normalization: String,
    observed_matches: usize,
    observed_total: usize,
    full_domain_mismatches: Option<usize>,
    full_domain_cases: Option<usize>,
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

#[test]
fn tool_audit_schema_requires_complete_provenance_and_verification() {
    let schema: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(
            workspace_root().join("experiments/occam-generalization-v2/tool-audit.schema.json"),
        )
        .unwrap(),
    )
    .unwrap();
    let required = schema["$defs"]["tool"]["required"].as_array().unwrap();
    for field in [
        "tool",
        "version_output",
        "executable_sha256",
        "command",
        "input_sha256",
        "output_sha256",
        "output_normalization",
        "observed_matches",
        "observed_total",
        "full_domain_mismatches",
        "full_domain_cases",
    ] {
        assert!(
            required.iter().any(|value| value.as_str() == Some(field)),
            "{field}"
        );
    }
}

#[test]
fn generated_audit_has_three_distinct_path_free_tool_records() {
    let path = workspace_root().join("experiments/occam-generalization-v2/tool-audit.json");
    let audit: Audit = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
    assert_eq!(audit.schema_version, 2);
    assert_eq!(audit.tools.len(), 3);
    let names = audit
        .tools
        .iter()
        .map(|record| record.tool.as_str())
        .collect::<std::collections::HashSet<_>>();
    assert_eq!(
        names,
        ["yosys", "yosys-abc", "espresso"].into_iter().collect()
    );
    for record in audit.tools {
        assert!(!record.version_output.trim().is_empty());
        assert_eq!(record.executable_sha256.len(), 64);
        assert_eq!(record.input_sha256.len(), 64);
        assert_eq!(record.output_sha256.len(), 64);
        assert!(matches!(
            record.output_normalization.as_str(),
            "none" | "strip one leading ABC timestamp banner comment"
        ));
        if record.tool == "yosys-abc" {
            assert_eq!(
                record.output_normalization,
                "strip one leading ABC timestamp banner comment"
            );
        } else {
            assert_eq!(record.output_normalization, "none");
        }
        assert_eq!(record.command[0], record.tool);
        assert!(
            record
                .command
                .iter()
                .all(|argument| !argument.starts_with('/'))
        );
        assert_eq!(record.observed_matches, record.observed_total);
        if let Some(cases) = record.full_domain_cases {
            assert!(cases > 0);
            assert_eq!(record.full_domain_mismatches, Some(0));
        }
    }
}
