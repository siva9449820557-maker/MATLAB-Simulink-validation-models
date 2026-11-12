"""Estimate the best R^2 any model can reach, given random shadowing and hop order.

Every design in dataset.csv is simulated again with a different seed.
For two independent runs yA, yB of the same design, Cov(yA, yB) estimates the
variance a perfect model could explain, so the ceiling is Cov(yA, yB) / Var(y).
"""
import numpy as np
import pandas as pd
from multiprocessing import Pool
from sim_core import simulate

import sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30000
OUT = ['PDR', 'SDR']


def rerun(r):
    i, d = r
    return simulate(int(d.K), float(d.MeanD_m), float(d.StdD_m), float(d.Tx_dBm), int(d.Pkt_bits),
                    int(d.Retries), float(d.Noise_dB), seed=200000 + i, duration=60.0)


if __name__ == '__main__':
    A = pd.read_csv('dataset.csv').head(N)
    with Pool(4) as p:
        B = pd.DataFrame(p.map(rerun, list(A.iterrows()), chunksize=25))
    rows = []
    for o in OUT:
        a, b = A[o].to_numpy(float), B[o].to_numpy(float)
        ok = np.isfinite(a) & np.isfinite(b)
        a, b = a[ok], b[ok]
        cov = np.mean((a - a.mean()) * (b - b.mean()))
        var = 0.5 * (a.var() + b.var())
        rows.append(dict(output=o, n=int(ok.sum()), ceiling_R2=round(cov / var, 3)))
    res = pd.DataFrame(rows)
    res.to_csv('r2_ceiling.csv', index=False)
    print(res.to_string(index=False))
