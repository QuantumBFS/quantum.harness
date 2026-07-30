use sha2::{Digest, Sha256};

use crate::{
    Circuit, OccamError, ResourceLimits, TestInputs, evaluate_with_limits,
    limits::{checked_add, checked_mul},
};

pub fn prediction_csv_from_circuit(
    circuit: &Circuit,
    inputs: &TestInputs,
    limits: &ResourceLimits,
) -> Result<String, OccamError> {
    if circuit.input_count != inputs.input_width {
        return Err(OccamError::Validation(format!(
            "test input width {} does not match circuit INPUTS {}",
            inputs.input_width, circuit.input_count
        )));
    }
    limits.require(
        "prediction output width",
        circuit.outputs.len(),
        limits.max_output_width,
    )?;
    let row_bytes = checked_add(
        checked_add(
            inputs.input_width,
            circuit.outputs.len(),
            "prediction row bit count",
        )?,
        2,
        "prediction row bytes",
    )?;
    let output_bytes = checked_add(
        "input,output\n".len(),
        checked_mul(row_bytes, inputs.rows.len(), "prediction CSV row bytes")?,
        "prediction CSV bytes",
    )?;
    let max_bytes = limits.max_generated_bytes.min(limits.max_source_bytes);
    limits.require("prediction CSV bytes", output_bytes, max_bytes)?;

    let mut csv = String::new();
    csv.try_reserve_exact(output_bytes).map_err(|error| {
        OccamError::Validation(format!(
            "cannot allocate prediction CSV ({output_bytes} bytes): {error}"
        ))
    })?;
    csv.push_str("input,output\n");
    for row in &inputs.rows {
        if row.len() != inputs.input_width {
            return Err(OccamError::Validation(format!(
                "test input row width {} does not match declared width {}",
                row.len(),
                inputs.input_width
            )));
        }
        push_bits(&mut csv, row);
        csv.push(',');
        push_bits(&mut csv, &evaluate_with_limits(circuit, row, limits)?);
        csv.push('\n');
    }
    debug_assert_eq!(csv.len(), output_bytes);
    Ok(csv)
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn push_bits(output: &mut String, bits: &[bool]) {
    output.extend(bits.iter().map(|bit| if *bit { '1' } else { '0' }));
}

#[cfg(test)]
mod tests {
    use crate::{DEFAULT_LIMITS, parse_netlist, parse_test_inputs};

    use super::*;

    #[test]
    fn renders_exact_canonical_bytes() {
        let circuit = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS w1\n").unwrap();
        let inputs = parse_test_inputs("input\n00\n10\n").unwrap();
        assert_eq!(
            prediction_csv_from_circuit(&circuit, &inputs, &DEFAULT_LIMITS).unwrap(),
            "input,output\n00,0\n10,1\n"
        );
    }
}
