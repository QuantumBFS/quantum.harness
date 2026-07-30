use std::{fs, path::PathBuf, process::Command};

use occam71_rust::{
    Circuit, DEFAULT_LIMITS, circuit_to_blif, evaluate_with_limits, parse_mapped_blif,
    parse_netlist,
};

fn assert_circuits_equivalent(lhs: &Circuit, rhs: &Circuit) {
    assert_eq!(lhs.input_count, rhs.input_count);
    assert_eq!(lhs.outputs.len(), rhs.outputs.len());
    let cases = 1usize << lhs.input_count;
    let mut input = vec![false; lhs.input_count];
    for packed in 0..cases {
        for (bit, value) in input.iter_mut().enumerate() {
            *value = packed & (1 << bit) != 0;
        }
        assert_eq!(
            evaluate_with_limits(lhs, &input, &DEFAULT_LIMITS).unwrap(),
            evaluate_with_limits(rhs, &input, &DEFAULT_LIMITS).unwrap(),
            "input {packed}"
        );
    }
}

fn workspace_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}

#[test]
fn blif_round_trip_preserves_free_inversion_and_gate_count() {
    let source = "\
INPUTS 2
w1 = XOR x1 x2
w2 = NAND w1 ~x1
OUTPUTS ~w2
";
    let circuit = parse_netlist(source).unwrap();
    let blif = circuit_to_blif(&circuit, "roundtrip").unwrap();
    let mapped = parse_mapped_blif(&blif).unwrap();
    let imported = parse_netlist(&mapped.into_official_netlist().unwrap()).unwrap();

    assert_eq!(mapped.model(), "roundtrip");
    assert_eq!(mapped.official_gate_count(), 2);
    assert_eq!(imported.gates.len(), 2);
    assert_circuits_equivalent(&circuit, &imported);
}

#[test]
fn every_official_operation_round_trips_through_names_tables() {
    let source = "\
INPUTS 3
w1 = AND x1 ~x2
w2 = OR ~w1 x3
w3 = XOR w1 w2
w4 = NAND ~w2 x1
w5 = NOR w3 ~w4
w6 = XNOR ~w5 w1
OUTPUTS w1 ~w2 w3 ~w4 w5 ~w6
";
    let circuit = parse_netlist(source).unwrap();
    let mapped = parse_mapped_blif(&circuit_to_blif(&circuit, "basis").unwrap()).unwrap();
    let imported = parse_netlist(&mapped.into_official_netlist().unwrap()).unwrap();

    assert_eq!(imported.gates.len(), circuit.gates.len());
    assert_circuits_equivalent(&circuit, &imported);
}

#[test]
fn mapped_gate_import_topologically_sorts_and_folds_aliases() {
    let mapped = parse_mapped_blif(
        "\
.model mapped
.inputs i0 i1
.outputs o0
.gate INV a=n1 O=o0
.gate XOR2 a=i0 b=i1 O=n1
.end
",
    )
    .unwrap();
    let imported = parse_netlist(&mapped.into_official_netlist().unwrap()).unwrap();
    assert_eq!(imported.gates.len(), 1);
    assert!(imported.outputs[0].inverted);

    let expected = parse_netlist("INPUTS 2\nw1 = XOR x1 x2\nOUTPUTS ~w1\n").unwrap();
    assert_circuits_equivalent(&expected, &imported);
}

#[test]
fn mapped_import_rejects_unsafe_or_unknown_constructs() {
    for source in [
        ".model x\n.inputs a\n.outputs o\n.latch a o\n.end\n",
        ".model x\n.inputs a\n.outputs o\n.subckt child a=a o=o\n.end\n",
        ".model x\n.inputs a b\n.outputs o\n.gate MUX a=a b=b O=o\n.end\n",
        ".model x\n.inputs a\n.outputs o\n.gate INV a=n O=o\n.gate INV a=o O=n\n.end\n",
        ".model x\n.inputs a\n.outputs missing\n.end\n",
    ] {
        assert!(parse_mapped_blif(source).is_err(), "{source}");
    }
}

#[test]
fn pinned_abc_accepts_the_library_and_emits_importable_mapping() {
    let root = workspace_root();
    let commit = "e76768b9d34f9dc67cb6608efecd55db271ff849";
    let abc = root.join(format!("target/tools/abc/{commit}/abc"));
    if !abc.is_file() {
        eprintln!("pinned ABC absent; run ./scripts/fetch-abc.sh");
        return;
    }
    let temporary = std::env::temp_dir().join(format!("occam71-blif-{}", std::process::id()));
    if temporary.exists() {
        fs::remove_dir_all(&temporary).unwrap();
    }
    fs::create_dir_all(&temporary).unwrap();
    let circuit =
        parse_netlist("INPUTS 3\nw1 = XOR x1 x2\nw2 = NAND w1 ~x3\nOUTPUTS ~w2 w1\n").unwrap();
    fs::write(
        temporary.join("original.blif"),
        circuit_to_blif(&circuit, "abc_roundtrip").unwrap(),
    )
    .unwrap();
    fs::copy(
        root.join("tools/abc/occam.genlib"),
        temporary.join("occam.genlib"),
    )
    .unwrap();
    fs::write(
        temporary.join("flow.abc"),
        "\
read_blif original.blif
strash
read_library occam.genlib
map -a
write_blif mapped.blif
quit
",
    )
    .unwrap();
    let output = Command::new(&abc)
        .args(["-f", "flow.abc"])
        .current_dir(&temporary)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "stdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let mapped =
        parse_mapped_blif(&fs::read_to_string(temporary.join("mapped.blif")).unwrap()).unwrap();
    let imported = parse_netlist(&mapped.into_official_netlist().unwrap()).unwrap();
    assert_circuits_equivalent(&circuit, &imported);
    fs::remove_dir_all(temporary).unwrap();
}
