use clean_ising::config::{ExactConfig, CRITICAL_K};
use clean_ising::transfer::{apply_transfer, dominant_eigenpair};

#[test]
fn k_zero_dominant_eigenvalue_is_two_to_l() {
    let cfg = ExactConfig::strict_for_test();
    let result = dominant_eigenpair(6, 0.0, &cfg).unwrap();
    assert!((result.lambda - 64.0).abs() < 1.0e-11);
    assert!(result.residual < cfg.residual_tolerance);
}

#[test]
fn matrix_free_apply_matches_direct_definition() {
    let l = 5;
    let k = CRITICAL_K;
    let input: Vec<f64> = (0..(1 << l)).map(|i| (i + 1) as f64 / 32.0).collect();
    let mut actual = vec![0.0; 1 << l];
    apply_transfer(l, k, &input, &mut actual).unwrap();
    let expected = direct_apply(l, k, &input);
    for (index, (a, e)) in actual.iter().zip(expected).enumerate() {
        assert!(
            (a - e).abs() < 1.0e-11,
            "state {index}: actual={a:.16e}, expected={e:.16e}"
        );
    }
}

#[test]
fn dominant_eigenvalues_match_direct_dense_power_iteration() {
    let cfg = ExactConfig::strict_for_test();
    for l in [2, 4, 6, 8] {
        for k in [0.0, 0.2, CRITICAL_K] {
            let actual = dominant_eigenpair(l, k, &cfg).unwrap().lambda;
            let expected = direct_dominant_eigenvalue(l, k);
            let relative = (actual - expected).abs() / expected;
            assert!(
                relative < 2.0e-12,
                "L={l}, K={k}: actual={actual:.16e}, expected={expected:.16e}"
            );
        }
    }
}

fn direct_apply(l: usize, k: f64, input: &[f64]) -> Vec<f64> {
    let dimension = 1_usize << l;
    let mut output = vec![0.0; dimension];
    for target in 0..dimension {
        let target_horizontal = horizontal_sum(target, l);
        for source in 0..dimension {
            let source_horizontal = horizontal_sum(source, l);
            let vertical: i32 = (0..l)
                .map(|bit| spin(target, bit) * spin(source, bit))
                .sum();
            let exponent =
                k * (0.5 * f64::from(target_horizontal + source_horizontal) + f64::from(vertical));
            output[target] += exponent.exp() * input[source];
        }
    }
    output
}

fn direct_dominant_eigenvalue(l: usize, k: f64) -> f64 {
    let dimension = 1_usize << l;
    let mut vector = vec![1.0 / (dimension as f64).sqrt(); dimension];
    let mut lambda = 0.0;
    for _ in 0..20_000 {
        let output = direct_apply(l, k, &vector);
        let norm = output.iter().map(|value| value * value).sum::<f64>().sqrt();
        let next: Vec<f64> = output.into_iter().map(|value| value / norm).collect();
        let applied = direct_apply(l, k, &next);
        let next_lambda = next
            .iter()
            .zip(applied.iter())
            .map(|(x, tx)| x * tx)
            .sum::<f64>();
        if (next_lambda - lambda).abs() <= 1.0e-14 * next_lambda.abs().max(1.0) {
            return next_lambda;
        }
        vector = next;
        lambda = next_lambda;
    }
    panic!("direct dense power iteration did not converge for L={l}, K={k}");
}

fn horizontal_sum(state: usize, l: usize) -> i32 {
    (0..l)
        .map(|bit| spin(state, bit) * spin(state, (bit + 1) % l))
        .sum()
}

fn spin(state: usize, bit: usize) -> i32 {
    if state & (1 << bit) == 0 {
        -1
    } else {
        1
    }
}
