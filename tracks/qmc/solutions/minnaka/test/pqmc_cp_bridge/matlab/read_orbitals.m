function orbitals = read_orbitals(path, expected_rows, expected_cols)
%READ_ORBITALS Read the strict ASCII matrix shared with ALF and C++.

arguments
    path {mustBeTextScalar}
    expected_rows (1,1) double {mustBeInteger,mustBePositive}
    expected_cols (1,1) double {mustBeInteger,mustBePositive}
end

file_id = fopen(path, 'r');
assert(file_id >= 0, 'bridge:orbitals:open', ...
    'Cannot open orbital file: %s', path);
cleanup = onCleanup(@() fclose(file_id));
shape = fscanf(file_id, '%d', 2);
assert(numel(shape) == 2, 'bridge:orbitals:header', ...
    'Orbital file lacks a two-integer header: %s', path);
assert(shape(1) == expected_rows && shape(2) == expected_cols, ...
    'bridge:orbitals:shape', ...
    'Orbital shape is %dx%d, expected %dx%d', ...
    shape(1), shape(2), expected_rows, expected_cols);
values = fscanf(file_id, '%f');
assert(numel(values) == expected_rows * expected_cols, ...
    'bridge:orbitals:count', 'Orbital value count mismatch: %s', path);
assert(all(isfinite(values)) && isreal(values), ...
    'bridge:orbitals:finite', 'Orbital matrix must be finite and real');
orbitals = reshape(values, [expected_cols, expected_rows]).';
end
