use std::{collections::HashMap, path::Path};

use crate::{
    Dataset, OccamError, Sample, VerificationMetrics, compile_expression, pack_dataset,
    parse_netlist, sha256_hex, verify_prepacked,
};

use super::{
    LearnedHypothesis, OracleTask, ResearchMethod, ResearchTools, Split, TrialBudget, TrialKey,
    TrialRecord, TrialStatus, default_adapters, expected_trial_keys, load_experiment_config,
    official_and_synthetic_tasks, split_task,
};

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
    run_trial_with_tools(
        task,
        split,
        key,
        config_sha256,
        ResearchTools::default(),
        TrialBudget::default(),
    )
}

pub fn run_trial_with_tools(
    task: &OracleTask,
    split: &Split,
    key: TrialKey,
    config_sha256: &str,
    tools: ResearchTools,
    budget: TrialBudget,
) -> Result<TrialRecord, OccamError> {
    let observed = task.observe(&split.observed_indices)?;
    let observed_rows = split.observed_indices.len();
    let held_out_rows = split.held_out_indices.len();
    let hypothesis = if key.method == ResearchMethod::OracleExpression {
        Ok(LearnedHypothesis::Expression {
            expression: task.oracle.clone(),
            minimum_unique: Some(true),
            detail: "evaluator-only oracle lower bound".into(),
        })
    } else {
        let adapters = default_adapters(tools);
        let adapter = adapters
            .iter()
            .find(|adapter| adapter.method() == key.method)
            .ok_or_else(|| {
                OccamError::Validation(format!(
                    "research method {:?} has no automatic adapter",
                    key.method
                ))
            })?;
        adapter.fit(&observed, key.seed, &budget)
    };
    let hypothesis = match hypothesis {
        Ok(hypothesis) => hypothesis,
        Err(failure) => {
            return Ok(failure_record(
                key,
                config_sha256,
                observed_rows,
                held_out_rows,
                failure.status(),
                failure.to_string(),
            ));
        }
    };
    let evaluated = evaluate_hypothesis(task, split, &hypothesis);
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
    ) = match evaluated {
        Ok(evaluated) => evaluated,
        Err(error) => {
            let status = match &error {
                OccamError::ResourceLimit { .. } | OccamError::ArithmeticOverflow { .. } => {
                    TrialStatus::ResourceLimit
                }
                _ => TrialStatus::Error,
            };
            return Ok(failure_record(
                key,
                config_sha256,
                observed_rows,
                held_out_rows,
                status,
                format!("hypothesis evaluation failed: {error}"),
            ));
        }
    };
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
        host_identifier: String::new(),
        process_id: 0,
        started_unix_micros: 0,
        hypothesis_sha256: Some(hash),
        detail,
    })
}

pub(crate) fn failure_record(
    key: TrialKey,
    config_sha256: &str,
    observed_rows: usize,
    held_out_rows: usize,
    status: TrialStatus,
    detail: String,
) -> TrialRecord {
    TrialRecord {
        schema_version: 1,
        key,
        config_sha256: config_sha256.to_owned(),
        status,
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
        host_identifier: String::new(),
        process_id: 0,
        started_unix_micros: 0,
        hypothesis_sha256: None,
        detail,
    }
}

#[allow(clippy::type_complexity)]
fn evaluate_hypothesis(
    task: &OracleTask,
    split: &Split,
    hypothesis: &LearnedHypothesis,
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
        LearnedHypothesis::Expression {
            expression,
            minimum_unique,
            detail,
        } => {
            let compiled = compile_expression(expression, task.semantics, &crate::DEFAULT_LIMITS)?;
            let circuit = parse_netlist(&compiled.netlist)?;
            let training_dataset = subset(task.full_domain(), &split.observed_indices);
            let held_out_dataset = subset(task.full_domain(), &split.held_out_indices);
            let training = verify_prepacked(&circuit, &pack_dataset(&training_dataset)?)?;
            let held_out = verify_prepacked(&circuit, &pack_dataset(&held_out_dataset)?)?;
            let full_domain = verify_prepacked(&circuit, &pack_dataset(task.full_domain())?)?;
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
        LearnedHypothesis::Circuit {
            netlist,
            description_length,
            minimum_unique,
            detail,
        } => {
            let circuit = parse_netlist(netlist)?;
            let training_dataset = subset(task.full_domain(), &split.observed_indices);
            let held_out_dataset = subset(task.full_domain(), &split.held_out_indices);
            let training = verify_prepacked(&circuit, &pack_dataset(&training_dataset)?)?;
            let held_out = verify_prepacked(&circuit, &pack_dataset(&held_out_dataset)?)?;
            let full_domain = verify_prepacked(&circuit, &pack_dataset(task.full_domain())?)?;
            Ok((
                training,
                held_out,
                full_domain,
                None,
                *description_length,
                Some(circuit.gates.len()),
                *minimum_unique,
                sha256_hex(netlist.as_bytes()),
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
