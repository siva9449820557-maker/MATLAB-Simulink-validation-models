"""Design optimisation with the trained ANN.

Route length fixed at 293 m (plant layout) and payload fixed at 900 bits
(application data). Decision variables: hops K, spacing spread, transmit
power, maximum retries. Objective: maximise the interference level the route
tolerates while meeting all targets; ties broken by lower energy.
"""
import json
import numpy as np
import pandas as pd
from train_ann import e_min_mJ

M = json.load(open('ann_model.json'))
XM, XS = np.array(M['x_mean']), np.array(M['x_std'])
SD_M = 293.0
PKT = 900
TARGET = dict(PDR=0.90, SDR=0.90, PST_s=2.0, LatP99_ms=100.0)
R_GRID = np.round(np.arange(0, 40.01, 0.1), 2)


def predict(name, X):
    """ANN equations exactly as exported (also used by the Excel calculator)."""
    o = M['outputs'][name]
    X = np.atleast_2d(np.asarray(X, float))
    Z = (X - XM) / XS
    h = np.tanh(Z @ np.array(o['W1']).T + np.array(o['b1']))
    z = h @ np.array(o['W2']) + o['b2']
    y = o['y_mean'] + o['y_std'] * z
    if o['transform'] == 'log10cap':
        y = 10 ** y
    elif o['transform'] == 'log10ratio':
        y = e_min_mJ(X) * 10 ** y
    elif o['transform'] == 'logit':
        y = 1 / (1 + np.exp(-y))
    if name in ('PDR', 'SDR'):
        y = np.clip(y, 0, 1)
    return y


def all_outputs(X):
    return {n: predict(n, X) for n in M['outputs']}


def tolerance(K, std, tx, rt):
    """Largest interference level (dB) up to which every target holds."""
    mean_d = SD_M / K
    X = np.column_stack([np.full(R_GRID.size, K), np.full(R_GRID.size, mean_d), np.full(R_GRID.size, std),
                         np.full(R_GRID.size, tx), np.full(R_GRID.size, PKT), np.full(R_GRID.size, rt), R_GRID])
    out = all_outputs(X)
    ok = ((out['PDR'] >= TARGET['PDR']) & (out['SDR'] >= TARGET['SDR'])
          & (out['MinPST_s'] <= TARGET['PST_s']) & (out['LatP99_ms'] <= TARGET['LatP99_ms']))
    if not ok[0]:
        return -1.0, out
    bad = np.where(~ok)[0]
    rstar = R_GRID[bad[0] - 1] if bad.size else R_GRID[-1]
    return float(rstar), out


def design_row(K, std, tx, rt, label):
    rstar, out = tolerance(K, std, tx, rt)
    nom = {k: float(v[0]) for k, v in out.items()}
    return dict(design=label, K=K, MeanD_m=round(SD_M / K, 2), StdD_m=std, Tx_dBm=tx, Pkt_bits=PKT,
                Retries=rt, Tolerance_dB=rstar, **{f'{k}_nominal': v for k, v in nom.items()})


if __name__ == '__main__':
    rows = []
    for K in range(5, 13):
        mean_d = SD_M / K
        for std in np.arange(0, min(15.0, 0.5 * mean_d) + 1e-9, 1.0):
            for tx in np.arange(-10, 0.01, 1.0):
                for rt in range(0, 6):
                    rstar, out = tolerance(K, std, tx, rt)
                    rows.append(dict(K=K, MeanD_m=mean_d, StdD_m=std, Tx_dBm=tx, Retries=rt,
                                     Tolerance_dB=rstar, Energy_mJ_nominal=float(out['Energy_mJ'][0]),
                                     LatP99_ms_nominal=float(out['LatP99_ms'][0])))
    G = pd.DataFrame(rows)
    G.to_csv('design_grid.csv', index=False)
    best_tol = G.Tolerance_dB.max()
    near = G[G.Tolerance_dB >= best_tol - 1e-9]          # maximum tolerance; energy breaks exact ties
    opt = near.sort_values('Energy_mJ_nominal').iloc[0]
    lean = G[G.Tolerance_dB >= best_tol - 0.5].sort_values('Energy_mJ_nominal').iloc[0]
    print('designs evaluated:', len(G), ' best tolerance:', best_tol)
    print('optimum (maximum tolerance):')
    print(opt.to_string())

    table = pd.DataFrame([
        design_row(int(opt.K), float(opt.StdD_m), float(opt.Tx_dBm), int(opt.Retries), 'ANN optimum'),
        design_row(int(lean.K), float(lean.StdD_m), float(lean.Tx_dBm), int(lean.Retries),
                   'Energy-lean alternative (within 0.5 dB)'),
        design_row(10, 11.57, 0.0, 3, 'Original route (Table 4 of v1)'),
        design_row(10, 0.0, 0.0, 3, 'Original route, uniform spacing'),
    ])
    table.to_csv('optimum_table.csv', index=False)
    print(table.T.to_string())

    # Pareto front: best tolerance achievable for each energy level (transmit power trade-off)
    pareto = (G.sort_values('Energy_mJ_nominal')
                .assign(best=lambda d: d.Tolerance_dB.cummax())
                .query('Tolerance_dB == best')
                .drop_duplicates('Tolerance_dB'))
    pareto.to_csv('pareto.csv', index=False)
    print('pareto points:', len(pareto))
