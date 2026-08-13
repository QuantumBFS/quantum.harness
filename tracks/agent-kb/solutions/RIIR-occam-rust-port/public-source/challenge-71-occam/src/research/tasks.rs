use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use crate::{Dataset, Expr, ExprSemantics, OccamError, Sample, parse_expression, sha256_hex};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum TaskClass {
    Official,
    Synthetic,
}

#[derive(Clone, Debug)]
pub struct OracleTask {
    pub id: String,
    pub class: TaskClass,
    pub semantics: ExprSemantics,
    pub oracle: Expr,
    full_domain: Dataset,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedTask {
    pub id: String,
    pub input_width: usize,
    pub output_width: usize,
    pub samples: Vec<Sample>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct TaskManifest {
    pub id: String,
    pub class: TaskClass,
    pub operand_bits: usize,
    pub output_bits: usize,
    pub oracle: String,
    pub domain_rows: usize,
    pub domain_sha256: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TaskFile {
    schema_version: u32,
    tasks: Vec<TaskDefinition>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TaskDefinition {
    id: String,
    class: TaskClass,
    operand_bits: usize,
    output_bits: usize,
    oracle: String,
}

pub fn official_and_synthetic_tasks() -> Result<Vec<OracleTask>, OccamError> {
    let file: TaskFile = serde_json::from_str(include_str!(
        "../../../experiments/occam-generalization/tasks.json"
    ))
    .map_err(|error| {
        OccamError::Validation(format!("research task manifest is invalid: {error}"))
    })?;
    if file.schema_version != 1 || file.tasks.len() != 16 {
        return Err(OccamError::Validation(
            "research task manifest must contain schema 1 and sixteen tasks".into(),
        ));
    }
    let mut ids = HashSet::new();
    file.tasks
        .into_iter()
        .map(|definition| {
            if !ids.insert(definition.id.clone()) {
                return Err(OccamError::Validation(format!(
                    "duplicate research task {}",
                    definition.id
                )));
            }
            let semantics = ExprSemantics::new(definition.operand_bits, definition.output_bits)?;
            let oracle = parse_expression(&definition.oracle)?;
            let full_domain = complete_domain(&oracle, semantics)?;
            Ok(OracleTask {
                id: definition.id,
                class: definition.class,
                semantics,
                oracle,
                full_domain,
            })
        })
        .collect()
}

impl OracleTask {
    pub fn observe(&self, indices: &[usize]) -> Result<ObservedTask, OccamError> {
        let mut seen = HashSet::new();
        let samples = indices
            .iter()
            .map(|index| {
                if !seen.insert(*index) {
                    return Err(OccamError::Validation(format!(
                        "duplicate observed index {index}"
                    )));
                }
                self.full_domain
                    .samples
                    .get(*index)
                    .cloned()
                    .ok_or_else(|| {
                        OccamError::Validation(format!(
                            "observed index {index} is outside task {}",
                            self.id
                        ))
                    })
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(ObservedTask {
            id: self.id.clone(),
            input_width: self.full_domain.input_width,
            output_width: self.full_domain.output_width,
            samples,
        })
    }

    pub fn full_domain(&self) -> &Dataset {
        &self.full_domain
    }

    pub fn manifest(&self) -> TaskManifest {
        let bytes = render_dataset(&self.full_domain);
        TaskManifest {
            id: self.id.clone(),
            class: self.class,
            operand_bits: self.semantics.operand_bits,
            output_bits: self.semantics.output_bits,
            oracle: self.oracle.to_string(),
            domain_rows: self.full_domain.samples.len(),
            domain_sha256: sha256_hex(bytes.as_bytes()),
        }
    }
}

impl ObservedTask {
    pub fn dataset(&self) -> Dataset {
        Dataset {
            input_width: self.input_width,
            output_width: self.output_width,
            samples: self.samples.clone(),
        }
    }
}

fn complete_domain(expression: &Expr, semantics: ExprSemantics) -> Result<Dataset, OccamError> {
    let input_width =
        semantics
            .operand_bits
            .checked_mul(2)
            .ok_or(OccamError::ArithmeticOverflow {
                context: "research task input width",
            })?;
    let cases = 1usize
        .checked_shl(
            u32::try_from(input_width).map_err(|_| OccamError::ArithmeticOverflow {
                context: "research task domain shift",
            })?,
        )
        .ok_or(OccamError::ArithmeticOverflow {
            context: "research task domain rows",
        })?;
    let mut samples = Vec::with_capacity(cases);
    for packed in 0..cases {
        let input = (0..input_width)
            .map(|bit| packed & (1usize << bit) != 0)
            .collect::<Vec<_>>();
        let mask = (1usize << semantics.operand_bits) - 1;
        let x = (packed & mask) as u64;
        let y = (packed >> semantics.operand_bits) as u64;
        let value = expression.evaluate(x, y, semantics)?;
        let expected = (0..semantics.output_bits)
            .map(|bit| value & (1u64 << bit) != 0)
            .collect();
        samples.push(Sample { input, expected });
    }
    Ok(Dataset {
        input_width,
        output_width: semantics.output_bits,
        samples,
    })
}

pub fn render_dataset(dataset: &Dataset) -> String {
    let mut output = String::from("input,output\n");
    for sample in &dataset.samples {
        output.extend(sample.input.iter().map(|bit| if *bit { '1' } else { '0' }));
        output.push(',');
        output.extend(
            sample
                .expected
                .iter()
                .map(|bit| if *bit { '1' } else { '0' }),
        );
        output.push('\n');
    }
    output
}
