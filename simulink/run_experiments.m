%% STEP 3: RUN ALL EXPERIMENTS  (version 2: 30 seeds, about 3x longer than the 10-seed run)
% Runs every scenario for several random seeds and saves the results to
% results/experiments.mat. Nothing is adjusted after the simulation: every
% metric is computed from the logged signals by wsn_metrics.m.
%
% Scenarios
%   1. Interference level sweep (0, 20, 24, 26, 28, 30, 32, 34 dB), ASMA off and on
%   2. Ablation at 30 dB: power boost only, extra retries only
%   3. Disturbance shape at 30 dB: ramp and burst, ASMA off and on

clear; clc;
nSeeds = 30;     % final paper figures; set to 10 for a faster trial
mdl = wsn_model_name(wsn_params(1));
if ~exist([mdl '.slx'], 'file')
    build_wsn_model('optimum', false);
end
load_system(mdl);
if ~exist('results', 'dir')
    mkdir('results');
end

%% Scenario list
levels = [0 20 24 26 28 30 32 34];
S = struct('name', {}, 'noiseRise_dB', {}, 'asma', {}, 'usePower', {}, 'useRetries', {}, 'profile', {});
for R = levels
    S(end+1) = scenario(sprintf('step_%02ddB_noASMA', R), R, 0, 1, 1, 'step'); %#ok<SAGROW>
    S(end+1) = scenario(sprintf('step_%02ddB_ASMA', R),   R, 1, 1, 1, 'step'); %#ok<SAGROW>
end
S(end+1) = scenario('step_30dB_powerOnly',   30, 1, 1, 0, 'step');
S(end+1) = scenario('step_30dB_retriesOnly', 30, 1, 0, 1, 'step');
S(end+1) = scenario('ramp_30dB_noASMA',  30, 0, 1, 1, 'ramp');
S(end+1) = scenario('ramp_30dB_ASMA',    30, 1, 1, 1, 'ramp');
S(end+1) = scenario('burst_30dB_noASMA', 30, 0, 1, 1, 'burst');
S(end+1) = scenario('burst_30dB_ASMA',   30, 1, 1, 1, 'burst');

%% Run
results = struct('scenario', {}, 'seed', {}, 'P', {}, 'M', {});
exampleLogs = struct();
total = numel(S) * nSeeds;
k = 0;
tStart = tic;
for i = 1:numel(S)
    for seed = 1:nSeeds
        P = wsn_params(seed);
        P.noiseRise_dB   = S(i).noiseRise_dB;
        P.asmaEnabled    = S(i).asma;
        P.asmaUsePower   = S(i).usePower;
        P.asmaUseRetries = S(i).useRetries;
        P.intProfile     = S(i).profile;
        assignin('base', 'P', P);
        rng(seed, 'twister');

        out = sim(mdl);
        L = wsn_extract(out, P);
        M = wsn_metrics(L, P);

        k = k + 1;
        results(k).scenario = S(i).name;
        results(k).seed = seed;
        results(k).P = P;
        results(k).M = M;
        if seed == 1
            exampleLogs.(S(i).name) = L;
        end
        fprintf('[%3d/%3d] %-24s seed %2d  PDR(dist) %.3f  minPST %.2f s  trip %d  (%.0f s elapsed)\n', ...
            k, total, S(i).name, seed, M.pdrDisturbance, M.minPST99_s, M.failSafeTrip, toc(tStart));
    end
    % checkpoint after each scenario, so an interruption loses little work
    save(fullfile('results', 'experiments_partial.mat'), 'results', 'S', 'exampleLogs');
end

runInfo.date = datetime('now');
runInfo.matlab = version;
runInfo.nSeeds = nSeeds;
Pinfo = wsn_params(1);
runInfo.design = Pinfo.design;
runInfo.nHops = Pinfo.nHops;
save(fullfile('results', 'experiments.mat'), 'results', 'S', 'exampleLogs', 'runInfo');
fprintf('\nSaved results/experiments.mat. Next: run analyze_results.m\n');

function s = scenario(name, R, asma, usePower, useRetries, profile)
s = struct('name', name, 'noiseRise_dB', R, 'asma', asma, ...
           'usePower', usePower, 'useRetries', useRetries, 'profile', profile);
end
