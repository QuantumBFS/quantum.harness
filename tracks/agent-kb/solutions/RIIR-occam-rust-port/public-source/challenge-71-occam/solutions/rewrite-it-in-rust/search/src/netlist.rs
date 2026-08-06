use std::collections::HashMap;

use crate::{
    Circuit, DEFAULT_LIMITS, Gate, GateOp, OccamError, Operand, ResourceLimits, Source,
    limits::checked_add,
};

pub fn parse_netlist(source: &str) -> Result<Circuit, OccamError> {
    parse_netlist_with_limits(source, &DEFAULT_LIMITS)
}

pub fn parse_netlist_with_limits(
    source: &str,
    limits: &ResourceLimits,
) -> Result<Circuit, OccamError> {
    limits.require(
        "netlist source bytes",
        source.len(),
        limits.max_source_bytes,
    )?;
    let mut input_count = None;
    let mut outputs = None;
    let mut gates = Vec::new();
    let mut wires = HashMap::<usize, usize>::new();

    for (line_index, raw_line) in source.lines().enumerate() {
        let line_number = line_index + 1;
        let line = raw_line.split('#').next().unwrap_or_default().trim();
        if line.is_empty() {
            continue;
        }
        let tokens: Vec<_> = line.split_whitespace().collect();
        match tokens.first().copied() {
            Some("INPUTS") => {
                if input_count.is_some() {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        "duplicate INPUTS declaration",
                    ));
                }
                if tokens.len() != 2 {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        "INPUTS requires exactly one positive integer",
                    ));
                }
                let count = tokens[1].parse::<usize>().map_err(|_| {
                    OccamError::parse(
                        "netlist",
                        line_number,
                        format!("invalid input count {}", tokens[1]),
                    )
                })?;
                if count == 0 {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        "input count must be positive",
                    ));
                }
                limits.require("circuit inputs", count, limits.max_inputs)?;
                input_count = Some(count);
            }
            Some("OUTPUTS") => {
                if outputs.is_some() {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        "duplicate OUTPUTS declaration",
                    ));
                }
                let count = input_count.ok_or_else(|| {
                    OccamError::parse("netlist", line_number, "INPUTS must appear before OUTPUTS")
                })?;
                if tokens.len() < 2 {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        "OUTPUTS requires at least one operand",
                    ));
                }
                limits.require("circuit outputs", tokens.len() - 1, limits.max_outputs)?;
                outputs = Some(
                    tokens[1..]
                        .iter()
                        .map(|token| parse_operand(token, count, &wires, line_number))
                        .collect::<Result<Vec<_>, _>>()?,
                );
            }
            Some(_) => {
                let count = input_count.ok_or_else(|| {
                    OccamError::parse(
                        "netlist",
                        line_number,
                        "INPUTS must appear before gate definitions",
                    )
                })?;
                if tokens.len() != 5 || tokens[1] != "=" {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        format!("bad gate line: {line}"),
                    ));
                }
                let wire_id = parse_wire_name(tokens[0], line_number)?;
                if wires.contains_key(&wire_id) {
                    return Err(OccamError::parse(
                        "netlist",
                        line_number,
                        format!("wire w{wire_id} defined twice"),
                    ));
                }
                let op = parse_gate_op(tokens[2], line_number)?;
                let lhs = parse_operand(tokens[3], count, &wires, line_number)?;
                let rhs = parse_operand(tokens[4], count, &wires, line_number)?;
                let dense_id = gates.len();
                let next_gate_count = checked_add(dense_id, 1, "circuit gate count")?;
                limits.require("circuit gates", next_gate_count, limits.max_gates)?;
                wires.insert(wire_id, dense_id);
                gates.push(Gate {
                    output: dense_id,
                    op,
                    lhs,
                    rhs,
                });
            }
            None => unreachable!(),
        }
    }

    let input_count =
        input_count.ok_or_else(|| OccamError::Validation("missing INPUTS line".into()))?;
    let outputs = outputs.ok_or_else(|| OccamError::Validation("missing OUTPUTS line".into()))?;
    Ok(Circuit {
        input_count,
        wire_count: gates.len(),
        gates,
        outputs,
    })
}

fn parse_gate_op(token: &str, line: usize) -> Result<GateOp, OccamError> {
    match token {
        "AND" => Ok(GateOp::And),
        "OR" => Ok(GateOp::Or),
        "XOR" => Ok(GateOp::Xor),
        "NAND" => Ok(GateOp::Nand),
        "NOR" => Ok(GateOp::Nor),
        "XNOR" => Ok(GateOp::Xnor),
        _ => Err(OccamError::parse(
            "netlist",
            line,
            format!("unknown op {token}; allowed: AND OR XOR NAND NOR XNOR"),
        )),
    }
}

fn parse_operand(
    token: &str,
    input_count: usize,
    wires: &HashMap<usize, usize>,
    line: usize,
) -> Result<Operand, OccamError> {
    let (inverted, name) = token
        .strip_prefix('~')
        .map_or((false, token), |name| (true, name));
    if name.is_empty() {
        return Err(OccamError::parse("netlist", line, "empty inverted operand"));
    }
    let source = if let Some(number) = name.strip_prefix('x') {
        let one_based = parse_positive_id(number, "input", line)?;
        if one_based > input_count {
            return Err(OccamError::parse(
                "netlist",
                line,
                format!("input x{one_based} out of range 1..={input_count}"),
            ));
        }
        Source::Input(one_based - 1)
    } else if let Some(number) = name.strip_prefix('w') {
        let external = parse_positive_id(number, "wire", line)?;
        let dense = wires.get(&external).copied().ok_or_else(|| {
            OccamError::parse(
                "netlist",
                line,
                format!("wire w{external} used before definition"),
            )
        })?;
        Source::Wire(dense)
    } else {
        return Err(OccamError::parse(
            "netlist",
            line,
            format!("bad operand {token}"),
        ));
    };
    Ok(Operand { source, inverted })
}

fn parse_wire_name(token: &str, line: usize) -> Result<usize, OccamError> {
    let number = token.strip_prefix('w').ok_or_else(|| {
        OccamError::parse(
            "netlist",
            line,
            format!("gate output must be a wire name, got {token}"),
        )
    })?;
    parse_positive_id(number, "wire", line)
}

fn parse_positive_id(token: &str, kind: &str, line: usize) -> Result<usize, OccamError> {
    let id = token.parse::<usize>().map_err(|_| {
        OccamError::parse(
            "netlist",
            line,
            format!("invalid {kind} identifier {token}"),
        )
    })?;
    if id == 0 {
        return Err(OccamError::parse(
            "netlist",
            line,
            format!("{kind} identifiers are one-based"),
        ));
    }
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_all_gates_comments_and_inverted_output() {
        let source = "
            # all supported operations
            INPUTS 2
            w1 = AND x1 x2
            w2 = OR w1 x1
            w3 = XOR w2 x2
            w4 = NAND w3 x1
            w5 = NOR w4 x2
            w6 = XNOR ~w5 x1
            OUTPUTS ~w6 x2
        ";
        let circuit = parse_netlist(source).unwrap();
        assert_eq!(circuit.input_count, 2);
        assert_eq!(circuit.gates.len(), 6);
        assert_eq!(circuit.outputs.len(), 2);
        assert!(circuit.outputs[0].inverted);
    }

    #[test]
    fn rejects_duplicate_wire() {
        let error =
            parse_netlist("INPUTS 1\nw1 = XOR x1 x1\nw1 = OR x1 x1\nOUTPUTS w1").unwrap_err();
        assert!(error.to_string().contains("defined twice"));
    }

    #[test]
    fn rejects_undefined_wire() {
        let error = parse_netlist("INPUTS 1\nw1 = XOR w2 x1\nOUTPUTS w1").unwrap_err();
        assert!(error.to_string().contains("used before definition"));
    }

    #[test]
    fn rejects_out_of_range_input() {
        let error = parse_netlist("INPUTS 1\nw1 = XOR x2 x1\nOUTPUTS w1").unwrap_err();
        assert!(error.to_string().contains("out of range"));
    }

    #[test]
    fn rejects_unknown_gate() {
        let error = parse_netlist("INPUTS 1\nw1 = IMP x1 x1\nOUTPUTS w1").unwrap_err();
        assert!(error.to_string().contains("unknown op"));
    }

    #[test]
    fn requires_declarations() {
        assert!(parse_netlist("OUTPUTS x1").is_err());
        assert!(parse_netlist("INPUTS 1").is_err());
    }

    #[test]
    fn rejects_malformed_gate_line() {
        let error = parse_netlist("INPUTS 1\nw1 XOR x1 x1\nOUTPUTS x1").unwrap_err();
        assert!(error.to_string().contains("bad gate line"));
    }

    #[test]
    fn enforces_input_gate_output_and_source_limits() {
        let mut limits = DEFAULT_LIMITS;
        limits.max_inputs = 1;
        assert!(matches!(
            parse_netlist_with_limits("INPUTS 2\nOUTPUTS x1", &limits),
            Err(OccamError::ResourceLimit {
                resource: "circuit inputs",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_gates = 0;
        assert!(matches!(
            parse_netlist_with_limits("INPUTS 1\nw1 = XOR x1 x1\nOUTPUTS w1", &limits),
            Err(OccamError::ResourceLimit {
                resource: "circuit gates",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_outputs = 1;
        assert!(matches!(
            parse_netlist_with_limits("INPUTS 2\nOUTPUTS x1 x2", &limits),
            Err(OccamError::ResourceLimit {
                resource: "circuit outputs",
                ..
            })
        ));

        let mut limits = DEFAULT_LIMITS;
        limits.max_source_bytes = 3;
        assert!(matches!(
            parse_netlist_with_limits("INPUTS 1\nOUTPUTS x1", &limits),
            Err(OccamError::ResourceLimit {
                resource: "netlist source bytes",
                ..
            })
        ));
    }
}
