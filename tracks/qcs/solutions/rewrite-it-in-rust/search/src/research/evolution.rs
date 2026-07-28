use std::{
    collections::{HashMap, HashSet},
    time::Instant,
};

use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha8Rng;

use crate::{BinaryOp, Expr, ExprSemantics, decode_lsb};

use super::{
    LearnedHypothesis, LearnerFailure, ObservedTask, ResearchLearner, ResearchMethod, TrialBudget,
};

const BINARY_OPERATORS: [BinaryOp; 9] = [
    BinaryOp::Add,
    BinaryOp::Subtract,
    BinaryOp::AbsDiff,
    BinaryOp::Multiply,
    BinaryOp::BitXor,
    BinaryOp::BitAnd,
    BinaryOp::BitOr,
    BinaryOp::Min,
    BinaryOp::Max,
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct EvolutionConfig {
    pub population: usize,
    pub generations: usize,
    pub elite: usize,
    pub tournament: usize,
    pub mutation_probability_per_mille: u16,
    pub max_description_cost: usize,
}

impl Default for EvolutionConfig {
    fn default() -> Self {
        Self {
            population: 128,
            generations: 200,
            elite: 8,
            tournament: 4,
            mutation_probability_per_mille: 700,
            max_description_cost: 12,
        }
    }
}

impl EvolutionConfig {
    pub fn for_tests() -> Self {
        Self {
            population: 32,
            generations: 20,
            elite: 4,
            tournament: 3,
            mutation_probability_per_mille: 700,
            max_description_cost: 8,
        }
    }

    fn validate(self) -> Result<Self, LearnerFailure> {
        if self.population < 2
            || self.generations == 0
            || self.elite == 0
            || self.elite >= self.population
            || self.tournament == 0
            || self.tournament > self.population
            || self.mutation_probability_per_mille > 1_000
            || self.max_description_cost < 3
        {
            return Err(LearnerFailure::ToolError(
                "invalid grammar-evolution configuration".into(),
            ));
        }
        Ok(self)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EvolutionTraceEntry {
    pub generation: usize,
    pub row_mismatches: usize,
    pub bit_mismatches: usize,
    pub description_cost: usize,
    pub estimated_gate_count: usize,
    pub expression: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EvolutionResult {
    pub best_expression: Expr,
    pub best_row_mismatches: usize,
    pub best_bit_mismatches: usize,
    pub evaluated_expressions: usize,
    pub trace: Vec<EvolutionTraceEntry>,
}

pub struct GrammarEvolutionLearner {
    config: EvolutionConfig,
}

impl GrammarEvolutionLearner {
    pub fn new(config: EvolutionConfig) -> Self {
        Self { config }
    }
}

impl Default for GrammarEvolutionLearner {
    fn default() -> Self {
        Self::new(EvolutionConfig::default())
    }
}

impl ResearchLearner for GrammarEvolutionLearner {
    fn method(&self) -> ResearchMethod {
        ResearchMethod::GrammarEvolution
    }

    fn fit(
        &self,
        observed: &ObservedTask,
        seed: u64,
        budget: &TrialBudget,
    ) -> Result<LearnedHypothesis, LearnerFailure> {
        let result = evolve_with_budget(observed, seed, self.config, budget)?;
        Ok(LearnedHypothesis::Expression {
            expression: result.best_expression,
            minimum_unique: None,
            detail: format!(
                "seeded grammar evolution evaluated {} canonical expressions across {} generations; best training row errors={}",
                result.evaluated_expressions,
                result.trace.len(),
                result.best_row_mismatches
            ),
        })
    }
}

pub fn evolve(
    observed: &ObservedTask,
    seed: u64,
    config: EvolutionConfig,
) -> Result<EvolutionResult, LearnerFailure> {
    evolve_with_budget(observed, seed, config, &TrialBudget::default())
}

pub fn evolve_with_budget(
    observed: &ObservedTask,
    seed: u64,
    config: EvolutionConfig,
    budget: &TrialBudget,
) -> Result<EvolutionResult, LearnerFailure> {
    let config = config.validate()?;
    if observed.input_width == 0 || !observed.input_width.is_multiple_of(2) {
        return Err(LearnerFailure::Unsupported(
            "grammar evolution requires two equal-width operands".into(),
        ));
    }
    if observed.samples.is_empty() {
        return Err(LearnerFailure::NoHypothesis(
            "grammar evolution requires at least one observed row".into(),
        ));
    }
    let semantics = ExprSemantics::new(observed.input_width / 2, observed.output_width)
        .map_err(|error| LearnerFailure::Unsupported(error.to_string()))?;
    validate_rows(observed)?;
    if budget.timeout.is_zero() {
        return Err(LearnerFailure::Timeout(
            "grammar evolution has a zero timeout".into(),
        ));
    }

    let deadline = Instant::now() + budget.timeout;
    let mixed_seed = seed
        ^ (observed.input_width as u64).rotate_left(17)
        ^ (observed.output_width as u64).rotate_left(33)
        ^ (observed.samples.len() as u64).rotate_left(49);
    let mut rng = ChaCha8Rng::seed_from_u64(mixed_seed);
    let mut population = initial_population(config, semantics, &mut rng);
    let mut evaluator = FitnessEvaluator {
        observed,
        semantics,
        deadline,
        max_evaluated: budget.max_nodes,
        cache: HashMap::new(),
    };
    let mut trace = Vec::with_capacity(config.generations);
    let mut stable_zero = None::<Expr>;
    let mut final_best = None::<Ranked>;

    for generation in 0..config.generations {
        let mut ranked = evaluator.rank(population)?;
        ranked.truncate(config.population);
        let best = ranked[0].clone();
        trace.push(EvolutionTraceEntry {
            generation,
            row_mismatches: best.fitness.row_mismatches,
            bit_mismatches: best.fitness.bit_mismatches,
            description_cost: best.fitness.description_cost,
            estimated_gate_count: best.fitness.estimated_gate_count,
            expression: best.fitness.expression.clone(),
        });

        if best.fitness.row_mismatches == 0 {
            if stable_zero.as_ref() == Some(&best.expression) {
                final_best = Some(best);
                break;
            }
            stable_zero = Some(best.expression.clone());
        } else {
            stable_zero = None;
        }
        final_best = Some(best);
        if generation + 1 == config.generations {
            break;
        }

        let mut next = ranked
            .iter()
            .take(config.elite)
            .map(|candidate| candidate.expression.clone())
            .collect::<Vec<_>>();
        while next.len() < config.population {
            let parent = tournament_select(&ranked, config.tournament, &mut rng);
            let child =
                if rng.random_range(0..1_000) < u32::from(config.mutation_probability_per_mille) {
                    mutate(
                        &parent.expression,
                        config.max_description_cost,
                        semantics,
                        &mut rng,
                    )
                } else {
                    parent.expression.clone()
                };
            next.push(child);
        }
        population = next;
    }

    let best = final_best.ok_or_else(|| {
        LearnerFailure::NoHypothesis("grammar evolution produced no candidate".into())
    })?;
    Ok(EvolutionResult {
        best_expression: best.expression,
        best_row_mismatches: best.fitness.row_mismatches,
        best_bit_mismatches: best.fitness.bit_mismatches,
        evaluated_expressions: evaluator.cache.len(),
        trace,
    })
}

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct Fitness {
    row_mismatches: usize,
    bit_mismatches: usize,
    description_cost: usize,
    estimated_gate_count: usize,
    expression: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct Ranked {
    expression: Expr,
    fitness: Fitness,
}

struct FitnessEvaluator<'a> {
    observed: &'a ObservedTask,
    semantics: ExprSemantics,
    deadline: Instant,
    max_evaluated: usize,
    cache: HashMap<Expr, Fitness>,
}

impl FitnessEvaluator<'_> {
    fn rank(&mut self, population: Vec<Expr>) -> Result<Vec<Ranked>, LearnerFailure> {
        let mut unique = HashSet::new();
        let mut ranked = Vec::new();
        for expression in population {
            if !unique.insert(expression.clone()) {
                continue;
            }
            let fitness = self.fitness(&expression)?;
            ranked.push(Ranked {
                expression,
                fitness,
            });
        }
        if ranked.is_empty() {
            return Err(LearnerFailure::NoHypothesis(
                "grammar evolution population became empty".into(),
            ));
        }
        ranked.sort_by(|lhs, rhs| {
            (&lhs.fitness, &lhs.expression).cmp(&(&rhs.fitness, &rhs.expression))
        });
        Ok(ranked)
    }

    fn fitness(&mut self, expression: &Expr) -> Result<Fitness, LearnerFailure> {
        if let Some(fitness) = self.cache.get(expression) {
            return Ok(fitness.clone());
        }
        if Instant::now() >= self.deadline {
            return Err(LearnerFailure::Timeout(
                "grammar evolution exceeded the trial timeout".into(),
            ));
        }
        if self.cache.len() >= self.max_evaluated {
            return Err(LearnerFailure::ResourceLimit(format!(
                "grammar evolution expression limit {} exceeded",
                self.max_evaluated
            )));
        }
        let mut row_mismatches = 0usize;
        let mut bit_mismatches = 0usize;
        for sample in &self.observed.samples {
            let operand_bits = self.semantics.operand_bits;
            let x = decode_lsb(&sample.input[..operand_bits])
                .map_err(|error| LearnerFailure::ToolError(error.to_string()))?;
            let y = decode_lsb(&sample.input[operand_bits..])
                .map_err(|error| LearnerFailure::ToolError(error.to_string()))?;
            let expected = decode_lsb(&sample.expected)
                .map_err(|error| LearnerFailure::ToolError(error.to_string()))?;
            let actual = expression
                .evaluate(x, y, self.semantics)
                .map_err(|error| LearnerFailure::ToolError(error.to_string()))?;
            if actual != expected {
                row_mismatches += 1;
                bit_mismatches += (actual ^ expected).count_ones() as usize;
            }
        }
        let fitness = Fitness {
            row_mismatches,
            bit_mismatches,
            description_cost: expression.description_cost(),
            estimated_gate_count: estimated_gate_count(expression),
            expression: expression.to_string(),
        };
        self.cache.insert(expression.clone(), fitness.clone());
        Ok(fitness)
    }
}

fn initial_population(
    config: EvolutionConfig,
    semantics: ExprSemantics,
    rng: &mut ChaCha8Rng,
) -> Vec<Expr> {
    let mut population = vec![
        Expr::x(),
        Expr::y(),
        Expr::constant(0),
        Expr::constant(1),
        Expr::square(Expr::x()),
        Expr::square(Expr::y()),
    ];
    for operator in BINARY_OPERATORS {
        population.push(Expr::binary(operator, Expr::x(), Expr::y()));
        population.push(Expr::binary(operator, Expr::y(), Expr::x()));
    }
    while population.len() < config.population {
        population.push(random_expression(
            config.max_description_cost,
            semantics,
            rng,
        ));
    }
    canonical_unique(population, config.max_description_cost)
}

fn tournament_select<'a>(
    ranked: &'a [Ranked],
    tournament: usize,
    rng: &mut ChaCha8Rng,
) -> &'a Ranked {
    let mut selected = rng.random_range(0..ranked.len());
    for _ in 1..tournament {
        selected = selected.min(rng.random_range(0..ranked.len()));
    }
    &ranked[selected]
}

fn mutate(
    expression: &Expr,
    max_cost: usize,
    semantics: ExprSemantics,
    rng: &mut ChaCha8Rng,
) -> Expr {
    let candidate = match rng.random_range(0..5) {
        0 => random_expression(max_cost, semantics, rng),
        1 => replace_operator(expression, rng),
        2 => {
            if rng.random_bool(0.5) {
                Expr::square(expression.clone())
            } else {
                Expr::shift_left(expression.clone(), rng.random_range(1..=3))
            }
        }
        3 => replace_child(expression, max_cost, semantics, rng),
        _ => replace_subtree(expression, max_cost, semantics, rng),
    };
    bounded_canonical(candidate, max_cost).unwrap_or_else(|| expression.clone())
}

fn replace_operator(expression: &Expr, rng: &mut ChaCha8Rng) -> Expr {
    match expression {
        Expr::Binary { lhs, rhs, .. } => Expr::binary(
            BINARY_OPERATORS[rng.random_range(0..BINARY_OPERATORS.len())],
            (**lhs).clone(),
            (**rhs).clone(),
        ),
        Expr::Square(value) | Expr::ShiftLeft { value, .. } => {
            if rng.random_bool(0.5) {
                Expr::square((**value).clone())
            } else {
                Expr::shift_left((**value).clone(), rng.random_range(1..=3))
            }
        }
        _ => expression.clone(),
    }
}

fn replace_child(
    expression: &Expr,
    max_cost: usize,
    semantics: ExprSemantics,
    rng: &mut ChaCha8Rng,
) -> Expr {
    let child = random_expression(max_cost.saturating_sub(2).max(1), semantics, rng);
    match expression {
        Expr::Binary { op, lhs, rhs } if rng.random_bool(0.5) => {
            Expr::binary(*op, child, (**rhs).clone())
        }
        Expr::Binary { op, lhs, .. } => Expr::binary(*op, (**lhs).clone(), child),
        Expr::Square(_) => Expr::square(child),
        Expr::ShiftLeft { amount, .. } => Expr::shift_left(child, *amount),
        _ => child,
    }
}

fn replace_subtree(
    expression: &Expr,
    max_cost: usize,
    semantics: ExprSemantics,
    rng: &mut ChaCha8Rng,
) -> Expr {
    if rng.random_bool(0.35) {
        return random_expression(max_cost, semantics, rng);
    }
    match expression {
        Expr::Binary { op, lhs, rhs } if rng.random_bool(0.5) => Expr::binary(
            *op,
            replace_subtree(lhs, max_cost.saturating_sub(2).max(1), semantics, rng),
            (**rhs).clone(),
        ),
        Expr::Binary { op, lhs, rhs } => Expr::binary(
            *op,
            (**lhs).clone(),
            replace_subtree(rhs, max_cost.saturating_sub(2).max(1), semantics, rng),
        ),
        Expr::Square(value) => Expr::square(replace_subtree(
            value,
            max_cost.saturating_sub(1).max(1),
            semantics,
            rng,
        )),
        Expr::ShiftLeft { value, amount } => Expr::shift_left(
            replace_subtree(value, max_cost.saturating_sub(1).max(1), semantics, rng),
            *amount,
        ),
        _ => random_expression(max_cost, semantics, rng),
    }
}

fn random_expression(max_cost: usize, semantics: ExprSemantics, rng: &mut ChaCha8Rng) -> Expr {
    if max_cost < 2 || rng.random_bool(0.3) {
        return random_terminal(semantics, rng);
    }
    let candidate = if max_cost < 3 || rng.random_bool(0.3) {
        let child = random_expression(max_cost - 1, semantics, rng);
        if rng.random_bool(0.5) {
            Expr::square(child)
        } else {
            Expr::shift_left(child, rng.random_range(1..=3))
        }
    } else {
        let remaining = max_cost - 1;
        let lhs_cost = rng.random_range(1..remaining);
        let rhs_cost = remaining - lhs_cost;
        Expr::binary(
            BINARY_OPERATORS[rng.random_range(0..BINARY_OPERATORS.len())],
            random_expression(lhs_cost, semantics, rng),
            random_expression(rhs_cost, semantics, rng),
        )
    };
    bounded_canonical(candidate, max_cost).unwrap_or_else(|| random_terminal(semantics, rng))
}

fn random_terminal(semantics: ExprSemantics, rng: &mut ChaCha8Rng) -> Expr {
    match rng.random_range(0..4) {
        0 => Expr::x(),
        1 => Expr::y(),
        _ => Expr::constant(rng.random_range(0..=semantics.output_mask().min(3))),
    }
}

fn bounded_canonical(expression: Expr, max_cost: usize) -> Option<Expr> {
    let expression = expression.canonicalize().ok()?;
    (expression.description_cost() <= max_cost).then_some(expression)
}

fn canonical_unique(population: Vec<Expr>, max_cost: usize) -> Vec<Expr> {
    let mut seen = HashSet::new();
    population
        .into_iter()
        .filter_map(|expression| bounded_canonical(expression, max_cost))
        .filter(|expression| seen.insert(expression.clone()))
        .collect()
}

fn estimated_gate_count(expression: &Expr) -> usize {
    match expression {
        Expr::X | Expr::Y | Expr::Constant(_) => 0,
        Expr::Square(value) => estimated_gate_count(value).saturating_add(3),
        Expr::ShiftLeft { value, .. } => estimated_gate_count(value).saturating_add(1),
        Expr::Binary { op, lhs, rhs } => estimated_gate_count(lhs)
            .saturating_add(estimated_gate_count(rhs))
            .saturating_add(match op {
                BinaryOp::Multiply => 4,
                BinaryOp::Add | BinaryOp::Subtract | BinaryOp::AbsDiff => 3,
                BinaryOp::Min | BinaryOp::Max => 2,
                BinaryOp::BitXor | BinaryOp::BitAnd | BinaryOp::BitOr => 1,
            }),
    }
}

fn validate_rows(observed: &ObservedTask) -> Result<(), LearnerFailure> {
    for sample in &observed.samples {
        if sample.input.len() != observed.input_width
            || sample.expected.len() != observed.output_width
        {
            return Err(LearnerFailure::ToolError(
                "observed row width does not match the task".into(),
            ));
        }
    }
    Ok(())
}
