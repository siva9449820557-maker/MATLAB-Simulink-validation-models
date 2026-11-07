"""Figures for the ANN section."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optimize import predict, SD_M

plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Sans', 'axes.grid': True,
                     'grid.alpha': 0.3, 'axes.spines.top': False, 'axes.spines.right': False})
C_OPT, C_ORIG, C_LEAN = '#1f5fbf', '#c0392b', '#2e8b57'
df = pd.read_csv('dataset.csv')
P = json.load(open('holdout_predictions.json'))
acc = pd.read_csv('accuracy.csv')
opt = pd.read_csv('optimum_table.csv').iloc[0]

# 1. Parity plots on the held-out 25 %
labels = {'PDR': 'On-time PDR', 'SDR': 'SDR (PST 2 s)', 'NWLat_ms': 'Mean latency (ms)',
          'LatP99_ms': '99th pct latency (ms)', 'Energy_mJ': 'Energy per packet (mJ)',
          'MinPST_s': 'Shortest supportable PST (s)'}
fig, ax = plt.subplots(2, 3, figsize=(10, 6.4))
for a, (k, lab) in zip(ax.ravel(), labels.items()):
    t = np.array(P[k]['true'], float); y = np.array(P[k]['ann'], float)
    if k == 'MinPST_s':
        t = np.minimum(t, 60)
    a.hexbin(t, y, gridsize=45, bins='log', cmap='Blues', mincnt=1,
             xscale='log' if k in ('Energy_mJ', 'MinPST_s') else 'linear',
             yscale='log' if k in ('Energy_mJ', 'MinPST_s') else 'linear')
    lo, hi = np.nanmin(t[t > 0]), np.nanmax(t)
    a.plot([lo, hi], [lo, hi], 'k--', lw=0.8)
    r2 = acc[(acc.output == k) & acc.model.str.startswith('ANN')].R2.iloc[0]
    a.set_title(f'{lab}\nR$^2$ = {r2:.3f} (n = {len(t)})', fontsize=9)
    a.set_xlabel('Simulated'); a.set_ylabel('ANN predicted')
fig.suptitle('ANN accuracy on held-out designs (25 % of 30,000)', fontsize=10)
fig.tight_layout()
fig.savefig('fig_ann_parity.png', dpi=300)

# 2. Tolerance by hop count and retries (uniform spacing, 0 dBm, 293 m, 900 bits)
G = pd.read_csv('design_grid.csv')
H = G[(G.Tx_dBm == 0) & (G.StdD_m == 0)].pivot(index='K', columns='Retries', values='Tolerance_dB')
fig, a = plt.subplots(figsize=(5.6, 4.2))
im = a.imshow(H.values, cmap='viridis', aspect='auto', origin='lower')
a.set_xticks(range(H.shape[1])); a.set_xticklabels(H.columns)
a.set_yticks(range(H.shape[0])); a.set_yticklabels(H.index)
for i in range(H.shape[0]):
    for j in range(H.shape[1]):
        v = H.values[i, j]
        a.text(j, i, f'{v:.1f}', ha='center', va='center', fontsize=8,
               color='white' if v < H.values.mean() else 'black',
               fontweight='bold' if (H.index[i] == opt.K and H.columns[j] == opt.Retries) else 'normal')
a.set_xlabel('Maximum retries per hop'); a.set_ylabel('Number of hops K')
a.set_title('ANN-predicted interference tolerance (dB)\n293 m route, uniform spacing, 0 dBm, 900-bit payload', fontsize=9)
a.grid(False)
fig.colorbar(im, ax=a, label='dB')
fig.tight_layout()
fig.savefig('fig_tolerance_map.png', dpi=300)

# 3. Validation: ANN vs simulation across interference levels
V = pd.read_csv('validation_python.csv')
names = {
    'ANN optimum': ('K=11, uniform, 0 dBm, 2 retries', (11, 0.0, 0.0, 2), C_OPT),
    'Energy-lean alternative': ('ANN optimum (K=9, uniform, 0 dBm, 5 retries)', (9, 0.0, 0.0, 5), C_LEAN),
    'Original route (v1)': ('Original route (K=10, std 11.57 m, 0 dBm, 3 retries)', (10, 11.57, 0.0, 3), C_ORIG),
}
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
Rd = np.linspace(0, 32, 161)
for lab, (vname, (K, std, tx, rt), col) in names.items():
    X = np.column_stack([np.full_like(Rd, K), np.full_like(Rd, SD_M / K), np.full_like(Rd, std),
                         np.full_like(Rd, tx), np.full_like(Rd, 900), np.full_like(Rd, rt), Rd])
    for a, k in zip(ax, ['PDR', 'LatP99_ms']):
        d = V[(V.design == vname) & (V.output == k)].sort_values('Noise_dB')
        a.plot(Rd, predict(k, X), '-', color=col, lw=1.4, label=f'{lab}: ANN')
        a.errorbar(d.Noise_dB, d.sim_mean, yerr=d.sim_ci95, fmt='o', ms=3.5, color=col, capsize=2,
                   label=f'{lab}: simulation (300 seeds)')
ax[0].axhline(0.9, color='k', ls='--', lw=0.8)
ax[0].set_ylabel('On-time PDR'); ax[0].set_ylim(0.3, 1.02)
ax[1].axhline(100, color='k', ls='--', lw=0.8)
ax[1].set_ylabel('99th percentile latency (ms)')
for a in ax:
    a.set_xlabel('Interference on middle three hops (dB)')
ax[0].legend(fontsize=7, loc='lower left')
fig.tight_layout()
fig.savefig('fig_ann_validation.png', dpi=300)

# 4. Prediction profiler at the optimum, interference 24 dB
base = dict(K=opt.K, MeanD_m=opt.MeanD_m, StdD_m=0.0, Tx_dBm=0.0, Pkt_bits=900, Retries=opt.Retries, Noise_dB=24.0)
ranges = {'K': (2, 12), 'MeanD_m': (10, 60), 'StdD_m': (0, 15), 'Tx_dBm': (-10, 0),
          'Pkt_bits': (200, 900), 'Retries': (0, 5), 'Noise_dB': (0, 40)}
xl = {'K': 'Hops K', 'MeanD_m': 'Mean hop (m)', 'StdD_m': 'Hop std (m)', 'Tx_dBm': 'Tx power (dBm)',
      'Pkt_bits': 'Payload (bits)', 'Retries': 'Max retries', 'Noise_dB': 'Interference (dB)'}
outs = ['PDR', 'SDR', 'NWLat_ms', 'Energy_mJ', 'MinPST_s']
order = list(ranges)
fig, ax = plt.subplots(len(outs), len(order), figsize=(13, 8.5), sharey='row')
for j, var in enumerate(order):
    xs = np.linspace(*ranges[var], 60)
    X = np.tile([base[v] for v in order], (len(xs), 1)).astype(float)
    X[:, j] = xs
    for i, o in enumerate(outs):
        a = ax[i, j]
        a.plot(xs, predict(o, X), color=C_OPT, lw=1.4)
        a.axvline(base[var], color='grey', ls=':', lw=0.8)
        if i == len(outs) - 1:
            a.set_xlabel(xl[var])
        if j == 0:
            a.set_ylabel(labels[o].replace(' (', '\n('))
        if o in ('Energy_mJ', 'MinPST_s'):
            a.set_yscale('log')
fig.suptitle('ANN prediction profiles around the optimum (dotted line) at 24 dB interference', fontsize=10)
fig.tight_layout()
fig.savefig('fig_ann_profiler.png', dpi=300)

# 5. Trade-off: tolerance vs nominal energy (best design for each energy level)
PA = pd.read_csv('pareto.csv')
fig, a = plt.subplots(figsize=(5.6, 4))
a.scatter(G.Energy_mJ_nominal, G.Tolerance_dB, s=3, color='#bbbbbb', label='All 8,052 designs')
a.step(PA.Energy_mJ_nominal, PA.Tolerance_dB, where='post', color=C_OPT, lw=1.5, label='Best tolerance for the energy')
a.plot(opt.Energy_mJ_nominal, opt.Tolerance_dB, '*', ms=12, color=C_OPT, label='ANN optimum')
o1 = pd.read_csv('optimum_table.csv').iloc[2]
a.plot(o1.Energy_mJ_nominal, o1.Tolerance_dB, 's', ms=7, color=C_ORIG, label='Original route (v1)')
a.set_ylim(0, 28)
a.set_xlabel('Energy per delivered packet, no interference (mJ)')
a.set_ylabel('Interference tolerance (dB)')
a.legend(fontsize=7, loc='lower right')
fig.tight_layout()
fig.savefig('fig_tradeoff.png', dpi=300)
print('figures written')
