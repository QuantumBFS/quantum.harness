function result = run_proposal_prefix(config_input)
%RUN_PROPOSAL_PREFIX Test natural CPMC proposal hits for fixed path prefixes.

if ischar(config_input) || isstring(config_input)
    config=jsondecode(fileread(config_input));
else
    config=config_input;
end
required={'package_dir','trial_dir','output_file','output_csv','seed', ...
    'independent_walkers','minimum_expected_hits','targets'};
for index=1:numel(required)
    assert(isfield(config,required{index}), ...
        'bridge:proposal:config','Missing config field %s',required{index});
end
addpath(config.package_dir);
addpath(fileparts(mfilename('fullpath')));

[Phi_I,Phi_T]=proposal_trials(config.trial_dir);
params=struct('Lx',4,'Ly',4,'Lz',1,'N_up',8,'N_dn',8, ...
    'kx',0,'ky',0,'kz',0,'U',4,'tx',1,'ty',1,'tz',0, ...
    'deltau',0.05);
H_k=H_K(params.Lx,params.Ly,params.Lz,params.kx,params.ky, ...
    params.kz,params.tx,params.ty,params.tz);
Khalf=expm(-0.5*params.deltau*H_k);
gamma=acosh(exp(0.5*params.deltau*params.U));
aux_fld=[exp(gamma),exp(-gamma);exp(-gamma),exp(gamma)];
rng(config.seed,'twister');

targets=config.targets;
result=repmat(struct( ...
    'sample_id','','stratum','','prefix_events',0, ...
    'logQ_prefix',0,'Q_prefix',0,'expected_hits',0, ...
    'observed_hits',0,'z_score',0,'within_4sigma',false), ...
    numel(targets),1);
for target_index=1:numel(targets)
    target=targets(target_index);
    fields=target.fields(:);
    [prefix_events,logQ,observed]=proposal_one_target( ...
        fields,Phi_I,Phi_T,Khalf,aux_fld, ...
        config.independent_walkers,config.minimum_expected_hits);
    probability=exp(logQ);
    expected=config.independent_walkers*probability;
    variance=config.independent_walkers*probability*(1-probability);
    if variance>0
        z=(observed-expected)/sqrt(variance);
    else
        z=double(observed~=round(expected))*Inf;
    end
    result(target_index)=struct( ...
        'sample_id',char(target.sample_id), ...
        'stratum',char(target.stratum), ...
        'prefix_events',prefix_events, ...
        'logQ_prefix',logQ,'Q_prefix',probability, ...
        'expected_hits',expected,'observed_hits',observed, ...
        'z_score',z,'within_4sigma',abs(z)<=4);
    fprintf(['proposal sample=%s events=%d expected=%.3f ', ...
        'observed=%d z=%.3f\n'], ...
        target.sample_id,prefix_events,expected,observed,z);
end
save(config.output_file,'result','config','-v7');
writetable(struct2table(result),config.output_csv);
end

function [prefix_events,logQ,observed]=proposal_one_target( ...
    fields,Phi_I,Phi_T,Khalf,aux_fld,walkers,minimum_expected)
N_sites=size(Phi_I,1);
N_up=size(Phi_I,2)/2;
N_par=size(Phi_I,2);
phi=Phi_I;
[O,inv_up,inv_dn]=proposal_overlap(phi,Phi_T,N_up,N_par);
assert(real(O)>1e-10 && abs(imag(O))<1e-12, ...
    'bridge:proposal:init','Initial overlap is not positive real');
observed=walkers;
logQ=0;
prefix_events=0;
for event=1:numel(fields)
    site=mod(event-1,N_sites)+1;
    if site==1
        [phi,O,inv_up,inv_dn,alive]=proposal_halfK( ...
            phi,O,Khalf,Phi_T,N_up,N_par);
        if ~alive
            break
        end
    end
    row=phi(site,:);
    trial_row=Phi_T(site,:);
    temp1_up=row(1:N_up)*inv_up;
    temp1_dn=row(N_up+1:N_par)*inv_dn;
    temp2_up=inv_up*trial_row(1:N_up)';
    temp2_dn=inv_dn*trial_row(N_up+1:N_par)';
    G_up=temp1_up*trial_row(1:N_up)';
    G_dn=temp1_dn*trial_row(N_up+1:N_par)';
    RR=(aux_fld-ones(2,2)).*[G_up,G_up;G_dn,G_dn]+ones(2,2);
    ratios=RR(1,:).*RR(2,:);
    positive=max(real(ratios),zeros(1,2));
    normalization=sum(positive);
    if fields(event)==1
        chosen=1;
    elseif fields(event)==-1
        chosen=2;
    else
        error('bridge:proposal:field','Target field must be +/-1');
    end
    if normalization<=0 || positive(chosen)<=0
        break
    end
    q_target=positive(chosen)/normalization;
    candidate_logQ=logQ+log(q_target);
    if walkers*exp(candidate_logQ)<minimum_expected
        break
    end
    observed=sum(rand(observed,1)<=q_target);
    logQ=candidate_logQ;
    prefix_events=event;
    row(1:N_up)=row(1:N_up)*aux_fld(1,chosen);
    row(N_up+1:N_par)=row(N_up+1:N_par)*aux_fld(2,chosen);
    O=O*ratios(chosen);
    inv_up=inv_up+(1-aux_fld(1,chosen))/RR(1,chosen)* ...
        temp2_up*temp1_up;
    inv_dn=inv_dn+(1-aux_fld(2,chosen))/RR(2,chosen)* ...
        temp2_dn*temp1_dn;
    phi(site,:)=row;
    if site==N_sites && event<numel(fields)
        [phi,O,inv_up,inv_dn,alive]=proposal_halfK( ...
            phi,O,Khalf,Phi_T,N_up,N_par);
        if ~alive
            break
        end
    end
end
end

function [phi,O,inv_up,inv_dn,alive]=proposal_halfK( ...
    phi,O,Khalf,Phi_T,N_up,N_par)
phi=Khalf*phi;
[O_new,inv_up,inv_dn]=proposal_overlap(phi,Phi_T,N_up,N_par);
ratio=real(O_new/O);
alive=ratio>0 && isfinite(ratio);
if alive
    O=O_new;
end
end

function [O,inv_up,inv_dn]=proposal_overlap(phi,Phi_T,N_up,N_par)
overlap_up=Phi_T(:,1:N_up)'*phi(:,1:N_up);
overlap_dn=Phi_T(:,N_up+1:N_par)'*phi(:,N_up+1:N_par);
inv_up=overlap_up\eye(N_up);
inv_dn=overlap_dn\eye(N_par-N_up);
O=det(overlap_up)*det(overlap_dn);
end

function [Phi_I,Phi_T]=proposal_trials(trial_dir)
N_sites=16; N_up=8; N_dn=8;
I_up_alf=read_orbitals(fullfile(trial_dir,'trial_I_up.dat'),N_sites,N_up);
I_dn_alf=read_orbitals(fullfile(trial_dir,'trial_I_down.dat'),N_sites,N_dn);
T_up_alf=read_orbitals(fullfile(trial_dir,'trial_T_up.dat'),N_sites,N_up);
T_dn_alf=read_orbitals(fullfile(trial_dir,'trial_T_down.dat'),N_sites,N_dn);
site_map=readmatrix(fullfile(trial_dir,'site_map.dat'),'FileType','text');
assert(isequal(size(site_map),[N_sites,4]), ...
    'bridge:proposal:siteMap','site_map.dat has wrong shape');
I_up=zeros(size(I_up_alf)); I_dn=zeros(size(I_dn_alf));
T_up=zeros(size(T_up_alf)); T_dn=zeros(size(T_dn_alf));
for alf=1:N_sites
    cpp=site_map(alf,2)+1;
    I_up(cpp,:)=I_up_alf(alf,:);
    I_dn(cpp,:)=I_dn_alf(alf,:);
    T_up(cpp,:)=T_up_alf(alf,:);
    T_dn(cpp,:)=T_dn_alf(alf,:);
end
Phi_I=[I_up,I_dn];
Phi_T=[T_up,T_dn];
end
