%% STEP 3: VALIDATE THE ANN AGAINST SIMULINK  (about 10-20 minutes)
% Runs the Simulink model for two route designs at several interference levels
% (ASMA off, interference on the middle three hops for the whole 60 s run, the
% same conditions as the ANN training data) and compares the simulated averages
% with the ANN predictions in ann_predictions.csv.
%
% Designs
%   optimum : ANN optimum  - 11 hops of 26.6 m, uniform, 0 dBm, 2 retries
%   v1      : first-version route - 10 hops, mean 29.3 m, std 11.57 m, 0 dBm, 3 retries
%
% Writes results/ann_validation.csv and results/fig_ann_validation_simulink.png.

clear; clc;
nSeeds  = 20;                                   % 20 is enough; 30 for extra precision
levels  = [0 20 22 24 25 26 27 28 30 32];
designs = {'optimum', 'v1'};
outputs = {'PDR', 'SDR', 'NWLat_ms', 'LatP99_ms', 'Energy_mJ', 'MinPST_s'};
if ~exist('results', 'dir')
    mkdir('results');
end
A   = readtable('ann_predictions.csv', 'TextType', 'char');
TOL = readtable('ann_tolerance.csv', 'TextType', 'char');

rows = {};
tStart = tic;
for d = 1:numel(designs)
    mdl = build_wsn_model(designs{d}, false);
    load_system(mdl);
    for R = levels
        vals = nan(nSeeds, numel(outputs));
        for seed = 1:nSeeds
            P = wsn_params(seed, designs{d});
            P.Tstop        = 60;
            P.intOn_s      = 0;
            P.intOff_s     = 60;
            P.noiseRise_dB = R;
            P.asmaEnabled  = 0;
            assignin('base', 'P', P);
            rng(seed, 'twister');
            out = sim(mdl, 'StopTime', num2str(P.Tstop));
            L = wsn_extract(out, P);
            M = wsn_metrics(L, P);
            vals(seed, :) = [M.pdrDisturbance, M.sdrAtPST, M.latMeanDisturbance_ms, ...
                             M.latP99Disturbance_ms, M.energyPerPktDisturbance_mJ, min(M.minPST99_s, 60)];
        end
        for o = 1:numel(outputs)
            x = vals(:, o);
            x = x(isfinite(x));
            ann = A.(outputs{o})(strcmp(A.design, designs{d}) & abs(A.Noise_dB - R) < 1e-9);
            rows(end+1, :) = {designs{d}, R, outputs{o}, mean(x), 1.96*std(x)/sqrt(numel(x)), ...
                              median(x), ann, numel(x)}; %#ok<SAGROW>
        end
        fprintf('%-8s %4.1f dB  PDR sim %.3f  ANN %.3f   (%.0f s elapsed)\n', designs{d}, R, ...
            mean(vals(:, 1), 'omitnan'), A.PDR(strcmp(A.design, designs{d}) & abs(A.Noise_dB - R) < 1e-9), toc(tStart));
    end
end
V = cell2table(rows, 'VariableNames', {'design', 'Noise_dB', 'output', 'sim_mean', 'sim_ci95', ...
                                       'sim_median', 'ann', 'n_seeds'});
writetable(V, fullfile('results', 'ann_validation.csv'));

%% Interference tolerance: simulated (mean PDR crosses 0.90) vs ANN
fprintf('\nInterference tolerance (dB): ANN prediction vs Simulink\n');
for d = 1:numel(designs)
    v = V(strcmp(V.design, designs{d}) & strcmp(V.output, 'PDR'), :);
    v = sortrows(v, 'Noise_dB');
    i = find(v.sim_mean < 0.90, 1, 'first');
    if isempty(i) || i == 1
        simTol = NaN;
    else
        simTol = v.Noise_dB(i-1) + (v.sim_mean(i-1) - 0.90) / (v.sim_mean(i-1) - v.sim_mean(i)) * ...
                 (v.Noise_dB(i) - v.Noise_dB(i-1));
    end
    fprintf('  %-8s ANN %.1f dB   Simulink %.1f dB\n', designs{d}, ...
        TOL.ANN_tolerance_dB(strcmp(TOL.design, designs{d})), simTol);
end

%% Accuracy summary over all levels
fprintf('\nMean absolute difference, ANN vs Simulink average:\n');
for o = 1:numel(outputs)
    v = V(strcmp(V.output, outputs{o}), :);
    fprintf('  %-10s %.3f\n', outputs{o}, mean(abs(v.sim_mean - v.ann), 'omitnan'));
end

%% Figure
cols = {[0.10 0.40 0.80], [0.80 0.25 0.20]};
names = {'ANN optimum (11 hops)', 'First-version route (10 hops)'};
f = figure('Color', 'w', 'Position', [100 100 1000 380]);
panels = {'PDR', 'LatP99_ms'};
ylab = {'On-time PDR', '99th percentile latency (ms)'};
for p = 1:2
    subplot(1, 2, p); hold on
    for d = 1:numel(designs)
        a = A(strcmp(A.design, designs{d}), :);
        plot(a.Noise_dB, a.(panels{p}), '-', 'Color', cols{d}, 'LineWidth', 1.4);
        v = V(strcmp(V.design, designs{d}) & strcmp(V.output, panels{p}), :);
        errorbar(v.Noise_dB, v.sim_mean, v.sim_ci95, 'o', 'Color', cols{d}, 'MarkerSize', 4, ...
            'MarkerFaceColor', cols{d});
    end
    if p == 1
        yline(0.90, 'k--'); ylim([0.3 1.02]);
        legend({[names{1} ': ANN'], [names{1} ': Simulink'], [names{2} ': ANN'], [names{2} ': Simulink']}, ...
            'Location', 'southwest');
    else
        yline(100, 'k--');
    end
    xlabel('Interference on the middle three hops (dB)'); ylabel(ylab{p}); grid on
end
exportgraphics(f, fullfile('results', 'fig_ann_validation_simulink.png'), 'Resolution', 300);
fprintf('\nWrote results/ann_validation.csv and results/fig_ann_validation_simulink.png\n');
