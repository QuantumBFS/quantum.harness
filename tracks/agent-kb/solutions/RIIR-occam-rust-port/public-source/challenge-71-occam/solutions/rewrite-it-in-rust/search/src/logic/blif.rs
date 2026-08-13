use crate::{Circuit, GateOp, OccamError, Operand, Source};

pub fn circuit_to_blif(circuit: &Circuit, model: &str) -> Result<String, OccamError> {
    validate_model_name(model)?;
    if circuit.input_count == 0 || circuit.outputs.is_empty() {
        return Err(OccamError::Validation(
            "BLIF export requires at least one input and output".into(),
        ));
    }
    let mut output = String::new();
    output.push_str(&format!(".model {model}\n"));
    output.push_str(".inputs");
    for input in 0..circuit.input_count {
        output.push_str(&format!(" i{input}"));
    }
    output.push('\n');
    output.push_str(".outputs");
    for index in 0..circuit.outputs.len() {
        output.push_str(&format!(" o{index}"));
    }
    output.push('\n');

    for (index, gate) in circuit.gates.iter().enumerate() {
        if gate.output != index {
            return Err(OccamError::Validation(format!(
                "BLIF export requires dense gate outputs, gate {index} has output {}",
                gate.output
            )));
        }
        let lhs = export_operand(&mut output, gate.lhs, &format!("g{index}a"));
        let rhs = export_operand(&mut output, gate.rhs, &format!("g{index}b"));
        output.push_str(&format!(".names {lhs} {rhs} n{index}\n"));
        output.push_str(truth_table(gate.op));
    }
    for (index, operand) in circuit.outputs.iter().enumerate() {
        let source = source_name(operand.source);
        output.push_str(&format!(".names {source} o{index}\n"));
        output.push_str(if operand.inverted { "0 1\n" } else { "1 1\n" });
    }
    output.push_str(".end\n");
    Ok(output)
}

fn export_operand(output: &mut String, operand: Operand, alias: &str) -> String {
    let source = source_name(operand.source);
    if operand.inverted {
        output.push_str(&format!(".names {source} {alias}\n0 1\n"));
        alias.to_owned()
    } else {
        source
    }
}

fn source_name(source: Source) -> String {
    match source {
        Source::Input(index) => format!("i{index}"),
        Source::Wire(index) => format!("n{index}"),
    }
}

fn truth_table(operation: GateOp) -> &'static str {
    match operation {
        GateOp::And => "11 1\n",
        GateOp::Or => "1- 1\n-1 1\n",
        GateOp::Xor => "10 1\n01 1\n",
        GateOp::Nand => "0- 1\n-0 1\n",
        GateOp::Nor => "00 1\n",
        GateOp::Xnor => "00 1\n11 1\n",
    }
}

fn validate_model_name(model: &str) -> Result<(), OccamError> {
    if model.is_empty()
        || !model
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
    {
        return Err(OccamError::Validation(format!(
            "BLIF model name {model:?} must contain only ASCII letters, digits, and underscores"
        )));
    }
    Ok(())
}
