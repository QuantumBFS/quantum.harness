use rand::{SeedableRng, seq::SliceRandom};
use rand_chacha::ChaCha8Rng;
use sha2::{Digest, Sha256};

use crate::{OccamError, research::OracleTask};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Split {
    pub observed_indices: Vec<usize>,
    pub held_out_indices: Vec<usize>,
}

pub fn split_task(
    task: &OracleTask,
    fraction: f64,
    seed: u64,
    experiment_seed: u64,
) -> Result<Split, OccamError> {
    if !fraction.is_finite() || fraction <= 0.0 || fraction >= 1.0 {
        return Err(OccamError::Validation(format!(
            "research fraction must be in (0,1), got {fraction}"
        )));
    }
    let rows = task.full_domain().samples.len();
    let observed = ((rows as f64 * fraction).round() as usize).max(1);
    let basis_points = (fraction * 100_000.0).round() as u64;
    let mut hasher = Sha256::new();
    hasher.update(experiment_seed.to_le_bytes());
    hasher.update(task.id.as_bytes());
    hasher.update(basis_points.to_le_bytes());
    hasher.update(seed.to_le_bytes());
    let digest: [u8; 32] = hasher.finalize().into();
    let mut rng = ChaCha8Rng::from_seed(digest);
    let mut indices = (0..rows).collect::<Vec<_>>();
    indices.shuffle(&mut rng);
    let mut observed_indices = indices[..observed].to_vec();
    let mut held_out_indices = indices[observed..].to_vec();
    observed_indices.sort_unstable();
    held_out_indices.sort_unstable();
    Ok(Split {
        observed_indices,
        held_out_indices,
    })
}
