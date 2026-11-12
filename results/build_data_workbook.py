"""Build Manuscript_data_workbook.xlsx: every number in the manuscript traced to the raw result files.

Raw data are copied in (blue text); every derived number is an Excel formula (black text), so the
reader can follow each value back to the per-seed results. Usage:
    python build_data_workbook.py <results_dir> <ann_dir> <simulink_dir> <out.xlsx>
"""
import sys
import numpy as np
import pandas as pd
import scipy.io as sio
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.comments import Comment

RES, ANN, SIM, OUT = sys.argv[1:5]
FONT = 'Arial'
BLUE = Font(name=FONT, size=10, color='0000FF')
BLACK = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=13, bold=True)
NOTE = Font(name=FONT, size=9, italic=True, color='555555')
HEAD_FILL = PatternFill('solid', fgColor='DDE6F0')
OK_FILL = PatternFill('solid', fgColor='E2F0D9')
thin = Side(style='thin', color='BFBFBF')
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

wb = Workbook()


def sheet(name, title, note=None):
    ws = wb.create_sheet(name)
    ws['A1'] = title; ws['A1'].font = TITLE
    if note:
        ws['A2'] = note; ws['A2'].font = NOTE
    return ws


def header(ws, row, names, col=1, widths=None):
    for j, n in enumerate(names):
        c = ws.cell(row=row, column=col + j, value=n)
        c.font = BOLD; c.fill = HEAD_FILL; c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical='center')
    if widths:
        for j, w in enumerate(widths):
            ws.column_dimensions[L(col + j)].width = w


def put(ws, row, col, value, font=BLACK, fmt=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font
    if fmt:
        c.number_format = fmt
    return c


def clean(v):
    if isinstance(v, (float, np.floating)) and not np.isfinite(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


# ------------------------------------------------------------------ Per_seed (raw)
PS = pd.read_csv(f'{RES}/per_seed_metrics.csv')
ws = sheet('Per_seed', 'Per-seed results of all Simulink runs (copied from results/per_seed_metrics.csv)',
           'One row per scenario and seed (22 scenarios x 30 seeds). Blue = raw data. Empty cell = not defined '
           '(no packet delivered, or ASMA never activated). Column W is a helper formula.')
cols = list(PS.columns)
header(ws, 4, cols + ['lateFraction (delivered minus on-time)'], widths=[24, 6] + [13] * 21)
R0 = 5
for i, r in enumerate(PS.itertuples(index=False)):
    for j, v in enumerate(r):
        put(ws, R0 + i, j + 1, clean(v), BLUE)
    rr = R0 + i
    put(ws, rr, len(cols) + 1, f'=IF(AND(ISNUMBER(D{rr}),ISNUMBER(E{rr})),E{rr}-D{rr},"")', BLACK, '0.000')
ws.freeze_panes = 'C5'
COL = {c: L(j + 1) for j, c in enumerate(cols)}
COL['late'] = L(len(cols) + 1)
scen = list(dict.fromkeys(PS.scenario))
block = {s: (R0 + PS.index[PS.scenario == s].min(), R0 + PS.index[PS.scenario == s].max()) for s in scen}
for s, (a, b) in block.items():
    assert b - a == 29, s


def rng(s, c):
    a, b = block[s]
    return f'Per_seed!{COL[c]}{a}:{COL[c]}{b}'


# ------------------------------------------------------------------ Scenarios (formulas)
ws = sheet('Scenarios', 'Summary per scenario, computed from Per_seed with formulas',
           'Medians and quartiles over the 30 seeds (QUARTILE = Excel QUARTILE.INC). SDR is the mean over seeds. '
           'Trips and false activations are counts over the 30 runs.')
SC_COLS = [
    ('Scenario', None, None, 26), ('Seeds', 'COUNT', 'seed', 7),
    ('On-time PDR, median', 'MEDIAN', 'pdrDisturbance', 11), ('PDR Q1', 'Q1', 'pdrDisturbance', 9),
    ('PDR Q3', 'Q3', 'pdrDisturbance', 9), ('Delivered (any latency), median', 'MEDIAN', 'delivDisturbance', 12),
    ('Late fraction, median', 'MEDIAN', 'late', 10),
    ('PST_min (s), median', 'MEDIAN', 'minPST99_s', 10), ('PST_min Q1', 'Q1', 'minPST99_s', 9),
    ('PST_min Q3', 'Q3', 'minPST99_s', 9),
    ('SDR at PST 2 s, mean', 'AVERAGE', 'sdrAtPST', 10), ('SDR at PST 2 s, median', 'MEDIAN', 'sdrAtPST', 10),
    ('Fail-safe trips (count)', 'SUM', 'failSafeTrip', 9),
    ('Energy per delivered packet during interference (mJ), median', 'MEDIAN', 'energyPerPktDisturbance_mJ', 14),
    ('Energy per packet, whole run (mJ), median', 'MEDIAN', 'energyPerPkt_mJ', 12),
    ('99th pct latency during interference (ms), median', 'MEDIAN', 'latP99Disturbance_ms', 13),
    ('Mean latency, interference-free part (ms), median', 'MEDIAN', 'latMeanNominal_ms', 13),
    ('99th pct latency, interference-free part (ms), median', 'MEDIAN', 'latP99Nominal_ms', 13),
    ('Reaction time (s), median', 'MEDIAN', 'reaction_s', 10), ('Recovery time (s), median', 'MEDIAN', 'recovery_s', 10),
    ('False activations (count)', 'SUM', 'falseActivations', 10),
    ('ASMA active, fraction of run, median', 'MEDIAN', 'asmaFraction', 10),
    ('Residual errors per hour, CRC-16 bound, median', 'MEDIAN', 'residualPerHour', 13),
]
header(ws, 4, [c[0] for c in SC_COLS], widths=[c[3] for c in SC_COLS])
ws.row_dimensions[4].height = 64
SCN = {}
for i, s in enumerate(scen):
    r = 5 + i; SCN[s] = r
    put(ws, r, 1, s, BLACK)
    for j, (name, fn, c, _) in enumerate(SC_COLS[1:], start=2):
        R = rng(s, c)
        f = {'COUNT': f'=COUNT({R})', 'MEDIAN': f'=MEDIAN({R})', 'AVERAGE': f'=AVERAGE({R})', 'SUM': f'=SUM({R})',
             'Q1': f'=QUARTILE({R},1)', 'Q3': f'=QUARTILE({R},3)'}[fn]
        if fn in ('MEDIAN', 'AVERAGE', 'Q1', 'Q3'):   # empty when the metric is undefined in every run
            f = f'=IF(COUNT({R})=0,"",{f[1:]})'
        fmt = '0' if fn in ('COUNT', 'SUM') else ('0.00E+00' if c == 'residualPerHour' else '0.000')
        put(ws, r, j, f, BLACK, fmt)
ws.freeze_panes = 'B5'
SCOL = {c[0]: L(j + 1) for j, c in enumerate(SC_COLS)}


def S(scenario, colname):
    """Reference to a Scenarios cell."""
    return f"Scenarios!{SCOL[colname]}{SCN[scenario]}"


def nm(dB, on):
    return f'step_{dB:02d}dB_{"ASMA" if on else "noASMA"}'


# ------------------------------------------------------------------ Table 4
ws = sheet('Table4', 'Manuscript Table 4, recomputed from the per-seed data',
           'Top block: computed with formulas. Middle block: values as printed in the manuscript. '
           'Bottom block: ✓ when the computed value rounds to the printed value.')
T4 = [('On-time PDR', 'On-time PDR, median', '0.000', 0.0005), ('PST_min (s)', 'PST_min (s), median', '0.00', 0.005),
      ('SDR at PST 2 s (mean)', 'SDR at PST 2 s, mean', '0.000', 0.0005),
      ('Fail-safe trips', 'Fail-safe trips (count)', '0', 0.01),
      ('Energy (mJ/packet)', 'Energy per delivered packet during interference (mJ), median', '0.00', 0.005)]
printed = {28: [0.959, 0.995, 0.74, 0.68, 0.986, 1.000, 1, 0, 3.24, 3.22],
           30: [0.853, 0.975, 0.79, 0.68, 0.957, 1.000, 2, 1, 3.59, 3.29],
           32: [0.593, 0.944, 0.99, 0.71, 0.927, 0.977, 8, 2, 4.65, 3.46],
           34: [0.224, 0.755, 2.09, 0.80, 0.788, 0.949, 17, 3, 10.11, 3.84]}
heads = ['Interference (dB)'] + [f'{t[0]} {w}' for t in T4 for w in ('without ASMA', 'with ASMA')]
for top, label in [(4, 'Computed'), (11, 'Printed in manuscript'), (18, 'Match')]:
    put(ws, top - 1, 1, label, BOLD)
    header(ws, top, heads, widths=[13] + [12] * 10)
    ws.row_dimensions[top].height = 45
for i, dB in enumerate([28, 30, 32, 34]):
    rc, rp, rm = 5 + i, 12 + i, 19 + i
    for r in (rc, rp, rm):
        put(ws, r, 1, dB, BLACK)
    for k, (lab, col, fmt, tol) in enumerate(T4):
        for w, on in enumerate((False, True)):
            j = 2 + 2 * k + w
            put(ws, rc, j, '=' + S(nm(dB, on), col), BLACK, fmt)
            put(ws, rp, j, printed[dB][2 * k + w], BLUE, fmt)
            put(ws, rm, j, f'=IF(ABS({L(j)}{rc}-{L(j)}{rp})<={tol}+1E-9,"✓","✗")', BLACK)
put(ws, 24, 1, 'Values that match', BOLD)
put(ws, 24, 2, '=COUNTIF(B19:K22,"✓")', BLACK, '0'); put(ws, 24, 3, 'of 40', BLACK)
put(ws, 26, 1, 'Interference level where median on-time PDR falls to 0.90 (linear interpolation between levels)', BOLD)
put(ws, 27, 1, 'Without ASMA (between 28 and 30 dB)', BLACK)
put(ws, 27, 4, '=28+2*(B5-0.9)/(B5-B6)', BLACK, '0.0')
put(ws, 28, 1, 'With ASMA (between 32 and 34 dB)', BLACK)
put(ws, 28, 4, '=32+2*(C7-0.9)/(C7-C8)', BLACK, '0.0')
put(ws, 29, 1, 'Gain in tolerance (dB)', BLACK)
put(ws, 29, 4, '=D28-D27', BLACK, '0.0')
ws.freeze_panes = 'B5'

# ------------------------------------------------------------------ Paired comparison
ws = sheet('Paired', 'Paired comparison over the same 30 seeds (ASMA minus no ASMA)',
           'Each seed fixes shadowing and node placement, so the with/without runs of a seed form a pair. '
           'CI = mean ± 1.96 × standard error (as in analyze_results.m). Sign test p = 2 × BINOMDIST(min(higher, lower), '
           'higher + lower, 0.5).')
groups = [(f'PDR {dB} dB', 'pdrDisturbance', dB) for dB in (28, 30, 32, 34)] + \
         [('Energy 30 dB (mJ)', 'energyPerPktDisturbance_mJ', 30)]
hd = ['Seed']
for g in groups:
    hd += [f'{g[0]} without ASMA', f'{g[0]} with ASMA', f'{g[0]} difference']
header(ws, 4, hd, widths=[7] + [11] * (len(hd) - 1))
ws.row_dimensions[4].height = 45
for s in range(30):
    r = 5 + s
    put(ws, r, 1, s + 1, BLACK)
    for gi, (lab, c, dB) in enumerate(groups):
        j = 2 + 3 * gi
        a_off = block[nm(dB, False)][0] + s; a_on = block[nm(dB, True)][0] + s
        put(ws, r, j, f'=Per_seed!{COL[c]}{a_off}', BLACK, '0.000')
        put(ws, r, j + 1, f'=Per_seed!{COL[c]}{a_on}', BLACK, '0.000')
        put(ws, r, j + 2, f'={L(j + 1)}{r}-{L(j)}{r}', BLACK, '0.000')
stats = ['Seeds (n)', 'Mean difference', 'Standard deviation', 'Standard error', '95% CI low', '95% CI high',
         'Seeds higher with ASMA', 'Seeds lower with ASMA', 'Sign test p (two-sided)']
PAIR = {}
for k, st in enumerate(stats):
    r = 37 + k
    put(ws, r, 1, st, BOLD)
    for gi, (lab, c, dB) in enumerate(groups):
        d = L(4 + 3 * gi); R = f'{d}5:{d}34'; col = d
        f = [f'=COUNT({R})', f'=AVERAGE({R})', f'=STDEV({R})', f'={col}39/SQRT({col}37)', f'={col}38-1.96*{col}40',
             f'={col}38+1.96*{col}40', f'=COUNTIF({R},">0")', f'=COUNTIF({R},"<0")',
             f'=MIN(1,2*BINOMDIST(MIN({col}43,{col}44),{col}43+{col}44,0.5,TRUE))'][k]
        fmt = ['0', '0.000', '0.000', '0.000', '0.000', '0.000', '0', '0', '0.00E+00'][k]
        put(ws, r, 4 + 3 * gi, f, BLACK, fmt)
        PAIR[(lab, st)] = f'Paired!{col}{r}'
ws.column_dimensions['A'].width = 24
ws.freeze_panes = 'B5'

# ------------------------------------------------------------------ Ablation and disturbance shape
ws = sheet('Ablation', 'Ablation and disturbance shape at 30 dB (medians over 30 seeds)',
           'Late fraction = packets delivered after the 100 ms deadline (delivered minus on-time), per seed, then median.')
header(ws, 4, ['Variant', 'Scenario', 'On-time PDR', 'Late fraction', '99th pct latency (ms)'], widths=[30, 24, 12, 12, 14])
AB = [('No ASMA', 'step_30dB_noASMA'), ('Retries only (+2)', 'step_30dB_retriesOnly'),
      ('Power boost only (+3 dB)', 'step_30dB_powerOnly'), ('ASMA, both actions', 'step_30dB_ASMA'),
      ('Ramp, no ASMA', 'ramp_30dB_noASMA'), ('Ramp, ASMA', 'ramp_30dB_ASMA'),
      ('Burst, no ASMA', 'burst_30dB_noASMA'), ('Burst, ASMA', 'burst_30dB_ASMA')]
ABR = {}
for i, (lab, s) in enumerate(AB):
    r = 5 + i; ABR[s] = r
    put(ws, r, 1, lab); put(ws, r, 2, s)
    put(ws, r, 3, '=' + S(s, 'On-time PDR, median'), BLACK, '0.000')
    put(ws, r, 4, '=' + S(s, 'Late fraction, median'), BLACK, '0.000')
    put(ws, r, 5, '=' + S(s, '99th pct latency during interference (ms), median'), BLACK, '0.0')

# ------------------------------------------------------------------ Nominal route and residual error
ws = sheet('Nominal_residual', 'Nominal route (no interference) and residual-error bound',
           'Residual bound: every failed frame in the simulation (each attempt fails with the frame error probability '
           'from Eq. (3)) is assumed corrupted; a c-bit check misses a random corruption with probability 2^-c.')
ws.column_dimensions['A'].width = 70; ws.column_dimensions['B'].width = 14; ws.column_dimensions['C'].width = 40
n0 = nm(0, False)
rows = [
    ('Nominal route, 0 dB, without ASMA (30 seeds, medians)', None, None, None),
    ('On-time PDR', '=' + S(n0, 'On-time PDR, median'), '0.000', ''),
    ('Mean latency (ms)', '=' + S(n0, 'Mean latency, interference-free part (ms), median'), '0.0', ''),
    ('99th percentile latency (ms)', '=' + S(n0, '99th pct latency, interference-free part (ms), median'), '0.0',
     'percentile over the packets of one run, then median over seeds'),
    ('Energy per packet (mJ)', '=' + S(n0, 'Energy per packet, whole run (mJ), median'), '0.00', ''),
    ('Shortest supportable PST, PST_min (s)', '=' + S(n0, 'PST_min (s), median'), '0.00', ''),
    ('', None, None, None),
    ('Residual (undetected) error bound', None, None, None),
    ('Residual errors per hour with the 16-bit 802.15.4 frame check, 0 dB (median)',
     '=' + S(n0, 'Residual errors per hour, CRC-16 bound, median'), '0.00E+00', 'Per_seed column V'),
    ('Implied failed frames per hour (= residual × 2^16)', '=B12*2^16', '0.0', 'all failed attempts on all hops'),
    ('With an added 32-bit safety-layer check (× 2^-32)', '=B12*2^-32', '0.00E+00', ''),
    ('Residual errors per hour, 16-bit check, 34 dB without ASMA (median)',
     '=' + S(nm(34, False), 'Residual errors per hour, CRC-16 bound, median'), '0.00E+00', 'worst case simulated'),
    ('With an added 32-bit safety-layer check (× 2^-32)', '=B15*2^-32', '0.00E+00', ''),
    ('PFH limit for SIL 1 (per hour, IEC 61508, upper end of the SIL 1 band)', 1e-5, '0.00E+00', 'IEC 61508'),
    ('Budget for the safety communication: 1% of the PFH limit (IEC 61784-3)', '=B17*0.01', '0.00E+00', 'IEC 61784-3'),
    ('Within budget with the 32-bit check at 34 dB?', '=IF(B16<B18,"yes","no")', None, ''),
]
for i, (lab, f, fmt, note) in enumerate(rows):
    r = 4 + i
    put(ws, r, 1, lab, BOLD if f is None and lab else BLACK)
    if f is not None:
        put(ws, r, 2, f, BLUE if isinstance(f, float) else BLACK, fmt)
    if note:
        put(ws, r, 3, note, NOTE)

# ------------------------------------------------------------------ ANN validation (Fig. 2)
V = pd.read_csv(f'{RES}/ann_validation.csv').sort_values(['design', 'output', 'Noise_dB']).reset_index(drop=True)
ws = sheet('ANN_validation', 'ANN against Simulink (Fig. 2a-b), copied from results/ann_validation.csv',
           'design "v1" is the baseline design in the manuscript. Columns I-J are helper formulas.')
vc = list(V.columns)
header(ws, 4, vc + ['|Simulink mean - ANN|', 'PDR crossing of 0.90 (Simulink mean)', 'PDR crossing of 0.90 (ANN)'],
       widths=[10, 10, 12, 11, 10, 11, 10, 8, 12, 14, 14])
for i, r in enumerate(V.itertuples(index=False)):
    rr = 5 + i
    for j, v in enumerate(r):
        put(ws, rr, j + 1, clean(v), BLUE, '0.000' if isinstance(v, float) else None)
    put(ws, rr, 9, f'=ABS(D{rr}-G{rr})', BLACK, '0.000')
    if i > 0:
        p = rr - 1
        for col, val in ((10, 'D'), (11, 'G')):
            put(ws, rr, col, f'=IF(AND(C{rr}="PDR",C{p}="PDR",A{rr}=A{p},{val}{p}>=0.9,{val}{rr}<0.9),'
                             f'B{p}+({val}{p}-0.9)*(B{rr}-B{p})/({val}{p}-{val}{rr}),"")', BLACK, '0.00')
last = 4 + len(V)
VR = lambda c: f'ANN_validation!${c}$5:${c}${last}'
ws.freeze_panes = 'A5'
put(ws, last + 2, 1, 'Mean absolute error, on-time PDR', BOLD)
put(ws, last + 2, 4, f'=AVERAGEIFS({VR("I")},{VR("C")},"PDR")', BLACK, '0.000')
put(ws, last + 3, 1, 'Mean absolute error, mean latency (ms)', BOLD)
put(ws, last + 3, 4, f'=AVERAGEIFS({VR("I")},{VR("C")},"NWLat_ms")', BLACK, '0.00')
for k, (d, lab) in enumerate([('optimum', 'Optimum'), ('v1', 'Baseline (v1)')]):
    put(ws, last + 4 + k, 1, f'Tolerance in Simulink, {lab} (dB, PDR = 0.90)', BOLD)
    put(ws, last + 4 + k, 4, f'=_xlfn.MINIFS({VR("J")},{VR("A")},"{d}")', BLACK, '0.00')
    put(ws, last + 6 + k, 1, f'PDR crossing of the ANN curve, {lab} (dB, 2 dB grid)', BOLD)
    put(ws, last + 6 + k, 4, f'=_xlfn.MINIFS({VR("K")},{VR("A")},"{d}")', BLACK, '0.00')
put(ws, last + 8, 1, 'ANN-predicted PDR, optimum, 0 dB', BOLD)
put(ws, last + 8, 4, f'=SUMIFS({VR("G")},{VR("A")},"optimum",{VR("C")},"PDR",{VR("B")},0)', BLACK, '0.000')
put(ws, last + 9, 1, 'Simulink PDR, optimum, 0 dB', BOLD)
put(ws, last + 9, 4, f'=SUMIFS({VR("D")},{VR("A")},"optimum",{VR("C")},"PDR",{VR("B")},0)', BLACK, '0.000')
put(ws, last + 10, 1, 'Simulink energy per packet, optimum, 0 dB (mJ)', BOLD)
put(ws, last + 10, 4, f'=SUMIFS({VR("D")},{VR("A")},"optimum",{VR("C")},"Energy_mJ",{VR("B")},0)', BLACK, '0.00')
put(ws, last + 11, 1, 'Simulink energy per packet, baseline, 0 dB (mJ)', BOLD)
put(ws, last + 11, 4, f'=SUMIFS({VR("D")},{VR("A")},"v1",{VR("C")},"Energy_mJ",{VR("B")},0)', BLACK, '0.00')
put(ws, last + 12, 1, 'Extra energy of the optimum (fraction)', BOLD)
put(ws, last + 12, 4, f'=D{last + 10}/D{last + 11}-1', BLACK, '0.0%')
VAL = {k: f'ANN_validation!D{last + o}' for k, o in
       [('mae_pdr', 2), ('mae_lat', 3), ('tol_opt', 4), ('tol_v1', 5), ('ann_pdr0', 8), ('sim_pdr0', 9),
        ('e_opt', 10), ('e_v1', 11), ('e_extra', 12)]}

# ------------------------------------------------------------------ Design grid (optimizer, Fig. 2c)
G = pd.read_csv(f'{ANN}/design_grid.csv')
TOL = pd.read_csv(f'{SIM}/ann_tolerance.csv')
ws = sheet('Design_grid', 'Optimizer: ANN-predicted tolerance of every candidate design (ann/design_grid.csv)',
           '293 m route, 900-bit payload. Tolerance = highest interference (0.1 dB steps) at which all four targets hold.')
header(ws, 4, list(G.columns), widths=[6, 10, 9, 9, 9, 13, 13, 13])
for i, r in enumerate(G.itertuples(index=False)):
    for j, v in enumerate(r):
        put(ws, 5 + i, j + 1, clean(v), BLUE)
gl = 4 + len(G)
put(ws, 1, 10, 'Summary', BOLD)
summ = [('Designs evaluated', f'=COUNT(A5:A{gl})', '#,##0'),
        ('Highest predicted tolerance (dB)', f'=MAX(F5:F{gl})', '0.0'),
        ('Hops K of the best design', f'=INDEX(A5:A{gl},MATCH(K3,F5:F{gl},0))', '0'),
        ('Hop spacing of the best design (m)', f'=INDEX(B5:B{gl},MATCH(K3,F5:F{gl},0))', '0.0'),
        ('Spacing std of the best design (m)', f'=INDEX(C5:C{gl},MATCH(K3,F5:F{gl},0))', '0.0'),
        ('Transmit power of the best design (dBm)', f'=INDEX(D5:D{gl},MATCH(K3,F5:F{gl},0))', '0'),
        ('Retries of the best design', f'=INDEX(E5:E{gl},MATCH(K3,F5:F{gl},0))', '0'),
        ('ANN tolerance of the baseline design (dB, from ann_tolerance.csv)', float(TOL.set_index('design').loc['v1', 'ANN_tolerance_dB']), '0.0')]
for i, (lab, f, fmt) in enumerate(summ):
    put(ws, 2 + i, 10, lab); put(ws, 2 + i, 11, f, BLUE if isinstance(f, float) else BLACK, fmt)
ws.column_dimensions['J'].width = 52; ws.column_dimensions['K'].width = 10
ws.freeze_panes = 'A5'

# ------------------------------------------------------------------ Table 3 accuracy
A = pd.read_csv(f'{ANN}/accuracy.csv')
CE = pd.read_csv(f'{ANN}/r2_ceiling.csv')
ws = sheet('Table3_accuracy', 'Held-out accuracy (Table 3), copied from ann/accuracy.csv and ann/r2_ceiling.csv',
           'R² for energy and PST_min is computed on the log scale. Ceiling: every design simulated a second time '
           'with a different seed; ceiling = Cov(run 1, run 2) / Var (ann/ceiling.py).')
header(ws, 4, list(A.columns), widths=[12, 26, 8, 10, 10, 10])
for i, r in enumerate(A.itertuples(index=False)):
    for j, v in enumerate(r):
        put(ws, 5 + i, j + 1, clean(v), BLUE, '0.000' if j >= 3 else None)
cr = 6 + len(A)
header(ws, cr, list(CE.columns))
for i, r in enumerate(CE.itertuples(index=False)):
    for j, v in enumerate(r):
        put(ws, cr + 1 + i, j + 1, clean(v), BLUE, '0.000' if j == 2 else None)
ACC = {(r.output, r.model.split(' (')[0]): f'Table3_accuracy!D{5 + i}' for i, r in A.iterrows()}
CEIL = {r.output: f'Table3_accuracy!C{cr + 1 + i}' for i, r in CE.iterrows()}
NT = {r.output: f'Table3_accuracy!C{5 + i}' for i, r in A.iterrows()}

# ------------------------------------------------------------------ Fig. 5c SDR curves
mat = sio.loadmat(f'{RES}/experiments.mat', squeeze_me=True, struct_as_record=False)
Rm = mat['results']
ws = sheet('Fig5c_SDR_curves', 'Mean SDR versus PST at 30 dB (Fig. 5c), averaged over 30 seeds from results/experiments.mat',
           'Values computed in Python from the sdrCurve field of each run (blue = derived data, not a formula). '
           'Row "PST = 2.0 s" should equal the mean SDR on sheet Scenarios.')
VAR = [('step_30dB_noASMA', 'No ASMA'), ('step_30dB_retriesOnly', 'Retries only'),
       ('step_30dB_powerOnly', 'Power boost only'), ('step_30dB_ASMA', 'ASMA, both')]
header(ws, 4, ['PST (s)'] + [v[1] for v in VAR], widths=[10, 12, 12, 14, 12])
grid = [r.M.pstGrid_s for r in Rm if r.scenario == VAR[0][0]][0]
curves = [np.array([r.M.sdrCurve for r in Rm if r.scenario == s]).mean(0) for s, _ in VAR]
for i, x in enumerate(grid):
    put(ws, 5 + i, 1, float(x), BLUE, '0.0')
    for j, c in enumerate(curves):
        put(ws, 5 + i, 2 + j, float(c[i]), BLUE, '0.000')

# ------------------------------------------------------------------ Claims (front sheet)
ws = wb['Sheet']; ws.title = 'Claims'; wb.move_sheet('Claims', -(len(wb.sheetnames) - 1))
ws['A1'] = 'Every number in the manuscript, recomputed from the raw results'; ws['A1'].font = TITLE
ws['A2'] = ('Column D = value printed in the manuscript (blue). Column E = value computed in this workbook (formula; '
            'follow it to the sheet named in column I). Column G: ✓ when the computed value agrees with the printed one '
            'within the rounding in column F ("<" or ">" = the claim is an upper or lower bound).')
ws['A2'].font = NOTE; ws['A2'].alignment = Alignment(wrap_text=True); ws.merge_cells('A2:I2'); ws.row_dimensions[2].height = 42
header(ws, 4, ['#', 'Section', 'What the manuscript says', 'Printed value', 'Computed value', 'Rounding / test',
               'Match', 'Unit', 'Where to look'], widths=[5, 15, 62, 12, 13, 11, 8, 8, 30])
P30, P32, E30 = 'PDR 30 dB', 'PDR 32 dB', 'Energy 30 dB (mJ)'
o30, a30 = nm(30, False), nm(30, True)
claims = [
    ('Abstract, 4.2', 'ANN R² for on-time delivery (PDR)', 0.889, ACC[('PDR', 'ANN')], 0.0005, '', 'Table3_accuracy'),
    ('Abstract, 4.2', 'ANN R² for mean latency', 0.991, ACC[('NWLat_ms', 'ANN')], 0.0005, '', 'Table3_accuracy'),
    ('4.2', 'Held-out designs for PDR and SDR', 7500, NT['PDR'], 0.5, '', 'Table3_accuracy'),
    ('4.2', 'Held-out designs for latency and energy', 5241, NT['NWLat_ms'], 0.5, '', 'Table3_accuracy'),
    ('4.2', 'R² ceiling for PDR (random shadowing and hop order)', 0.886, CEIL['PDR'], 0.0005, '', 'Table3_accuracy'),
    ('4.2', 'R² ceiling for SDR', 0.838, CEIL['SDR'], 0.0005, '', 'Table3_accuracy'),
    ('4.3', 'Designs evaluated by the optimizer', 8052, 'Design_grid!K2', 0.5, '', 'Design_grid'),
    ('4.3', 'Predicted tolerance of the optimum (dB)', 26.1, 'Design_grid!K3', 0.05, 'dB', 'Design_grid'),
    ('4.3', 'Optimum: number of hops', 11, 'Design_grid!K4', 0.01, '', 'Design_grid'),
    ('4.3', 'Optimum: hop spacing (m)', 26.6, 'Design_grid!K5', 0.05, 'm', 'Design_grid'),
    ('4.3', 'Optimum: spacing standard deviation (uniform = 0)', 0, 'Design_grid!K6', 0.01, 'm', 'Design_grid'),
    ('4.3', 'Optimum: retries', 2, 'Design_grid!K8', 0.01, '', 'Design_grid'),
    ('4.3', 'Predicted tolerance of the baseline design (dB)', 24.6, 'Design_grid!K9', 0.05, 'dB', 'Design_grid'),
    ('4.3', 'ANN vs Simulink: mean absolute error in on-time PDR', 0.021, VAL['mae_pdr'], 0.0005, '', 'ANN_validation'),
    ('4.3', 'ANN vs Simulink: mean absolute error in mean latency (ms)', 0.5, VAL['mae_lat'], 0.05, 'ms', 'ANN_validation'),
    ('Abstract, 4.3', 'Simulated tolerance of the optimum (dB)', 27.1, VAL['tol_opt'], 0.05, 'dB', 'ANN_validation'),
    ('Abstract, 4.3', 'Simulated tolerance of the baseline design (dB)', 24.3, VAL['tol_v1'], 0.05, 'dB', 'ANN_validation'),
    ('4.3', 'Gain from optimization (dB)', 2.8, f'{VAL["tol_opt"]}-{VAL["tol_v1"]}', 0.05, 'dB', 'ANN_validation'),
    ('4.3', 'Energy per packet without interference, optimum (mJ)', 3.04, VAL['e_opt'], 0.005, 'mJ', 'ANN_validation'),
    ('4.3', 'Energy per packet without interference, baseline (mJ)', 2.76, VAL['e_v1'], 0.005, 'mJ', 'ANN_validation'),
    ('4.3', 'Extra energy of the optimum (10%)', 0.10, VAL['e_extra'], 0.005, '', 'ANN_validation'),
    ('4.3', 'ANN-predicted PDR of the optimum without interference', 0.97, VAL['ann_pdr0'], 0.005, '', 'ANN_validation'),
    ('4.3', 'Simulink PDR of the optimum without interference', 1.00, VAL['sim_pdr0'], 0.005, '', 'ANN_validation'),
    ('6.1', 'Nominal route: on-time PDR', 1.000, 'Nominal_residual!B5', 0.0005, '', 'Nominal_residual'),
    ('6.1', 'Nominal route: mean latency (ms)', 81.9, 'Nominal_residual!B6', 0.05, 'ms', 'Nominal_residual'),
    ('6.1', 'Nominal route: 99th-percentile latency (ms)', 87.5, 'Nominal_residual!B7', 0.05, 'ms', 'Nominal_residual'),
    ('6.1', 'Nominal route: energy per packet (mJ)', 3.04, 'Nominal_residual!B8', 0.005, 'mJ', 'Nominal_residual'),
    ('6.1, 6.2', 'Nominal route: shortest supportable PST (s)', 0.67, 'Nominal_residual!B9', 0.005, 's', 'Nominal_residual'),
    ('Abstract, 6.2', 'Interference at which median PDR falls to 0.90, without ASMA (dB)', 29.1, 'Table4!D27', 0.05, 'dB', 'Table4'),
    ('Abstract, 6.2', 'Same, with ASMA (dB)', 32.5, 'Table4!D28', 0.05, 'dB', 'Table4'),
    ('7', 'Tolerance added by ASMA (about 3.4 dB)', 3.4, 'Table4!D29', 0.05, 'dB', 'Table4'),
    ('6.2', 'Table 4: printed values that match the data (of 40)', 40, 'Table4!B24', 0.01, '', 'Table4'),
    ('6.2', 'Paired PDR gain at 30 dB (mean)', 0.155, PAIR[(P30, 'Mean difference')], 0.0005, '', 'Paired'),
    ('6.2', 'Paired PDR gain at 30 dB, 95% CI low', 0.106, PAIR[(P30, '95% CI low')], 0.0005, '', 'Paired'),
    ('6.2', 'Paired PDR gain at 30 dB, 95% CI high', 0.205, PAIR[(P30, '95% CI high')], 0.0005, '', 'Paired'),
    ('6.2', 'Seeds with higher PDR with ASMA at 30 dB', 30, PAIR[(P30, 'Seeds higher with ASMA')], 0.01, '', 'Paired'),
    ('6.2', 'Seeds with lower PDR with ASMA at 30 dB', 0, PAIR[(P30, 'Seeds lower with ASMA')], 0.01, '', 'Paired'),
    ('6.2', 'Sign test p at 30 dB (below 10^-8)', 1e-8, PAIR[(P30, 'Sign test p (two-sided)')], '<', '', 'Paired'),
    ('6.2', 'Paired PDR gain at 32 dB (mean)', 0.304, PAIR[(P32, 'Mean difference')], 0.0005, '', 'Paired'),
    ('6.2', 'Seeds with higher PDR with ASMA at 32 dB', 30, PAIR[(P32, 'Seeds higher with ASMA')], 0.01, '', 'Paired'),
    ('Abstract, 6.2', 'Fail-safe trips at 34 dB without ASMA', 17, S(nm(34, False), 'Fail-safe trips (count)'), 0.01, '', 'Scenarios'),
    ('Abstract, 6.2', 'Fail-safe trips at 34 dB with ASMA', 3, S(nm(34, True), 'Fail-safe trips (count)'), 0.01, '', 'Scenarios'),
    ('6.2', 'Median PST_min at 34 dB without ASMA (s)', 2.09, S(nm(34, False), 'PST_min (s), median'), 0.005, 's', 'Scenarios'),
    ('Abstract, 6.2', 'Median PST_min with ASMA stays at or below 0.80 s (34 dB, the worst case)', 0.805,
     S(nm(34, True), 'PST_min (s), median'), '<', 's', 'Scenarios'),
    ('6.2', 'Mean SDR at PST 2 s with ASMA, 34 dB (above 0.94)', 0.94, S(nm(34, True), 'SDR at PST 2 s, mean'), '>', '', 'Scenarios'),
    ('6.2', 'Mean SDR at PST 2 s without ASMA, 34 dB', 0.79, S(nm(34, False), 'SDR at PST 2 s, mean'), 0.005, '', 'Scenarios'),
    ('6.2', 'Reaction time at 30 dB (s)', 0.6, S(a30, 'Reaction time (s), median'), 0.05, 's', 'Scenarios'),
    ('6.2', 'Recovery time at 30 dB, median (s)', 2.65, S(a30, 'Recovery time (s), median'), 0.005, 's', 'Scenarios'),
    ('6.2', 'False activations in 30 runs at 30 dB', 1, S(a30, 'False activations (count)'), 0.01, '', 'Scenarios'),
    ('6.2', 'Ramp, median PDR without ASMA', 0.925, f'Ablation!C{ABR["ramp_30dB_noASMA"]}', 0.0005, '', 'Ablation'),
    ('6.2', 'Ramp, median PDR with ASMA', 0.989, f'Ablation!C{ABR["ramp_30dB_ASMA"]}', 0.0005, '', 'Ablation'),
    ('6.2', 'Burst, median PDR without ASMA', 0.932, f'Ablation!C{ABR["burst_30dB_noASMA"]}', 0.0005, '', 'Ablation'),
    ('6.2', 'Burst, median PDR with ASMA', 0.984, f'Ablation!C{ABR["burst_30dB_ASMA"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'Power boost only: median PDR', 0.980, f'Ablation!C{ABR["step_30dB_powerOnly"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'Both actions: median PDR', 0.975, f'Ablation!C{ABR["step_30dB_ASMA"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'Retries only: median PDR', 0.883, f'Ablation!C{ABR["step_30dB_retriesOnly"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'No ASMA: median PDR', 0.853, f'Ablation!C{ABR["step_30dB_noASMA"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'Retries only: packets after the deadline (6.8%)', 0.068, f'Ablation!D{ABR["step_30dB_retriesOnly"]}', 0.0005, '', 'Ablation'),
    ('6.3', 'Retries only: 99th-percentile latency (ms)', 110.8, f'Ablation!E{ABR["step_30dB_retriesOnly"]}', 0.05, 'ms', 'Ablation'),
    ('6.4', 'Energy at 30 dB without ASMA, median (mJ)', 3.59, S(o30, 'Energy per delivered packet during interference (mJ), median'), 0.005, 'mJ', 'Scenarios'),
    ('6.4', 'Energy at 30 dB with ASMA, median (mJ)', 3.29, S(a30, 'Energy per delivered packet during interference (mJ), median'), 0.005, 'mJ', 'Scenarios'),
    ('6.4', 'Seeds with lower energy with ASMA at 30 dB', 26, PAIR[(E30, 'Seeds lower with ASMA')], 0.01, '', 'Paired'),
    ('6.4', 'Energy at 34 dB without ASMA, median (mJ)', 10.1, S(nm(34, False), 'Energy per delivered packet during interference (mJ), median'), 0.05, 'mJ', 'Scenarios'),
    ('6.4', 'Energy at 34 dB with ASMA, median (mJ)', 3.8, S(nm(34, True), 'Energy per delivered packet during interference (mJ), median'), 0.05, 'mJ', 'Scenarios'),
    ('6.4', 'Energy overhead of ASMA at 20 dB (below 2%)', 0.02,
     f'{S(nm(20, True), "Energy per delivered packet during interference (mJ), median")}/'
     f'{S(nm(20, False), "Energy per delivered packet during interference (mJ), median")}-1', '<', '', 'Scenarios'),
    ('6.4', 'Energy overhead of ASMA at 24 dB (below 2%)', 0.02,
     f'{S(nm(24, True), "Energy per delivered packet during interference (mJ), median")}/'
     f'{S(nm(24, False), "Energy per delivered packet during interference (mJ), median")}-1', '<', '', 'Scenarios'),
    ('6.4', 'Failed frames per hour without interference (about 72)', 72, 'Nominal_residual!B13', 0.5, '/h', 'Nominal_residual'),
    ('6.4', 'Residual errors per hour, 16-bit frame check only', 1.1e-3, 'Nominal_residual!B12', 0.05e-3, '/h', 'Nominal_residual'),
    ('6.4', 'Residual errors per hour with a 32-bit safety check', 2.6e-13, 'Nominal_residual!B14', 0.05e-13, '/h', 'Nominal_residual'),
    ('6.4', 'Same, worst case simulated (34 dB without ASMA)', 1.4e-10, 'Nominal_residual!B16', 0.05e-10, '/h', 'Nominal_residual'),
]
for i, (sec, txt, val, ref, tol, unit, where) in enumerate(claims):
    r = 5 + i
    put(ws, r, 1, i + 1); put(ws, r, 2, sec); c = put(ws, r, 3, txt); c.alignment = Alignment(wrap_text=True)
    fmt = '0.00E+00' if abs(val) and abs(val) < 1e-3 else ('#,##0' if val >= 1000 else None)
    put(ws, r, 4, val, BLUE, fmt)
    put(ws, r, 5, '=' + ref, BLACK, fmt or ('0.000' if abs(val) < 10 else '0.0'))
    put(ws, r, 6, tol, BLUE, '0.0E+00' if isinstance(tol, float) and tol < 1e-3 else None)
    if tol == '<':
        g = f'=IF(E{r}<D{r},"✓","✗")'
    elif tol == '>':
        g = f'=IF(E{r}>D{r},"✓","✗")'
    else:
        g = f'=IF(ABS(E{r}-D{r})<=F{r}+1E-12*ABS(D{r}),"✓","✗")'
    put(ws, r, 7, g, BOLD).alignment = Alignment(horizontal='center')
    put(ws, r, 8, unit); put(ws, r, 9, where)
end = 4 + len(claims)
put(ws, end + 2, 3, 'Claims that match the data', BOLD)
put(ws, end + 2, 5, f'=COUNTIF(G5:G{end},"✓")', BOLD, '0'); put(ws, end + 2, 6, f'of {len(claims)}')
put(ws, end + 4, 3, 'Not covered here: Fig. 4 shows one run (seed 27); its time series is not stored in the results files. '
                    'Its scenario values are rows of seed 27 on sheet Per_seed.', NOTE)
ws.freeze_panes = 'A5'

# ------------------------------------------------------------------ Guide sheet
gs = wb.create_sheet('Guide', 1)
lines = [
    ('How to use this workbook', TITLE),
    ('1. Start on sheet Claims. Each row is a number printed in the manuscript, the same number recomputed here, '
     'and ✓ when they agree.', BLACK),
    ('2. To check a value, click its computed cell (column E) and follow the formula to the sheet named in column I.', BLACK),
    ('3. Blue text = raw data copied from the result files. Black text = Excel formulas. Nothing is typed in by hand.', BLACK),
    ('', BLACK),
    ('Sheets', BOLD),
    ('Per_seed: every Simulink run (22 scenarios × 30 seeds), from results/per_seed_metrics.csv', BLACK),
    ('Scenarios: medians, quartiles, means and counts per scenario (formulas over Per_seed)', BLACK),
    ('Table4: manuscript Table 4 recomputed, side by side with the printed values', BLACK),
    ('Paired: the with/without ASMA difference for each seed, mean, CI and sign test', BLACK),
    ('Ablation: power only, retries only, both; ramp and burst interference', BLACK),
    ('Nominal_residual: the route without interference and the residual-error bound', BLACK),
    ('ANN_validation: Fig. 2a-b data (results/ann_validation.csv), error and tolerance', BLACK),
    ('Design_grid: the 8,052 designs the optimizer evaluated (Fig. 2c, ann/design_grid.csv)', BLACK),
    ('Table3_accuracy: Table 3 (ann/accuracy.csv) and the R² ceiling (ann/r2_ceiling.csv)', BLACK),
    ('Fig5c_SDR_curves: the data behind Fig. 5c (results/experiments.mat)', BLACK),
    ('', BLACK),
    ('Scenario names', BOLD),
    ('step_30dB_ASMA = interference of 30 dB on hops 5-7 from 30 s to 70 s, ASMA on. noASMA = ASMA off. '
     'powerOnly / retriesOnly = ASMA with only one action. ramp / burst = other interference shapes. '
     'Design "v1" in the ANN files = the baseline design in the manuscript.', BLACK),
]
for i, (t, f) in enumerate(lines):
    c = gs.cell(row=1 + i, column=1, value=t); c.font = f; c.alignment = Alignment(wrap_text=True)
gs.column_dimensions['A'].width = 120
for w in wb.worksheets:
    w.sheet_view.zoomScale = 100
wb.save(OUT)
print('saved', OUT, 'claims', len(claims))
