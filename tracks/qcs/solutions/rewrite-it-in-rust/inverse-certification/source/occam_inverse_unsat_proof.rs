use std::{env, fs, path::PathBuf};

use occam71_rust::{
    ArithmeticFamily, InverseSpec, SynthesisLimits, build_relation_problem,
    write_relation_unsat_proof,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    if args.len() != 4 {
        return Err(
            "usage: occam_inverse_unsat_proof <family> <operand-bits> <gate-bound> <output-dir>"
                .into(),
        );
    }
    let family = match args[0].as_str() {
        "add" => ArithmeticFamily::Add,
        "abs-diff" => ArithmeticFamily::AbsDiff,
        "multiply" => ArithmeticFamily::Multiply,
        "sum-of-squares" => ArithmeticFamily::SumOfSquares,
        value => return Err(format!("unknown family {value:?}").into()),
    };
    let operand_bits = args[1].parse::<usize>()?;
    let gate_bound = args[2].parse::<usize>()?;
    let output_dir = PathBuf::from(&args[3]);
    fs::create_dir_all(&output_dir)?;

    let problem = build_relation_problem(InverseSpec::new(family, operand_bits)?)?;
    let artifact = write_relation_unsat_proof(
        &problem,
        gate_bound,
        &SynthesisLimits {
            max_gates: gate_bound,
            ..SynthesisLimits::default()
        },
        &output_dir.join("k-minus-1.cnf"),
        &output_dir.join("k-minus-1.drat"),
    )?;
    let manifest = format!("{}\n", serde_json::to_string_pretty(&artifact)?);
    fs::write(output_dir.join("proof-manifest.json"), &manifest)?;
    print!("{manifest}");
    Ok(())
}
