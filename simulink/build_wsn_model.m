function mdl = build_wsn_model(design, openModel)
%BUILD_WSN_MODEL  STEP 1: builds the Simulink model for a route design.
%   build_wsn_model              builds the ANN-optimum route (11 hops) and opens it
%   build_wsn_model('v1')        builds the first-version route (10 hops)
%   mdl = build_wsn_model(design, false)   builds without opening (used by other scripts)
%
% Creates IWSN_ASMA_Model_K<hops>.slx in this folder. Re-running it rebuilds the model.
%
% Model layout (left to right):
%   Clock -> Interference -> WSN_Path (multi-hop route) -> ASMA_Controller (base station)
%   ASMA_Controller -> Delay_Boost / Delay_Retries -> back to WSN_Path (downlink commands)
%   To Workspace blocks log every signal used in the analysis (names start with log_).
%
% The detailed logic is in plain MATLAB files that the blocks call:
%   interference_profile.m, wsn_path_step.m, asma_controller_step.m

if nargin < 1 || isempty(design)
    design = 'optimum';
end
if nargin < 2
    openModel = true;
end
P = wsn_params(1, design);
assignin('base', 'P', P);
n = P.nHops;
mdl = wsn_model_name(P);

if bdIsLoaded(mdl)
    close_system(mdl, 0);
end
if exist([mdl '.slx'], 'file')
    delete([mdl '.slx']);
end
new_system(mdl);
if openModel
    open_system(mdl);
end
set_param(mdl, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
    'FixedStep', num2str(P.Ts), 'StopTime', num2str(P.Tstop), ...
    'ReturnWorkspaceOutputs', 'on', 'SaveTime', 'off', 'SaveOutput', 'off');

%% Blocks
add_block('simulink/Sources/Digital Clock', [mdl '/Clock'], ...
    'SampleTime', num2str(P.Ts), 'Position', [30 200 90 230]);

add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/Interference'], ...
    'Position', [160 80 300 130]);
add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/WSN_Path'], ...
    'Position', [400 120 600 340]);
add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/ASMA_Controller'], ...
    'Position', [760 120 960 340]);
add_block('simulink/Discrete/Delay', [mdl '/Delay_Boost'], ...
    'DelayLength', num2str(P.cmdDelaySteps), 'InitialCondition', '0', ...
    'Orientation', 'left', 'Position', [600 420 660 460]);
add_block('simulink/Discrete/Delay', [mdl '/Delay_Retries'], ...
    'DelayLength', num2str(P.cmdDelaySteps), 'InitialCondition', num2str(P.retriesNominal), ...
    'Orientation', 'left', 'Position', [600 500 660 540]);

%% MATLAB Function block code (thin wrappers around the .m files)
setFcnCode([mdl '/Interference'], sprintf([ ...
    'function noiseRise_dB = fcn(t)\n' ...
    'coder.extrinsic(''interference_profile'');\n' ...
    'noiseRise_dB = 0;\n' ...
    'noiseRise_dB = interference_profile(t);\n']));

setFcnCode([mdl '/WSN_Path'], sprintf([ ...
    'function [delivered, latency_s, onTime, hopAtt, hopSucc, hopSnr_dB, energy_J] = fcn(t, noiseRise_dB, boost, retries)\n' ...
    'coder.extrinsic(''wsn_path_step'');\n' ...
    'delivered = 0; latency_s = 0; onTime = 0; energy_J = 0;\n' ...
    'hopAtt = zeros(%d,1); hopSucc = zeros(%d,1); hopSnr_dB = zeros(%d,1);\n' ...
    '[delivered, latency_s, onTime, hopAtt, hopSucc, hopSnr_dB, energy_J] = wsn_path_step(t, noiseRise_dB, boost, retries);\n'], ...
    n, n, n));

setFcnCode([mdl '/ASMA_Controller'], sprintf([ ...
    'function [boostCmd, retryCmd, opMode, pdrWin, hopPRR] = fcn(t, delivered, onTime, latency_s, hopAtt, hopSucc, hopSnr_dB)\n' ...
    'coder.extrinsic(''asma_controller_step'');\n' ...
    'boostCmd = zeros(%d,1); retryCmd = zeros(%d,1); hopPRR = zeros(%d,1); opMode = 0; pdrWin = 0;\n' ...
    '[boostCmd, retryCmd, opMode, pdrWin, hopPRR] = asma_controller_step(t, delivered, onTime, latency_s, hopAtt, hopSucc, hopSnr_dB);\n'], ...
    n, n, n));

%% Signal connections
lines = {
    'Clock/1',           'Interference/1'
    'Clock/1',           'WSN_Path/1'
    'Clock/1',           'ASMA_Controller/1'
    'Interference/1',    'WSN_Path/2'
    'Delay_Boost/1',     'WSN_Path/3'
    'Delay_Retries/1',   'WSN_Path/4'
    'WSN_Path/1',        'ASMA_Controller/2'
    'WSN_Path/3',        'ASMA_Controller/3'
    'WSN_Path/2',        'ASMA_Controller/4'
    'WSN_Path/4',        'ASMA_Controller/5'
    'WSN_Path/5',        'ASMA_Controller/6'
    'WSN_Path/6',        'ASMA_Controller/7'
    'ASMA_Controller/1', 'Delay_Boost/1'
    'ASMA_Controller/2', 'Delay_Retries/1'
    };
for i = 1:size(lines, 1)
    add_line(mdl, lines{i, 1}, lines{i, 2}, 'autorouting', 'smart');
end

%% Logging (To Workspace, array format)
logs = {
    'log_t',         'Clock/1'
    'log_noise',     'Interference/1'
    'log_delivered', 'WSN_Path/1'
    'log_latency',   'WSN_Path/2'
    'log_onTime',    'WSN_Path/3'
    'log_hopAtt',    'WSN_Path/4'
    'log_hopSucc',   'WSN_Path/5'
    'log_hopSnr',    'WSN_Path/6'
    'log_energy',    'WSN_Path/7'
    'log_boost',     'Delay_Boost/1'
    'log_retries',   'Delay_Retries/1'
    'log_mode',      'ASMA_Controller/3'
    'log_pdrWin',    'ASMA_Controller/4'
    'log_hopPRR',    'ASMA_Controller/5'
    };
for i = 1:size(logs, 1)
    y = 30 + 45*(i - 1);
    blk = [mdl '/' logs{i, 1}];
    add_block('simulink/Sinks/To Workspace', blk, 'VariableName', logs{i, 1}, ...
        'SaveFormat', 'Array', 'MaxDataPoints', 'inf', 'SampleTime', '-1', ...
        'Position', [1150 y 1250 y + 25]);
    add_line(mdl, logs{i, 2}, [logs{i, 1} '/1'], 'autorouting', 'smart');
end

save_system(mdl);
fprintf('Built %s.slx (%s route, %d hops).\n', mdl, P.design, n);
end

%% ------------------------------------------------------------------------
function setFcnCode(blockPath, code)
% Puts code into a MATLAB Function block (works across recent MATLAB releases).
try
    cfg = get_param(blockPath, 'MATLABFunctionConfiguration');
    cfg.FunctionScript = code;
catch
    rt = sfroot;
    chart = rt.find('-isa', 'Stateflow.EMChart', 'Path', blockPath);
    chart.Script = code;
end
end
