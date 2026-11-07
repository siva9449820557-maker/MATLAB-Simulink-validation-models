# ANN surrogate for IWSN route design (retrained, physics-based)

Replaces the JMP model of the first version. Everything here is open source
(Python 3, NumPy, scikit-learn, Matplotlib, openpyxl) and reproducible with the
commands below.

## Method in brief

1. **Simulator** (`sim_core.py`): the same physics as the Simulink model. IEEE
   802.15.4 O-QPSK at 250 kbps, dual-slope path loss (46 + 11 log10 d up to 11 m,
   30 + 26 log10 d beyond), 4 dB log-normal shadowing, Rician fading (K = 3 dB)
   per attempt, CSMA/CA backoff, ACKs, retries, per-hop queueing, 100 ms deadline,
   CC2420-fit radio energy. Cross-checked against the reference implementation
   (`reference_python/wsn_ref.py`): with shadowing removed, on-time PDR agrees
   within statistical error (0.161 vs 0.159 at 33 dB; 0.011 vs 0.011 at 35 dB).
2. **Dataset** (`gen_dataset.py`): 30,000 route designs from a Latin hypercube over
   seven inputs, each simulated for 60 s (600 packets) with interference on the
   middle three hops.

   | Input | Range |
   | --- | --- |
   | Number of hops K | 2-12 |
   | Mean hop distance | 10-60 m |
   | Std of hop distance | 0 to min(15 m, half the mean) |
   | Transmit power | -10 to 0 dBm |
   | Payload | 200-900 bits |
   | Maximum retries | 0-5 |
   | Interference on middle three hops | 0-40 dB |

3. **ANN** (`train_ann.py`): one network per output, one hidden layer of tanh
   units (size chosen by 3-fold cross-validation from 4, 6, 8, 10), L2 penalty
   1e-3, L-BFGS. 75 % of designs for training, 25 % held out.
   Energy is modelled as E = E_min x 10^y, where E_min is the exact energy with no
   retransmissions, so the ANN learns only the retransmission overhead.
   Energy and shortest PST are fitted on a log scale (typical values); the
   other outputs are fitted as averages.
4. **Optimiser** (`optimize.py`): route length fixed at 293 m and payload at 900 bits.
   Searches 8,052 designs (K 5-12, spacing spread, transmit power, retries) for the
   largest interference level at which PDR >= 0.90, SDR >= 0.90 (PST 2 s),
   99th-percentile latency <= 100 ms and shortest supportable PST <= 2 s all hold.

## Accuracy on held-out designs (R²)

| Output | ANN (hidden units) | Gradient boosting | Linear regression | Closed-form AWGN product |
| --- | --- | --- | --- | --- |
| On-time PDR | 0.889 (8) | 0.885 | 0.759 | 0.715 |
| SDR at PST 2 s | 0.836 (8) | 0.832 | 0.663 | - |
| Mean latency | 0.991 (8) | 0.990 | 0.962 | - |
| 99th pct latency | 0.975 (10) | 0.970 | 0.911 | - |
| Energy per packet (log) | 0.787 (4) | 0.779 | 0.660 | - |
| Shortest PST (log) | 0.842 (4) | 0.838 | 0.661 | - |

Random shadowing and hop placement make identical designs perform differently,
which caps the achievable R² at about 0.885 for PDR and 0.837 for SDR (measured by
simulating 1,500 designs twice with different seeds). The ANN reaches that ceiling.

## Optimum design (`optimum_table.csv`)

| Design | Hops | Hop spacing | Retries | ANN tolerance | Simulated tolerance | Mean latency | Energy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **ANN optimum** | 11 | 26.6 m, uniform | 2 | 26.1 dB | 27.4 dB | 82 ms | 3.0 mJ |
| Energy-lean alternative | 9 | 32.6 m, uniform | 5 | 25.9 dB | 26.5 dB | 66 ms | 2.5 mJ |
| First-version route | 10 | 29.3 m, std 11.57 m | 3 | 24.6 dB | 25.5 dB | 75 ms | 2.7 mJ |

All at 0 dBm and 900-bit payload. Simulated tolerance: interference level at which
the mean on-time PDR over 300 seeds falls to 0.90. The ANN ranks the designs
correctly and is conservative by about 1 dB.

Key design insight: more hops shorten each link (more signal margin), but beyond
about 11 hops the 100 ms deadline and retry delays make packets late; more retries
help short routes and hurt long ones (`fig_tolerance_map.png`).

## Validation against simulation (300 seeds per point, `validation_python.csv`)

Mean absolute difference between ANN and simulation over three designs and ten
interference levels: PDR 0.027, SDR 0.019, mean latency 1.2 ms, 99th-percentile
latency 0.9 ms, energy 0.23 mJ (vs median), shortest PST 0.42 s (vs median).

Known limitation: with no interference the ANN predicts PDR 0.97 for the optimum,
where simulation gives 1.00. It underestimates near the top of the range, which is
the safe direction.

## Files

| File | Content |
| --- | --- |
| `dataset.csv` | 30,000 simulated designs (inputs and outputs) |
| `ann_model.json` | All weights, scalings and transforms |
| `accuracy.csv` | Held-out accuracy of ANN and baselines |
| `design_grid.csv`, `optimum_table.csv`, `pareto.csv` | Optimisation results |
| `validation_python.csv` | ANN vs simulation, 300 seeds per point |
| `fig_ann_parity.png` | Predicted vs simulated, held-out designs |
| `fig_tolerance_map.png` | Tolerance by hop count and retries |
| `fig_ann_validation.png` | ANN vs simulation across interference |
| `fig_ann_profiler.png` | Prediction profiles around the optimum |
| `fig_tradeoff.png` | Tolerance vs energy across all designs |
| `IWSN_ANN_Calculator.xlsx` | Excel calculator built from the same equations |

## Reproduce

```
python3 gen_dataset.py 30000   # about 2 minutes on 2 cores
python3 train_ann.py           # about 2 minutes
python3 optimize.py
python3 validate_py.py
python3 make_figures.py
python3 build_excel.py
```
