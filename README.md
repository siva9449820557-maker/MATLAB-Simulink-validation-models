# Multi-Objective WSN Routing Optimization Framework with Active Safety-Margin Augmentation (ASMA)

This repository hosts the open-access core simulation engine, data extraction scripts, and analytical verification models for the two-layer cyber-physical co-design framework presented in our manuscript targeted for the *Journal of Industrial Information Integration (JIII)*. 

The architecture is divided into two decoupled layers:
1. **The Offline Predictive Engine:** An Artificial Neural Network (ANN) trained via use-case-driven synthetic data generation to optimize multi-hop macro-topologies.
2. **The Runtime Surveillance Layer:** The Active Safety-Margin Augmentation (ASMA) closed-loop control system modeled as a deterministic Finite State Machine (FSM) to protect link margins against severe over-the-air (OTA) channel distortions.

---

## 📁 Repository Structure and Script Roadmap

```text
├── 01_ANN_Model_Validation/
│   ├── ANN_Optima_Vs_Simulink_Matrix.m    # Module A: Offline vs. Discrete-Event validation script
│   └── Verification_Data_Source.mat       # Consolidated baseline design dataset
│
├── 02_Case_A_Unhardened_Baseline/
│   ├── WSN_Static_Path_Model.slx          # Module B: Simulink canvas without ASMA feedback loop
│   └── Case_A_Data_Extraction.m           # Squeeze-protected baseline telemetry parser
│
└── 03_Case_B_Active_ASMA/
    ├── WSN_Self_Healing_ASMA_Model.slx    # Module C: Simulink canvas with active FSM feedback loop
    └── Case_B_Data_Extraction_Plotter.m   # Transient recovery parser and time-series generator
```

---

## 💻 Script Documentation and Execution Outlines

### Module A: Offline Analytical Optimization and Conservative Boundary Verification
* **Script Location:** `01_ANN_Model_Validation/ANN_Optima_Vs_Simulink_Matrix.m`
* **Purpose:** This script cross-references the optimal output settings computed by the offline multi-objective ANN framework against the empirical steady-state results extracted from the discrete-event Simulink model under normal operating constraints.
* **Reviewer Verification Guide:** Running this script automatically parses the validation matrix. It explicitly computes the operational deltas to demonstrate that the ANN analytical framework and the Simulink empirical canvas converge closely. For safety-critical cross-layer Quality of Service (QoS) dimensions—such as end-to-end network latency and the Safety Compliance Index ($1 - \text{FPDR}$)—the script demonstrates that the offline ANN optimizer yields a **conservative prediction**. This intentional alignment provides functional safety design engineers with a highly dependable safety cushion during early network deployment phases.

### Module B: Case A - Unhardened Static Baseline Operations (Without ASMA)
* **Simulink Canvas:** `02_Case_A_Unhardened_Baseline/WSN_Static_Path_Model.slx`
* **Data Extraction Script:** `02_Case_A_Unhardened_Baseline/Case_A_Data_Extraction.m`
* **Purpose:** Evaluates the runtime vulnerability of conventional static optimization routing configurations when subjected to extreme localized channel stress.
* **Execution Procedure:**
  1. Open the Simulink canvas file inside the MATLAB environment.
  2. Verify that the time-varying Over-the-Air (OTA) noise variance block is calibrated to a malicious ceiling of `0.0950` injected at $t = 30.0\text{ s}$.
  3. Run the simulation for a total horizon of `100 seconds`.
  4. Execute `Case_A_Data_Extraction.m`. This file applies a dimension-shielding `squeeze()` operator to the raw binary workspace success arrays (`out.success(:)`) to eliminate multi-dimensional Singleton errors. 
  5. The script outputs the unmitigated performance drop: because the closed-loop path is inactive ($u_2 = 0$), the Packet Delivery Rate (PDR) collapses permanently to a catastrophic steady-state floor of **43.14%**, severely breaching the mandatory Process Safety Time ($PST_{\text{limit}} = 2.0\text{ s}$) ceiling.

### Module C: Case B - Dynamic Self-Healing Operations (With Active ASMA Feedback)
* **Simulink Canvas:** `03_Case_B_Active_ASMA/WSN_Self_Healing_ASMA_Model.slx`
* **Data Extraction Script:** `03_Case_B_Active_ASMA/Case_B_Data_Extraction_Plotter.m`
* **Purpose:** Validates the temporal determinism, automated link-hardening capabilities, and FSM transition rules governing the runtime ASMA engine.
* **Execution Procedure:**
  1. Open the self-healing Simulink model. Notice that the surveillance feedback line is engaged, linking the central gateway monitoring daemon to the edge node's internal registers through a discrete 3-Port Structural Switch.
  2. Execute the 100-second simulation under identical noise parameters ($\Theta_{\text{Noise}} = 0.0950$ at $t = 30.0\text{ s}$).
  3. Execute the `Case_B_Data_Extraction_Plotter.m` routine. 
  4. The code automatically extracts the flat 1D time-series vectors from the logged workspace parameters (`out.success` and `out.AsmaActive`). It generates high-resolution dual-window transient graphs mapping the intersection milestone at the early-warning envelope ($\psi_{\text{PDR}} = 0.93$).
  5. The output demonstrates the dynamic link recovery: the red ASMA hardening status curve shifts instantly from 0% to 100% at $t = 31.2\text{ s}$, applying a localized $+3\text{ dB}$ transmit power boost and scaling MAC retries from 3 to 5. This co-design action cushions the path, stabilizing the network metric at a highly resilient **99.20% PDR** within a tight **1.2-second actual transient recovery window** ($T_{\text{actual}} < PST_{\text{limit}}$), visually confirming strict temporal safety compliance.

---

## ⚙️ Bounded Environmental and Calibration Matrix
To guarantee identical boundary conditions and absolute reproducibility across all script modules, ensure that your workspace variables match the following parameters before executing a simulation run:

| Architectural Configuration | Core Parameter Boundary Value | Industrial System Description |
| :--- | :---: | :--- |
| **Path Node Count ($K$)** | `10 Nodes` | Multi-hop routing layout path |
| **Total Path Geometry Length** | `293 meters` | Cumulative distributed network scale |
| **Application Layer Payload** | `900 bits` | Bounded data frame size per hop |
| **Base Transceiver Transmission Rate** | `165 Kbps` | Digital physical layer bit rate constraint |
| **Nominal Node Power Ceiling** | `11 mW` | Physical hardware operational budget |
| **Normalized Residual Power ($Nom_{\text{ResW}}$)**| `0.75` | Initialized local node safety allocation |
| **Primary System Detection Threshold** | `0.03` | Transceiver circuit receiver barrier sensitivity |
| **Proactive Early Warning Envelope** | `93%` PDR / `7%` FPDR | ASMA trigger threshold barriers ($\mathbf{\Psi}$) |
| **Absolute Functional Safety Floor** | `90%` PDR | Mandatory low-demand SIL-1 certification boundary |
| **Process Safety Time Upper Limit** | `2.0 seconds` | Predefined temporal safety constraint ceiling ($PST_{\text{limit}}$) |

---

## 📜 Academic License
This framework code and its corresponding simulation canvas blocks are released under the MIT Open-Source Academic License. You are free to modify, scale, and customize the modules for specific industrial environments, provided full attribution is credited to the source manuscript.
