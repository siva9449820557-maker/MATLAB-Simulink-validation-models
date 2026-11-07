function L = wsn_extract(out, P)
%WSN_EXTRACT  Reads every logged signal from a Simulink run into struct L.
%   L = wsn_extract(out, P)
%
%   Strict by design: if any signal is missing or has the wrong size, it stops
%   with an error. It never substitutes or adjusts a value.

names = {'log_t', 'log_noise', 'log_delivered', 'log_latency', 'log_onTime', ...
         'log_hopAtt', 'log_hopSucc', 'log_hopSnr', 'log_energy', ...
         'log_boost', 'log_retries', 'log_mode', 'log_pdrWin', 'log_hopPRR'};
fields = {'t', 'noise', 'delivered', 'latency', 'onTime', ...
          'hopAtt', 'hopSucc', 'hopSnr', 'energy', ...
          'boost', 'retries', 'mode', 'pdrWin', 'hopPRR'};
widths = [1 1 1 1 1 P.nHops P.nHops P.nHops 1 P.nHops P.nHops 1 1 P.nHops];

available = out.who;
L = struct();
for i = 1:numel(names)
    if ~any(strcmp(available, names{i}))
        error('wsn_extract:missing', 'Logged signal "%s" not found in the simulation output.', names{i});
    end
    x = double(squeeze(out.get(names{i})));
    if isvector(x) && widths(i) > 1 && numel(x) == widths(i)
        x = x(:).';                       % single time step stored as a column
    end
    if widths(i) == 1
        x = x(:);
    elseif size(x, 2) ~= widths(i) && size(x, 1) == widths(i)
        x = x.';
    end
    if size(x, 2) ~= widths(i)
        error('wsn_extract:size', 'Signal "%s" has size %s; expected %d columns.', ...
              names{i}, mat2str(size(x)), widths(i));
    end
    L.(fields{i}) = x;
end

N = numel(L.t);
for i = 2:numel(fields)
    if size(L.(fields{i}), 1) ~= N
        error('wsn_extract:length', 'Signal "%s" has %d samples; the clock has %d.', ...
              names{i}, size(L.(fields{i}), 1), N);
    end
end
if any(abs(diff(L.t) - P.Ts) > 1e-6)
    error('wsn_extract:step', 'Logged time steps are not uniform at P.Ts = %g s.', P.Ts);
end
end
