function [boostCmd, retryCmd, opMode, pdrWin, hopPRR] = ...
    asma_controller_step(t, delivered, onTime, latency_s, hopAtt, hopSucc, hopSnr_dB) %#ok<INUSL>
%ASMA_CONTROLLER_STEP  Base-station monitor and Active Safety-Margin
%   Augmentation (ASMA) controller. Called once per model step.
%
%   What it does each step:
%     1. Stores node telemetry (attempts, successes, SNR) in a sliding window.
%     2. Every P.eval_s seconds, computes each hop's link success ratio (PRR)
%        and SNR estimate, and the end-to-end on-time delivery ratio.
%     3. If ASMA is enabled: boosts any hop whose PRR is below P.prrOn;
%        releases a boost only after P.minDwell_s AND when the hop's SNR
%        without the boost would be at least P.snrRelease_dB (hysteresis).
%     4. Safety-function watchdog (always active, with or without ASMA): if no
%        on-time packet has arrived for (PST - actuation time), the system
%        trips to the fail-safe state (opMode 2), which is latched.
%
%   Outputs
%     boostCmd  nHops x 1, 1 = apply +P.boost_dB at that hop
%     retryCmd  nHops x 1, maximum retries per hop (3 nominal, 5 boosted)
%     opMode    0 nominal, 1 ASMA active on at least one hop, 2 fail-safe
%     pdrWin    end-to-end on-time delivery ratio over the window
%     hopPRR    nHops x 1, per-hop link success ratio over the window

persistent P W k att succ snrW ot gen boost boostStart lastOK failSafe prr pdr
if isempty(P) || t < 1e-9
    P = wsn_get_params();
    W = round(P.window_s / P.Ts);
    n = P.nHops;
    k = 0;
    att  = zeros(n, W);
    succ = zeros(n, W);
    snrW = zeros(n, W);
    ot   = zeros(1, W);
    gen  = zeros(1, W);
    boost      = zeros(n, 1);
    boostStart = zeros(n, 1);
    lastOK   = 0;
    failSafe = 0;
    prr = ones(n, 1);
    pdr = 1;
end

% 1. store telemetry in the ring buffer
j = mod(k, W) + 1;
att(:, j)  = hopAtt;
succ(:, j) = hopSucc;
snrW(:, j) = hopSnr_dB .* hopAtt;
ot(j)  = onTime;
gen(j) = 1;
k = k + 1;

% 4. safety-function watchdog
if onTime > 0.5
    lastOK = t + latency_s;
end
if failSafe == 0 && (t - lastOK) > (P.PST_s - P.tAct_s)
    failSafe = 1;
end

% 2-3. evaluation and ASMA decisions every P.eval_s
evalSteps = round(P.eval_s / P.Ts);
if mod(k, evalSteps) == 0
    A = sum(att, 2);
    S = sum(succ, 2);
    prr = ones(P.nHops, 1);
    prr(A > 0) = S(A > 0) ./ A(A > 0);
    snrEst = 99 * ones(P.nHops, 1);
    snrEst(A > 0) = sum(snrW(A > 0, :), 2) ./ A(A > 0);
    pdr = sum(ot) / max(sum(gen), 1);

    if P.asmaEnabled && failSafe == 0
        for i = 1:P.nHops
            if boost(i) < 0.5
                if A(i) >= P.minAttempts && prr(i) < P.prrOn
                    boost(i) = 1;
                    boostStart(i) = t;
                end
            else
                if (t - boostStart(i)) >= P.minDwell_s && ...
                        (snrEst(i) - P.boost_dB) >= P.snrRelease_dB
                    boost(i) = 0;
                end
            end
        end
    end
end

if failSafe
    opMode = 2;
elseif any(boost > 0.5)
    opMode = 1;
else
    opMode = 0;
end
boostCmd = boost * P.asmaUsePower;
retryCmd = P.retriesNominal + boost * P.asmaUseRetries * (P.retriesBoost - P.retriesNominal);
pdrWin = pdr;
hopPRR = prr;
end
