use crate::request::{canonical_bytes, sha256};
use crate::secure_fs::{open_absolute_file, read_regular_file_limited};
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::path::Path;

const MAX_LINEAR_SIZE: usize = 96;
const MAX_SITE_COUNT: usize = 2 * MAX_LINEAR_SIZE * MAX_LINEAR_SIZE;
const MAX_BOND_COUNT: usize = 3 * MAX_LINEAR_SIZE * MAX_LINEAR_SIZE;
const MAX_GRAPH_BYTES: u64 = 2 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Graph {
    pub lattice: String,
    pub length: usize,
    pub site_count: usize,
    pub bonds: Vec<[usize; 2]>,
    pub sha256: String,
}

#[derive(Serialize)]
struct GraphPayload<'a> {
    bonds: &'a [[usize; 2]],
    lattice: &'a str,
    length: usize,
    site_count: usize,
}

fn canonical_bond(left: usize, right: usize) -> [usize; 2] {
    if left < right {
        [left, right]
    } else {
        [right, left]
    }
}

fn triangular_bonds(length: usize) -> Vec<[usize; 2]> {
    let mut bonds = BTreeSet::new();
    for y in 0..length {
        for x in 0..length {
            let left = x + length * y;
            for (dx, dy) in [(1_isize, 0_isize), (0, 1), (1, -1)] {
                let nx = (x as isize + dx).rem_euclid(length as isize) as usize;
                let ny = (y as isize + dy).rem_euclid(length as isize) as usize;
                bonds.insert(canonical_bond(left, nx + length * ny));
            }
        }
    }
    bonds.into_iter().collect()
}

fn honeycomb_bonds(length: usize) -> Vec<[usize; 2]> {
    let mut bonds = BTreeSet::new();
    for y in 0..length {
        for x in 0..length {
            let a = 2 * (x + length * y);
            let neighbors = [
                (x, y),
                ((x + length - 1) % length, y),
                (x, (y + length - 1) % length),
            ];
            for (nx, ny) in neighbors {
                bonds.insert(canonical_bond(a, 2 * (nx + length * ny) + 1));
            }
        }
    }
    bonds.into_iter().collect()
}

impl Graph {
    pub fn load(path: &Path, requested_hash: &str) -> Result<Self> {
        let descriptor = open_absolute_file(path)
            .with_context(|| format!("cannot securely open graph {}", path.display()))?;
        let bytes = read_regular_file_limited(descriptor, "graph", MAX_GRAPH_BYTES)?;
        let graph: Self = serde_json::from_slice(&bytes).context("invalid graph JSON")?;
        graph.validate(requested_hash)?;
        Ok(graph)
    }

    fn validate(&self, requested_hash: &str) -> Result<()> {
        let payload = GraphPayload {
            bonds: &self.bonds,
            lattice: &self.lattice,
            length: self.length,
            site_count: self.site_count,
        };
        let computed = sha256(&canonical_bytes(&payload)?);
        ensure!(self.sha256 == computed, "graph embedded SHA256 mismatch");
        ensure!(requested_hash == computed, "graph request SHA256 mismatch");
        ensure!(
            self.length <= MAX_LINEAR_SIZE,
            "graph length exceeds pre-allocation ceiling L<=96"
        );
        ensure!(
            self.site_count <= MAX_SITE_COUNT,
            "graph site_count exceeds pre-allocation ceiling"
        );
        ensure!(
            self.bonds.len() <= MAX_BOND_COUNT,
            "graph bond count exceeds pre-allocation ceiling"
        );

        let expected_bonds = match self.lattice.as_str() {
            "triangular" => {
                ensure!(
                    self.length >= 3,
                    "graph triangular length must be at least 3"
                );
                let expected_sites = self
                    .length
                    .checked_mul(self.length)
                    .context("graph triangular site_count overflow")?;
                ensure!(
                    self.site_count == expected_sites,
                    "graph triangular site_count mismatch"
                );
                triangular_bonds(self.length)
            }
            "honeycomb" => {
                ensure!(
                    self.length >= 2,
                    "graph honeycomb length must be at least 2"
                );
                let expected_sites = self
                    .length
                    .checked_mul(self.length)
                    .and_then(|value| value.checked_mul(2))
                    .context("graph honeycomb site_count overflow")?;
                ensure!(
                    self.site_count == expected_sites,
                    "graph honeycomb site_count mismatch"
                );
                honeycomb_bonds(self.length)
            }
            _ => anyhow::bail!("graph lattice is unsupported"),
        };
        ensure!(
            self.bonds == expected_bonds,
            "graph topology is not the canonical periodic lattice"
        );
        Ok(())
    }
}
