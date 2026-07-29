use crate::config::RunConfig;
use crate::disorder::{sample_row, DisorderRow};
use crate::rng::{derive_seed, make_rng};
use crate::transfer::apply_transfer;
use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone)]
pub struct ProductState {
    width: usize,
    vector: Vec<f64>,
    scratch: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct JointBlock {
    pub block_index: usize,
    pub phi_by_width: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReplicaEstimate {
    pub replica: usize,
    pub seed: u64,
    pub widths: Vec<usize>,
    pub blocks: Vec<JointBlock>,
    pub negative_bonds: usize,
    pub total_bonds: usize,
}

impl ProductState {
    pub fn new(width: usize) -> Result<Self> {
        let dimension = 1_usize
            .checked_shl(width as u32)
            .ok_or_else(|| anyhow::anyhow!("transfer width L={width} is too large"))?;
        if width < 2 {
            bail!("transfer width L must be at least 2");
        }
        let initial = 1.0 / dimension as f64;
        Ok(Self {
            width,
            vector: vec![initial; dimension],
            scratch: vec![0.0; dimension],
        })
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn l1_norm(&self) -> f64 {
        self.vector.iter().sum()
    }

    pub fn advance(&mut self, k: f64, row: &DisorderRow) -> Result<f64> {
        apply_transfer(self.width, k, row, &self.vector, &mut self.scratch)?;
        let norm: f64 = self.scratch.iter().sum();
        if !norm.is_finite() || norm <= 0.0 {
            bail!(
                "transfer product at width {} produced invalid L1 norm {norm}",
                self.width
            );
        }
        for value in &mut self.scratch {
            *value /= norm;
        }
        std::mem::swap(&mut self.vector, &mut self.scratch);
        Ok(norm.ln())
    }
}

pub fn estimate_replica(config: &RunConfig, replica: usize) -> Result<ReplicaEstimate> {
    config.validate()?;
    if replica >= config.disorder.replicas {
        bail!(
            "replica index {replica} is outside configured range 0..{}",
            config.disorder.replicas
        );
    }

    let max_width = *config
        .widths
        .last()
        .ok_or_else(|| anyhow::anyhow!("widths must not be empty"))?;
    let seed = derive_seed(config.base_seed, replica, 0);
    let mut rng = make_rng(seed);
    let mut states: Vec<ProductState> = config
        .widths
        .iter()
        .map(|&width| ProductState::new(width))
        .collect::<Result<_>>()?;
    let mut negative_bonds = 0;
    let mut total_bonds = 0;

    for _ in 0..config.disorder.burn_in_rows {
        let row = sample_row(max_width, config.antiferromagnetic_probability, &mut rng)?;
        count_bonds(&row, &mut negative_bonds, &mut total_bonds);
        for state in &mut states {
            state.advance(config.nishimori_k, &row)?;
        }
    }

    let block_count = config.disorder.measurement_rows / config.disorder.block_rows;
    let mut blocks = Vec::with_capacity(block_count);
    for block_index in 0..block_count {
        let mut sums = vec![0.0; states.len()];
        for _ in 0..config.disorder.block_rows {
            let row = sample_row(max_width, config.antiferromagnetic_probability, &mut rng)?;
            count_bonds(&row, &mut negative_bonds, &mut total_bonds);
            for (sum, state) in sums.iter_mut().zip(&mut states) {
                *sum += state.advance(config.nishimori_k, &row)?;
            }
        }
        let rows = config.disorder.block_rows as f64;
        let phi_by_width = sums
            .into_iter()
            .zip(&config.widths)
            .map(|(sum, &width)| sum / (rows * width as f64))
            .collect();
        blocks.push(JointBlock {
            block_index,
            phi_by_width,
        });
    }

    Ok(ReplicaEstimate {
        replica,
        seed,
        widths: config.widths.clone(),
        blocks,
        negative_bonds,
        total_bonds,
    })
}

fn count_bonds(row: &DisorderRow, negative: &mut usize, total: &mut usize) {
    *negative += row
        .horizontal
        .iter()
        .chain(&row.vertical)
        .filter(|&&bond| bond == -1)
        .count();
    *total += row.horizontal.len() + row.vertical.len();
}
