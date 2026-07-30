% Reproducible-seed shim for the official CPMC-Lab initialization script.
%
% CPMC_Lab calls a script named `initialization`.  The official script ends
% by replacing MATLAB's random stream with a clock-derived seed.  This shim
% runs that script unchanged, then applies the approved fixed seed immediately
% before propagation begins.  All initialized physical state is preserved.

cpmc_package_root = getenv('CPMC_LAB_ROOT');
if isempty(cpmc_package_root)
    error('CPMC_LAB_ROOT must point to the official CPMC-Lab directory.');
end
cpmc_official_initialization = fullfile(cpmc_package_root, 'initialization.m');
if ~isfile(cpmc_official_initialization)
    error('Official initialization script not found: %s', cpmc_official_initialization);
end

run(cpmc_official_initialization);

cpmc_seed_text = getenv('CPMC_LAB_SEED');
cpmc_seed = str2double(cpmc_seed_text);
if isempty(cpmc_seed_text) || ~isfinite(cpmc_seed) || ...
        cpmc_seed < 0 || cpmc_seed ~= floor(cpmc_seed)
    error('CPMC_LAB_SEED must be a non-negative integer.');
end
rand('twister', cpmc_seed);

clear cpmc_package_root cpmc_official_initialization cpmc_seed_text cpmc_seed;
