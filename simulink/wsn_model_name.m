function mdl = wsn_model_name(P)
%WSN_MODEL_NAME  Simulink model name for a parameter set (one model per hop count).
mdl = sprintf('IWSN_ASMA_Model_K%d', P.nHops);
end
