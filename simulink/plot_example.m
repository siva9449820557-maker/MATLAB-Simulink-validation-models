%% REDRAW FIGURE 1 WITH A REPRESENTATIVE SEED  (about 1 minute)
% Figure 1 needs one example run. Instead of seed 1, this picks the seed whose
% on-time PDR without ASMA at 30 dB is closest to the median over all seeds
% (ties: the lower PDR), re-runs that seed with and without ASMA, and redraws
% results/fig1_timeseries_30dB.png. The chosen seed is printed and shown in the title.

clear; clc;
R = 30;
PS = readtable(fullfile('results', 'per_seed_metrics.csv'), 'TextType', 'char');
x = PS(strcmp(PS.scenario, sprintf('step_%02ddB_noASMA', R)), :);
med = median(x.pdrDisturbance);
[~, order] = sortrows([abs(x.pdrDisturbance - med), x.pdrDisturbance]);
seed = x.seed(order(1));
fprintf('Median on-time PDR without ASMA at %d dB: %.3f. Using seed %d (PDR %.3f).\n', ...
    R, med, seed, x.pdrDisturbance(order(1)));

P0 = wsn_params(seed);
mdl = wsn_model_name(P0);
if ~exist([mdl '.slx'], 'file')
    build_wsn_model('optimum', false);
end
load_system(mdl);
Lx = cell(1, 2);
for a = 0:1
    P = wsn_params(seed);
    P.noiseRise_dB = R;
    P.asmaEnabled  = a;
    assignin('base', 'P', P);
    rng(seed, 'twister');
    out = sim(mdl);
    Lx{a + 1} = wsn_extract(out, P);
end
Lo = Lx{1};
Ln = Lx{2};
Mo = wsn_metrics(Lo, P0);
Mn = wsn_metrics(Ln, P0);
fprintf('On-time PDR during interference: ASMA off %.3f, ASMA on %.3f\n', Mo.pdrDisturbance, Mn.pdrDisturbance);

hopLbl = sprintf('hops %d-%d', P0.intHops(1), P0.intHops(end));
cOff = [0.80 0.25 0.20];
cOn  = [0.10 0.40 0.80];
f = figure('Color', 'w', 'Position', [100 100 900 560]);
subplot(2, 1, 1);
patch([P0.intOn_s P0.intOff_s P0.intOff_s P0.intOn_s], [0 0 102 102], [0.92 0.92 0.92], 'EdgeColor', 'none'); hold on
plot(Lo.t, 100*Lo.pdrWin, 'Color', cOff, 'LineWidth', 1.3);
plot(Ln.t, 100*Ln.pdrWin, 'Color', cOn, 'LineWidth', 1.3);
yline(90, 'k--', '90%', 'LabelHorizontalAlignment', 'left', 'LabelVerticalAlignment', 'bottom');
yline(93, 'k:', '93% warning', 'LabelHorizontalAlignment', 'right', 'LabelVerticalAlignment', 'bottom');
ylim([0 102]); ylabel({'End-to-end on-time PDR', '(2 s window, %)'});
legend({sprintf('Interference (%d dB)', R), 'ASMA off', 'ASMA on'}, 'Location', 'southwest');
title(sprintf('(a) Delivery under a %d dB interference step on %s (seed %d, median case)', R, hopLbl, seed));
grid on
subplot(2, 1, 2);
stairs(Ln.t, sum(Ln.boost > 0.5 | Ln.retries > P0.retriesNominal, 2), 'Color', cOn, 'LineWidth', 1.3); hold on
tripO = Lo.t(find(Lo.mode >= 1.5, 1));
tripN = Ln.t(find(Ln.mode >= 1.5, 1));
if ~isempty(tripO), xline(tripO, '--', 'Color', cOff, 'Label', 'Fail-safe trip (ASMA off)'); end
if ~isempty(tripN), xline(tripN, '--', 'Color', cOn, 'Label', 'Fail-safe trip (ASMA on)'); end
ylabel('Hops hardened by ASMA'); xlabel('Time (s)'); ylim([-0.2 4]); grid on
title('(b) ASMA activity');
exportgraphics(f, fullfile('results', 'fig1_timeseries_30dB.png'), 'Resolution', 300);
fprintf('Saved results/fig1_timeseries_30dB.png\n');
