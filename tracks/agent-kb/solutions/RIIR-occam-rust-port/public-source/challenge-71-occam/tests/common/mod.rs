#![allow(dead_code)]

use std::{
    collections::HashSet,
    fs,
    path::{Path, PathBuf},
};

use serde::Deserialize;

pub const OFFICIAL_ARCHIVE_SHA256: &str =
    "c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b";

#[derive(Debug, Deserialize)]
pub struct OracleManifest {
    pub schema_version: u32,
    pub archive: OracleArchive,
    pub cases: Vec<OracleCase>,
}

#[derive(Debug, Deserialize)]
pub struct OracleArchive {
    pub url: String,
    pub sha256: String,
}

#[derive(Debug, Deserialize)]
pub struct OracleCase {
    pub name: String,
    pub circuit: CircuitSource,
    pub dataset: String,
    pub gates: usize,
    pub samples: usize,
    pub exact_matches: usize,
    pub correct_bits: usize,
    pub total_bits: usize,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum CircuitSource {
    OfficialFile { path: String },
    GeneratedAdder { bits: usize },
    GeneratedMultiplier { bits: usize },
}

pub fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate is a workspace member")
        .to_owned()
}

pub fn vendor_root() -> PathBuf {
    workspace_root().join("vendor/occam-circuit")
}

pub fn manifest_path() -> PathBuf {
    workspace_root().join("tests/oracles/occam-v1.json")
}

pub fn load_manifest() -> OracleManifest {
    let source = fs::read_to_string(manifest_path()).expect("read oracle manifest");
    let manifest: OracleManifest = serde_json::from_str(&source).expect("parse oracle manifest");
    validate_manifest(&manifest);
    manifest
}

pub fn validate_manifest(manifest: &OracleManifest) {
    assert_eq!(manifest.schema_version, 1, "unsupported manifest schema");
    assert_eq!(manifest.archive.sha256, OFFICIAL_ARCHIVE_SHA256);
    assert!(manifest.archive.url.starts_with("https://github.com/"));
    assert!(!manifest.cases.is_empty());
    let mut names = HashSet::new();
    for case in &manifest.cases {
        assert!(names.insert(&case.name), "duplicate case {}", case.name);
        assert!(!case.dataset.is_empty());
        assert!(case.samples > 0);
        assert!(case.exact_matches <= case.samples);
        assert!(case.correct_bits <= case.total_bits);
        assert!(case.total_bits > 0);
        match &case.circuit {
            CircuitSource::OfficialFile { path } => assert!(!path.is_empty()),
            CircuitSource::GeneratedAdder { bits }
            | CircuitSource::GeneratedMultiplier { bits } => assert!(*bits > 0),
        }
    }
}

pub fn materialize_circuit(case: &OracleCase, vendor: &Path) -> String {
    match &case.circuit {
        CircuitSource::OfficialFile { path } => {
            fs::read_to_string(vendor.join(path)).expect("read official circuit")
        }
        CircuitSource::GeneratedAdder { bits } => {
            occam71_rust::ripple_carry_adder(*bits).expect("generate adder")
        }
        CircuitSource::GeneratedMultiplier { bits } => {
            occam71_rust::shift_add_multiplier(*bits).expect("generate multiplier")
        }
    }
}
