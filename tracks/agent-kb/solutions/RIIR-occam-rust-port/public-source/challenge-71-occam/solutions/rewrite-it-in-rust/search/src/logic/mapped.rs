use std::collections::{HashMap, HashSet};

use crate::{GateOp, OccamError, Operand, Source};

use super::library::{Cell, cell_by_name};

#[derive(Clone, Debug, Eq, PartialEq)]
enum Definition {
    Constant(bool),
    Alias {
        source: String,
        inverted: bool,
    },
    Gate {
        operation: GateOp,
        lhs: String,
        rhs: String,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MappedNetwork {
    model: String,
    inputs: Vec<String>,
    outputs: Vec<String>,
    definitions: HashMap<String, Definition>,
}

pub fn parse_mapped_blif(source: &str) -> Result<MappedNetwork, OccamError> {
    let lines = logical_lines(source)?;
    let mut model = None;
    let mut inputs = None;
    let mut outputs = None;
    let mut definitions = HashMap::new();
    let mut ended = false;
    let mut index = 0usize;
    while index < lines.len() {
        let line = &lines[index];
        let tokens = line.split_whitespace().collect::<Vec<_>>();
        let directive = tokens.first().copied().unwrap_or_default();
        match directive {
            ".model" => {
                if model.is_some() || tokens.len() != 2 {
                    return Err(invalid(index + 1, "expected exactly one '.model NAME'"));
                }
                model = Some(tokens[1].to_owned());
            }
            ".inputs" => {
                if inputs.is_some() || tokens.len() < 2 {
                    return Err(invalid(index + 1, "invalid or duplicate .inputs"));
                }
                inputs = Some(unique_names(&tokens[1..], index + 1, "input")?);
            }
            ".outputs" => {
                if outputs.is_some() || tokens.len() < 2 {
                    return Err(invalid(index + 1, "invalid or duplicate .outputs"));
                }
                outputs = Some(unique_names(&tokens[1..], index + 1, "output")?);
            }
            ".gate" => parse_gate(&tokens, index + 1, &mut definitions)?,
            ".names" => {
                if tokens.len() < 2 {
                    return Err(invalid(index + 1, ".names requires an output net"));
                }
                let header = &tokens[1..];
                let mut rows = Vec::new();
                while index + 1 < lines.len() && !lines[index + 1].starts_with('.') {
                    index += 1;
                    rows.push(lines[index].clone());
                }
                parse_names(header, &rows, index + 1, &mut definitions)?;
            }
            ".end" => {
                if tokens.len() != 1 || ended {
                    return Err(invalid(index + 1, "invalid or duplicate .end"));
                }
                ended = true;
                if index + 1 != lines.len() {
                    return Err(invalid(index + 1, "content follows .end"));
                }
            }
            ".latch" | ".subckt" => {
                return Err(invalid(
                    index + 1,
                    "sequential logic and subcircuits are forbidden",
                ));
            }
            _ => {
                return Err(invalid(
                    index + 1,
                    &format!("unknown directive {directive}"),
                ));
            }
        }
        index += 1;
    }

    let model = model.ok_or_else(|| invalid(0, "missing .model"))?;
    let inputs = inputs.ok_or_else(|| invalid(0, "missing .inputs"))?;
    let outputs = outputs.ok_or_else(|| invalid(0, "missing .outputs"))?;
    if !ended {
        return Err(invalid(0, "missing .end"));
    }
    let input_set = inputs.iter().cloned().collect::<HashSet<_>>();
    if input_set.len() != inputs.len() {
        return Err(invalid(0, "duplicate input name"));
    }
    if definitions.keys().any(|name| input_set.contains(name)) {
        return Err(invalid(0, "a mapped net redefines an input"));
    }
    let network = MappedNetwork {
        model,
        inputs,
        outputs,
        definitions,
    };
    network.validate_dependencies()?;
    Ok(network)
}

impl MappedNetwork {
    pub fn model(&self) -> &str {
        &self.model
    }

    pub fn official_gate_count(&self) -> usize {
        self.definitions
            .values()
            .filter(|definition| matches!(definition, Definition::Gate { .. }))
            .count()
    }

    pub fn into_official_netlist(&self) -> Result<String, OccamError> {
        let mut builder = OfficialBuilder::new(self);
        let outputs = self
            .outputs
            .iter()
            .map(|output| builder.resolve(output))
            .collect::<Result<Vec<_>, _>>()?;
        if outputs.is_empty() {
            return Err(OccamError::Validation(
                "mapped network has no outputs".into(),
            ));
        }
        let mut source = format!("INPUTS {}\n", self.inputs.len());
        source.push_str(&builder.lines.join("\n"));
        if !builder.lines.is_empty() {
            source.push('\n');
        }
        source.push_str("OUTPUTS");
        for output in outputs {
            source.push(' ');
            source.push_str(&render_operand(output));
        }
        source.push('\n');
        Ok(source)
    }

    fn validate_dependencies(&self) -> Result<(), OccamError> {
        let inputs = self.inputs.iter().cloned().collect::<HashSet<_>>();
        let mut state = HashMap::<String, u8>::new();
        for output in &self.outputs {
            visit(output, &inputs, &self.definitions, &mut state)?;
        }
        Ok(())
    }
}

struct OfficialBuilder<'a> {
    network: &'a MappedNetwork,
    input_indices: HashMap<String, usize>,
    resolved: HashMap<String, Operand>,
    visiting: HashSet<String>,
    lines: Vec<String>,
    zero: Option<Operand>,
}

impl<'a> OfficialBuilder<'a> {
    fn new(network: &'a MappedNetwork) -> Self {
        Self {
            network,
            input_indices: network
                .inputs
                .iter()
                .enumerate()
                .map(|(index, name)| (name.clone(), index))
                .collect(),
            resolved: HashMap::new(),
            visiting: HashSet::new(),
            lines: Vec::new(),
            zero: None,
        }
    }

    fn resolve(&mut self, net: &str) -> Result<Operand, OccamError> {
        if let Some(index) = self.input_indices.get(net) {
            return Ok(Operand {
                source: Source::Input(*index),
                inverted: false,
            });
        }
        if let Some(operand) = self.resolved.get(net) {
            return Ok(*operand);
        }
        if !self.visiting.insert(net.to_owned()) {
            return Err(OccamError::Validation(format!(
                "mapped BLIF contains a cycle through {net}"
            )));
        }
        let definition = self.network.definitions.get(net).ok_or_else(|| {
            OccamError::Validation(format!("mapped BLIF references undefined net {net}"))
        })?;
        let operand = match definition {
            Definition::Constant(value) => {
                let zero = self.zero()?;
                Operand {
                    inverted: *value,
                    ..zero
                }
            }
            Definition::Alias { source, inverted } => {
                let mut operand = self.resolve(source)?;
                operand.inverted ^= *inverted;
                operand
            }
            Definition::Gate {
                operation,
                lhs,
                rhs,
            } => {
                let lhs = self.resolve(lhs)?;
                let rhs = self.resolve(rhs)?;
                let wire = self.lines.len();
                self.lines.push(format!(
                    "w{} = {} {} {}",
                    wire + 1,
                    operation_name(*operation),
                    render_operand(lhs),
                    render_operand(rhs)
                ));
                Operand {
                    source: Source::Wire(wire),
                    inverted: false,
                }
            }
        };
        self.visiting.remove(net);
        self.resolved.insert(net.to_owned(), operand);
        Ok(operand)
    }

    fn zero(&mut self) -> Result<Operand, OccamError> {
        if let Some(zero) = self.zero {
            return Ok(zero);
        }
        if self.network.inputs.is_empty() {
            return Err(OccamError::Validation(
                "cannot lower a constant network without an input".into(),
            ));
        }
        let wire = self.lines.len();
        self.lines.push(format!("w{} = XOR x1 x1", wire + 1));
        let zero = Operand {
            source: Source::Wire(wire),
            inverted: false,
        };
        self.zero = Some(zero);
        Ok(zero)
    }
}

fn parse_gate(
    tokens: &[&str],
    line: usize,
    definitions: &mut HashMap<String, Definition>,
) -> Result<(), OccamError> {
    if tokens.len() < 3 {
        return Err(invalid(line, ".gate requires a cell and pin assignments"));
    }
    let cell = cell_by_name(tokens[1])
        .ok_or_else(|| invalid(line, &format!("unknown mapped cell {}", tokens[1])))?;
    let mut pins = HashMap::new();
    for assignment in &tokens[2..] {
        let (pin, net) = assignment
            .split_once('=')
            .ok_or_else(|| invalid(line, "gate pins must use PIN=net"))?;
        if pin.is_empty() || net.is_empty() || pins.insert(pin, net).is_some() {
            return Err(invalid(line, "invalid or duplicate gate pin"));
        }
    }
    let output = take_pin(&mut pins, &["O", "Y"], line, "output")?;
    let definition = match cell {
        Cell::Constant(value) => Definition::Constant(value),
        Cell::Alias { inverted } => Definition::Alias {
            source: take_pin(&mut pins, &["a", "A", "i", "I"], line, "input")?.to_owned(),
            inverted,
        },
        Cell::Gate(operation) => Definition::Gate {
            operation,
            lhs: take_pin(&mut pins, &["a", "A"], line, "a")?.to_owned(),
            rhs: take_pin(&mut pins, &["b", "B"], line, "b")?.to_owned(),
        },
    };
    if !pins.is_empty() {
        return Err(invalid(line, "mapped gate has unknown pins"));
    }
    insert_definition(definitions, output.to_owned(), definition, line)
}

fn take_pin<'a>(
    pins: &mut HashMap<&'a str, &'a str>,
    choices: &[&str],
    line: usize,
    label: &str,
) -> Result<&'a str, OccamError> {
    let matching = pins
        .keys()
        .copied()
        .filter(|pin| choices.contains(pin))
        .collect::<Vec<_>>();
    if matching.len() > 1 {
        return Err(invalid(line, &format!("duplicate {label} pin aliases")));
    }
    let key = matching
        .first()
        .ok_or_else(|| invalid(line, &format!("missing {label} pin")))?;
    Ok(pins.remove(key).unwrap())
}

fn parse_names(
    header: &[&str],
    rows: &[String],
    line: usize,
    definitions: &mut HashMap<String, Definition>,
) -> Result<(), OccamError> {
    let output = header.last().unwrap().to_string();
    let inputs = &header[..header.len() - 1];
    if inputs.len() > 2 {
        return Err(invalid(line, ".names supports at most two inputs"));
    }
    let truth = truth_vector(inputs.len(), rows, line)?;
    let definition = match inputs.len() {
        0 => Definition::Constant(truth[0]),
        1 if truth == [false, true] => Definition::Alias {
            source: inputs[0].to_owned(),
            inverted: false,
        },
        1 if truth == [true, false] => Definition::Alias {
            source: inputs[0].to_owned(),
            inverted: true,
        },
        1 => {
            return Err(invalid(
                line,
                "one-input .names must be buffer, inverter, or constant",
            ));
        }
        2 => Definition::Gate {
            operation: operation_from_truth(&truth)
                .ok_or_else(|| invalid(line, "two-input .names is outside official gate basis"))?,
            lhs: inputs[0].to_owned(),
            rhs: inputs[1].to_owned(),
        },
        _ => unreachable!(),
    };
    insert_definition(definitions, output, definition, line)
}

fn truth_vector(arity: usize, rows: &[String], line: usize) -> Result<Vec<bool>, OccamError> {
    let mut truth = vec![false; 1usize << arity];
    for row in rows {
        let fields = row.split_whitespace().collect::<Vec<_>>();
        let (cube, value) = if arity == 0 {
            if fields.len() != 1 {
                return Err(invalid(line, "constant .names rows contain only 0 or 1"));
            }
            ("", fields[0])
        } else {
            if fields.len() != 2 {
                return Err(invalid(line, ".names row must contain cube and output"));
            }
            (fields[0], fields[1])
        };
        if value != "1" || cube.len() != arity {
            return Err(invalid(line, "only on-set .names cubes are accepted"));
        }
        for (assignment, result) in truth.iter_mut().enumerate() {
            if cube.bytes().enumerate().all(|(bit, value)| match value {
                b'0' => assignment & (1 << (arity - bit - 1)) == 0,
                b'1' => assignment & (1 << (arity - bit - 1)) != 0,
                b'-' => true,
                _ => false,
            }) {
                *result = true;
            }
        }
    }
    Ok(truth)
}

fn operation_from_truth(truth: &[bool]) -> Option<GateOp> {
    match truth {
        [false, false, false, true] => Some(GateOp::And),
        [false, true, true, true] => Some(GateOp::Or),
        [false, true, true, false] => Some(GateOp::Xor),
        [true, true, true, false] => Some(GateOp::Nand),
        [true, false, false, false] => Some(GateOp::Nor),
        [true, false, false, true] => Some(GateOp::Xnor),
        _ => None,
    }
}

fn insert_definition(
    definitions: &mut HashMap<String, Definition>,
    output: String,
    definition: Definition,
    line: usize,
) -> Result<(), OccamError> {
    if output.is_empty() || definitions.insert(output.clone(), definition).is_some() {
        return Err(invalid(line, &format!("net {output:?} is defined twice")));
    }
    Ok(())
}

fn visit(
    net: &str,
    inputs: &HashSet<String>,
    definitions: &HashMap<String, Definition>,
    state: &mut HashMap<String, u8>,
) -> Result<(), OccamError> {
    if inputs.contains(net) {
        return Ok(());
    }
    match state.get(net) {
        Some(2) => return Ok(()),
        Some(1) => {
            return Err(OccamError::Validation(format!(
                "mapped BLIF contains a cycle through {net}"
            )));
        }
        _ => {}
    }
    state.insert(net.to_owned(), 1);
    let definition = definitions.get(net).ok_or_else(|| {
        OccamError::Validation(format!("mapped BLIF references undefined net {net}"))
    })?;
    match definition {
        Definition::Constant(_) => {}
        Definition::Alias { source, .. } => visit(source, inputs, definitions, state)?,
        Definition::Gate { lhs, rhs, .. } => {
            visit(lhs, inputs, definitions, state)?;
            visit(rhs, inputs, definitions, state)?;
        }
    }
    state.insert(net.to_owned(), 2);
    Ok(())
}

fn logical_lines(source: &str) -> Result<Vec<String>, OccamError> {
    let mut lines = Vec::new();
    let mut pending = String::new();
    for raw in source.lines() {
        let line = raw.split('#').next().unwrap_or_default().trim();
        if line.is_empty() {
            continue;
        }
        let continued = line.ends_with('\\');
        let fragment = line.strip_suffix('\\').unwrap_or(line).trim_end();
        if !pending.is_empty() {
            pending.push(' ');
        }
        pending.push_str(fragment);
        if !continued {
            lines.push(std::mem::take(&mut pending));
        }
    }
    if !pending.is_empty() {
        return Err(OccamError::Validation(
            "mapped BLIF ends with an unfinished continuation".into(),
        ));
    }
    Ok(lines)
}

fn unique_names(tokens: &[&str], line: usize, kind: &str) -> Result<Vec<String>, OccamError> {
    let names = tokens
        .iter()
        .map(|name| (*name).to_owned())
        .collect::<Vec<_>>();
    let unique = names.iter().collect::<HashSet<_>>();
    if names.iter().any(String::is_empty) || unique.len() != names.len() {
        return Err(invalid(line, &format!("duplicate or empty {kind} name")));
    }
    Ok(names)
}

fn operation_name(operation: GateOp) -> &'static str {
    match operation {
        GateOp::And => "AND",
        GateOp::Or => "OR",
        GateOp::Xor => "XOR",
        GateOp::Nand => "NAND",
        GateOp::Nor => "NOR",
        GateOp::Xnor => "XNOR",
    }
}

fn render_operand(operand: Operand) -> String {
    let name = match operand.source {
        Source::Input(index) => format!("x{}", index + 1),
        Source::Wire(index) => format!("w{}", index + 1),
    };
    if operand.inverted {
        format!("~{name}")
    } else {
        name
    }
}

fn invalid(line: usize, detail: &str) -> OccamError {
    OccamError::parse("mapped BLIF", line, detail)
}
