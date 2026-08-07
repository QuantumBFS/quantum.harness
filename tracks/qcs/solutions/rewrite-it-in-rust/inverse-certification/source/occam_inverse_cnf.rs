use std::{env, fs, path::PathBuf};

use occam71_rust::{
    ArithmeticFamily, InverseSpec, SynthesisLimits, build_relation_problem, write_relation_cnf,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    if args.len() != 4 {
        return Err(
            "usage: occam_inverse_cnf <family> <operand-bits> <gate-bound> <cnf-path>".into(),
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
    let cnf_path = PathBuf::from(&args[3]);
    if let Some(parent) = cnf_path.parent() {
        fs::create_dir_all(parent)?;
    }
    let problem = build_relation_problem(InverseSpec::new(family, operand_bits)?)?;
    let artifact = write_relation_cnf(
        &problem,
        gate_bound,
        &SynthesisLimits {
            max_gates: gate_bound,
            ..SynthesisLimits::default()
        },
        &cnf_path,
    )?;
    println!("{}", serde_json::to_string_pretty(&artifact)?);
    Ok(())
}
