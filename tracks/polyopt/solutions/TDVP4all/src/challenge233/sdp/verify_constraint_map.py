import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re


class ConstraintVerificationError(RuntimeError):
    pass


_MANIFEST_KEYS = {
    "schema_version",
    "canonicalizer_schema_version",
    "purpose",
    "localizer_semantics",
    "boundary",
    "state_convention",
    "rabi_coefficient",
    "detuning_uniform",
    "algebra",
    "spatial_group",
    "data_file",
    "data_sha256",
    "relation_table_sha256",
    "design_sha256",
    "source_file_sha256",
}

_PAYLOAD_KEYS = {
    "size",
    "moment_basis",
    "localizer_basis",
    "moment_entries",
    "zero_localizers",
    "group_elements",
    "moment_basis_permutations",
    "localizer_basis_permutations",
    "moment_entry_permutations",
    "zero_localizer_permutations",
    "irrep_catalog",
    "moment_sector_multiplicities",
    "localizer_sector_multiplicities",
    "moment_entry_orbits",
    "zero_localizer_orbits",
    "assembly_statistics",
}

_SOURCE_PATHS = {
    "src/challenge233/sdp/algebra.py",
    "src/challenge233/sdp/symmetry.py",
    "src/challenge233/sdp/basis.py",
    "src/challenge233/sdp/constraints.py",
    "src/challenge233/sdp/artifact.py",
}

_ZERO = (Fraction(0), Fraction(0))
_ONE = (Fraction(1), Fraction(0))
_NEG_ONE = (Fraction(-1), Fraction(0))
_POS_I = (Fraction(0), Fraction(1))
_NEG_I = (Fraction(0), Fraction(-1))
_HALF = (Fraction(1, 2), Fraction(0))

_LOCAL_PRODUCTS = {
    ("I", "I"): (_ONE, "I"),
    ("I", "X"): (_ONE, "X"),
    ("I", "Y"): (_ONE, "Y"),
    ("I", "Z"): (_ONE, "Z"),
    ("X", "I"): (_ONE, "X"),
    ("Y", "I"): (_ONE, "Y"),
    ("Z", "I"): (_ONE, "Z"),
    ("X", "X"): (_ONE, "I"),
    ("Y", "Y"): (_ONE, "I"),
    ("Z", "Z"): (_ONE, "I"),
    ("X", "Y"): (_POS_I, "Z"),
    ("Y", "Z"): (_POS_I, "X"),
    ("Z", "X"): (_POS_I, "Y"),
    ("Y", "X"): (_NEG_I, "Z"),
    ("Z", "Y"): (_NEG_I, "X"),
    ("X", "Z"): (_NEG_I, "Y"),
}

_FRACTION_PATTERN = re.compile(r"-?(?:0|[1-9][0-9]*)/[1-9][0-9]*")


def _fail(message):
    raise ConstraintVerificationError(message)


def _exact_keys(value, expected, component):
    if not isinstance(value, dict):
        _fail(f"{component} must be a JSON object")
    actual = set(value)
    unknown = sorted(actual - set(expected))
    if unknown:
        _fail(f"{component} has unknown key: {unknown[0]}")
    missing = sorted(set(expected) - actual)
    if missing:
        _fail(f"{component} is missing key: {missing[0]}")


def _integer(value, component):
    if type(value) is not int:
        _fail(f"{component} must be an integer")
    return value


def _fraction_text(value):
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _parse_fraction(value, component):
    if (
        not isinstance(value, str)
        or _FRACTION_PATTERN.fullmatch(value) is None
    ):
        _fail(f"{component} is not a canonical rational string")
    try:
        parsed = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ConstraintVerificationError(
            f"{component} is not a valid rational"
        ) from error
    if _fraction_text(parsed) != value:
        _fail(f"{component} is not in lowest terms")
    return parsed


def _coefficient_add(left, right):
    return (left[0] + right[0], left[1] + right[1])


def _coefficient_multiply(left, right):
    return (
        left[0] * right[0] - left[1] * right[1],
        left[0] * right[1] + left[1] * right[0],
    )


def _coefficient_conjugate(value):
    return (value[0], -value[1])


def _decode_coefficient(value, component):
    _exact_keys(value, {"real", "imag"}, component)
    return (
        _parse_fraction(value["real"], f"{component}.real"),
        _parse_fraction(value["imag"], f"{component}.imag"),
    )


def _canonicalize_factors(factors):
    phase = _ONE
    local = {}
    for site, label in factors:
        previous = local.get(site, "I")
        local_phase, result = _LOCAL_PRODUCTS[(previous, label)]
        phase = _coefficient_multiply(phase, local_phase)
        if result == "I":
            local.pop(site, None)
        else:
            local[site] = result
    return phase, tuple(sorted(local.items()))


def _normalize_polynomial(terms):
    combined = {}
    for word, coefficient in terms:
        combined[word] = _coefficient_add(
            combined.get(word, _ZERO),
            coefficient,
        )
    return tuple(
        (word, coefficient)
        for word, coefficient in sorted(combined.items())
        if coefficient != _ZERO
    )


def _word_polynomial(word):
    return ((word, _ONE),)


def _polynomial_adjoint(polynomial):
    return _normalize_polynomial(
        (
            word,
            _coefficient_conjugate(coefficient),
        )
        for word, coefficient in polynomial
    )


def _polynomial_multiply(left, right):
    products = []
    for left_word, left_coefficient in left:
        for right_word, right_coefficient in right:
            phase, word = _canonicalize_factors(
                left_word + right_word
            )
            products.append(
                (
                    word,
                    _coefficient_multiply(
                        _coefficient_multiply(
                            left_coefficient,
                            right_coefficient,
                        ),
                        phase,
                    ),
                )
            )
    return _normalize_polynomial(products)


def _decode_word(value, size, component):
    if not isinstance(value, list):
        _fail(f"{component} must be a factor list")
    factors = []
    for factor_index, factor in enumerate(value):
        if not isinstance(factor, list) or len(factor) != 2:
            _fail(
                f"{component} factor {factor_index} must be [site, label]"
            )
        site = _integer(
            factor[0],
            f"{component} factor {factor_index} site",
        )
        label = factor[1]
        if not 0 <= site < size:
            _fail(
                f"{component} factor {factor_index} site is out of range"
            )
        if label not in {"X", "Y", "Z"}:
            _fail(
                f"{component} factor {factor_index} has invalid label"
            )
        factors.append((site, label))
    word = tuple(factors)
    sites = tuple(site for site, _ in word)
    if sites != tuple(sorted(set(sites))):
        _fail(f"{component} is not in canonical site order")
    return word


def _decode_polynomial(value, size, component):
    if not isinstance(value, list):
        _fail(f"{component} must be a term list")
    terms = []
    for term_index, term in enumerate(value):
        term_component = f"{component} term {term_index}"
        _exact_keys(
            term,
            {"word", "coefficient"},
            term_component,
        )
        word = _decode_word(
            term["word"],
            size,
            f"{term_component} word",
        )
        coefficient = _decode_coefficient(
            term["coefficient"],
            f"{term_component} coefficient",
        )
        if coefficient == _ZERO:
            _fail(f"{term_component} has a zero coefficient")
        terms.append((word, coefficient))
    if tuple(terms) != tuple(sorted(terms)):
        _fail(f"{component} terms are not canonically ordered")
    if len({word for word, _ in terms}) != len(terms):
        _fail(f"{component} contains duplicate words")
    return tuple(terms)


def _blockade_polynomial(site, size):
    next_site = (site + 1) % size
    left = _normalize_polynomial(
        (
            ((), _HALF),
            (((site, "Z"),), _HALF),
        )
    )
    right = _normalize_polynomial(
        (
            ((), _HALF),
            (((next_site, "Z"),), _HALF),
        )
    )
    return _polynomial_multiply(left, right)


def _normalize_element(element, size):
    return (element[0] % size, bool(element[1]))


def _compose_elements(left, right, size):
    sign = -1 if left[1] else 1
    return _normalize_element(
        (
            left[0] + sign * right[0],
            left[1] ^ right[1],
        ),
        size,
    )


def _site_action(element, site, size):
    sign = -1 if element[1] else 1
    return (element[0] + sign * site) % size


def _word_action(element, word, size):
    return tuple(
        sorted(
            (
                _site_action(element, site, size),
                label,
            )
            for site, label in word
        )
    )


def _polynomial_action(element, polynomial, size):
    return _normalize_polynomial(
        (
            _word_action(element, word, size),
            coefficient,
        )
        for word, coefficient in polynomial
    )


def _blockade_site_action(element, site, size):
    if element[1]:
        return (element[0] - site - 1) % size
    return (element[0] + site) % size


def _canonical_relation_table_json():
    local_products = {}
    for (left, right), (phase, result) in sorted(
        _LOCAL_PRODUCTS.items()
    ):
        local_products[f"{left},{right}"] = {
            "phase": {
                "real": _fraction_text(phase[0]),
                "imag": _fraction_text(phase[1]),
            },
            "result": result,
        }
    payload = {
        "definitions": {
            "P": "(I-Z)/2",
            "Y": "iXZ",
            "n": "(I+Z)/2",
        },
        "different_site": "commute",
        "local_products": local_products,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_json(path, component):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConstraintVerificationError(
            f"cannot read {component}: {error}"
        ) from error


def _verify_manifest(output_directory):
    manifest_path = output_directory / "manifest.json"
    manifest = _load_json(manifest_path, "manifest")
    _exact_keys(manifest, _MANIFEST_KEYS, "manifest")
    expected_values = {
        "schema_version": 1,
        "canonicalizer_schema_version": 1,
        "purpose": (
            "legacy-structural-arbitrary-sandwich-not-solver-input"
        ),
        "localizer_semantics": "unsound-for-state-support",
        "boundary": "periodic",
        "state_convention": "0=down, 1=up",
        "rabi_coefficient": "1",
        "detuning_uniform": True,
        "algebra": "pauli-xz-derived-y-p-n",
        "spatial_group": "D_N",
        "data_file": "constraint-map.json",
    }
    for key, expected in expected_values.items():
        if manifest[key] != expected:
            _fail(f"manifest {key} does not match the schema")

    data_path = output_directory / manifest["data_file"]
    try:
        data_bytes = data_path.read_bytes()
    except OSError as error:
        raise ConstraintVerificationError(
            f"cannot read constraint-map data: {error}"
        ) from error
    if hashlib.sha256(data_bytes).hexdigest() != manifest["data_sha256"]:
        _fail("constraint-map data SHA-256 does not match manifest")

    relation_hash = hashlib.sha256(
        _canonical_relation_table_json().encode("utf-8")
    ).hexdigest()
    if relation_hash != manifest["relation_table_sha256"]:
        _fail("relation-table SHA-256 does not match manifest")

    project_root = Path(__file__).resolve().parents[3]
    design_path = (
        project_root
        / "docs/superpowers/specs/"
        / "2026-07-29-pxp-sdp-algebra-symmetry-design.md"
    )
    if hashlib.sha256(
        design_path.read_bytes()
    ).hexdigest() != manifest["design_sha256"]:
        _fail("design SHA-256 does not match manifest")

    source_hashes = manifest["source_file_sha256"]
    _exact_keys(
        source_hashes,
        _SOURCE_PATHS,
        "manifest source_file_sha256",
    )
    for relative_path in sorted(_SOURCE_PATHS):
        actual_hash = hashlib.sha256(
            (project_root / relative_path).read_bytes()
        ).hexdigest()
        if actual_hash != source_hashes[relative_path]:
            _fail(
                "source SHA-256 does not match manifest: "
                f"{relative_path}"
            )
    return data_path


def _decode_basis(value, size, component):
    if not isinstance(value, list):
        _fail(f"{component} must be a list")
    words = tuple(
        _decode_word(
            raw_word,
            size,
            f"{component} word {index}",
        )
        for index, raw_word in enumerate(value)
    )
    if len(set(words)) != len(words):
        _fail(f"{component} contains duplicate words")
    return words


def _verify_moment_entries(raw_entries, basis, size):
    if not isinstance(raw_entries, list):
        _fail("moment_entries must be a list")
    expected_count = len(basis) ** 2
    if len(raw_entries) != expected_count:
        _fail(
            "moment entry count does not equal the basis square"
        )
    entries = []
    for index, raw_entry in enumerate(raw_entries):
        component = f"moment entry {index}"
        _exact_keys(
            raw_entry,
            {"row", "column", "polynomial"},
            component,
        )
        row = _integer(raw_entry["row"], f"{component} row")
        column = _integer(
            raw_entry["column"],
            f"{component} column",
        )
        expected_row, expected_column = divmod(
            index,
            len(basis),
        )
        if (row, column) != (expected_row, expected_column):
            _fail(f"{component} index metadata is inconsistent")
        polynomial = _decode_polynomial(
            raw_entry["polynomial"],
            size,
            f"{component} polynomial",
        )
        expected_polynomial = _polynomial_multiply(
            _polynomial_adjoint(
                _word_polynomial(basis[row])
            ),
            _word_polynomial(basis[column]),
        )
        if polynomial != expected_polynomial:
            _fail(f"moment product mismatch at index {index}")
        entries.append((row, column, polynomial))
    return tuple(entries)


def _verify_zero_localizers(raw_entries, basis, size):
    if not isinstance(raw_entries, list):
        _fail("zero_localizers must be a list")
    basis_size = len(basis)
    expected_count = size * basis_size**2
    if len(raw_entries) != expected_count:
        _fail(
            "localizer row count does not equal "
            "N times the localizer-basis square"
        )
    entries = []
    block_size = basis_size**2
    for index, raw_entry in enumerate(raw_entries):
        component = f"zero localizer {index}"
        _exact_keys(
            raw_entry,
            {"site", "row", "column", "polynomial"},
            component,
        )
        site = _integer(raw_entry["site"], f"{component} site")
        row = _integer(raw_entry["row"], f"{component} row")
        column = _integer(
            raw_entry["column"],
            f"{component} column",
        )
        expected_site = index // block_size
        within_site = index % block_size
        expected_row, expected_column = divmod(
            within_site,
            basis_size,
        )
        if (
            site,
            row,
            column,
        ) != (
            expected_site,
            expected_row,
            expected_column,
        ):
            _fail(f"{component} index metadata is inconsistent")
        polynomial = _decode_polynomial(
            raw_entry["polynomial"],
            size,
            f"{component} polynomial",
        )
        expected_polynomial = _polynomial_multiply(
            _polynomial_multiply(
                _polynomial_adjoint(
                    _word_polynomial(basis[row])
                ),
                _blockade_polynomial(site, size),
            ),
            _word_polynomial(basis[column]),
        )
        if polynomial != expected_polynomial:
            _fail(f"localizer product mismatch at index {index}")
        entries.append((site, row, column, polynomial))
    return tuple(entries)


def _verify_group_elements(raw_elements, size):
    if not isinstance(raw_elements, list):
        _fail("group_elements must be a list")
    elements = []
    for index, raw_element in enumerate(raw_elements):
        component = f"group element {index}"
        _exact_keys(
            raw_element,
            {"shift", "reflected"},
            component,
        )
        shift = _integer(
            raw_element["shift"],
            f"{component} shift",
        )
        reflected = raw_element["reflected"]
        if type(reflected) is not bool:
            _fail(f"{component} reflected must be Boolean")
        elements.append((shift, reflected))
    expected = tuple(
        (shift, reflected)
        for reflected in (False, True)
        for shift in range(size)
    )
    if tuple(elements) != expected:
        _fail("group element list is not the complete ordered D_N")

    identity = (0, False)
    translation = (1, False)
    reflection = (0, True)
    power = identity
    for _ in range(size):
        power = _compose_elements(translation, power, size)
    if power != identity:
        _fail("D_N relation T^N=I failed")
    if (
        _compose_elements(reflection, reflection, size)
        != identity
    ):
        _fail("D_N relation R^2=I failed")
    if _compose_elements(
        reflection,
        _compose_elements(translation, reflection, size),
        size,
    ) != (size - 1, False):
        _fail("D_N relation RTR=T^-1 failed")
    return expected


def _decode_permutations(
    raw_permutations,
    group_order,
    representation_size,
    component,
):
    if not isinstance(raw_permutations, list):
        _fail(f"{component} must be a list")
    if len(raw_permutations) != group_order:
        _fail(f"{component} does not contain every group element")
    result = []
    for index, raw_permutation in enumerate(raw_permutations):
        if not isinstance(raw_permutation, list):
            _fail(f"{component} {index} must be a list")
        permutation = tuple(
            _integer(
                value,
                f"{component} {index} value {position}",
            )
            for position, value in enumerate(raw_permutation)
        )
        if len(permutation) != representation_size:
            _fail(f"{component} {index} has the wrong length")
        if sorted(permutation) != list(range(representation_size)):
            _fail(f"{component} {index} is not a permutation")
        result.append(permutation)
    return tuple(result)


def _expected_basis_permutation(
    basis,
    element,
    size,
    component,
):
    index = {word: position for position, word in enumerate(basis)}
    permutation = []
    for word in basis:
        image = _word_action(element, word, size)
        if image not in index:
            _fail(f"{component} is not closed under D_N")
        permutation.append(index[image])
    return tuple(permutation)


def _permutation_message(element, component):
    action = "reflection" if element[1] else "translation"
    return f"{action} permutation mismatch in {component}"


def _verify_permutations(
    payload,
    size,
    elements,
    moment_basis,
    localizer_basis,
    moment_entries,
    localizer_entries,
):
    group_order = len(elements)
    moment_basis_permutations = _decode_permutations(
        payload["moment_basis_permutations"],
        group_order,
        len(moment_basis),
        "moment-basis permutations",
    )
    localizer_basis_permutations = _decode_permutations(
        payload["localizer_basis_permutations"],
        group_order,
        len(localizer_basis),
        "localizer-basis permutations",
    )
    moment_entry_permutations = _decode_permutations(
        payload["moment_entry_permutations"],
        group_order,
        len(moment_entries),
        "moment-entry permutations",
    )
    zero_localizer_permutations = _decode_permutations(
        payload["zero_localizer_permutations"],
        group_order,
        len(localizer_entries),
        "zero-localizer permutations",
    )

    moment_size = len(moment_basis)
    localizer_size = len(localizer_basis)
    localizer_block_size = localizer_size**2
    for group_index, element in enumerate(elements):
        expected_moment_basis = _expected_basis_permutation(
            moment_basis,
            element,
            size,
            "moment basis",
        )
        if (
            moment_basis_permutations[group_index]
            != expected_moment_basis
        ):
            _fail(_permutation_message(element, "moment basis"))

        expected_localizer_basis = _expected_basis_permutation(
            localizer_basis,
            element,
            size,
            "localizer basis",
        )
        if (
            localizer_basis_permutations[group_index]
            != expected_localizer_basis
        ):
            _fail(_permutation_message(element, "localizer basis"))

        expected_moment_entries = tuple(
            expected_moment_basis[row] * moment_size
            + expected_moment_basis[column]
            for row in range(moment_size)
            for column in range(moment_size)
        )
        if (
            moment_entry_permutations[group_index]
            != expected_moment_entries
        ):
            _fail(_permutation_message(element, "moment entries"))

        expected_localizers = tuple(
            _blockade_site_action(element, site, size)
            * localizer_block_size
            + expected_localizer_basis[row] * localizer_size
            + expected_localizer_basis[column]
            for site in range(size)
            for row in range(localizer_size)
            for column in range(localizer_size)
        )
        if (
            zero_localizer_permutations[group_index]
            != expected_localizers
        ):
            _fail(
                _permutation_message(element, "zero localizers")
            )

        for source, destination in enumerate(
            expected_moment_entries
        ):
            if _polynomial_action(
                element,
                moment_entries[source][2],
                size,
            ) != moment_entries[destination][2]:
                _fail(
                    "moment-entry equivariance mismatch at "
                    f"group {group_index}, index {source}"
                )
        for source, destination in enumerate(expected_localizers):
            if _polynomial_action(
                element,
                localizer_entries[source][3],
                size,
            ) != localizer_entries[destination][3]:
                _fail(
                    "zero-localizer equivariance mismatch at "
                    f"group {group_index}, index {source}"
                )

    return (
        moment_basis_permutations,
        localizer_basis_permutations,
        moment_entry_permutations,
        zero_localizer_permutations,
    )


def _expected_irrep_catalog(size):
    catalog = [
        {
            "label": "k=0,r=+1",
            "dimension": 1,
            "momenta": [0],
            "reflection_parity": 1,
        },
        {
            "label": "k=0,r=-1",
            "dimension": 1,
            "momenta": [0],
            "reflection_parity": -1,
        },
    ]
    if size % 2 == 0:
        catalog.extend(
            (
                {
                    "label": "k=pi,r=+1",
                    "dimension": 1,
                    "momenta": [size // 2],
                    "reflection_parity": 1,
                },
                {
                    "label": "k=pi,r=-1",
                    "dimension": 1,
                    "momenta": [size // 2],
                    "reflection_parity": -1,
                },
            )
        )
    for momentum in range(1, (size + 1) // 2):
        catalog.append(
            {
                "label": f"k={momentum}<->{size - momentum}",
                "dimension": 2,
                "momenta": [momentum, size - momentum],
                "reflection_parity": None,
            }
        )
    return tuple(catalog)


def _verify_irrep_catalog(raw_catalog, size):
    if not isinstance(raw_catalog, list):
        _fail("irrep_catalog must be a list")
    expected = _expected_irrep_catalog(size)
    if len(raw_catalog) != len(expected):
        _fail("irrep catalog has the wrong number of sectors")
    decoded = []
    for index, (raw_irrep, expected_irrep) in enumerate(
        zip(raw_catalog, expected)
    ):
        component = f"irrep catalog entry {index}"
        _exact_keys(
            raw_irrep,
            {
                "label",
                "dimension",
                "momenta",
                "reflection_parity",
            },
            component,
        )
        label = raw_irrep["label"]
        dimension = _integer(
            raw_irrep["dimension"],
            f"{component} dimension",
        )
        raw_momenta = raw_irrep["momenta"]
        if not isinstance(raw_momenta, list):
            _fail(f"{component} momenta must be a list")
        momenta = [
            _integer(value, f"{component} momentum")
            for value in raw_momenta
        ]
        parity = raw_irrep["reflection_parity"]
        if dimension == 2:
            if (
                len(momenta) != 2
                or sum(momenta) % size != 0
            ):
                _fail(f"momentum pair is incomplete at {component}")
            if parity is not None:
                _fail(
                    f"reflection parity must be null at {component}"
                )
        else:
            if parity not in (-1, 1):
                _fail(f"reflection parity is invalid at {component}")

        if label != expected_irrep["label"]:
            _fail(f"{component} label is not the complete D_N catalog")
        if dimension != expected_irrep["dimension"]:
            _fail(f"{component} dimension is incorrect")
        if momenta != expected_irrep["momenta"]:
            if expected_irrep["dimension"] == 2:
                _fail(f"momentum pair is incorrect at {component}")
            _fail(f"{component} self-inverse momentum is incorrect")
        if parity != expected_irrep["reflection_parity"]:
            _fail(f"reflection parity mismatch at {component}")
        decoded.append(
            {
                "label": label,
                "dimension": dimension,
                "momenta": momenta,
                "reflection_parity": parity,
            }
        )
    if sum(item["dimension"] ** 2 for item in decoded) != 2 * size:
        _fail("irrep catalog fails the D_N group-dimension sum")
    return tuple(decoded)


def _translation_orbits(basis, size):
    translation = (1, False)
    unassigned = set(basis)
    result = []
    while unassigned:
        representative = min(unassigned)
        members = []
        current = representative
        for _ in range(size):
            if current in members:
                break
            members.append(current)
            current = _word_action(translation, current, size)
        if current != representative:
            _fail("translation orbit did not close")
        if not set(members) <= unassigned:
            _fail("translation orbits overlap")
        unassigned.difference_update(members)
        result.append((representative, tuple(members)))
    return tuple(result)


def _expected_sector_multiplicities(basis, size, catalog):
    orbits = _translation_orbits(basis, size)
    location = {}
    for orbit_index, (_, members) in enumerate(orbits):
        for shift, word in enumerate(members):
            location[word] = (orbit_index, shift)

    counts = {item["label"]: 0 for item in catalog}
    for irrep in catalog:
        if irrep["dimension"] == 2:
            momentum = irrep["momenta"][0]
            counts[irrep["label"]] = sum(
                (momentum * len(members)) % size == 0
                for _, members in orbits
            )

    self_inverse = [0]
    if size % 2 == 0:
        self_inverse.append(size // 2)
    reflection = (0, True)
    for momentum in self_inverse:
        supporting = {
            index
            for index, (_, members) in enumerate(orbits)
            if (momentum * len(members)) % size == 0
        }
        remaining = set(supporting)
        parity_counts = {1: 0, -1: 0}
        while remaining:
            orbit_index = min(remaining)
            representative = orbits[orbit_index][0]
            image = _word_action(
                reflection,
                representative,
                size,
            )
            image_orbit, shift = location[image]
            if image_orbit not in supporting:
                _fail(
                    "reflection does not preserve self-inverse momentum"
                )
            if image_orbit == orbit_index:
                parity = (
                    1
                    if (momentum * shift) % size == 0
                    else -1
                )
                parity_counts[parity] += 1
                remaining.remove(orbit_index)
            else:
                if image_orbit not in remaining:
                    _fail(
                        "reflection orbit pairing is not involutive"
                    )
                parity_counts[1] += 1
                parity_counts[-1] += 1
                remaining.remove(orbit_index)
                remaining.remove(image_orbit)
        momentum_label = "0" if momentum == 0 else "pi"
        counts[f"k={momentum_label},r=+1"] = parity_counts[1]
        counts[f"k={momentum_label},r=-1"] = parity_counts[-1]

    return tuple(
        {
            "label": irrep["label"],
            "multiplicity": counts[irrep["label"]],
        }
        for irrep in catalog
    )


def _verify_sector_multiplicities(
    raw_inventory,
    basis,
    size,
    catalog,
    component,
):
    if not isinstance(raw_inventory, list):
        _fail(f"{component} must be a list")
    decoded = []
    for index, raw_item in enumerate(raw_inventory):
        item_component = f"{component} entry {index}"
        _exact_keys(
            raw_item,
            {"label", "multiplicity"},
            item_component,
        )
        label = raw_item["label"]
        if not isinstance(label, str):
            _fail(f"{item_component} label must be a string")
        multiplicity = _integer(
            raw_item["multiplicity"],
            f"{item_component} multiplicity",
        )
        if multiplicity < 0:
            _fail(f"{item_component} multiplicity is negative")
        decoded.append(
            {
                "label": label,
                "multiplicity": multiplicity,
            }
        )
    expected = _expected_sector_multiplicities(
        basis,
        size,
        catalog,
    )
    if tuple(decoded) != expected:
        _fail(f"{component} do not match the exact D_N decomposition")
    represented_dimension = sum(
        irrep["dimension"] * item["multiplicity"]
        for irrep, item in zip(catalog, decoded)
    )
    if represented_dimension != len(basis):
        _fail(
            f"{component} do not reconstruct the basis dimension"
        )
    return tuple(decoded)


def _expected_index_orbits(table_size, permutations):
    unassigned = set(range(table_size))
    result = []
    while unassigned:
        representative = min(unassigned)
        members = tuple(
            sorted(
                {
                    permutation[representative]
                    for permutation in permutations
                }
            )
        )
        if not set(members) <= unassigned:
            _fail("equivariance index orbits overlap")
        unassigned.difference_update(members)
        result.append(
            {
                "representative": representative,
                "members": list(members),
            }
        )
    return tuple(result)


def _decode_orbits(raw_orbits, component):
    if not isinstance(raw_orbits, list):
        _fail(f"{component} must be a list")
    decoded = []
    for index, raw_orbit in enumerate(raw_orbits):
        orbit_component = f"{component} entry {index}"
        _exact_keys(
            raw_orbit,
            {"representative", "members"},
            orbit_component,
        )
        representative = _integer(
            raw_orbit["representative"],
            f"{orbit_component} representative",
        )
        raw_members = raw_orbit["members"]
        if not isinstance(raw_members, list):
            _fail(f"{orbit_component} members must be a list")
        members = [
            _integer(
                member,
                f"{orbit_component} member",
            )
            for member in raw_members
        ]
        decoded.append(
            {
                "representative": representative,
                "members": members,
            }
        )
    return tuple(decoded)


def _group_index_for_member(
    representative,
    member,
    permutations,
):
    for group_index, permutation in enumerate(permutations):
        if permutation[representative] == member:
            return group_index
    _fail("equivariance orbit member is unreachable")


def _verify_moment_orbits(
    raw_orbits,
    permutations,
    elements,
    entries,
    size,
):
    decoded = _decode_orbits(raw_orbits, "moment-entry orbits")
    expected = _expected_index_orbits(len(entries), permutations)
    if decoded != expected:
        _fail("moment-entry orbits do not match the group action")
    for orbit in decoded:
        representative = orbit["representative"]
        representative_polynomial = entries[representative][2]
        for member in orbit["members"]:
            group_index = _group_index_for_member(
                representative,
                member,
                permutations,
            )
            expanded = _polynomial_action(
                elements[group_index],
                representative_polynomial,
                size,
            )
            if expanded != entries[member][2]:
                _fail(
                    "moment-entry orbit expansion mismatch at "
                    f"index {member}"
                )


def _verify_localizer_orbits(
    raw_orbits,
    permutations,
    elements,
    entries,
    size,
):
    decoded = _decode_orbits(
        raw_orbits,
        "zero-localizer orbits",
    )
    expected = _expected_index_orbits(len(entries), permutations)
    if decoded != expected:
        _fail("zero-localizer orbits do not match the group action")
    for orbit in decoded:
        representative = orbit["representative"]
        representative_polynomial = entries[representative][3]
        for member in orbit["members"]:
            group_index = _group_index_for_member(
                representative,
                member,
                permutations,
            )
            expanded = _polynomial_action(
                elements[group_index],
                representative_polynomial,
                size,
            )
            if expanded != entries[member][3]:
                _fail(
                    "zero-localizer orbit expansion mismatch at "
                    f"index {member}"
                )


def _verify_statistics(
    raw_statistics,
    size,
    moment_basis_size,
    localizer_basis_size,
):
    expected = {
        "moment_basis_size": moment_basis_size,
        "moment_entry_count": moment_basis_size**2,
        "localizer_basis_size": localizer_basis_size,
        "zero_localizer_count": size * localizer_basis_size**2,
        "group_order": 2 * size,
        "dense_complex_matrix_bytes": (
            16 * moment_basis_size**2
            + 16 * size * localizer_basis_size**2
        ),
    }
    _exact_keys(
        raw_statistics,
        set(expected),
        "assembly_statistics",
    )
    for key, expected_value in expected.items():
        value = _integer(
            raw_statistics[key],
            f"assembly_statistics {key}",
        )
        if value != expected_value:
            _fail(f"assembly statistic {key} is incorrect")
    return expected


def _verify_constraint_map(output_directory):
    output_directory = Path(output_directory)
    data_path = _verify_manifest(output_directory)
    payload = _load_json(data_path, "constraint-map data")
    _exact_keys(payload, _PAYLOAD_KEYS, "constraint-map payload")

    size = _integer(payload["size"], "constraint-map size")
    if size < 4:
        _fail("constraint-map size must be at least 4")
    moment_basis = _decode_basis(
        payload["moment_basis"],
        size,
        "moment_basis",
    )
    localizer_basis = _decode_basis(
        payload["localizer_basis"],
        size,
        "localizer_basis",
    )
    moment_entries = _verify_moment_entries(
        payload["moment_entries"],
        moment_basis,
        size,
    )
    localizer_entries = _verify_zero_localizers(
        payload["zero_localizers"],
        localizer_basis,
        size,
    )
    elements = _verify_group_elements(
        payload["group_elements"],
        size,
    )
    (
        _,
        _,
        moment_entry_permutations,
        zero_localizer_permutations,
    ) = _verify_permutations(
        payload,
        size,
        elements,
        moment_basis,
        localizer_basis,
        moment_entries,
        localizer_entries,
    )
    catalog = _verify_irrep_catalog(
        payload["irrep_catalog"],
        size,
    )
    _verify_sector_multiplicities(
        payload["moment_sector_multiplicities"],
        moment_basis,
        size,
        catalog,
        "moment sector multiplicities",
    )
    _verify_sector_multiplicities(
        payload["localizer_sector_multiplicities"],
        localizer_basis,
        size,
        catalog,
        "localizer sector multiplicities",
    )
    _verify_moment_orbits(
        payload["moment_entry_orbits"],
        moment_entry_permutations,
        elements,
        moment_entries,
        size,
    )
    _verify_localizer_orbits(
        payload["zero_localizer_orbits"],
        zero_localizer_permutations,
        elements,
        localizer_entries,
        size,
    )
    statistics = _verify_statistics(
        payload["assembly_statistics"],
        size,
        len(moment_basis),
        len(localizer_basis),
    )
    return {
        "status": "verified",
        "size": size,
        "group_order": len(elements),
        "localizer_site_count": len(
            {entry[0] for entry in localizer_entries}
        ),
        "moment_entry_count": statistics["moment_entry_count"],
        "zero_localizer_count": statistics[
            "zero_localizer_count"
        ],
    }


def verify_constraint_map(output_directory):
    try:
        return _verify_constraint_map(output_directory)
    except ConstraintVerificationError:
        raise
    except (
        IndexError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        ZeroDivisionError,
    ) as error:
        raise ConstraintVerificationError(
            f"malformed constraint-map artifact: {error}"
        ) from error


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently verify a PXP structural constraint map"
    )
    parser.add_argument("run_directory")
    arguments = parser.parse_args(argv)
    try:
        summary = verify_constraint_map(arguments.run_directory)
    except ConstraintVerificationError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
