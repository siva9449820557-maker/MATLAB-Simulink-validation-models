"""Generate the physics-based training dataset for the ANN.

Each row is one route design simulated for 60 s (600 packets) with the
interference level applied to the middle three hops for the whole run.
Inputs are sampled with a Latin hypercube over the design space.
"""
import sys
import numpy as np
import pandas as pd
from multiprocessing import Pool
from sim_core import simulate

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SEED = 2026

RANGES = {
    'K':         (2, 12),      # hops (integer)
    'MeanD_m':   (10, 60),     # mean hop distance
    'StdFrac':   (0, 1),       # std as a fraction of min(15 m, 0.5 * mean)
    'Tx_dBm':    (-10, 0),     # design transmit power (ASMA adds +3 dB)
    'Pkt_bits':  (200, 900),   # payload
    'Retries':   (0, 5),       # macMaxFrameRetries (integer)
    'Noise_dB':  (0, 40),      # interference rise on the middle three hops
}


def lhs(n, k, rng):
    u = (rng.permuted(np.tile(np.arange(n), (k, 1)), axis=1).T + rng.random((n, k))) / n
    return u


def row(args):
    i, K, mean_d, std_d, tx, pkt, rt, nr = args
    out = simulate(int(K), float(mean_d), float(std_d), float(tx), int(pkt), int(rt), float(nr),
                   seed=100000 + i, duration=60.0)
    return dict(K=int(K), MeanD_m=mean_d, StdD_m=std_d, Tx_dBm=tx, Pkt_bits=int(pkt),
                Retries=int(rt), Noise_dB=nr, SD_m=K * mean_d, **out)


if __name__ == '__main__':
    rng = np.random.default_rng(SEED)
    U = lhs(N, len(RANGES), rng)
    names = list(RANGES)
    X = {n: RANGES[n][0] + U[:, j] * (RANGES[n][1] - RANGES[n][0]) for j, n in enumerate(names)}
    K = np.clip(np.round(2 + U[:, 0] * 10.999 - 0.5).astype(int), 2, 12)
    Rt = np.clip(np.floor(U[:, 5] * 6).astype(int), 0, 5)
    std = X['StdFrac'] * np.minimum(15.0, 0.5 * X['MeanD_m'])
    std[K == 1] = 0
    pkt = np.round(X['Pkt_bits'] / 8) * 8
    tasks = [(i, K[i], X['MeanD_m'][i], std[i], X['Tx_dBm'][i], pkt[i], Rt[i], X['Noise_dB'][i])
             for i in range(N)]
    with Pool(2) as p:
        rows = p.map(row, tasks, chunksize=50)
    df = pd.DataFrame(rows)
    df.to_csv('dataset.csv', index=False)
    print(df.describe().T[['mean', 'min', 'max']].round(3))
    print('rows', len(df), 'with no delivery', int((df.Delivered == 0).sum()))
