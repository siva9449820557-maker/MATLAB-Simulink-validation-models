import numpy as np, pandas as pd, json
from multiprocessing import Pool
from sim_core import simulate
from optimize import predict
DES = {'ANN optimum (K=9, uniform, 0 dBm, 5 retries)': (9, 0.0, 0.0, 5),  # energy-lean alternative
       'Original route (K=10, std 11.57 m, 0 dBm, 3 retries)': (10, 11.57, 0.0, 3),
       'K=11, uniform, 0 dBm, 2 retries': (11, 0.0, 0.0, 2)}
RS = [0, 20, 22, 24, 25, 26, 27, 28, 30, 32]
NSEED = 300
def job(a):
    K, std, tx, rt, R, s = a
    return simulate(K, 293.0 / K, std, tx, 900, rt, R, seed=5_000_000 + s, duration=60)
rows = []
with Pool(2) as p:
    for lab, (K, std, tx, rt) in DES.items():
        for R in RS:
            res = p.map(job, [(K, std, tx, rt, R, s) for s in range(NSEED)], chunksize=25)
            X = np.array([[K, 293.0 / K, std, tx, 900, rt, R]])
            for k in ['PDR', 'SDR', 'NWLat_ms', 'LatP99_ms', 'Energy_mJ', 'MinPST_s']:
                v = np.array([r[k] for r in res], float)
                if k == 'MinPST_s':
                    v = np.minimum(v, 60)
                v = v[np.isfinite(v)]
                rows.append(dict(design=lab, Noise_dB=R, output=k, sim_mean=v.mean(),
                                 sim_ci95=1.96 * v.std() / np.sqrt(len(v)), sim_median=np.median(v),
                                 ann=float(predict(k, X)[0])))
D = pd.DataFrame(rows)
D.to_csv('validation_python.csv', index=False)
pv = D[D.output == 'PDR'].pivot(index='Noise_dB', columns='design', values=['sim_mean', 'ann'])
print(pv.round(3).to_string())
for lab in DES:
    d = D[(D.design == lab) & (D.output == 'PDR')].sort_values('Noise_dB')
    x, y = d.Noise_dB.to_numpy(), d.sim_mean.to_numpy()
    i = np.where(y < 0.9)[0][0]
    tol = x[i-1] + (y[i-1] - 0.9) / (y[i-1] - y[i]) * (x[i] - x[i-1])
    print(f'{lab}: simulated tolerance (mean PDR = 0.90) = {tol:.1f} dB')
