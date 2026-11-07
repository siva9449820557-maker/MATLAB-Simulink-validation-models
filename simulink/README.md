# IWSN + ASMA Simulink package (version 3)

This folder builds and runs Simulink models of a multi-hop industrial wireless
sensor network route with and without Active Safety-Margin Augmentation (ASMA),
validates the retrained ANN against Simulink, and computes every reported metric
from the logged simulation data.

**Integrity rule:** no script edits, replaces or "aligns" any simulated value.
If a signal is missing, the scripts stop with an error. Never type numbers into
the results by hand; re-run instead.

## What changed in version 3

- The default route is now the **ANN optimum**: 11 hops of 26.6 m (293 m in
  total), uniform spacing, 0 dBm, 900-bit payload, 2 retries. ASMA adds +3 dB and
  2 retries (2 to 4). Interference hits the middle three hops (hops 5-7).
- The first-version route (10 hops, mean 29.3 m, std 11.57 m, 3 retries) is
  still available as design `'v1'` for comparison.
- One Simulink model per hop count: `IWSN_ASMA_Model_K11.slx`, `IWSN_ASMA_Model_K10.slx`.
  The scripts build them automatically when needed.
- New `validate_ann.m` compares the ANN predictions with Simulink.
- Transmit power draw now follows a fit to CC2420 datasheet currents.

## What you need

- MATLAB and Simulink (tested design for R2026b). No other toolboxes.

## Steps

1. Put all files in one folder (replace the old ones) and make it MATLAB's
   **Current Folder**. You can delete the old `IWSN_ASMA_Model.slx` and the old
   `results` folder (or rename it to keep it).
2. Type `build_wsn_model` - builds and opens the 11-hop model.
3. Type `quick_check` (about 1 minute). All checks should say `OK`.
4. Type `validate_ann` (about 10-20 minutes). Writes `results/ann_validation.csv`
   and `results/fig_ann_validation_simulink.png`, and prints ANN vs Simulink numbers.
5. Type `run_experiments` (30 seeds; about three times as long as your 10-seed run).
6. Type `analyze_results`.
7. Type `plot_example` to redraw Figure 1 with the median-case seed.

## What to expect (from the Python reference; your values will be close, not identical)

ANN validation, on-time PDR with interference on hops 5-7 for the whole run:

| Interference | Optimum route (ANN / simulation) | First-version route (ANN / simulation) |
| --- | --- | --- |
| 0 dB | 0.97 / 1.00 | 0.99 / 1.00 |
| 26 dB | 0.90 / 0.95 | 0.85 / 0.88 |
| 28 dB | 0.84 / 0.87 | 0.76 / 0.75 |
| 30 dB | 0.73 / 0.73 | 0.62 / 0.56 |

Interference tolerance (PDR stays at least 0.90): ANN 26.1 dB vs simulation about
27.4 dB for the optimum; ANN 24.6 dB vs simulation about 25.5 dB for the first version.

ASMA experiments on the optimum route (on-time PDR during interference, ASMA off / on):

| Interference | Mean PDR | Fail-safe trips (of 20 seeds) |
| --- | --- | --- |
| 28 dB | 0.87 / 0.98 | 0 / 0 |
| 30 dB | 0.70 / 0.93 | 4 / 0 |
| 32 dB | 0.49 / 0.79 | 6 / 1 |
| 34 dB | 0.28 / 0.60 | 13 / 5 |

Nominal mean latency should be about 82 ms and energy about 3.0 mJ per packet.

## Changing an assumption

Change values **only** in `wsn_params.m`, then re-run from step 3.

## Files

| File | Purpose |
| --- | --- |
| `wsn_params.m` | All parameters and assumptions; route designs `'optimum'` and `'v1'` |
| `build_wsn_model.m` | Builds the Simulink model for a design |
| `wsn_model_name.m` | Model file name for a design (one per hop count) |
| `interference_profile.m` | Interference level over time (step, ramp, burst) |
| `wsn_path_step.m` | One packet over the route: path loss, fading, 802.15.4 errors, retries, latency, energy |
| `asma_controller_step.m` | Base-station monitoring, ASMA decisions with hysteresis, fail-safe watchdog |
| `wsn_get_params.m` | Shares the parameters with the model blocks |
| `wsn_extract.m` | Reads logged signals strictly (errors if anything is missing) |
| `wsn_metrics.m` | Computes every metric from the logged data |
| `quick_check.m` | Three test runs with sanity checks |
| `validate_ann.m` | ANN vs Simulink for both route designs |
| `ann_predictions.csv`, `ann_tolerance.csv` | ANN predictions used by `validate_ann.m` |
| `run_experiments.m` | All ASMA scenarios across seeds |
| `analyze_results.m` | Summary tables, key numbers and figures |
| `plot_example.m` | Redraws Figure 1 using the seed with median degradation |
| `reference_python/wsn_ref.py` | Independent cross-check of the model logic |

## If something goes wrong

- **"Undefined function or variable"**: check that MATLAB's Current Folder is this folder.
- **Any error**: copy the full red message and send it to me.
- **Any `CHECK` line in `quick_check`**: send me the printed output.
