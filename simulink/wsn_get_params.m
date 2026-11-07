function P = wsn_get_params()
%WSN_GET_PARAMS  Returns the parameter struct P from the base workspace.
%   If P does not exist yet (for example when the model is run directly with
%   the Run button), it is created with default values from wsn_params.m.
if evalin('base', 'exist(''P'', ''var'')')
    P = evalin('base', 'P');
else
    P = wsn_params();
    assignin('base', 'P', P);
end
end
