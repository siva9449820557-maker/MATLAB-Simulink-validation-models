%% STEP 2: QUICK CHECK  (about 1 minute)
% Runs the model 3 times with seed 1 and prints the key numbers, so you can
% confirm everything works before the full batch:
%   A. no interference, ASMA off   (nominal route, compare with ANN Table 4)
%   B. 30 dB interference, ASMA off
%   C. 30 dB interference, ASMA on
% Send me the printed output if anything looks wrong or an error appears.

clear; clc;
mdl = wsn_model_name(wsn_params(1));
if ~exist([mdl '.slx'], 'file')
    build_wsn_model('optimum', false);
end
load_system(mdl);

cases = {
    'A: no interference, ASMA off', 0,  0
    'B: 30 dB interference, ASMA off', 30, 0
    'C: 30 dB interference, ASMA on',  30, 1
    };
L = cell(3, 1);
for c = 1:3
    P = wsn_params(1);
    P.noiseRise_dB = cases{c, 2};
    P.asmaEnabled  = cases{c, 3};
    assignin('base', 'P', P);
    rng(1, 'twister');
    out = sim(mdl);
    L{c} = wsn_extract(out, P);
    M = wsn_metrics(L{c}, P);

    fprintf('\n=== %s ===\n', cases{c, 1});
    fprintf('Packets generated                 : %d\n', numel(L{c}.t));
    fprintf('On-time PDR before interference   : %.4f\n', M.pdrNominal);
    fprintf('On-time PDR during interference   : %.4f\n', M.pdrDisturbance);
    fprintf('Mean / 99th pct latency (nominal) : %.1f / %.1f ms\n', M.latMeanNominal_ms, M.latP99Nominal_ms);
    fprintf('Hazard signalling time, 99th pct  : %.2f s  -> shortest supportable PST %.2f s\n', M.sigP99_s, M.minPST99_s);
    fprintf('SDR at PST = %.1f s                : %.4f\n', P.PST_s, M.sdrAtPST);
    fprintf('Energy per delivered packet       : %.2f mJ\n', M.energyPerPkt_mJ);
    fprintf('ASMA active                       : %.1f %% of time, reaction %.1f s\n', 100*M.asmaFraction, M.reaction_s);
    fprintf('Fail-safe trip                    : %d\n', M.failSafeTrip);
    fprintf('Residual error estimate (FPDR)    : %.2e per packet\n', M.fpdrEstimate);
end

%% Sanity checks on the nominal run
fprintf('\n=== Sanity checks (run A) ===\n');
M = wsn_metrics(L{1}, wsn_params(1));
check(M.pdrNominal >= 0.99, 'Nominal on-time PDR is at least 0.99');
check(M.latMeanNominal_ms > 50 && M.latMeanNominal_ms < 90, 'Nominal mean latency is between 50 and 90 ms');
check(all(L{1}.noise == 0), 'No interference was applied in run A');
check(max(L{2}.noise) > 0, 'Interference was applied in run B');
check(all(L{2}.boost(:) == 0), 'ASMA stayed off in run B');

%% Plot
figure('Color', 'w', 'Name', 'Quick check');
plot(L{2}.t, 100*L{2}.pdrWin, 'Color', [0.8 0.2 0.2], 'LineWidth', 1.2); hold on
plot(L{3}.t, 100*L{3}.pdrWin, 'Color', [0.1 0.4 0.8], 'LineWidth', 1.2);
yline(90, 'k--', '90 %');
yline(93, 'k:', '93 % warning');
xlabel('Time (s)'); ylabel('End-to-end on-time PDR, 2 s window (%)');
legend('30 dB, ASMA off', '30 dB, ASMA on', 'Location', 'southwest');
ylim([0 102]); grid on
title('Quick check: seed 1');

function check(ok, msg)
if ok
    fprintf('  OK     %s\n', msg);
else
    fprintf('  CHECK  %s  <-- please send me this output\n', msg);
end
end
