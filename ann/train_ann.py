"""Train the ANN surrogate (one small tanh network per output) and baselines.

Writes: ann_model.json (all weights and scalings), accuracy.csv, and
holdout predictions for parity plots.
"""
import json
import math
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, KFold
from sklearn.neural_network import MLPRegressor
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import sim_core as sc

INPUTS = ['K', 'MeanD_m', 'StdD_m', 'Tx_dBm', 'Pkt_bits', 'Retries', 'Noise_dB']
PST_CAP = 60.0
# output name -> (column, transform, inverse, rows filter)
OUTPUTS = {
    'PDR':       ('PDR',       'none'),
    'SDR':       ('SDR',       'none'),
    'NWLat_ms':  ('NWLat_ms',  'none'),
    'LatP99_ms': ('LatP99_ms', 'none'),
    'Energy_mJ': ('Energy_mJ', 'log10ratio'),   # ANN learns log10(E / E_min)
    'MinPST_s':  ('MinPST_s',  'log10cap'),
}
LOG_SCALE_METRIC = {'Energy_mJ', 'MinPST_s'}      # R2 reported on log scale for heavy-tailed outputs
P_CLIP = 0.002
NEEDS_DELIVERY = {'NWLat_ms', 'LatP99_ms', 'Energy_mJ'}


def e_min_mJ(X):
    """Energy per delivered packet with no retransmissions (exact, from the radio model)."""
    X = np.atleast_2d(X)
    K, tx, pkt = X[:, 0], X[:, 3], X[:, 4]
    ptx = sc.V_SUPPLY * (sc.I_TX_BASE + sc.I_TX_PA * 10 ** (tx / 20))
    frame = (pkt + sc.MAC_OVH + sc.PHY_OVH) / sc.BIT_RATE
    return 1e3 * K * (ptx * frame + sc.P_RX * (sc.TURN + sc.ACK_WAIT))


def fwd(y, tr, X):
    if tr == 'log10ratio':
        return np.log10(y / e_min_mJ(X))
    if tr == 'log10cap':
        return np.log10(np.minimum(y, PST_CAP))
    if tr == 'logit':
        p = np.clip(y, P_CLIP, 1 - P_CLIP)
        return np.log(p / (1 - p))
    return y


def inv(z, tr, X):
    if tr == 'log10ratio':
        return e_min_mJ(X) * 10 ** z
    if tr == 'log10cap':
        return 10 ** z
    if tr == 'logit':
        return 1 / (1 + np.exp(-z))
    return z


def closed_form_pdr(r):
    """Baseline: mean-SNR AWGN product model with retries (no fading, shadowing or deadline)."""
    d = sc.hop_distances(int(r.K), r.MeanD_m, r.StdD_m)
    zone = sc.interference_hops(int(r.K))
    p = 1.0
    for i, di in enumerate(d):
        snr = r.Tx_dBm - sc.path_loss(di) - sc.NOISE_FLOOR - (r.Noise_dB if (i + 1) in zone else 0)
        per = 1 - math.exp((r.Pkt_bits + sc.MAC_OVH) * sc.log1m_ber(snr))
        p *= 1 - per ** (int(r.Retries) + 1)
    return p


if __name__ == '__main__':
    df = pd.read_csv('dataset.csv')
    print('max FPDR in dataset:', df.FPDR.max())
    tr_idx, te_idx = train_test_split(np.arange(len(df)), test_size=0.25, random_state=7)
    X = df[INPUTS].to_numpy(float)
    xm, xs = X[tr_idx].mean(0), X[tr_idx].std(0)
    Xs = (X - xm) / xs

    model = {'inputs': INPUTS, 'x_mean': xm.tolist(), 'x_std': xs.tolist(),
             'pst_cap_s': PST_CAP, 'outputs': {}}
    acc_rows = []
    preds = {'row': te_idx.tolist()}
    for name, (colname, tr) in OUTPUTS.items():
        y_all = df[colname].to_numpy(float)
        ok = np.isfinite(y_all) | (tr == 'log10cap')
        if name in NEEDS_DELIVERY:
            ok &= df.Delivered.to_numpy() >= 0.05
        tri = tr_idx[ok[tr_idx]]
        tei = te_idx[ok[te_idx]]
        with np.errstate(all='ignore'):
            z = fwd(y_all, tr, X)
        zm, zs = z[tri].mean(), z[tri].std()
        zt = (z - zm) / zs

        # choose hidden size by 3-fold CV on the training set
        best = None
        for H in (4, 6, 8, 10):
            errs = []
            for a, b in KFold(3, shuffle=True, random_state=1).split(tri):
                m = MLPRegressor(hidden_layer_sizes=(H,), activation='tanh', solver='lbfgs', alpha=1e-3,
                                 max_iter=3000, random_state=0)
                m.fit(Xs[tri[a]], zt[tri[a]])
                errs.append(np.mean((m.predict(Xs[tri[b]]) - zt[tri[b]]) ** 2))
            if best is None or np.mean(errs) < best[1] * 0.98:
                best = (H, np.mean(errs))
        H = best[0]
        mlp = MLPRegressor(hidden_layer_sizes=(H,), activation='tanh', solver='lbfgs', alpha=1e-3,
                           max_iter=5000, random_state=0).fit(Xs[tri], zt[tri])
        lin = LinearRegression().fit(Xs[tri], zt[tri])
        gbr = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.08,
                                            random_state=0).fit(X[tri], zt[tri])

        def evaluate(label, zhat):
            yhat = inv(zm + zs * zhat, tr, X[tei])
            ytrue = y_all[tei]
            if tr == 'log10cap':
                ytrue = np.minimum(ytrue, PST_CAP)
            if name in ('PDR', 'SDR'):
                yhat = np.clip(yhat, 0, 1)
            if name in LOG_SCALE_METRIC:
                r2 = r2_score(np.log10(ytrue), np.log10(yhat))
            else:
                r2 = r2_score(ytrue, yhat)
            acc_rows.append(dict(output=name, model=label, n_test=len(tei),
                                 R2=r2,
                                 RMSE=math.sqrt(mean_squared_error(ytrue, yhat)),
                                 MAE=mean_absolute_error(ytrue, yhat)))
            return yhat

        y_ann = evaluate(f'ANN (tanh, {H} hidden)', mlp.predict(Xs[tei]))
        evaluate('Linear regression', lin.predict(Xs[tei]))
        evaluate('Gradient boosting', gbr.predict(X[tei]))
        if name == 'PDR':
            cf = np.array([closed_form_pdr(r) for r in df.iloc[tei].itertuples()])
            acc_rows.append(dict(output=name, model='Closed-form AWGN product', n_test=len(tei),
                                 R2=r2_score(y_all[tei], cf),
                                 RMSE=math.sqrt(mean_squared_error(y_all[tei], cf)),
                                 MAE=mean_absolute_error(y_all[tei], cf)))
        preds[name] = {'row': tei.tolist(), 'true': y_all[tei].tolist(), 'ann': y_ann.tolist()}
        model['outputs'][name] = {
            'transform': tr, 'hidden': H,
            'W1': mlp.coefs_[0].T.tolist(),        # H x 7
            'b1': mlp.intercepts_[0].tolist(),     # H
            'W2': mlp.coefs_[1][:, 0].tolist(),    # H
            'b2': float(mlp.intercepts_[1][0]),
            'y_mean': float(zm), 'y_std': float(zs),
            'trained_rows': int(len(tri)),
        }
        print(f'{name}: hidden {H}, CV mse {best[1]:.4f}')

    acc = pd.DataFrame(acc_rows)
    acc.to_csv('accuracy.csv', index=False)
    print(acc.round(4).to_string(index=False))
    json.dump(model, open('ann_model.json', 'w'), indent=1)
    json.dump(preds, open('holdout_predictions.json', 'w'))
