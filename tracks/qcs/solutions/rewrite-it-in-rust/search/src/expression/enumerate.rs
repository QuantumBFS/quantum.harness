use std::{
    collections::{BTreeSet, HashMap, HashSet},
    time::{Duration, Instant},
};

use crate::{
    BinaryOp, Dataset, Expr, ExprSemantics, MdlSearchConfig, MdlSearchReport, MdlSearchResult,
    OccamError, SearchTermination, SemanticKey, decode_lsb, evaluate_rows,
    expression::report::CostSearchStats,
};

#[derive(Clone, Debug)]
struct ClassRecord {
    representative: Expr,
    description_cost: usize,
    equal_cost_expression_count: usize,
    alternatives: Vec<String>,
}

#[derive(Default)]
struct SearchProgress {
    costs: Vec<CostSearchStats>,
    generated_expressions: usize,
    evaluated_expressions: usize,
    retained_semantic_classes: usize,
}

pub fn search_mdl(
    dataset: &Dataset,
    config: &MdlSearchConfig,
) -> Result<MdlSearchResult, OccamError> {
    validate_config(config)?;
    let semantics = validate_dataset(dataset)?;
    let expected = expected_key(dataset)?;
    let started = Instant::now();
    let timeout = Duration::from_millis(config.timeout_millis);
    let mut progress = SearchProgress::default();
    let mut buckets = vec![Vec::<Expr>::new(); config.max_description_cost + 1];
    let mut classes = HashMap::<SemanticKey, ClassRecord>::new();

    for cost in 1..=config.max_description_cost {
        if timed_out(started, timeout) {
            return Ok(finish(
                None,
                SearchTermination::Timeout,
                config,
                progress,
                None,
            ));
        }
        let generated_before = progress.generated_expressions;
        let evaluated_before = progress.evaluated_expressions;
        let retained_before = progress.retained_semantic_classes;
        let mut candidates = BTreeSet::new();
        let generation = generate_cost_bucket(
            cost,
            &buckets,
            config,
            started,
            timeout,
            &mut progress,
            &mut candidates,
        );
        if let Err(termination) = generation {
            push_cost_stats(
                cost,
                generated_before,
                evaluated_before,
                retained_before,
                &mut progress,
            );
            return Ok(finish(None, termination, config, progress, None));
        }

        for expression in candidates {
            if expression.description_cost() != cost {
                continue;
            }
            if timed_out(started, timeout) {
                push_cost_stats(
                    cost,
                    generated_before,
                    evaluated_before,
                    retained_before,
                    &mut progress,
                );
                return Ok(finish(
                    None,
                    SearchTermination::Timeout,
                    config,
                    progress,
                    None,
                ));
            }
            progress.evaluated_expressions =
                checked_increment(progress.evaluated_expressions, "evaluated expressions")?;
            let key = evaluate_rows(&expression, dataset, semantics)?;
            if let Some(record) = classes.get_mut(&key) {
                if record.description_cost == cost {
                    record.equal_cost_expression_count = checked_increment(
                        record.equal_cost_expression_count,
                        "equal-cost expressions",
                    )?;
                    if record.alternatives.len() < config.max_alternatives_per_class {
                        record.alternatives.push(expression.to_string());
                        record.alternatives.sort();
                        record.alternatives.dedup();
                    }
                }
                continue;
            }
            if classes.len() >= config.max_semantic_classes {
                push_cost_stats(
                    cost,
                    generated_before,
                    evaluated_before,
                    retained_before,
                    &mut progress,
                );
                return Ok(finish(
                    None,
                    SearchTermination::SemanticClassLimit,
                    config,
                    progress,
                    None,
                ));
            }
            let display = expression.to_string();
            classes.insert(
                key,
                ClassRecord {
                    representative: expression.clone(),
                    description_cost: cost,
                    equal_cost_expression_count: 1,
                    alternatives: vec![display],
                },
            );
            buckets[cost].push(expression);
            progress.retained_semantic_classes = checked_increment(
                progress.retained_semantic_classes,
                "retained semantic classes",
            )?;
        }
        buckets[cost].sort();
        push_cost_stats(
            cost,
            generated_before,
            evaluated_before,
            retained_before,
            &mut progress,
        );

        if let Some(record) = classes.get(&expected)
            && record.description_cost == cost
        {
            return Ok(finish(
                Some(record.representative.clone()),
                SearchTermination::Found,
                config,
                progress,
                Some(record),
            ));
        }
    }

    Ok(finish(
        None,
        SearchTermination::CostExhausted,
        config,
        progress,
        None,
    ))
}

fn validate_config(config: &MdlSearchConfig) -> Result<(), OccamError> {
    for (name, value) in [
        ("maximum description cost", config.max_description_cost),
        (
            "maximum generated expressions",
            config.max_generated_expressions,
        ),
        ("maximum semantic classes", config.max_semantic_classes),
        (
            "maximum alternatives per class",
            config.max_alternatives_per_class,
        ),
    ] {
        if value == 0 {
            return Err(OccamError::Validation(format!("{name} must be positive")));
        }
    }
    if config
        .shift_amounts
        .iter()
        .any(|amount| !(1..=3).contains(amount))
    {
        return Err(OccamError::Validation(
            "MDL shift amounts must be in 1..=3".into(),
        ));
    }
    if config
        .shift_amounts
        .iter()
        .copied()
        .collect::<HashSet<_>>()
        .len()
        != config.shift_amounts.len()
    {
        return Err(OccamError::Validation(
            "MDL shift amounts must be unique".into(),
        ));
    }
    if config
        .enabled_binary_ops
        .iter()
        .copied()
        .collect::<HashSet<_>>()
        .len()
        != config.enabled_binary_ops.len()
    {
        return Err(OccamError::Validation(
            "MDL binary operators must be unique".into(),
        ));
    }
    Ok(())
}

fn validate_dataset(dataset: &Dataset) -> Result<ExprSemantics, OccamError> {
    if dataset.input_width == 0 || !dataset.input_width.is_multiple_of(2) {
        return Err(OccamError::Validation(format!(
            "MDL dataset input width {} must be positive and even",
            dataset.input_width
        )));
    }
    if dataset.samples.is_empty() {
        return Err(OccamError::Validation(
            "MDL dataset must contain at least one sample".into(),
        ));
    }
    ExprSemantics::new(dataset.input_width / 2, dataset.output_width)
}

fn expected_key(dataset: &Dataset) -> Result<SemanticKey, OccamError> {
    let mut expected = Vec::with_capacity(dataset.samples.len());
    for (index, sample) in dataset.samples.iter().enumerate() {
        if sample.expected.len() != dataset.output_width {
            return Err(OccamError::Validation(format!(
                "MDL sample {} output width {} does not match dataset output width {}",
                index + 1,
                sample.expected.len(),
                dataset.output_width
            )));
        }
        expected.push(decode_lsb(&sample.expected)?);
    }
    Ok(SemanticKey(expected))
}

#[allow(clippy::too_many_arguments)]
fn generate_cost_bucket(
    cost: usize,
    buckets: &[Vec<Expr>],
    config: &MdlSearchConfig,
    started: Instant,
    timeout: Duration,
    progress: &mut SearchProgress,
    candidates: &mut BTreeSet<Expr>,
) -> Result<(), SearchTermination> {
    if cost == 1 {
        for expression in [Expr::x(), Expr::y(), Expr::constant(0), Expr::constant(1)] {
            record_generated(expression, config, started, timeout, progress, candidates)?;
        }
        return Ok(());
    }

    if config.enable_square {
        for child in &buckets[cost - 1] {
            record_generated(
                Expr::square(child.clone()),
                config,
                started,
                timeout,
                progress,
                candidates,
            )?;
        }
    }
    for amount in &config.shift_amounts {
        for child in &buckets[cost - 1] {
            record_generated(
                Expr::shift_left(child.clone(), *amount),
                config,
                started,
                timeout,
                progress,
                candidates,
            )?;
        }
    }
    for operation in &config.enabled_binary_ops {
        let operator_cost = if *operation == BinaryOp::AbsDiff {
            2
        } else {
            1
        };
        let Some(children_cost) = cost.checked_sub(operator_cost) else {
            continue;
        };
        if children_cost < 2 {
            continue;
        }
        for lhs_cost in 1..children_cost {
            let rhs_cost = children_cost - lhs_cost;
            for lhs in &buckets[lhs_cost] {
                for rhs in &buckets[rhs_cost] {
                    record_generated(
                        Expr::binary(*operation, lhs.clone(), rhs.clone()),
                        config,
                        started,
                        timeout,
                        progress,
                        candidates,
                    )?;
                }
            }
        }
    }
    Ok(())
}

fn record_generated(
    expression: Expr,
    config: &MdlSearchConfig,
    started: Instant,
    timeout: Duration,
    progress: &mut SearchProgress,
    candidates: &mut BTreeSet<Expr>,
) -> Result<(), SearchTermination> {
    if timed_out(started, timeout) {
        return Err(SearchTermination::Timeout);
    }
    if progress.generated_expressions >= config.max_generated_expressions {
        return Err(SearchTermination::ExpressionLimit);
    }
    progress.generated_expressions += 1;
    let expression = expression
        .canonicalize()
        .map_err(|_| SearchTermination::ExpressionLimit)?;
    if expression.description_cost() <= config.max_description_cost {
        candidates.insert(expression);
    }
    Ok(())
}

fn push_cost_stats(
    cost: usize,
    generated_before: usize,
    evaluated_before: usize,
    retained_before: usize,
    progress: &mut SearchProgress,
) {
    progress.costs.push(CostSearchStats {
        description_cost: cost,
        generated_expressions: progress.generated_expressions - generated_before,
        evaluated_expressions: progress.evaluated_expressions - evaluated_before,
        retained_semantic_classes: progress.retained_semantic_classes - retained_before,
    });
}

fn finish(
    expression: Option<Expr>,
    termination: SearchTermination,
    config: &MdlSearchConfig,
    progress: SearchProgress,
    record: Option<&ClassRecord>,
) -> MdlSearchResult {
    let mut alternatives = record
        .map(|record| record.alternatives.clone())
        .unwrap_or_default();
    alternatives.sort();
    alternatives.dedup();
    MdlSearchResult {
        expression,
        report: MdlSearchReport {
            schema_version: 1,
            config: config.clone(),
            termination,
            costs: progress.costs,
            generated_expressions: progress.generated_expressions,
            evaluated_expressions: progress.evaluated_expressions,
            retained_semantic_classes: progress.retained_semantic_classes,
            description_cost: record.map(|record| record.description_cost),
            minimum_unique: record.map(|record| record.equal_cost_expression_count == 1),
            equal_cost_expression_count: record.map(|record| record.equal_cost_expression_count),
            alternatives,
        },
    }
}

fn timed_out(started: Instant, timeout: Duration) -> bool {
    started.elapsed() >= timeout
}

fn checked_increment(value: usize, context: &'static str) -> Result<usize, OccamError> {
    value
        .checked_add(1)
        .ok_or(OccamError::ArithmeticOverflow { context })
}
