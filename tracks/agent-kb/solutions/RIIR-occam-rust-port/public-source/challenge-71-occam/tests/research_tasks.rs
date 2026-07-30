use std::collections::HashSet;

use occam71_rust::official_and_synthetic_tasks;

#[test]
fn observed_task_contains_no_oracle_or_held_out_labels() {
    let oracle = official_and_synthetic_tasks().unwrap().remove(0);
    let observed = oracle.observe(&[0, 3, 7]).unwrap();
    let json = serde_json::to_value(&observed).unwrap();
    assert!(json.get("oracle").is_none());
    assert!(json.get("held_out").is_none());
    assert!(json.get("full_domain").is_none());
    assert_eq!(observed.samples.len(), 3);
}

#[test]
fn sixteen_domains_are_unique_complete_and_hash_locked_in_memory() {
    let tasks = official_and_synthetic_tasks().unwrap();
    assert_eq!(tasks.len(), 16);
    assert_eq!(
        tasks
            .iter()
            .map(|task| task.id.as_str())
            .collect::<HashSet<_>>()
            .len(),
        16
    );
    for task in tasks {
        let manifest = task.manifest();
        assert_eq!(manifest.domain_rows, 1 << (2 * manifest.operand_bits));
        assert_eq!(manifest.domain_sha256.len(), 64);
        assert_eq!(task.full_domain().samples.len(), manifest.domain_rows);
    }
}
