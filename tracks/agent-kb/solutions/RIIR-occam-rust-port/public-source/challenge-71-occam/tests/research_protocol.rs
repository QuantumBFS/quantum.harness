use std::{collections::HashSet, path::PathBuf};

use occam71_rust::{
    expected_trial_keys, load_experiment_config, official_and_synthetic_tasks, split_task,
};

#[test]
fn sampling_is_without_replacement_and_uses_the_complement() {
    let tasks = official_and_synthetic_tasks().unwrap();
    let task = tasks.iter().find(|task| task.id == "mystery-D").unwrap();
    let first = split_task(task, 0.05, 7, 8_147_115).unwrap();
    let second = split_task(task, 0.05, 7, 8_147_115).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.observed_indices.len(), 51);
    assert_eq!(first.held_out_indices.len(), 973);
    let observed = first.observed_indices.iter().collect::<HashSet<_>>();
    assert!(
        first
            .held_out_indices
            .iter()
            .all(|index| !observed.contains(index))
    );
}

#[test]
fn fixed_protocol_has_exactly_20480_unique_keys() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("experiments/occam-generalization/config.json");
    let config = load_experiment_config(&path).unwrap();
    let task_ids = official_and_synthetic_tasks()
        .unwrap()
        .into_iter()
        .map(|task| task.id)
        .collect::<Vec<_>>();
    let keys = expected_trial_keys(&task_ids, &config).unwrap();
    assert_eq!(keys.len(), 16 * 8 * 20 * 8);
    assert_eq!(keys.iter().collect::<HashSet<_>>().len(), keys.len());
}

#[test]
fn smoke_protocol_has_one_trial_per_task_and_method() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("experiments/occam-generalization-v2/smoke-config.json");
    let config = load_experiment_config(&path).unwrap();
    let task_ids = official_and_synthetic_tasks()
        .unwrap()
        .into_iter()
        .map(|task| task.id)
        .collect::<Vec<_>>();
    let keys = expected_trial_keys(&task_ids, &config).unwrap();
    assert_eq!(keys.len(), 16 * 8);
    assert_eq!(keys.iter().collect::<HashSet<_>>().len(), keys.len());
}
