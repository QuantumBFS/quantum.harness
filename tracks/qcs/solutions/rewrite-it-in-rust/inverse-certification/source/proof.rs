use std::{fs, path::Path};

use serde::{Deserialize, Serialize};
use varisat::{ProofFormat, Solver};

use crate::{OccamError, RelationProblem, build_relation_problem};

use super::{SynthesisLimits, cnf::encode_relation, solver::sha256_hex};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RelationCnfArtifact {
    pub gate_bound: usize,
    pub variables: usize,
    pub clauses: usize,
    pub literals: usize,
    pub cnf_sha256: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RelationUnsatProofArtifact {
    pub gate_bound: usize,
    pub variables: usize,
    pub clauses: usize,
    pub literals: usize,
    pub cnf_sha256: String,
    pub drat_sha256: String,
}

pub fn write_relation_cnf(
    problem: &RelationProblem,
    gate_bound: usize,
    limits: &SynthesisLimits,
    cnf_path: &Path,
) -> Result<RelationCnfArtifact, OccamError> {
    if problem != &build_relation_problem(problem.spec)? {
        return Err(OccamError::Validation(
            "CNF export requires the canonical complete inverse relation".into(),
        ));
    }
    let encoded = encode_relation(problem, gate_bound, limits)?;
    let statistics = encoded.statistics;
    let mut cnf = Vec::new();
    varisat_dimacs::write_dimacs(&mut cnf, &encoded.formula).map_err(|error| {
        OccamError::Validation(format!("failed to render relation DIMACS: {error}"))
    })?;
    fs::write(cnf_path, &cnf).map_err(|error| {
        OccamError::Validation(format!(
            "failed to write relation DIMACS {}: {error}",
            cnf_path.display()
        ))
    })?;
    Ok(RelationCnfArtifact {
        gate_bound,
        variables: statistics.variables,
        clauses: statistics.clauses,
        literals: statistics.literals,
        cnf_sha256: sha256_hex(&cnf),
    })
}

pub fn write_relation_unsat_proof(
    problem: &RelationProblem,
    gate_bound: usize,
    limits: &SynthesisLimits,
    cnf_path: &Path,
    drat_path: &Path,
) -> Result<RelationUnsatProofArtifact, OccamError> {
    if problem != &build_relation_problem(problem.spec)? {
        return Err(OccamError::Validation(
            "proof export requires the canonical complete inverse relation".into(),
        ));
    }
    let encoded = encode_relation(problem, gate_bound, limits)?;
    let statistics = encoded.statistics;
    let mut cnf = Vec::new();
    varisat_dimacs::write_dimacs(&mut cnf, &encoded.formula).map_err(|error| {
        OccamError::Validation(format!("failed to render relation DIMACS: {error}"))
    })?;
    fs::write(cnf_path, &cnf).map_err(|error| {
        OccamError::Validation(format!(
            "failed to write relation DIMACS {}: {error}",
            cnf_path.display()
        ))
    })?;

    let proof_file = fs::File::create(drat_path).map_err(|error| {
        OccamError::Validation(format!(
            "failed to create relation DRAT proof {}: {error}",
            drat_path.display()
        ))
    })?;
    let mut solver = Solver::new();
    solver.write_proof(proof_file, ProofFormat::Drat);
    solver.add_formula(&encoded.formula);
    let satisfiable = solver.solve().map_err(|error| {
        OccamError::Validation(format!("proof-producing SAT solve failed: {error}"))
    })?;
    solver.close_proof().map_err(|error| {
        OccamError::Validation(format!("failed to close relation DRAT proof: {error}"))
    })?;
    drop(solver);
    if satisfiable {
        return Err(OccamError::Validation(format!(
            "relation gate bound {gate_bound} is SAT; refusing to retain it as an UNSAT proof"
        )));
    }
    let drat = fs::read(drat_path).map_err(|error| {
        OccamError::Validation(format!(
            "failed to read relation DRAT proof {}: {error}",
            drat_path.display()
        ))
    })?;
    Ok(RelationUnsatProofArtifact {
        gate_bound,
        variables: statistics.variables,
        clauses: statistics.clauses,
        literals: statistics.literals,
        cnf_sha256: sha256_hex(&cnf),
        drat_sha256: sha256_hex(&drat),
    })
}
