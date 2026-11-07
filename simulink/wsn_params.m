function P = wsn_params(seed, design)
%WSN_PARAMS  All model parameters in one place.
%   P = wsn_params()                 seed 1, ANN-optimum route
%   P = wsn_params(seed)             given seed, ANN-optimum route
%   P = wsn_params(seed, 'optimum')  ANN-optimum route (11 hops, uniform, 0 dBm, 2 retries)
%   P = wsn_params(seed, 'v1')       route from the first version (10 hops, std 11.57 m, 3 retries)
%
%   Every value here is an assumption stated in the manuscript's parameter
%   table. Change values here only, never inside the other files.

if nargin < 1 || isempty(seed)
    seed = 1;
end
if nargin < 2 || isempty(design)
    design = 'optimum';
end

%% Simulation timing
P.Ts    = 0.1;      % packet period and model step (s): 10 packets per second
P.Tstop = 100;      % simulation length (s)
P.seed  = seed;

%% Route design (293 m route, 900-bit payload)
switch lower(design)
    case 'optimum'      % ANN optimum: maximum interference tolerance
        P.design         = 'optimum';
        P.nHops          = 11;
        P.meanD_m        = 293 / 11;
        P.stdD_m         = 0;
        P.txPower_dBm    = 0;
        P.retriesNominal = 2;
    case 'v1'           % route recommended in the first version (Table 4 of v1)
        P.design         = 'v1';
        P.nHops          = 10;
        P.meanD_m        = 29.3;
        P.stdD_m         = 11.57;
        P.txPower_dBm    = 0;
        P.retriesNominal = 3;
    otherwise
        error('wsn_params:design', 'Unknown design "%s". Use ''optimum'' or ''v1''.', design);
end
P.payloadBits  = 900;
P.retriesBoost = P.retriesNominal + 2;   % ASMA adds two retries per hop

%% Radio and channel (IEEE 802.15.4, 2.4 GHz, O-QPSK, 250 kbps)
P.boost_dB       = 3;      % ASMA transmit power boost
P.noiseFloor_dBm = -101;   % thermal noise over 2 MHz (-111 dBm) + 10 dB noise figure
P.shadowSigma_dB = 4;      % static log-normal shadowing per link
P.ricianK_dB     = 3;      % Rician K-factor for per-attempt fading
% Dual-slope path loss (positive dB), breakpoint 11 m, after NIST industrial data:
%   PL = 46 + 11*log10(d)  for d <= 11 m
%   PL = 30 + 26*log10(d)  for d >  11 m
P.plA1 = 11;  P.plB1 = 46;
P.plA2 = 26;  P.plB2 = 30;
P.plBreak_m = 11;

%% Interference (disturbance) on the middle three hops
nHit = min(3, P.nHops);
first = floor((P.nHops - nHit) / 2) + 1;
P.intHops       = first:(first + nHit - 1);   % hops 5-7 for 11 hops, 4-6 for 10 hops
P.intOn_s       = 30;       % onset
P.intOff_s      = 70;       % end
P.noiseRise_dB  = 30;       % rise of the noise floor on affected hops
P.intProfile    = 'step';   % 'step', 'ramp' or 'burst'
P.rampTime_s    = 20;       % ramp: time to reach full level
P.burstPeriod_s = 5;        % burst: period
P.burstOn_s     = 2;        % burst: on-time per period

%% Frame sizes and MAC timing (IEEE 802.15.4)
P.bitRate         = 250e3;
P.macOverheadBits = 11*8;         % MAC header + FCS
P.phyOverheadBits = 6*8;          % preamble, SFD, length
P.ackBits         = 11*8;         % ACK frame including PHY
P.backoffUnit_s   = 20*16e-6;     % 320 us
P.minBE           = 3;            % backoff exponent
P.cca_s           = 8*16e-6;
P.turnaround_s    = 12*16e-6;
P.ackWait_s       = 54*16e-6;     % macAckWaitDuration
P.proc_s          = 1e-3;         % forwarding delay per hop
P.deadline_s      = 0.100;        % end-to-end latency target

%% Radio energy (3 V supply). Transmit current fitted to CC2420 datasheet values:
%  I = 8.5 + 8.9*10^(P/20) mA (within 0.5 mA from -25 to 0 dBm; 21.1 mA at +3 dBm)
txW = @(dBm) 3 * (8.5e-3 + 8.9e-3 * 10.^(dBm/20));
P.pTx0_W     = txW(P.txPower_dBm);                 % transmit at design power
P.pTxBoost_W = txW(P.txPower_dBm + P.boost_dB);    % transmit with ASMA boost
P.pRx_W      = 3*18.8e-3;                          % receive / listen for ACK

%% ASMA controller at the base station
P.asmaEnabled    = 1;      % 0 = monitoring only, 1 = ASMA active
P.asmaUsePower   = 1;      % ablation: use the +3 dB boost
P.asmaUseRetries = 1;      % ablation: add two retries per hop
P.window_s       = 2.0;    % telemetry window for per-hop link success ratio
P.eval_s         = 0.5;    % controller evaluation period (node health reports)
P.prrOn          = 0.93;   % early-warning threshold: boost a hop below this
P.snrRelease_dB  = 6;      % release when un-boosted SNR estimate is at least this
P.minDwell_s     = 5;      % minimum time a boost stays on (hysteresis)
P.minAttempts    = 10;     % minimum attempts in window before deciding
P.cmdDelaySteps  = 2;      % downlink command delay in model steps (0.2 s)

%% Safety function
P.PST_s  = 2.0;   % process safety time (reference value; swept in analysis)
P.tAct_s = 0.5;   % logic solver + actuator time
P.crcBits = 16;   % IEEE 802.15.4 FCS (CRC-16)

%% Derived: hop distances and static shadowing, from the seed's own stream
% Spacing pattern with exactly the design mean and standard deviation, placed
% in random order along the route (same definition as the ANN training data).
z = linspace(-1, 1, P.nHops);
if P.nHops > 1
    z = (z - mean(z)) / std(z);
end
d = P.meanD_m + P.stdD_m * z(:);
s = RandStream('mt19937ar', 'Seed', seed + 7919);
P.shadow_dB = P.shadowSigma_dB * randn(s, P.nHops, 1);
P.d_m = d(randperm(s, P.nHops));
P.meanSnr0_dB = P.txPower_dBm - wsn_pathloss(P.d_m, P) - P.shadow_dB - P.noiseFloor_dBm;
end

function PL = wsn_pathloss(d, P)
PL = zeros(size(d));
near = d <= P.plBreak_m;
PL(near)  = P.plB1 + P.plA1 * log10(d(near));
PL(~near) = P.plB2 + P.plA2 * log10(d(~near));
end
