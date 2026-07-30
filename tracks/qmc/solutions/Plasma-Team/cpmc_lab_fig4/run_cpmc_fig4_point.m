function run_cpmc_fig4_point(run_dir, package_dir, point_name, seed)
%RUN_CPMC_FIG4_POINT Run one approved CPMC-Lab reproduction point.
%
% The official CPMC-Lab routine writes its MAT file into the current
% directory. This wrapper isolates every point, verifies the complete MAT
% output, records CSV summaries, and writes DONE.json before MATLAB shutdown.
% DONE.json plus the MAT/CSV files are the success criterion because the local
% MATLAB R2025a can crash in DDUX cleanup after valid output has been written.

arguments
    run_dir (1,1) string
    package_dir (1,1) string
    point_name (1,1) string
    seed (1,1) double {mustBeInteger,mustBeNonnegative}
end

run_dir = string(java.io.File(char(run_dir)).getCanonicalPath());
package_dir = string(java.io.File(char(package_dir)).getCanonicalPath());
assert(isfile(fullfile(package_dir, "CPMC_Lab.m")), ...
    "CPMC-Lab entry point not found: %s", package_dir);

cfg = point_config(point_name, seed);
point_dir = fullfile(run_dir, "raw", cfg.slug);
if ~isfolder(point_dir)
    mkdir(point_dir);
end

done_path = fullfile(point_dir, "DONE.json");
failed_path = fullfile(point_dir, "FAILED.json");
if isfile(done_path)
    fprintf("POINT_ALREADY_COMPLETE=%s\n", cfg.slug);
    return;
end
if isfile(failed_path)
    delete(failed_path);
end

old_dir = string(pwd);
cleanup_dir = onCleanup(@() cd(old_dir)); %#ok<NASGU>
cd(point_dir);

driver_dir = string(fileparts(mfilename("fullpath")));
addpath(package_dir, "-end");
addpath(driver_dir, "-begin");
assert(string(which("initialization")) == fullfile(driver_dir, "initialization.m"), ...
    "The reproducible initialization shim is not first on the MATLAB path.");
setenv("CPMC_LAB_ROOT", package_dir);
setenv("CPMC_LAB_SEED", string(cfg.seed));

started_at = datetime("now", "TimeZone", "local", ...
    "Format", "yyyy-MM-dd'T'HH:mm:ssXXX");
fprintf("CPMC_POINT_START=%s SEED=%d AT=%s\n", ...
    cfg.slug, cfg.seed, string(started_at));

try
    [E_ave, E_err, saved_file] = CPMC_Lab( ...
        cfg.Lx, cfg.Ly, cfg.Lz, cfg.N_up, cfg.N_dn, ...
        cfg.kx, cfg.ky, cfg.kz, cfg.U, cfg.tx, cfg.ty, cfg.tz, ...
        cfg.deltau, cfg.N_wlk, cfg.N_blksteps, cfg.N_eqblk, cfg.N_blk, ...
        cfg.itv_modsvd, cfg.itv_pc, cfg.itv_Em, char("_" + cfg.slug));

    saved_file = string(saved_file);
    assert(isfile(saved_file), "CPMC-Lab did not create %s", saved_file);
    saved = load(saved_file);
    required = ["E", "E_ave", "E_err", "time", "Lx", "Ly", "Lz", ...
        "N_up", "N_dn", "kx", "ky", "kz", "U", "deltau", "N_wlk", ...
        "N_blksteps", "N_eqblk", "N_blk", "itv_modsvd", "itv_pc", "itv_Em"];
    assert(all(isfield(saved, required)), "The saved MAT file is incomplete.");
    assert(numel(saved.E) == cfg.N_blk, ...
        "Expected %d block energies, found %d", cfg.N_blk, numel(saved.E));
    assert(all(isfinite(saved.E)), "Non-finite block energy detected.");
    assert(isfinite(E_ave) && isfinite(E_err) && E_err >= 0, ...
        "Non-finite energy or invalid standard error.");
    assert(isfinite(saved.time) && saved.time >= 0, "Invalid saved wall time.");
    assert(saved.Lx == cfg.Lx && saved.Ly == cfg.Ly && saved.Lz == cfg.Lz, ...
        "Saved lattice does not match the requested configuration.");
    assert(saved.N_up == cfg.N_up && saved.N_dn == cfg.N_dn, ...
        "Saved particle sector does not match the requested configuration.");
    assert(abs(saved.U - cfg.U) <= eps(max(1, abs(cfg.U))), ...
        "Saved interaction does not match the requested configuration.");
    assert(saved.N_wlk == cfg.N_wlk && saved.N_blk == cfg.N_blk && ...
        saved.N_eqblk == cfg.N_eqblk && saved.N_blksteps == cfg.N_blksteps, ...
        "Saved Monte Carlo settings do not match the requested configuration.");
    assert(abs(saved.E_ave - E_ave) <= 10 * eps(max(1, abs(E_ave))), ...
        "Returned and saved mean energies disagree.");
    assert(abs(saved.E_err - E_err) <= 10 * eps(max(1, abs(E_err))), ...
        "Returned and saved standard errors disagree.");

    exact_target = NaN;
    abs_difference = NaN;
    accepted = true;
    acceptance_rule = "scientific comparison deferred to final three-point plot";
    if cfg.slug == "smoke"
        exact_target = -2.44260;
        abs_difference = abs(E_ave - exact_target);
        accepted = E_err <= 0.03 && ...
            abs_difference <= max(4 * E_err, 0.02);
        acceptance_rule = "stderr <= 0.03 and |E-exact| <= max(4*stderr, 0.02)";
    elseif cfg.slug == "u0"
        exact_target = -18.578624239043;
        abs_difference = abs(E_ave - exact_target);
        accepted = abs_difference <= 1e-9;
        acceptance_rule = "|E-analytic| <= 1e-9";
    end

    completed_at = datetime("now", "TimeZone", "local", ...
        "Format", "yyyy-MM-dd'T'HH:mm:ssXXX");
    summary = table(string(cfg.slug), cfg.U, cfg.seed, E_ave, E_err, ...
        saved.time, exact_target, abs_difference, accepted, ...
        string(acceptance_rule), saved_file, string(started_at), ...
        string(completed_at), ...
        'VariableNames', {'point','U_over_t','seed','energy','stderr', ...
        'wall_seconds','exact_target','abs_difference','accepted', ...
        'acceptance_rule','mat_file','started_at','completed_at'});
    write_table_atomic(summary, fullfile(point_dir, "summary.csv"));
    blocks = table((1:numel(saved.E))', real(saved.E(:)), ...
        'VariableNames', {'block','energy'});
    write_table_atomic(blocks, fullfile(point_dir, "block_energies.csv"));

    marker = struct( ...
        "status", "complete", ...
        "point", cfg.slug, ...
        "U_over_t", cfg.U, ...
        "seed", cfg.seed, ...
        "energy", E_ave, ...
        "stderr", E_err, ...
        "wall_seconds", saved.time, ...
        "accepted", accepted, ...
        "mat_file", saved_file, ...
        "completed_at", string(completed_at));
    assert(accepted, "Point-level acceptance gate failed: %s", acceptance_rule);
    write_json_atomic(done_path, marker);
    fprintf("CPMC_POINT_DONE=%s E=%.12f STDERR=%.12f WALL=%.3f ACCEPTED=%d\n", ...
        cfg.slug, E_ave, E_err, saved.time, accepted);
catch err
    if isfile(done_path)
        delete(done_path);
    end
    marker = struct( ...
        "status", "failed", ...
        "point", cfg.slug, ...
        "seed", cfg.seed, ...
        "identifier", string(err.identifier), ...
        "message", string(err.message), ...
        "report", string(getReport(err, "extended", "hyperlinks", "off")), ...
        "failed_at", string(datetime("now", "TimeZone", "local", ...
        "Format", "yyyy-MM-dd'T'HH:mm:ssXXX")));
    write_json_atomic(failed_path, marker);
    fprintf(2, "CPMC_POINT_FAILED=%s MESSAGE=%s\n", cfg.slug, err.message);
    rethrow(err);
end
end

function cfg = point_config(point_name, seed)
point_name = lower(strtrim(point_name));
cfg = struct( ...
    "slug", point_name, ...
    "Lx", 16, "Ly", 1, "Lz", 1, ...
    "N_up", 5, "N_dn", 7, ...
    "kx", 0, "ky", 0, "kz", 0, ...
    "U", NaN, "tx", 1, "ty", 1, "tz", 1, ...
    "deltau", 0.01, "N_wlk", 5000, "N_blksteps", 40, ...
    "N_eqblk", 30, "N_blk", 150, ...
    "itv_modsvd", 1, "itv_pc", 5, "itv_Em", 40, ...
    "seed", seed);

switch point_name
    case "smoke"
        cfg.Lx = 2;
        cfg.N_up = 1;
        cfg.N_dn = 1;
        cfg.kx = 0.0819;
        cfg.U = 4;
        cfg.N_wlk = 100;
        cfg.N_eqblk = 2;
        cfg.N_blk = 20;
        cfg.itv_modsvd = 5;
        cfg.itv_pc = 10;
        cfg.itv_Em = 20;
    case "u0"
        cfg.U = 0;
    case "u1"
        cfg.U = 1;
    case "u2"
        cfg.U = 2;
    case "u3"
        cfg.U = 3;
    case "u4"
        cfg.U = 4;
    case "u5"
        cfg.U = 5;
    case "u6"
        cfg.U = 6;
    case "u7"
        cfg.U = 7;
    case "u8"
        cfg.U = 8;
    otherwise
        error("Unknown point '%s'. Expected smoke or u0 through u8.", point_name);
end

assert(cfg.Ly == 1 && cfg.Lz == 1, "This driver only targets a 1D ring.");
assert(cfg.tx == 1, "Energy unit must be t_x=1.");
end

function write_table_atomic(value, path)
temp_path = string(path) + ".tmp.csv";
writetable(value, temp_path);
movefile(temp_path, path, "f");
end

function write_json_atomic(path, value)
temp_path = string(path) + ".tmp";
fid = fopen(temp_path, "w");
assert(fid >= 0, "Could not open %s for writing.", temp_path);
fprintf(fid, "%s\n", jsonencode(value, "PrettyPrint", true));
fclose(fid);
movefile(temp_path, path, "f");
end
