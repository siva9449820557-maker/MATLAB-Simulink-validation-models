"""Excel calculator for the ANN: type a route design, read the predicted QoS
and the interference tolerance. All predictions are live formulas."""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter as L

M = json.load(open('ann_model.json'))
INP = M['inputs']
OUTS = list(M['outputs'])
NICE = {'K': 'Number of hops K', 'MeanD_m': 'Mean hop distance (m)', 'StdD_m': 'Std dev of hop distance (m)',
        'Tx_dBm': 'Transmit power (dBm)', 'Pkt_bits': 'Payload (bits)', 'Retries': 'Maximum retries per hop',
        'Noise_dB': 'Interference on middle 3 hops (dB)'}
RANGE = {'K': (2, 12), 'MeanD_m': (10, 60), 'StdD_m': (0, 15), 'Tx_dBm': (-10, 0),
         'Pkt_bits': (200, 900), 'Retries': (0, 5), 'Noise_dB': (0, 40)}
EXAMPLE = {'K': 11, 'MeanD_m': 26.64, 'StdD_m': 0, 'Tx_dBm': 0, 'Pkt_bits': 900, 'Retries': 2, 'Noise_dB': 0}
ONICE = {'PDR': ('On-time packet delivery ratio (PDR)', '0.000'),
         'SDR': ('Safety detection ratio (SDR) at PST 2 s', '0.000'),
         'NWLat_ms': ('Mean end-to-end latency (ms)', '0.0'),
         'LatP99_ms': ('99th percentile latency (ms)', '0.0'),
         'Energy_mJ': ('Energy per delivered packet (mJ)', '0.00'),
         'MinPST_s': ('Shortest supportable process safety time (s)', '0.00')}

F = 'Arial'
f_norm = Font(name=F, size=10)
f_bold = Font(name=F, size=10, bold=True)
f_title = Font(name=F, size=13, bold=True)
f_in = Font(name=F, size=10, color='0000FF')
f_link = Font(name=F, size=10, color='008000')
fill_in = PatternFill('solid', start_color='FFFF00')
fill_hdr = PatternFill('solid', start_color='DDE7F3')
thin = Border(bottom=Side(style='thin', color='999999'))

wb = Workbook()
calc = wb.active
calc.title = 'Calculator'
wt = wb.create_sheet('Weights')
tol = wb.create_sheet('Tolerance')
rd = wb.create_sheet('Read me')

for ws in (calc, wt, tol, rd):
    ws.sheet_view.showGridLines = False

# ------------------------------------------------------------------ Weights
wt['A1'] = 'ANN weights (trained in Python / scikit-learn on 30,000 simulated route designs)'
wt['A1'].font = f_title
wt['A3'] = 'Input scaling: z = (x - mean) / std'
wt['A3'].font = f_bold
for j, n in enumerate(INP):
    c = wt.cell(4, 2 + j, n); c.font = f_bold; c.fill = fill_hdr
    wt.cell(5, 2 + j, M['x_mean'][j]).font = f_norm
    wt.cell(6, 2 + j, M['x_std'][j]).font = f_norm
wt['A5'] = 'mean'; wt['A6'] = 'std'
wt['A5'].font = wt['A6'].font = f_bold
SCALE_MEAN = {n: f"Weights!${L(2 + j)}$5" for j, n in enumerate(INP)}
SCALE_STD = {n: f"Weights!${L(2 + j)}$6" for j, n in enumerate(INP)}

blocks = {}
r = 8
for o in OUTS:
    w = M['outputs'][o]
    H = w['hidden']
    wt.cell(r, 1, f"Output: {o}   (transform: {w['transform']}, {H} tanh hidden units)").font = f_bold
    r += 1
    hdr = ['Hidden unit'] + [f'W1 {n}' for n in INP] + ['b1', 'W2', 'Design term c (calculated)']
    for j, h in enumerate(hdr):
        c = wt.cell(r, 1 + j, h); c.font = f_bold; c.fill = fill_hdr
        c.alignment = Alignment(wrap_text=True)
    r += 1
    first = r
    for k in range(H):
        wt.cell(r, 1, k + 1).font = f_norm
        for j in range(len(INP)):
            wt.cell(r, 2 + j, w['W1'][k][j]).font = f_norm
        wt.cell(r, 9, w['b1'][k]).font = f_norm
        wt.cell(r, 10, w['W2'][k]).font = f_norm
        # c_k = b1 + sum over the six design inputs of W1 * z (interference handled separately)
        wt.cell(r, 11, f"=I{r}+SUMPRODUCT(B{r}:G{r},Calculator!$E$6:$J$6)").font = f_link
        r += 1
    last = r - 1
    wt.cell(r, 1, 'b2').font = f_bold; wt.cell(r, 2, w['b2']).font = f_norm
    wt.cell(r, 3, 'y mean').font = f_bold; wt.cell(r, 4, w['y_mean']).font = f_norm
    wt.cell(r, 5, 'y std').font = f_bold; wt.cell(r, 6, w['y_std']).font = f_norm
    blocks[o] = dict(c=f"Weights!$K${first}:$K${last}", w7=f"Weights!$H${first}:$H${last}",
                     w2=f"Weights!$J${first}:$J${last}", b2=f"Weights!$B${r}",
                     ym=f"Weights!$D${r}", ys=f"Weights!$F${r}", tr=w['transform'])
    r += 2
# radio constants used for the minimum energy E_min (row 100 onwards)
consts = [('Radio constants for E_min (CC2420-class, 3 V)', None, None),
          ('Transmit current, base term (A)', 8.5e-3, 'Fit to CC2420 datasheet: I = 8.5 + 8.9 x 10^(P/20) mA'),
          ('Transmit current, amplifier term (A)', 8.9e-3, 'Same fit; within 0.5 mA of the datasheet from -25 to 0 dBm'),
          ('Bit rate (bit/s)', 250e3, 'IEEE 802.15.4, 2.4 GHz O-QPSK'),
          ('MAC + PHY overhead per frame (bits)', 136, '11 bytes MAC header/FCS + 6 bytes PHY'),
          ('Receive power draw (W)', 3 * 18.8e-3, '18.8 mA at 3 V, listening for the ACK'),
          ('Turnaround + ACK wait per attempt (s)', 12 * 16e-6 + 54 * 16e-6, '12 + 54 symbols of 16 us'),
          ('Supply voltage (V)', 3.0, 'Assumed')]
for i, (lab, val, note) in enumerate(consts):
    wt.cell(101 + i, 1, lab).font = f_bold if val is None else f_norm
    if val is not None:
        c = wt.cell(101 + i, 2, val); c.font = f_in
        wt.cell(101 + i, 3, note).font = Font(name=F, size=9, italic=True)
wt.column_dimensions['A'].width = 12
for j in range(2, 12):
    wt.column_dimensions[L(j)].width = 13


def out_formula(o, zR):
    """Prediction for output o with the interference z-value in cell/expression zR."""
    b = blocks[o]
    core = f"{b['ym']}+{b['ys']}*({b['b2']}+SUMPRODUCT({b['w2']},TANH({b['c']}+{b['w7']}*{zR})))"
    if b['tr'] == 'log10cap':
        core = f"10^({core})"
    elif b['tr'] == 'log10ratio':
        core = f"Calculator!$B$14*10^({core})"
    if o in ('PDR', 'SDR'):
        core = f"MAX(0,MIN(1,{core}))"
    return '=' + core


# --------------------------------------------------------------- Calculator
calc['A1'] = 'IWSN route design calculator (ANN surrogate)'
calc['A1'].font = f_title
calc['A2'] = 'Edit the yellow cells (blue text). Everything else is calculated.'
calc['A2'].font = Font(name=F, size=10, italic=True)
calc['A4'] = 'Inputs'; calc['A4'].font = f_bold
heads = ['Input', 'Value', 'Training range', 'In range?']
for j, h in enumerate(heads):
    c = calc.cell(5, 1 + j, h); c.font = f_bold; c.fill = fill_hdr
# z-values for the six design inputs go in E6:J6, interference z in K6
row_of = {}
for i, n in enumerate(INP):
    rr = 6 + i
    row_of[n] = rr
    calc.cell(rr, 1, NICE[n]).font = f_norm
    c = calc.cell(rr, 2, EXAMPLE[n]); c.font = f_in; c.fill = fill_in
    calc.cell(rr, 3, f"{RANGE[n][0]} to {RANGE[n][1]}").font = f_norm
    calc.cell(rr, 4, f'=IF(AND(B{rr}>={RANGE[n][0]},B{rr}<={RANGE[n][1]}),"yes","OUTSIDE")').font = f_norm
calc['B6'].comment = Comment('Number of hops between sensor and base station (integer).', 'Model')
calc[f"B{row_of['StdD_m']}"].comment = Comment('Must not exceed half the mean hop distance.', 'Model')
calc[f"B{row_of['Retries']}"].comment = Comment('IEEE 802.15.4 macMaxFrameRetries (integer).', 'Model')
calc['F14'] = 'Scaled inputs z (used by the formulas; do not edit)'
calc['F14'].font = Font(name=F, size=9, italic=True, color='808080')
for j, n in enumerate(INP):
    calc.cell(15, 5 + j, n).font = Font(name=F, size=9, color='808080')
    c = calc.cell(16, 5 + j, f"=(B{row_of[n]}-{SCALE_MEAN[n]})/{SCALE_STD[n]}")
    c.font = Font(name=F, size=9, color='808080')
calc['B13'] = '=B6*B7'
calc['A13'] = 'Route length S-D (m)'
calc['A13'].font = f_norm; calc['B13'].font = f_norm; calc['B13'].number_format = '0.0'
# minimum energy per delivered packet (no retransmissions), from the radio model constants
calc['A14'] = 'Minimum energy per packet, no retransmissions (mJ)'
calc['B14'] = ('=1000*B6*(Weights!$B$108*(Weights!$B$102+Weights!$B$103*10^(B9/20))*(B10+Weights!$B$105)'
               '/Weights!$B$104+Weights!$B$106*Weights!$B$107)')
calc['A14'].font = f_norm; calc['B14'].font = f_norm; calc['B14'].number_format = '0.000'

calc['A18'] = 'Predicted outputs (average over shadowing, fading and hop order)'
calc['A18'].font = f_bold
for j, h in enumerate(['Output', 'Prediction', 'Target', 'Meets target?']):
    c = calc.cell(19, 1 + j, h); c.font = f_bold; c.fill = fill_hdr
targets = {'PDR': ('>=', 0.90), 'SDR': ('>=', 0.90), 'LatP99_ms': ('<=', 100.0), 'MinPST_s': ('<=', 2.0)}
z_noise = 'Calculator!$K$16'
for i, o in enumerate(OUTS):
    rr = 20 + i
    calc.cell(rr, 1, ONICE[o][0]).font = f_norm
    c = calc.cell(rr, 2, out_formula(o, z_noise)); c.font = f_bold; c.number_format = ONICE[o][1]
    if o in targets:
        op, v = targets[o]
        t = calc.cell(rr, 3, v); t.font = f_in; t.fill = fill_in; t.number_format = ONICE[o][1]
        calc.cell(rr, 4, f'=IF(B{rr}{op}C{rr},"yes","NO")').font = f_norm
calc['A27'] = 'Interference tolerance (dB): largest level at which all four targets still hold'
calc['A27'].font = f_bold
calc['B27'] = '=Tolerance!$B$4'
calc['B27'].font = Font(name=F, size=11, bold=True)
calc['B27'].number_format = '0.0'
calc['A29'] = ('Note: z-values in row 16 link the six design inputs (E16:J16) and interference (K16). '
               'The Weights sheet uses E16:J16.')
calc['A29'].font = Font(name=F, size=9, italic=True, color='808080')
calc.column_dimensions['A'].width = 52
calc.column_dimensions['B'].width = 14
calc.column_dimensions['C'].width = 15
calc.column_dimensions['D'].width = 14
for j in range(5, 12):
    calc.column_dimensions[L(j)].width = 11

# fix the Weights c-term reference to the z row (row 16)
for row in wt.iter_rows():
    for c in row:
        if isinstance(c.value, str) and 'Calculator!$E$6:$J$6' in c.value:
            c.value = c.value.replace('Calculator!$E$6:$J$6', 'Calculator!$E$16:$J$16')

# ---------------------------------------------------------------- Tolerance
tol['A1'] = 'Interference sweep for the design on the Calculator sheet'
tol['A1'].font = f_title
tol['A3'] = 'Targets: PDR and SDR at least the Calculator targets, 99th pct latency and shortest PST at most the targets.'
tol['A3'].font = Font(name=F, size=9, italic=True)
tol['A4'] = 'Tolerance (dB)'; tol['A4'].font = f_bold
hdr = ['Interference (dB)', 'z', 'PDR', 'SDR', '99th pct latency (ms)', 'Shortest PST (s)', 'All targets met?']
for j, h in enumerate(hdr):
    c = tol.cell(6, 1 + j, h); c.font = f_bold; c.fill = fill_hdr
first = 7
steps = [i * 0.5 for i in range(81)]
for i, R in enumerate(steps):
    rr = first + i
    tol.cell(rr, 1, R).font = f_norm
    tol.cell(rr, 2, f"=(A{rr}-{SCALE_MEAN['Noise_dB']})/{SCALE_STD['Noise_dB']}").font = f_norm
    for j, o in enumerate(['PDR', 'SDR', 'LatP99_ms', 'MinPST_s']):
        c = tol.cell(rr, 3 + j, out_formula(o, f'$B{rr}'))
        c.font = f_norm
        c.number_format = '0.000' if o in ('PDR', 'SDR') else '0.0'
    tol.cell(rr, 7, f"=AND(C{rr}>=Calculator!$C$20,D{rr}>=Calculator!$C$21,"
                    f"E{rr}<=Calculator!$C$23,F{rr}<=Calculator!$C$25)").font = f_norm
last = first + len(steps) - 1
rng_ok = f"$G${first}:$G${last}"
rng_R = f"$A${first}:$A${last}"
tol['B4'] = (f'=IF(G{first}=FALSE,-1,IFERROR(INDEX({rng_R},MATCH(FALSE,{rng_ok},0)-1),{steps[-1]}))')
tol['B4'].font = Font(name=F, size=11, bold=True)
tol['C4'] = '(-1 means the targets already fail without interference; 40 means they hold over the whole range)'
tol['C4'].font = Font(name=F, size=9, italic=True)
for j, wdt in enumerate([18, 10, 10, 10, 20, 16, 18]):
    tol.column_dimensions[L(1 + j)].width = wdt

# -------------------------------------------------------------------- Read me
lines = [
    ('IWSN route design calculator', f_title),
    ('', f_norm),
    ('What it does', f_bold),
    ('Predicts the end-to-end quality of service of a multi-hop IEEE 802.15.4 route from seven inputs, using the', f_norm),
    ('trained ANN (one tanh network per output). The Tolerance sheet sweeps interference from 0 to 40 dB and', f_norm),
    ('reports the largest level at which all safety targets still hold.', f_norm),
    ('', f_norm),
    ('How to use it', f_bold),
    ('1. On the Calculator sheet, edit the yellow cells (blue text): the seven inputs and the four targets.', f_norm),
    ('2. Read the predictions and the interference tolerance. Excel recalculates automatically.', f_norm),
    ('3. "OUTSIDE" next to an input means it is outside the training range: treat that prediction as unreliable.', f_norm),
    ('', f_norm),
    ('Example values', f_bold),
    ('The inputs are preset to the ANN optimum for a 293 m route: 11 hops of 26.64 m, uniform spacing, 0 dBm,', f_norm),
    ('900-bit payload, 2 retries.', f_norm),
    ('', f_norm),
    ('Model assumptions (same as the Simulink model)', f_bold),
    ('IEEE 802.15.4 O-QPSK at 2.4 GHz and 250 kbps; noise floor -101 dBm; dual-slope path loss 46+11log10(d) up to', f_norm),
    ('11 m and 30+26log10(d) beyond; 4 dB log-normal shadowing; Rician fading with K = 3 dB per attempt; CSMA/CA', f_norm),
    ('backoff with ACKs; 10 packets per second; 100 ms deadline; interference on the middle three hops;', f_norm),
    ('PST 2 s with 0.5 s actuation time. Predictions are averages over random shadowing and hop placement.', f_norm),
    ('', f_norm),
    ('Equation for every output', f_bold),
    ('z_j = (x_j - mean_j) / std_j;  h_k = tanh(b1_k + sum_j W1_kj z_j);  y = y_mean + y_std (b2 + sum_k W2_k h_k)', f_norm),
    ('Energy: E = E_min x 10^y, where E_min is the energy with no retransmissions (Calculator cell B14) and y is the', f_norm),
    ('ANN output, so the ANN learns only the retransmission overhead. Shortest PST: PST = 10^y. Both are typical', f_norm),
    ('(median-like) values. PDR and SDR are average values, limited to 0-1.', f_norm),
    ('All weights are on the Weights sheet.', f_norm),
]
for i, (t, f) in enumerate(lines):
    c = rd.cell(1 + i, 1, t); c.font = f
rd.column_dimensions['A'].width = 120

wb.move_sheet('Read me', offset=-3)
wb.active = 1
wb.save('IWSN_ANN_Calculator.xlsx')
print('saved')
