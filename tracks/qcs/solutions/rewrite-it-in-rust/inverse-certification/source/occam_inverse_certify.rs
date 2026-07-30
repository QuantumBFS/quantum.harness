use std::{env, fs, path::PathBuf, time::Duration};

use occam71_rust::{
    ArithmeticFamily, InverseSpec, SynthesisLimits, SynthesisStatus, build_relation_problem,
    synthesize_minimal_relation, write_relation_unsat_proof,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    if args.len() != 5 {
        return Err(
            "usage: occam_inverse_certify <family> <operand-bits> <max-gates> <timeout-seconds> <output-dir>"
                .into(),
        );
    }
    let family = parse_family(&args[0])?;
    let operand_bits = args[1].parse::<usize>()?;
    let max_gates = args[2].parse::<usize>()?;
    let timeout_seconds = args[3].parse::<u64>()?;
    let output_dir = PathBuf::from(&args[4]);
    fs::create_dir_all(&output_dir)?;

    let spec = InverseSpec::new(family, operand_bits)?;
    let problem = build_relation_problem(spec)?;
    let limits = SynthesisLimits {
        max_gates,
        timeout: Duration::from_secs(timeout_seconds),
        ..SynthesisLimits::default()
    };
    let certificate = synthesize_minimal_relation(&problem, &limits)?;
    fs::write(
        output_dir.join("certificate.json"),
        certificate.to_json_pretty()?,
    )?;
    if certificate.status == SynthesisStatus::Sat {
        let gate_count = certificate
            .minimal_gate_count
            .ok_or("SAT result has no gate count")?;
        fs::write(
            output_dir.join("circuit.txt"),
            certificate
                .netlist
                .as_deref()
                .ok_or("SAT result has no netlist")?,
        )?;
        if gate_count > 0 {
            let proof = write_relation_unsat_proof(
                &problem,
                gate_count - 1,
                &limits,
                &output_dir.join("k-minus-1.cnf"),
                &output_dir.join("k-minus-1.drat"),
            )?;
            fs::write(
                output_dir.join("proof-manifest.json"),
                format!("{}\n", serde_json::to_string_pretty(&proof)?),
            )?;
        }
    }
    println!("{}", certificate.to_json_pretty()?);
    Ok(())
}

fn parse_family(value: &str) -> Result<ArithmeticFamily, Box<dyn std::error::Error>> {
    match value {
        "add" => Ok(ArithmeticFamily::Add),
        "abs-diff" => Ok(ArithmeticFamily::AbsDiff),
        "multiply" => Ok(ArithmeticFamily::Multiply),
        "sum-of-squares" => Ok(ArithmeticFamily::SumOfSquares),
        _ => Err(format!("unknown family {value:?}").into()),
    }
}
