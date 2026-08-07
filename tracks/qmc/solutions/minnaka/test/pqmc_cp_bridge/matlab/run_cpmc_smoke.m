% Tiny real-MATLAB checks for all bridge modes and diagnostic RNG neutrality.

this_dir=fileparts(mfilename('fullpath'));
bridge_dir=fileparts(this_dir);
repo=fileparts(fileparts(bridge_dir));
common=struct( ...
    'package_dir',fullfile(bridge_dir,'runs','matlab_cp','package'), ...
    'trial_dir',fullfile(bridge_dir,'assets','trials'), ...
    'output_dir',fullfile(bridge_dir,'runs','matlab_cp','smoke'), ...
    'seed',771,'ltrot',2,'N_wlk',8,'N_blksteps',2, ...
    'N_eqblk',1,'N_blk',2,'itv_modsvd',1,'itv_pc',1,'itv_Em',1, ...
    'contract_hashes',struct('selected_projection',repmat('0',1,64)));
if ~exist(common.output_dir,'dir'); mkdir(common.output_dir); end

fixed=common;
fixed.mode='fixed_horizon';
fixed.run_id='fixed_diag_on';
fixed.diagnostics=true;
on=run_cpmc_bridge(fixed);
fixed.run_id='fixed_diag_off';
fixed.diagnostics=false;
off=run_cpmc_bridge(fixed);
assert(max(abs(on.diag.final_Phi-off.diag.final_Phi),[],'all')<1e-13);
assert(max(abs(on.diag.final_w-off.diag.final_w))<1e-13);
assert(max(abs(on.diag.final_O-off.diag.final_O))<1e-13);
assert(isequal(on.diag.path_bits_uint64,off.diag.path_bits_uint64));

proposal=common;
proposal.mode='proposal_only';
proposal.run_id='proposal';
run_cpmc_bridge(proposal);

production=common;
production.mode='production';
production.run_id='production';
run_cpmc_bridge(production);

prefix=struct( ...
    'package_dir',common.package_dir,'trial_dir',common.trial_dir, ...
    'output_file',fullfile(common.output_dir,'proposal_prefix.mat'), ...
    'output_csv',fullfile(common.output_dir,'proposal_prefix.csv'), ...
    'seed',1771,'independent_walkers',10000, ...
    'minimum_expected_hits',20, ...
    'targets',struct('sample_id','smoke','stratum','regular', ...
        'fields',ones(64,1)));
prefix_result=run_proposal_prefix(prefix);
assert(prefix_result.prefix_events>0);
assert(prefix_result.expected_hits>=20);
assert(prefix_result.within_4sigma);
disp('PASS: CPMC bridge smoke');
