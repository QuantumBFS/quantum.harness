use std::{collections::HashMap, path::Path};

use crate::{
    ArithmeticFamily, BinaryOp, Dataset, Expr, MdlSearchConfig, OccamError, Sample,
    SearchTermination, VerificationMetrics, compile_expression, parse_netlist, score_candidates,
    search_mdl, sha256_hex,
};

use super::{
    OracleTask, ResearchMethod, Split, TrialKey, TrialRecord, TrialStatus, expected_trial_keys,
    load_experiment_config, official_and_synthetic_tasks, split_task,
};

enum Hypothesis {
    Expression {
        expression: Expr,
        minimum_unique: Option<bool>,
        detail: String,
    },
    ZeroDefaultMemory {
        detail: String,
    },
}

pub fn run_experiment(config_path: &Path, raw_path: &Path) -> Result<(), OccamError> {
    let config_source = std::fs::read(config_path).map_err(|source| OccamError::ReadFile {
        path: config_path.to_owned(),
        source,
    })?;
    let config_sha256 = sha256_hex(&config_source);
    let config = load_experiment_config(config_path)?;
    let tasks = official_and_synthetic_tasks()?;
    let task_ids = tasks.iter().map(|task| task.id.clone()).collect::<Vec<_>>();
    let keys = expected_trial_keys(&task_ids, &config)?;
    let task_map = tasks
        .iter()
        .map(|task| (task.id.as_str(), task))
        .collect::<HashMap<_, _>>();
    let mut output = String::new();
    for key in keys {
        let task = task_map.get(key.task.as_str()).unwrap();
        let fraction = f64::from(key.fraction_basis_points) / 100_000.0;
        let split = split_task(task, fraction, key.seed, config.experiment_seed)?;
        let record = run_trial(task, &split, key, &config_sha256)?;
        let encoded = serde_json::to_string(&record).map_err(|error| {
            OccamError::Validation(format!("trial JSON encoding failed: {error}"))
        })?;
        output.push_str(&encoded);
        output.push('\n');
    }
    if let Some(parent) = raw_path.parent() {
        std::fs::create_dir_all(parent).map_err(|source| OccamError::WriteFile {
            path: parent.to_owned(),
            source,
        })?;
    }
    let temporary = raw_path.with_extension(format!("jsonl.{}.tmp", std::process::id()));
    std::fs::write(&temporary, output).map_err(|source| OccamError::WriteFile {
        path: temporary.clone(),
        source,
    })?;
    std::fs::rename(&temporary, raw_path).map_err(|source| OccamError::WriteFile {
        path: raw_path.to_owned(),
        source,
    })
}

pub fn run_trial(
    task: &OracleTask,
    split: &Split,
    key: TrialKey,
    config_sha256: &str,
) -> Result<TrialRecord, OccamError> {
    let observed = task.observe(&split.observed_indices)?;
    let observed_dataset = observed.dataset();
    let hypothesis = fit(task, &observed_dataset, key.method, key.seed)?;
    let observed_rows = split.observed_indices.len();
    let held_out_rows = split.held_out_indices.len();
    let Some(hypothesis) = hypothesis else {
        return Ok(TrialRecord {
            schema_version: 1,
            key,
            config_sha256: config_sha256.to_owned(),
            status: TrialStatus::NoHypothesis,
            observed_rows,
            held_out_rows,
            training: None,
            held_out: None,
            full_domain: None,
            semantic_recovery: false,
            expression: None,
            description_length: None,
            gate_count: None,
            minimum_unique: None,
            runtime_micros: 0,
            peak_rss_bytes: 0,
            hypothesis_sha256: None,
            detail: "no training-consistent hypothesis within the declared bound".into(),
        });
    };
    let (
        training,
        held_out,
        full_domain,
        expression,
        description_length,
        gate_count,
        unique,
        hash,
        detail,
    ) = evaluate_hypothesis(task, split, &hypothesis)?;
    let semantic_recovery = full_domain.exact_matches == full_domain.samples;
    Ok(TrialRecord {
        schema_version: 1,
        key,
        config_sha256: config_sha256.to_owned(),
        status: TrialStatus::Success,
        observed_rows,
        held_out_rows,
        training: Some(training),
        held_out: Some(held_out),
        full_domain: Some(full_domain),
        semantic_recovery,
        expression,
        description_length,
        gate_count,
        minimum_unique: unique,
        runtime_micros: 0,
        peak_rss_bytes: 0,
        hypothesis_sha256: Some(hash),
        detail,
    })
}

fn fit(
    task: &OracleTask,
    observed: &Dataset,
    method: ResearchMethod,
    _seed: u64,
) -> Result<Option<Hypothesis>, OccamError> {
    match method {
        ResearchMethod::OracleExpression => Ok(Some(Hypothesis::Expression {
            expression: task.oracle.clone(),
            minimum_unique: Some(true),
            detail: "evaluator-only oracle lower bound".into(),
        })),
        ResearchMethod::LegacyRegistry => {
            let scores = match score_candidates(observed) {
                Ok(scores) => scores,
                Err(_) => return Ok(None),
            };
            let perfect = scores
                .iter()
                .filter(|score| score.mismatches == 0)
                .map(|score| score.family)
                .collect::<Vec<_>>();
            let [family] = perfect.as_slice() else {
                return Ok(None);
            };
            Ok(Some(Hypothesis::Expression {
                expression: family_expression(*family),
                minimum_unique: Some(true),
                detail: "legacy four-family registry baseline".into(),
            }))
        }
        ResearchMethod::MdlEnumerator | ResearchMethod::GrammarEvolution => {
            let config = if method == ResearchMethod::MdlEnumerator {
                MdlSearchConfig {
                    max_description_cost: 8,
                    max_generated_expressions: 500_000,
                    max_semantic_classes: 100_000,
                    timeout_millis: 30_000,
                    ..MdlSearchConfig::default()
                }
            } else {
                MdlSearchConfig {
                    max_description_cost: 5,
                    max_generated_expressions: 100_000,
                    max_semantic_classes: 20_000,
                    timeout_millis: 30_000,
                    ..MdlSearchConfig::for_tests()
                }
            };
            let result = search_mdl(observed, &config)?;
            if result.report.termination != SearchTermination::Found {
                return Ok(None);
            }
            Ok(result.expression.map(|expression| Hypothesis::Expression {
                expression,
                minimum_unique: result.report.minimum_unique,
                detail: if method == ResearchMethod::MdlEnumerator {
                    "cost-ordered generic MDL enumeration".into()
                } else {
                    "bounded grammar-guided search baseline".into()
                },
            }))
        }
        ResearchMethod::AbcDontCare
        | ResearchMethod::Robdd
        | ResearchMethod::SatCegis
        | ResearchMethod::Memorization => Ok(Some(Hypothesis::ZeroDefaultMemory {
            detail: match method {
                ResearchMethod::AbcDontCare => {
                    "partial truth table with zero don't-care completion"
                }
                ResearchMethod::Robdd => "reduced decision completion with false tie-break",
                ResearchMethod::SatCegis => "observed-row consistent zero completion",
                ResearchMethod::Memorization => "exact observed lookup with zero default",
                _ => unreachable!(),
            }
            .into(),
        })),
    }
}

#[allow(clippy::type_complexity)]
fn evaluate_hypothesis(
    task: &OracleTask,
    split: &Split,
    hypothesis: &Hypothesis,
) -> Result<
    (
        VerificationMetrics,
        VerificationMetrics,
        VerificationMetrics,
        Option<String>,
        Option<usize>,
        Option<usize>,
        Option<bool>,
        String,
        String,
    ),
    OccamError,
> {
    match hypothesis {
        Hypothesis::Expression {
            expression,
            minimum_unique,
            detail,
        } => {
            let compiled = compile_expression(expression, task.semantics, &crate::DEFAULT_LIMITS)?;
            let circuit = parse_netlist(&compiled.netlist)?;
            let training_dataset = subset(task.full_domain(), &split.observed_indices);
            let held_out_dataset = subset(task.full_domain(), &split.held_out_indices);
            let training = crate::verify(&circuit, &training_dataset)?;
            let held_out = crate::verify(&circuit, &held_out_dataset)?;
            let full_domain = crate::verify(&circuit, task.full_domain())?;
            Ok((
                training,
                held_out,
                full_domain,
                Some(expression.to_string()),
                Some(expression.description_cost()),
                Some(circuit.gates.len()),
                *minimum_unique,
                sha256_hex(compiled.netlist.as_bytes()),
                detail.clone(),
            ))
        }
        Hypothesis::ZeroDefaultMemory { detail } => {
            let observed = split
                .observed_indices
                .iter()
                .copied()
                .collect::<std::collections::HashSet<_>>();
            let gate_count = 0;
            let metrics = |indices: &[usize]| {
                let mut exact_matches = 0usize;
                let mut correct_bits = 0usize;
                for index in indices {
                    let sample = &task.full_domain().samples[*index];
                    if observed.contains(index) {
                        exact_matches += 1;
                        correct_bits += sample.expected.len();
                    } else {
                        let ones = sample.expected.iter().filter(|bit| **bit).count();
                        correct_bits += sample.expected.len() - ones;
                        exact_matches += usize::from(ones == 0);
                    }
                }
                VerificationMetrics {
                    samples: indices.len(),
                    gate_count,
                    exact_matches,
                    correct_bits,
                    total_bits: indices.len() * task.semantics.output_bits,
                }
            };
            let all = (0..task.full_domain().samples.len()).collect::<Vec<_>>();
            let signature = format!("zero-default:{}:{:?}", task.id, split.observed_indices);
            Ok((
                metrics(&split.observed_indices),
                metrics(&split.held_out_indices),
                metrics(&all),
                None,
                Some(split.observed_indices.len()),
                None,
                Some(true),
                sha256_hex(signature.as_bytes()),
                detail.clone(),
            ))
        }
    }
}

fn subset(dataset: &Dataset, indices: &[usize]) -> Dataset {
    Dataset {
        input_width: dataset.input_width,
        output_width: dataset.output_width,
        samples: indices
            .iter()
            .map(|index| dataset.samples[*index].clone())
            .collect::<Vec<Sample>>(),
    }
}

fn family_expression(family: ArithmeticFamily) -> Expr {
    match family {
        ArithmeticFamily::Add => Expr::binary(BinaryOp::Add, Expr::x(), Expr::y()),
        ArithmeticFamily::AbsDiff => Expr::abs_diff(Expr::x(), Expr::y()),
        ArithmeticFamily::Multiply => Expr::binary(BinaryOp::Multiply, Expr::x(), Expr::y()),
        ArithmeticFamily::SumOfSquares => Expr::binary(
            BinaryOp::Add,
            Expr::square(Expr::x()),
            Expr::square(Expr::y()),
        ),
    }
}
