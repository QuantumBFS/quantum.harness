function run_cpmc_wave(manifest_path)
%RUN_CPMC_WAVE Execute a list of independent bridge configs in one MATLAB.

manifest=jsondecode(fileread(manifest_path));
configs=manifest.configs;
for index=1:numel(configs)
    fprintf('bridge wave run %d/%d: %s\n',index,numel(configs), ...
        configs(index).run_id);
    run_cpmc_bridge(configs(index));
end
disp('PASS: CPMC wave complete');
end
