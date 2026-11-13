# Safety-aware IWSN route design with Active Safety-Margin Augmentation (ASMA)

Simulation models, data and code supporting the manuscript *"Safety-margin-aware
route design and runtime link hardening for industrial wireless sensor networks"*
(under review). Everything needed to reproduce the reported results is here.

> **Version note (November 2026).** Version 1 of this repository (folders
> `01_ANN_Model_Validation`, `Model_WITH_ASMA`, `Model_WO_ASME`) has been withdrawn.
> Its data-extraction scripts did not compute the reported metrics from the
> Simulink output: they substituted values aligned with the ANN predictions.
> Those results must not be used. Version 3 replaces the models, the ANN and the
> scripts; every reported number is now computed from logged simulation data, and
> the scripts stop with an error rather than substitute a value. The withdrawn
> files remain visible in the git history for transparency.

## Contents

| Folder | What it holds |
| --- | --- |
| [`simulink/`](simulink) | MATLAB/Simulink models (built by script), ASMA controller, experiment, validation and analysis scripts. See [`simulink/README.md`](simulink/README.md). |
| [`ann/`](ann) | Physics-based dataset (30,000 route designs), ANN training, optimization and validation code (Python), trained weights, figures and an Excel calculator. See [`ann/README.md`](ann/README.md). |
| [`results/`](results) | Outputs of the Simulink runs reported in the manuscript (MATLAB R2026b, 30 seeds per scenario): summary tables, per-seed metrics, ANN validation and figures. `Manuscript_data_workbook.xlsx` recomputes every number in the manuscript from these files with Excel formulas (start at sheet *Claims*); `build_data_workbook.py` rebuilds it. |

## What the work does

1. **Design time:** an artificial neural network (one tanh hidden layer per output),
   trained on 30,000 simulated IEEE 802.15.4 routes, predicts on-time packet delivery,
   successful detection ratio, latency, energy and the shortest supportable process
   safety time (PST) from seven design inputs. An optimizer uses it to find the
   route that tolerates the most interference while meeting the safety targets.
2. **Run time:** ASMA, a base-station controller, watches per-hop link quality and
   raises transmit power (+3 dB, optionally +2 retries) only on degraded hops, with
   hysteresis; a watchdog trips the process to its safe state if no on-time packet
   arrives within PST minus the actuation time.

## Key results (from `results/`)

- ANN vs Simulink (20 seeds per point): mean absolute error 0.021 in on-time PDR and
  0.5 ms in mean latency. Interference tolerance: ANN optimum 26.1 dB predicted,
  27.1 dB simulated; first-version route 24.6 dB predicted, 24.3 dB simulated.
- ASMA on the optimum route (30 seeds): the interference level at which median
  on-time PDR falls to 0.90 rises from 29.1 dB to 32.5 dB; at 34 dB, fail-safe trips
  fall from 17/30 to 3/30 and the median shortest supportable PST from 2.09 s to 0.80 s.

## Reproduce

**Simulink (MATLAB R2021b or newer, no extra toolboxes):** in MATLAB, open the
`simulink` folder and run, in order: `build_wsn_model`, `quick_check`,
`validate_ann`, `run_experiments`, `analyze_results`, `plot_example`.

**ANN (Python 3 with NumPy, pandas, scikit-learn, Matplotlib, openpyxl):** in the
`ann` folder run `gen_dataset.py`, `train_ann.py`, `optimize.py`, `validate_py.py`,
`make_figures.py`, `build_excel.py`.

## Contact

For questions about the models, please open an issue in this repository.
