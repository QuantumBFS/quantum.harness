use nishimori_ising::disorder::{sample_row, DisorderRow};
use nishimori_ising::rng::make_rng;
use nishimori_ising::transfer::apply_transfer;

fn spin(state: usize, bit: usize) -> i32 {
    if state & (1 << bit) == 0 {
        -1
    } else {
        1
    }
}

fn dense_apply(width: usize, k: f64, row: &DisorderRow, input: &[f64]) -> Vec<f64> {
    let dimension = 1 << width;
    let mut output = vec![0.0; dimension];
    for (next, destination) in output.iter_mut().enumerate() {
        let horizontal_energy: i32 = (0..width)
            .map(|site| {
                let neighbor = (site + 1) % width;
                i32::from(row.horizontal[site]) * spin(next, site) * spin(next, neighbor)
            })
            .sum();
        for (previous, source) in input.iter().enumerate() {
            let vertical_energy: i32 = (0..width)
                .map(|site| i32::from(row.vertical[site]) * spin(previous, site) * spin(next, site))
                .sum();
            *destination += (k * f64::from(horizontal_energy + vertical_energy)).exp() * source;
        }
    }
    output
}

#[test]
fn disorder_replay_is_exact_and_widths_are_nested_prefixes() {
    let mut first_rng = make_rng(0x9abc_def0_1234_5678);
    let mut second_rng = make_rng(0x9abc_def0_1234_5678);
    for _ in 0..128 {
        let first = sample_row(14, 0.109_221_2, &mut first_rng).unwrap();
        let second = sample_row(14, 0.109_221_2, &mut second_rng).unwrap();
        assert_eq!(first, second);

        for width in [4, 6, 8, 10, 12] {
            let narrow = first.view(width).unwrap();
            let wider = first.view(width + 2).unwrap();
            assert_eq!(narrow.horizontal, &wider.horizontal[..width]);
            assert_eq!(narrow.vertical, &wider.vertical[..width]);
        }
    }
}

#[test]
fn sampled_negative_bond_frequency_matches_the_contract() {
    let probability = 0.109_221_2;
    let mut rng = make_rng(918_273_645);
    let rows = 20_000;
    let width = 14;
    let mut negative = 0_usize;
    for _ in 0..rows {
        let row = sample_row(width, probability, &mut rng).unwrap();
        negative += row
            .horizontal
            .iter()
            .chain(&row.vertical)
            .filter(|&&bond| bond == -1)
            .count();
    }
    let trials = (2 * rows * width) as f64;
    let observed = negative as f64 / trials;
    let standard_error = (probability * (1.0 - probability) / trials).sqrt();
    assert!((observed - probability).abs() < 5.0 * standard_error);
}

#[test]
fn matrix_free_transfer_matches_literal_dense_sum_through_l6() {
    let mut rng = make_rng(73_991);
    for width in 2..=6 {
        for sample in 0..8 {
            let row = sample_row(width, 0.109_221_2, &mut rng).unwrap();
            let dimension = 1 << width;
            let input: Vec<f64> = (0..dimension)
                .map(|state| 0.25 + ((state + 3 * sample) % 11) as f64 / 13.0)
                .collect();
            let expected = dense_apply(width, 1.049_360_476_302_568_4, &row, &input);
            let mut actual = vec![0.0; dimension];
            apply_transfer(width, 1.049_360_476_302_568_4, &row, &input, &mut actual).unwrap();

            for (got, want) in actual.iter().zip(expected) {
                let scale = want.abs().max(1.0);
                assert!((got - want).abs() <= 2.0e-12 * scale);
            }
        }
    }
}

#[test]
fn invalid_disorder_and_vector_shapes_are_rejected() {
    let row = DisorderRow {
        horizontal: vec![1; 3],
        vertical: vec![1; 3],
    };
    let mut output = vec![0.0; 16];
    assert!(apply_transfer(4, 1.0, &row, &[1.0; 16], &mut output).is_err());

    let row = DisorderRow {
        horizontal: vec![1; 4],
        vertical: vec![1; 4],
    };
    assert!(apply_transfer(4, 1.0, &row, &[1.0; 8], &mut output).is_err());
}
