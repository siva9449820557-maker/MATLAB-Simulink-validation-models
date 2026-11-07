function noiseRise_dB = interference_profile(t)
%INTERFERENCE_PROFILE  Noise-floor rise (dB) on the affected hops at time t.
%   Profiles (P.intProfile):
%     'step'  : full level from P.intOn_s to P.intOff_s
%     'ramp'  : rises linearly over P.rampTime_s, then holds until P.intOff_s
%     'burst' : on for P.burstOn_s in every P.burstPeriod_s, between on and off times

persistent P
if isempty(P) || t < 1e-9
    P = wsn_get_params();
end

noiseRise_dB = 0;
if t < P.intOn_s || t >= P.intOff_s
    return
end
switch P.intProfile
    case 'step'
        noiseRise_dB = P.noiseRise_dB;
    case 'ramp'
        noiseRise_dB = P.noiseRise_dB * min(1, (t - P.intOn_s) / P.rampTime_s);
    case 'burst'
        if mod(t - P.intOn_s, P.burstPeriod_s) < P.burstOn_s
            noiseRise_dB = P.noiseRise_dB;
        end
    otherwise
        error('interference_profile:unknown', 'Unknown P.intProfile "%s".', P.intProfile);
end
end
