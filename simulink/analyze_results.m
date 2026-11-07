%% STEP 4: ANALYSE RESULTS AND MAKE FIGURES  (version 2)
% Reads results/experiments.mat (from run_experiments.m) and writes:
%   results/per_seed_metrics.csv   every metric for every run (one row per run)
%   results/summary_table.csv      mean, 95% CI, median and quartiles per scenario
%   results/key_numbers.txt        headline numbers for the manuscript
%   results/fig1..fig6 *.png       figures (300 dpi)
%
% Version 2 changes: medians with interquartile ranges in the figures (the
% data are skewed, so mean +/- CI bars went above 1 and below 0), paired
% ASMA-vs-no-ASMA comparisons on the same seeds, and a per-seed export.

clear; clc;
load(fullfile('results', 'experiments.mat'), 'results', 'S', 'exampleLogs', 'runInfo');
P0 = wsn_params(1);
hopLbl = sprintf('hops %d-%d', P0.intHops(1), P0.intHops(end));

scalarMetrics = {'pdrNominal', 'pdrDisturbance', 'delivDisturbance', 'latMeanNominal_ms', ...
    'latP99Nominal_ms', 'latP99Disturbance_ms', 'sigP99_s', 'minPST99_s', 'sdrAtPST', ...
    'fracBelow90', 'recovery_s', 'energyPerPkt_mJ', 'energyPerPktDisturbance_mJ', ...
    'asmaFraction', 'reaction_s', 'falseActivations', 'hopSwitchEvents', ...
    'failSafeTrip', 'fpdrEstimate', 'residualPerHour'};

%% 1. Per-seed table
nR = numel(results);
C = cell(nR, 2 + numel(scalarMetrics));
for r = 1:nR
    C{r, 1} = results(r).scenario;
    C{r, 2} = results(r).seed;
    for m = 1:numel(scalarMetrics)
        C{r, 2 + m} = double(results(r).M.(scalarMetrics{m}));
    end
end
PS = cell2table(C, 'VariableNames', [{'scenario', 'seed'}, scalarMetrics]);
writetable(PS, fullfile('results', 'per_seed_metrics.csv'));

%% 2. Summary table
names = {S.name};
rows = cell(numel(names), 7 + 5*numel(scalarMetrics));
for i = 1:numel(names)
    rows(i, 1:7) = {names{i}, S(i).noiseRise_dB, S(i).asma, S(i).usePower, ...
        S(i).useRetries, S(i).profile, nnz(strcmp(PS.scenario, names{i}))};
    for m = 1:numel(scalarMetrics)
        x = col(PS, names{i}, scalarMetrics{m});
        [mu, hw] = meanCI(x);
        rows(i, 7 + 5*(m-1) + (1:5)) = {mu, hw, qtl(x, 50), qtl(x, 25), qtl(x, 75)};
    end
end
vn = {'scenario', 'noiseRise_dB', 'asma', 'usePower', 'useRetries', 'profile', 'nSeeds'};
for m = 1:numel(scalarMetrics)
    b = scalarMetrics{m};
    vn = [vn, {[b '_mean'], [b '_ci95'], [b '_median'], [b '_q25'], [b '_q75']}]; %#ok<AGROW>
end
T = cell2table(rows, 'VariableNames', vn);
writetable(T, fullfile('results', 'summary_table.csv'));
nSeeds = runInfo.nSeeds;

%% 3. Sweep data (step profile, full ASMA)
isSweep = strcmp({S.profile}, 'step') & [S.usePower] == 1 & [S.useRetries] == 1;
levels = unique([S(isSweep).noiseRise_dB]);
off = @(R) sprintf('step_%02ddB_noASMA', R);
on  = @(R) sprintf('step_%02ddB_ASMA', R);
Q = struct();   % rows: 25th percentile, median, 75th percentile; columns: levels
for fq = {'pdrDisturbance', 'minPST99_s', 'energyPerPktDisturbance_mJ', 'sdrAtPST'}
    for i = 1:numel(levels)
        xo = col(PS, off(levels(i)), fq{1});
        xn = col(PS, on(levels(i)), fq{1});
        Q.(fq{1}).off(:, i) = [qtl(xo, 25); qtl(xo, 50); qtl(xo, 75)];
        Q.(fq{1}).on(:, i)  = [qtl(xn, 25); qtl(xn, 50); qtl(xn, 75)];
    end
end
tolOff = crossLevel(levels, Q.pdrDisturbance.off(2, :), 0.90);
tolOn  = crossLevel(levels, Q.pdrDisturbance.on(2, :), 0.90);

%% 4. Key numbers
fid = fopen(fullfile('results', 'key_numbers.txt'), 'w');
pr = @(varargin) fprintf(fid, varargin{:});
pr('Key numbers: %d seeds per scenario. Median [interquartile range] unless stated.\n', nSeeds);
pr('Generated %s with MATLAB %s\n\n', char(runInfo.date), runInfo.matlab);

n0 = off(0);
pr('NOMINAL ROUTE (no interference) - compare with ANN prediction in Table 4\n');
pr('  On-time PDR            : %.4f (min over seeds %.4f)\n', qtl(col(PS, n0, 'pdrNominal'), 50), min(col(PS, n0, 'pdrNominal')));
pr('  Mean latency           : %.1f ms [%.1f-%.1f]\n', qtl3(col(PS, n0, 'latMeanNominal_ms')));
pr('  99th pct latency       : %.1f ms [%.1f-%.1f]\n', qtl3(col(PS, n0, 'latP99Nominal_ms')));
pr('  Energy per packet      : %.2f mJ\n', qtl(col(PS, n0, 'energyPerPkt_mJ'), 50));
fp = qtl(col(PS, n0, 'fpdrEstimate'), 50);
ph = qtl(col(PS, n0, 'residualPerHour'), 50);
pr('  Residual error, CRC-16 only (upper bound): %.2e per packet = %.2e per hour\n', fp, ph);
pr('  ... with an added 32-bit safety-layer CRC: %.2e per hour\n\n', ph * 2^-32);

pr('INTERFERENCE SWEEP (step on hops %s, %g-%g s)\n', mat2str(P0.intHops), P0.intOn_s, P0.intOff_s);
pr('  dB | On-time PDR off        | On-time PDR on         | Min PST s off | Min PST s on | SDR@%.0fs off/on | Trips off/on | Energy mJ off/on\n', P0.PST_s);
for R = levels
    a = off(R); b = on(R);
    pr('  %2d | %.3f [%.3f-%.3f]  | %.3f [%.3f-%.3f]  | %6.2f        | %6.2f       | %.3f / %.3f    | %2d/%d / %2d/%d | %.2f / %.2f\n', R, ...
        qtl3(col(PS, a, 'pdrDisturbance')), qtl3(col(PS, b, 'pdrDisturbance')), ...
        qtl(col(PS, a, 'minPST99_s'), 50), qtl(col(PS, b, 'minPST99_s'), 50), ...
        mean(col(PS, a, 'sdrAtPST')), mean(col(PS, b, 'sdrAtPST')), ...
        sum(col(PS, a, 'failSafeTrip')), nSeeds, sum(col(PS, b, 'failSafeTrip')), nSeeds, ...
        qtl(col(PS, a, 'energyPerPktDisturbance_mJ'), 50), qtl(col(PS, b, 'energyPerPktDisturbance_mJ'), 50));
end
pr('\n  Interference level where median on-time PDR falls to 0.90: %.1f dB without ASMA, %.1f dB with ASMA\n\n', tolOff, tolOn);

pr('PAIRED COMPARISON, SAME SEEDS (ASMA minus no ASMA): mean difference [95%% CI], seeds higher/lower, sign-test p\n');
for R = levels(levels > 0)
    [d, lo, hi, p, np, nn] = paired(PS, off(R), on(R), 'pdrDisturbance');
    pr('  %2d dB on-time PDR : %+.3f [%+.3f, %+.3f]  %d/%d  p = %.3g\n', R, d, lo, hi, np, nn, p);
end
for R = levels(levels > 0)
    [d, lo, hi, p, np, nn] = paired(PS, off(R), on(R), 'energyPerPktDisturbance_mJ');
    pr('  %2d dB energy mJ   : %+.2f [%+.2f, %+.2f]  %d/%d  p = %.3g\n', R, d, lo, hi, np, nn, p);
end

b = on(30);
pr('\nASMA AT 30 dB\n');
pr('  Reaction time (onset to boost at nodes) : %.2f s [%.2f-%.2f]\n', qtl3(col(PS, b, 'reaction_s')));
pr('  Recovery to 93%% windowed PDR           : %.2f s [%.2f-%.2f]\n', qtl3(col(PS, b, 'recovery_s')));
pr('  ASMA active, fraction of run           : %.2f\n', qtl(col(PS, b, 'asmaFraction'), 50));
pr('  False activations (all seeds)          : %d\n', sum(col(PS, b, 'falseActivations')));
pr('  Hop boost switch-on events per run     : %.1f\n', qtl(col(PS, b, 'hopSwitchEvents'), 50));

pr('\nABLATION AT 30 dB: on-time PDR | delivered late (any latency minus on-time) | 99th pct latency ms\n');
for nm = {off(30), 'step_30dB_retriesOnly', 'step_30dB_powerOnly', on(30)}
    late = col(PS, nm{1}, 'delivDisturbance') - col(PS, nm{1}, 'pdrDisturbance');
    pr('  %-22s : %.3f | %.3f | %.1f\n', nm{1}, qtl(col(PS, nm{1}, 'pdrDisturbance'), 50), ...
        qtl(late, 50), qtl(col(PS, nm{1}, 'latP99Disturbance_ms'), 50));
end

pr('\nDISTURBANCE SHAPE AT 30 dB: median on-time PDR off / on\n');
for prof = {'step', 'ramp', 'burst'}
    pr('  %-6s : %.3f / %.3f\n', prof{1}, qtl(col(PS, sprintf('%s_30dB_noASMA', prof{1}), 'pdrDisturbance'), 50), ...
        qtl(col(PS, sprintf('%s_30dB_ASMA', prof{1}), 'pdrDisturbance'), 50));
end
fclose(fid);
type(fullfile('results', 'key_numbers.txt'));

%% 5. Figures
cOff = [0.80 0.25 0.20];
cOn  = [0.10 0.40 0.80];
shade = [0.92 0.92 0.92];

% Fig 1: example time series at 30 dB (seed 1)
Lo = exampleLogs.(off(30));
Ln = exampleLogs.(on(30));
f = figure('Color', 'w', 'Position', [100 100 900 560]);
subplot(2, 1, 1);
patch([P0.intOn_s P0.intOff_s P0.intOff_s P0.intOn_s], [0 0 102 102], shade, 'EdgeColor', 'none'); hold on
plot(Lo.t, 100*Lo.pdrWin, 'Color', cOff, 'LineWidth', 1.3);
plot(Ln.t, 100*Ln.pdrWin, 'Color', cOn, 'LineWidth', 1.3);
yline(90, 'k--', '90%', 'LabelHorizontalAlignment', 'left', 'LabelVerticalAlignment', 'bottom');
yline(93, 'k:', '93% warning', 'LabelHorizontalAlignment', 'left', 'LabelVerticalAlignment', 'top');
ylim([0 102]); ylabel({'End-to-end on-time PDR', '(2 s window, %)'});
legend({'Interference (30 dB)', 'ASMA off', 'ASMA on'}, 'Location', 'southwest');
title(sprintf('(a) Delivery under a 30 dB interference step on %s (seed 1)', hopLbl)); grid on
subplot(2, 1, 2);
stairs(Ln.t, sum(Ln.boost > 0.5 | Ln.retries > P0.retriesNominal, 2), 'Color', cOn, 'LineWidth', 1.3); hold on
tripO = Lo.t(find(Lo.mode >= 1.5, 1));
tripN = Ln.t(find(Ln.mode >= 1.5, 1));
if ~isempty(tripO), xline(tripO, '--', 'Color', cOff, 'Label', 'Fail-safe trip (ASMA off)'); end
if ~isempty(tripN), xline(tripN, '--', 'Color', cOn, 'Label', 'Fail-safe trip (ASMA on)'); end
ylabel('Hops hardened by ASMA'); xlabel('Time (s)'); ylim([-0.2 4]); grid on
title('(b) ASMA activity');
exportgraphics(f, fullfile('results', 'fig1_timeseries_30dB.png'), 'Resolution', 300);

% Fig 2: on-time PDR during interference (median and interquartile range)
f = figure('Color', 'w', 'Position', [100 100 600 420]);
h1 = band(levels, Q.pdrDisturbance.off, cOff, 'o'); hold on
h2 = band(levels, Q.pdrDisturbance.on, cOn, 's');
yline(0.90, 'k--', '0.90', 'LabelHorizontalAlignment', 'left');
xlim([min(levels(levels > 0)) - 1, max(levels) + 1]);
xlabel(sprintf('Interference level on %s (dB)', hopLbl)); ylabel('On-time PDR during interference');
legend([h1 h2], {'ASMA off (median)', 'ASMA on (median)'}, 'Location', 'southwest');
ylim([0 1.02]); grid on
title(sprintf('Median and interquartile range, %d seeds', nSeeds));
exportgraphics(f, fullfile('results', 'fig2_pdr_vs_interference.png'), 'Resolution', 300);

% Fig 3: shortest supportable PST (median and IQR), capped at interference duration
cap = P0.intOff_s - P0.intOn_s;
f = figure('Color', 'w', 'Position', [100 100 600 420]);
h1 = band(levels, min(Q.minPST99_s.off, cap), cOff, 'o'); hold on
h2 = band(levels, min(Q.minPST99_s.on, cap), cOn, 's');
set(gca, 'YScale', 'log');
yline(P0.PST_s, 'k--', sprintf('Reference PST = %.1f s', P0.PST_s), 'LabelHorizontalAlignment', 'left');
xlim([min(levels(levels > 0)) - 1, max(levels) + 1]);
xlabel(sprintf('Interference level on %s (dB)', hopLbl)); ylabel('Shortest supportable PST (s)');
legend([h1 h2], {'ASMA off (median)', 'ASMA on (median)'}, 'Location', 'northwest'); grid on
title(sprintf('Median and interquartile range, %d seeds', nSeeds));
exportgraphics(f, fullfile('results', 'fig3_min_pst_vs_interference.png'), 'Resolution', 300);

% Fig 4: SDR vs PST at 30 dB, including ablation (mean over seeds)
f = figure('Color', 'w', 'Position', [100 100 600 420]);
curves = {off(30), 'step_30dB_retriesOnly', 'step_30dB_powerOnly', on(30)};
labels = {'ASMA off', 'Retries only', 'Power boost only', 'ASMA (both)'};
styles = {'-', ':', '-.', '-'};
colors = {cOff, [0.4 0.4 0.4], [0.3 0.6 0.3], cOn};
for c = 1:numel(curves)
    R = results(strcmp({results.scenario}, curves{c}));
    Cc = arrayfun(@(r) r.M.sdrCurve(:).', R, 'UniformOutput', false);
    Y = vertcat(Cc{:});
    plot(R(1).M.pstGrid_s, mean(Y, 1), styles{c}, 'Color', colors{c}, 'LineWidth', 1.4); hold on
end
yline(0.90, 'k--', '0.90', 'LabelHorizontalAlignment', 'left');
xlabel('Process safety time (s)'); ylabel('SDR: hazards signalled within PST - t_{act}');
legend(labels, 'Location', 'southeast'); ylim([0 1.02]); grid on
title('30 dB interference');
exportgraphics(f, fullfile('results', 'fig4_sdr_vs_pst_30dB.png'), 'Resolution', 300);

% Fig 5: energy per delivered packet during interference (median and IQR, log scale)
f = figure('Color', 'w', 'Position', [100 100 600 420]);
h1 = band(levels, Q.energyPerPktDisturbance_mJ.off, cOff, 'o'); hold on
h2 = band(levels, Q.energyPerPktDisturbance_mJ.on, cOn, 's');
set(gca, 'YScale', 'log');
xlim([min(levels(levels > 0)) - 1, max(levels) + 1]);
xlabel(sprintf('Interference level on %s (dB)', hopLbl)); ylabel('Energy per delivered packet (mJ)');
legend([h1 h2], {'ASMA off (median)', 'ASMA on (median)'}, 'Location', 'northwest'); grid on
title(sprintf('Median and interquartile range, %d seeds', nSeeds));
exportgraphics(f, fullfile('results', 'fig5_energy_vs_interference.png'), 'Resolution', 300);

% Fig 6: paired improvement in on-time PDR (same seeds)
lv = levels(levels > 0);
dm = zeros(size(lv)); dl = dm; dh = dm;
for i = 1:numel(lv)
    [dm(i), dl(i), dh(i)] = paired(PS, off(lv(i)), on(lv(i)), 'pdrDisturbance');
end
f = figure('Color', 'w', 'Position', [100 100 600 420]);
errorbar(lv, dm, dm - dl, dh - dm, '-s', 'Color', cOn, 'LineWidth', 1.3); hold on
yline(0, 'k-');
xlim([min(lv) - 1, max(lv) + 1]);
xlabel(sprintf('Interference level on %s (dB)', hopLbl));
ylabel('On-time PDR gain from ASMA (same seeds)');
title('Mean paired difference with 95% CI'); grid on
exportgraphics(f, fullfile('results', 'fig6_paired_gain.png'), 'Resolution', 300);

fprintf('Wrote per_seed_metrics.csv, summary_table.csv, key_numbers.txt and fig1-fig6 in the results folder.\n');

%% ------------------------------------------------------------------------
function x = col(PS, scenario, metric)
x = PS.(metric)(strcmp(PS.scenario, scenario));
end

function q = qtl(x, p)
% Percentile with linear interpolation (no toolbox). Inf values are kept.
x = sort(x(~isnan(x)));
if isempty(x)
    q = NaN;
    return
end
r  = 1 + (numel(x) - 1) * p / 100;
lo = floor(r);
hi = ceil(r);
if isinf(x(hi)) || isinf(x(lo))
    q = x(hi);
elseif lo == hi
    q = x(lo);
else
    q = x(lo) + (r - lo) * (x(hi) - x(lo));
end
end

function varargout = qtl3(x)
% Median, 25th and 75th percentiles, for printing "median [q25-q75]".
v = [qtl(x, 50), qtl(x, 25), qtl(x, 75)];
if nargout <= 1
    varargout = {v};
else
    varargout = num2cell(v(1:nargout));
end
end

function [mu, hw] = meanCI(x)
x = x(~isnan(x));
if isempty(x) || any(isinf(x))
    mu = mean(x); hw = NaN;
    return
end
mu = mean(x);
hw = 1.96 * std(x) / sqrt(numel(x));
end

function [d, lo, hi, p, nPos, nNeg] = paired(PS, a, b, metric)
% Paired difference b - a on matching seeds, 95% CI and two-sided sign test.
A = PS(strcmp(PS.scenario, a), :);
B = PS(strcmp(PS.scenario, b), :);
[~, ia, ib] = intersect(A.seed, B.seed);
x = B.(metric)(ib) - A.(metric)(ia);
x = x(isfinite(x));
d  = mean(x);
se = std(x) / sqrt(max(numel(x), 1));
lo = d - 1.96*se;
hi = d + 1.96*se;
nPos = sum(x > 0);
nNeg = sum(x < 0);
n = nPos + nNeg;
k = min(nPos, nNeg);
p = 0;
for i = 0:k
    p = p + exp(gammaln(n+1) - gammaln(i+1) - gammaln(n-i+1) - n*log(2));
end
p = min(1, 2*p);
if n == 0
    p = 1;
end
end

function L = crossLevel(levels, y, thr)
% Interference level at which y first falls below thr (linear interpolation).
L = NaN;
for i = 2:numel(levels)
    if y(i-1) >= thr && y(i) < thr
        L = levels(i-1) + (y(i-1) - thr) / (y(i-1) - y(i)) * (levels(i) - levels(i-1));
        return
    end
end
if all(y >= thr)
    L = Inf;   % never fell below thr in the tested range
end
end

function h = band(x, Qm, colour, marker)
% Shaded interquartile band (rows 1 and 3 of Qm) with the median line (row 2).
fill([x, fliplr(x)], [Qm(1, :), fliplr(Qm(3, :))], colour, ...
    'FaceAlpha', 0.15, 'EdgeColor', 'none');
hold on
h = plot(x, Qm(2, :), ['-' marker], 'Color', colour, 'LineWidth', 1.4, 'MarkerFaceColor', 'w');
end
