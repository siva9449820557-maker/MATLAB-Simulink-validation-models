function M = wsn_metrics(L, P)
%WSN_METRICS  Computes every reported metric from one run's logged data.
%   M = wsn_metrics(L, P), where L comes from wsn_extract.
%   Nothing here is assumed or hard-coded: each value is computed from L.

t   = L.t;
nom = t < P.intOn_s;
dis = t >= P.intOn_s & t < P.intOff_s;
dl  = L.delivered > 0.5;

%% Delivery and latency
M.pdrNominal     = mean(L.onTime(nom));         % on-time delivery before interference
M.pdrDisturbance = mean(L.onTime(dis));         % on-time delivery during interference
M.delivDisturbance = mean(L.delivered(dis));    % delivered at any latency during interference
M.pdrOverall     = mean(L.onTime);
latNom = L.latency(dl & nom);
latDis = L.latency(dl & dis);
M.latMeanNominal_ms = 1e3 * mean(latNom);
M.latP99Nominal_ms  = 1e3 * pctl(latNom, 99);
M.latMaxNominal_ms  = 1e3 * max([latNom; NaN]);
M.latP99Disturbance_ms = 1e3 * pctl(latDis, 99);
M.latMeanDisturbance_ms = 1e3 * mean(latDis);

%% Hazard signalling time during interference (safety-relevant delay)
% For a hazard at time h, the alarm reaches the base station with the first
% delivered packet generated at or after h. Evaluated on a 10 ms grid.
h = (P.intOn_s : 0.01 : P.intOff_s - 0.01).';
sig = hazardSignalTime(t(dl), t(dl) + L.latency(dl), h);
M.sigP99_s = pctl(sig, 99);
M.sigMax_s = max(sig);
M.minPST99_s = M.sigP99_s + P.tAct_s;           % shortest PST this run supports (99%)
M.sdrAtPST   = mean(sig <= (P.PST_s - P.tAct_s));
M.pstGrid_s  = (0.2 : 0.1 : 10).';
M.sdrCurve   = arrayfun(@(pst) mean(sig <= (pst - P.tAct_s)), M.pstGrid_s);

%% Time below the 0.90 boundary (end-to-end windowed on-time delivery)
M.fracBelow90 = mean(L.pdrWin(dis) < 0.90);
tDip = t(find(dis & L.pdrWin < P.prrOn, 1, 'first'));
if isempty(tDip)
    M.recovery_s = 0;
else
    tRec = t(find(t > tDip & L.pdrWin >= P.prrOn, 1, 'first'));
    if isempty(tRec)
        M.recovery_s = Inf;
    else
        M.recovery_s = tRec - P.intOn_s;
    end
end

%% Energy
M.energyPerPkt_mJ = 1e3 * sum(L.energy) / max(sum(L.delivered), 1);
M.energyPerPktDisturbance_mJ = 1e3 * sum(L.energy(dis)) / max(sum(L.delivered(dis)), 1);

%% ASMA activity (as applied at the nodes)
hopOn  = (L.boost > 0.5) | (L.retries > P.retriesNominal);
asmaOn = any(hopOn, 2);
M.asmaFraction = mean(asmaOn);
rise = [false; diff(asmaOn) > 0];
tRise = t(rise);
first = tRise(tRise >= P.intOn_s);
if isempty(first)
    M.reaction_s = NaN;                          % ASMA never engaged during interference
else
    M.reaction_s = first(1) - P.intOn_s;         % detection + command delay
end
M.falseActivations = sum(tRise < P.intOn_s | tRise > P.intOff_s + P.window_s);
M.hopSwitchEvents  = sum(sum(diff(double(hopOn)) > 0));
M.boostFractionPerHop = mean(hopOn, 1);

%% Fail-safe trips (safety-function watchdog)
M.failSafeTrip = any(L.mode >= 1.5);
if M.failSafeTrip
    M.tripTime_s = t(find(L.mode >= 1.5, 1, 'first'));
else
    M.tripTime_s = NaN;
end

%% Residual (undetected) error estimate, upper bound
% Each failed frame is assumed corrupted; CRC-16 misses a random corruption
% with probability 2^-16. FPDR = undetected erroneous packets per packet sent.
failedFrames = sum(L.hopAtt(:)) - sum(L.hopSucc(:));
M.residualErrors = failedFrames * 2^(-P.crcBits);
M.fpdrEstimate   = M.residualErrors / numel(t);
M.residualPerHour = M.residualErrors / (t(end) - t(1) + P.Ts) * 3600;
end

% -------------------------------------------------------------------------
function sig = hazardSignalTime(genOK, arrOK, h)
sig = inf(size(h));
if isempty(genOK)
    return
end
genOK = round(genOK * 1e6) / 1e6;
h     = round(h * 1e6) / 1e6;
sufMin = flipud(cummin(flipud(arrOK)));          % earliest arrival from index i onwards
if numel(genOK) < 2
    idx = nan(size(h));
    idx(h <= genOK(1)) = 1;
else
    idx = interp1(genOK, (1:numel(genOK)).', h, 'next');
end
ok = ~isnan(idx);
sig(ok) = sufMin(idx(ok)) - h(ok);
% hazards before the first delivered packet: use the first packet
early = h < genOK(1);
sig(early) = sufMin(1) - h(early);
end

function q = pctl(x, p)
% Percentile with linear interpolation (no toolbox needed).
% Empty input gives NaN; Inf values (alarm never delivered) are kept.
x = sort(x(~isnan(x)));
if isempty(x)
    q = NaN;
    return
end
r  = 1 + (numel(x) - 1) * p / 100;
lo = floor(r);
hi = ceil(r);
if isinf(x(hi))
    q = Inf;
elseif lo == hi
    q = x(lo);
else
    q = x(lo) + (r - lo) * (x(hi) - x(lo));
end
end
