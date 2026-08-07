use crate::graph::Graph;
use crate::request::Request;
use anyhow::{Context, Result, ensure};
use qmc::qmc::{GenericQMC, MatrixTermHandle};
use qmc::terms::tfim::TFIMTerm;
use qmc::traits::cluster_update::ClusterUpdater;
use qmc::traits::diagonal_update::DiagonalUpdate;
use qmc::traits::graph_traits::{GraphStateNavigator, TimeSlicedGraph};
use rand::SeedableRng;
use rand::rngs::SmallRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

const SEED_DOMAIN: &[u8] = b"qmc-sse-seed-v1";

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SerialObservations {
    pub energy: Vec<f64>,
    pub transverse_magnetization: Vec<f64>,
    pub m2: Vec<f64>,
    pub m4: Vec<f64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Bin {
    pub schema_version: String,
    pub adapter: String,
    pub bin_index: u64,
    pub sample_count: u64,
    pub serial_measurement_stride_samples: u64,
    pub serial_observations: SerialObservations,
    pub energy_sum: f64,
    pub energy_sum_squares: f64,
    pub transverse_magnetization_sum: f64,
    pub transverse_magnetization_sum_squares: f64,
    pub m2_sum: f64,
    pub m2_sum_squares: f64,
    pub m4_sum: f64,
    pub m4_sum_squares: f64,
    pub operator_count_sum: u64,
    pub time_slice_count_sum: u64,
    pub cluster_attempt_count: u64,
    pub cluster_accepted_count: u64,
    pub cluster_attempts_per_sweep: u64,
    pub sweep_count: u64,
    pub rng: String,
    pub seed_namespace: String,
    pub seed_derivation: String,
}

impl Bin {
    fn new(bin_index: u64, site_count: usize) -> Self {
        Self {
            schema_version: "qmc-sse-bin-v1".to_owned(),
            adapter: "QMC_SSE".to_owned(),
            bin_index,
            sample_count: 0,
            serial_measurement_stride_samples: 1,
            serial_observations: SerialObservations {
                energy: Vec::new(),
                transverse_magnetization: Vec::new(),
                m2: Vec::new(),
                m4: Vec::new(),
            },
            energy_sum: 0.0,
            energy_sum_squares: 0.0,
            transverse_magnetization_sum: 0.0,
            transverse_magnetization_sum_squares: 0.0,
            m2_sum: 0.0,
            m2_sum_squares: 0.0,
            m4_sum: 0.0,
            m4_sum_squares: 0.0,
            operator_count_sum: 0,
            time_slice_count_sum: 0,
            cluster_attempt_count: 0,
            cluster_accepted_count: 0,
            cluster_attempts_per_sweep: site_count as u64,
            sweep_count: 0,
            rng: "rand-0.9.5-SmallRng-Xoshiro256PlusPlus".to_owned(),
            seed_namespace: "QMC_SSE:qmc-sse-seed-v1".to_owned(),
            seed_derivation: "sha256:qmc-sse-seed-v1||u64be".to_owned(),
        }
    }

    pub fn validate(
        &self,
        expected_index: u64,
        bin_length: u64,
        thinning: u64,
        site_count: usize,
    ) -> Result<()> {
        ensure!(
            self.schema_version == "qmc-sse-bin-v1",
            "bin schema mismatch"
        );
        ensure!(self.adapter == "QMC_SSE", "bin adapter mismatch");
        ensure!(self.bin_index == expected_index, "bin index mismatch");
        ensure!(self.sample_count == bin_length, "bin sample count mismatch");
        ensure!(
            self.serial_measurement_stride_samples == 1
                && self.serial_observations.energy.len() == bin_length as usize
                && self.serial_observations.transverse_magnetization.len() == bin_length as usize
                && self.serial_observations.m2.len() == bin_length as usize
                && self.serial_observations.m4.len() == bin_length as usize,
            "bin serial retained-sample cadence mismatch"
        );
        ensure!(
            self.cluster_attempts_per_sweep == site_count as u64,
            "bin cluster sweep rule mismatch"
        );
        ensure!(
            self.rng == "rand-0.9.5-SmallRng-Xoshiro256PlusPlus",
            "bin RNG metadata mismatch"
        );
        ensure!(
            self.seed_namespace == "QMC_SSE:qmc-sse-seed-v1",
            "bin seed namespace mismatch"
        );
        ensure!(
            self.seed_derivation == "sha256:qmc-sse-seed-v1||u64be",
            "bin seed derivation mismatch"
        );
        let expected_sweeps = bin_length
            .checked_mul(thinning)
            .context("bin sweep count overflow")?;
        ensure!(
            self.sweep_count == expected_sweeps,
            "bin sweep count mismatch"
        );
        ensure!(
            self.cluster_attempt_count
                == self
                    .sweep_count
                    .checked_mul(site_count as u64)
                    .context("bin cluster attempt count overflow")?,
            "bin cluster attempt count mismatch"
        );
        ensure!(
            self.cluster_accepted_count <= self.cluster_attempt_count,
            "bin accepted clusters exceed attempts"
        );
        for value in [
            self.energy_sum,
            self.energy_sum_squares,
            self.transverse_magnetization_sum,
            self.transverse_magnetization_sum_squares,
            self.m2_sum,
            self.m2_sum_squares,
            self.m4_sum,
            self.m4_sum_squares,
        ] {
            ensure!(value.is_finite(), "bin contains a non-finite value");
        }
        ensure!(
            self.energy_sum_squares >= 0.0
                && self.transverse_magnetization_sum_squares >= 0.0
                && self.m2_sum >= 0.0
                && self.m2_sum_squares >= 0.0
                && self.m4_sum >= 0.0
                && self.m4_sum_squares >= 0.0,
            "bin contains an invalid primitive sum"
        );
        ensure!(
            self.m4_sum <= self.m2_sum && self.m2_sum <= self.sample_count as f64,
            "bin Pauli magnetization sums are out of range"
        );
        Ok(())
    }
}

struct Simulation {
    qmc: GenericQMC<bool, TFIMTerm<f64>>,
    x_handles: Vec<MatrixTermHandle>,
    rng: SmallRng,
    site_count: usize,
    beta: f64,
    field: f64,
}

impl Simulation {
    fn new(request: &Request, graph: &Graph) -> Self {
        let mut qmc = GenericQMC::<bool, TFIMTerm<f64>>::new(graph.site_count);
        let x_handles = (0..graph.site_count)
            .map(|site| qmc.add_term(TFIMTerm::X(request.field), [site]))
            .collect();
        for [left, right] in &graph.bonds {
            qmc.add_term(TFIMTerm::ZZ(-request.coupling), [*left, *right]);
        }
        let mut seed_hasher = Sha256::new();
        seed_hasher.update(SEED_DOMAIN);
        seed_hasher.update(request.seed.to_be_bytes());
        let seed: [u8; 32] = seed_hasher.finalize().into();
        Self {
            qmc,
            x_handles,
            rng: SmallRng::from_seed(seed),
            site_count: graph.site_count,
            beta: request.beta,
            field: request.field,
        }
    }

    fn sweep(&mut self) -> Result<u64> {
        self.qmc.maintain_maximum_filling_fraction(0.5, 16);
        self.qmc.diagonal_update(self.beta, &mut self.rng);
        let mut accepted = 0;
        for _ in 0..self.site_count {
            if self
                .qmc
                .cluster_update(&mut self.rng)
                .context("QMC_SSE cluster update failed")?
            {
                accepted += 1;
            }
        }
        debug_assert!(self.qmc.check_consistency());
        Ok(accepted)
    }

    fn measure_into(&self, bin: &mut Bin) -> Result<()> {
        let energy = self.qmc.get_energy(self.beta);
        let x_count: usize = self
            .x_handles
            .iter()
            .map(|handle| self.qmc.get_count_for_term(handle))
            .sum();
        let mx = (x_count as f64 / self.beta) / (self.field * self.site_count as f64) - 1.0;
        let magnetization = self
            .qmc
            .get_initial_state()
            .iter()
            .map(|state| if *state { -1.0 } else { 1.0 })
            .sum::<f64>()
            / self.site_count as f64;
        let m2 = magnetization * magnetization;
        let m4 = m2 * m2;
        for value in [energy, mx, m2, m4] {
            ensure!(
                value.is_finite(),
                "QMC_SSE produced a non-finite observable"
            );
        }
        bin.sample_count += 1;
        bin.serial_observations.energy.push(energy);
        bin.serial_observations.transverse_magnetization.push(mx);
        bin.serial_observations.m2.push(m2);
        bin.serial_observations.m4.push(m4);
        bin.energy_sum += energy;
        bin.energy_sum_squares += energy * energy;
        bin.transverse_magnetization_sum += mx;
        bin.transverse_magnetization_sum_squares += mx * mx;
        bin.m2_sum += m2;
        bin.m2_sum_squares += m2 * m2;
        bin.m4_sum += m4;
        bin.m4_sum_squares += m4 * m4;
        bin.operator_count_sum = bin
            .operator_count_sum
            .checked_add(self.qmc.get_number_of_non_identity_operators() as u64)
            .context("operator count sum overflow")?;
        bin.time_slice_count_sum = bin
            .time_slice_count_sum
            .checked_add(self.qmc.num_time_slices() as u64)
            .context("time-slice count sum overflow")?;
        Ok(())
    }
}

pub fn generate_bins(request: &Request, graph: &Graph) -> Result<Vec<Bin>> {
    let mut simulation = Simulation::new(request, graph);
    for _ in 0..request.thermalization_sweeps {
        simulation.sweep()?;
    }

    let mut bins = Vec::with_capacity(request.total_bins() as usize);
    for bin_index in 0..request.total_bins() {
        let mut bin = Bin::new(bin_index, graph.site_count);
        for _ in 0..request.bin_length {
            for _ in 0..request.thinning {
                bin.cluster_accepted_count += simulation.sweep()?;
                bin.cluster_attempt_count += graph.site_count as u64;
                bin.sweep_count += 1;
            }
            simulation.measure_into(&mut bin)?;
        }
        bin.validate(
            bin_index,
            request.bin_length,
            request.thinning,
            graph.site_count,
        )?;
        bins.push(bin);
    }
    Ok(bins)
}
