function [delivered, latency_s, onTime, hopAtt, hopSucc, hopSnr_dB, energy_J] = ...
    wsn_path_step(t, noiseRise_dB, boost, retries)
%WSN_PATH_STEP  Sends one packet from the sensor to the base station over the
%   multi-hop path, hop by hop, with IEEE 802.15.4 retransmissions.
%   Called once per model step (every P.Ts seconds) by the "WSN_Path" block.
%
%   Inputs
%     t             simulation time (s) = packet generation time
%     noiseRise_dB  interference level on the affected hops (dB)
%     boost         nHops x 1, 1 = hop transmits with +P.boost_dB
%     retries       nHops x 1, maximum retransmissions allowed per hop
%   Outputs
%     delivered     1 if the packet reached the base station
%     latency_s     end-to-end latency (NaN if lost)
%     onTime        1 if delivered within P.deadline_s
%     hopAtt        nHops x 1, transmission attempts at each hop
%     hopSucc       nHops x 1, 1 if the hop forwarded the packet
%     hopSnr_dB     nHops x 1, mean SNR over this packet's attempts (node telemetry)
%     energy_J      radio energy spent on this packet over all hops

persistent P busyUntil
if isempty(P) || t < 1e-9
    % New simulation run: reload parameters and clear queue state.
    P = wsn_get_params();
    busyUntil = zeros(P.nHops, 1);
end

n = P.nHops;
K = 10^(P.ricianK_dB/10);
macBits = P.payloadBits + P.macOverheadBits;
frame_s = (macBits + P.phyOverheadBits) / P.bitRate;
losMag  = sqrt(K/(K+1));
scatSd  = sqrt(1/(2*(K+1)));

hopAtt    = zeros(n, 1);
hopSucc   = zeros(n, 1);
hopSnr_dB = zeros(n, 1);
energy_J  = 0;
delivered = 0;
latency_s = NaN;
onTime    = 0;

isHit = false(n, 1);
isHit(P.intHops) = true;

tNow = t;                                   % time the packet is ready at hop i
for i = 1:n
    nr    = noiseRise_dB * isHit(i);
    isBst = boost(i) > 0.5;
    tc    = max(tNow, busyUntil(i));        % wait if this node is still busy
    ok    = false;
    snrSum = 0;
    if isBst
        pTx = P.pTxBoost_W;
    else
        pTx = P.pTx0_W;
    end
    for a = 1:(round(retries(i)) + 1)
        backoff = randi([0, 2^P.minBE - 1]) * P.backoffUnit_s;
        g = (losMag + scatSd*randn)^2 + (scatSd*randn)^2;     % Rician power gain
        snr = P.meanSnr0_dB(i) + P.boost_dB*isBst + 10*log10(g) - nr;
        ber = berOqpsk(snr);
        perData = 1 - (1 - ber)^macBits;
        perAck  = 1 - (1 - ber)^P.ackBits;
        tc = tc + backoff + P.cca_s + P.turnaround_s + frame_s + P.ackWait_s;
        energy_J = energy_J + pTx*frame_s + P.pRx_W*(P.turnaround_s + P.ackWait_s);
        hopAtt(i) = hopAtt(i) + 1;
        snrSum = snrSum + snr;
        if rand >= perData && rand >= perAck
            ok = true;
            break
        end
    end
    hopSnr_dB(i) = snrSum / hopAtt(i);
    busyUntil(i) = tc;
    if ~ok
        return                               % dropped after maximum retries
    end
    hopSucc(i) = 1;
    tNow = tc + P.proc_s;
end

delivered = 1;
latency_s = tNow - t;
onTime    = double(latency_s <= P.deadline_s);
end

% -------------------------------------------------------------------------
function ber = berOqpsk(snr_dB)
% Bit error rate of IEEE 802.15.4 O-QPSK DSSS in AWGN (IEEE 802.15.4, Annex E).
s = 10^(snr_dB/10);
k = 2:16;
c16 = [120 560 1820 4368 8008 11440 12870 11440 8008 4368 1820 560 120 16 1]; % nchoosek(16,k)
terms = (-1).^k .* c16 .* exp(20*s*(1./k - 1));
ber = (8/15) * (1/16) * sum(terms);
ber = min(max(ber, 0), 0.5);
end
