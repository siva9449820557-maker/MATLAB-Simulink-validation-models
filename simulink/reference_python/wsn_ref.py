"""Python reference implementation of the IWSN + ASMA simulation.

Mirrors the MATLAB functions wsn_path_step.m and asma_controller_step.m so the
logic can be checked and the disturbance range calibrated before MATLAB runs.
"""
import math
import numpy as np
from math import comb

# ----------------------------------------------------------------- parameters
def params():
    P = {}
    P['Ts'] = 0.1                 # packet period = model step (s)
    P['Tstop'] = 100.0
    P['nHops'] = 10
    P['d'] = np.array([24, 37, 12, 29, 43, 19, 33, 14, 42, 40], float)  # m; mean 29.3, std 11.57, sum 293
    P['txPower_dBm'] = 0.0
    P['boost_dB'] = 3.0
    P['noiseFloor_dBm'] = -101.0
    P['shadowSigma_dB'] = 4.0
    P['ricianK_dB'] = 3.0
    P['intHops'] = np.array([4, 5, 6])      # 1-based hop indices hit by interference
    P['intOn_s'] = 30.0
    P['intOff_s'] = 70.0
    P['noiseRise_dB'] = 30.0
    # IEEE 802.15.4 O-QPSK 2.4 GHz timing
    P['bitRate'] = 250e3
    P['payloadBits'] = 900
    P['macOverheadBits'] = 11 * 8
    P['phyOverheadBits'] = 6 * 8
    P['ackBits'] = 11 * 8
    P['symbol_s'] = 16e-6
    P['backoffUnit_s'] = 20 * 16e-6
    P['minBE'] = 3
    P['cca_s'] = 8 * 16e-6
    P['turnaround_s'] = 12 * 16e-6
    P['ackWait_s'] = 54 * 16e-6
    P['proc_s'] = 1e-3
    P['retriesNominal'] = 3
    P['retriesBoost'] = 5
    P['deadline_s'] = 0.100
    # radio energy (3 V supply)
    P['pTx0_W'] = 3 * 17.4e-3
    P['pTxBoost_W'] = 3 * (8.5e-3 + 8.9e-3 * 10 ** (3 / 20))   # CC2420 fit at +3 dBm
    P['pRx_W'] = 3 * 18.8e-3
    # ASMA controller
    P['asmaEnabled'] = 1
    P['window_s'] = 2.0
    P['eval_s'] = 0.5
    P['prrOn'] = 0.93
    P['snrRelease_dB'] = 6.0
    P['minDwell_s'] = 5.0
    P['minAttempts'] = 10
    P['cmdDelaySteps'] = 2
    # safety function
    P['PST_s'] = 2.0
    P['tAct_s'] = 0.5
    P['seed'] = 1
    P['asmaUsePower'] = 1
    P['asmaUseRetries'] = 1
    P['intProfile'] = 'step'
    P['rampTime_s'] = 20.0
    P['burstPeriod_s'] = 5.0
    P['burstOn_s'] = 2.0
    return P


def path_loss_dB(d):
    d = np.asarray(d, float)
    return np.where(d <= 11, 46 + 11 * np.log10(d), 30 + 26 * np.log10(d))


def ber_oqpsk(snr_dB):
    s = 10 ** (np.asarray(snr_dB, float) / 10)
    tot = np.zeros_like(s)
    for k in range(2, 17):
        tot += (-1) ** k * comb(16, k) * np.exp(20 * s * (1 / k - 1))
    return np.clip(8 / 15 / 16 * tot, 0, 0.5)


# ----------------------------------------------------------- path step (one packet)
class Path:
    def __init__(self, P, rng):
        self.P = P
        self.rng = rng
        self.busy = np.zeros(P['nHops'])
        self.shadow = P['shadowSigma_dB'] * rng.standard_normal(P['nHops'])
        self.meanSnr0 = (P['txPower_dBm'] - path_loss_dB(P['d']) - self.shadow
                         - P['noiseFloor_dBm'])

    def step(self, t, noiseRise, boost, retries):
        P, rng = self.P, self.rng
        n = P['nHops']
        K = 10 ** (P['ricianK_dB'] / 10)
        macBits = P['payloadBits'] + P['macOverheadBits']
        frame_s = (macBits + P['phyOverheadBits']) / P['bitRate']
        ack_s = P['ackBits'] / P['bitRate']
        hopAtt = np.zeros(n); hopSucc = np.zeros(n); hopSnr = np.zeros(n)
        energy = 0.0
        tNow = t
        delivered = 0
        for i in range(n):
            nr = noiseRise if (i + 1) in P['intHops'] else 0.0
            start = max(tNow, self.busy[i])
            tc = start
            ok = False
            snrSum = 0.0
            pTx = P['pTxBoost_W'] if boost[i] > 0.5 else P['pTx0_W']
            for a in range(int(retries[i]) + 1):
                bo = rng.integers(0, 2 ** P['minBE']) * P['backoffUnit_s']
                hI = math.sqrt(K / (K + 1)) + math.sqrt(1 / (2 * (K + 1))) * rng.standard_normal()
                hQ = math.sqrt(1 / (2 * (K + 1))) * rng.standard_normal()
                g = hI ** 2 + hQ ** 2
                snr = self.meanSnr0[i] + P['boost_dB'] * (boost[i] > 0.5) + 10 * math.log10(g) - nr
                perData = 1 - (1 - float(ber_oqpsk(snr))) ** macBits
                perAck = 1 - (1 - float(ber_oqpsk(snr))) ** P['ackBits']
                tc += bo + P['cca_s'] + P['turnaround_s'] + frame_s + P['ackWait_s']
                energy += pTx * frame_s + P['pRx_W'] * (P['turnaround_s'] + P['ackWait_s'])
                hopAtt[i] += 1
                snrSum += snr
                if rng.random() >= perData and rng.random() >= perAck:
                    ok = True
                    break
            hopSnr[i] = snrSum / hopAtt[i]
            self.busy[i] = tc
            if not ok:
                return 0, np.nan, hopAtt, hopSucc, hopSnr, energy
            hopSucc[i] = 1
            tNow = tc + P['proc_s']
        delivered = 1
        return delivered, tNow - t, hopAtt, hopSucc, hopSnr, energy


# ------------------------------------------------------------ ASMA controller
class Controller:
    def __init__(self, P):
        self.P = P
        n = P['nHops']
        self.W = int(round(P['window_s'] / P['Ts']))
        self.att = np.zeros((n, self.W)); self.succ = np.zeros((n, self.W))
        self.snrw = np.zeros((n, self.W)); self.ot = np.zeros(self.W); self.gen = np.zeros(self.W)
        self.k = 0
        self.boost = np.zeros(n); self.boostStart = np.zeros(n)
        self.lastOK = 0.0
        self.failSafe = 0; self.tripTime = np.nan
        self.prr = np.ones(n); self.pdrWin = 1.0

    def step(self, t, delivered, onTime, latency, hopAtt, hopSucc, hopSnr):
        P = self.P
        j = self.k % self.W
        self.att[:, j] = hopAtt; self.succ[:, j] = hopSucc
        self.snrw[:, j] = hopSnr * hopAtt; self.ot[j] = onTime; self.gen[j] = 1
        self.k += 1
        if onTime:
            self.lastOK = t + latency
        # watchdog of the safety function (always active)
        if not self.failSafe and (t - self.lastOK) > (P['PST_s'] - P['tAct_s']):
            self.failSafe = 1; self.tripTime = t
        evalSteps = int(round(P['eval_s'] / P['Ts']))
        if self.k % evalSteps == 0:
            A = self.att.sum(1); S = self.succ.sum(1)
            self.prr = np.where(A > 0, S / np.maximum(A, 1), 1.0)
            snrEst = np.where(A > 0, self.snrw.sum(1) / np.maximum(A, 1), 99.0)
            self.pdrWin = self.ot.sum() / max(self.gen.sum(), 1)
            if P['asmaEnabled'] and not self.failSafe:
                for i in range(P['nHops']):
                    if self.boost[i] < 0.5:
                        if A[i] >= P['minAttempts'] and self.prr[i] < P['prrOn']:
                            self.boost[i] = 1; self.boostStart[i] = t
                    else:
                        if (t - self.boostStart[i] >= P['minDwell_s']
                                and snrEst[i] - P['boost_dB'] >= P['snrRelease_dB']):
                            self.boost[i] = 0
        mode = 2 if self.failSafe else (1 if self.boost.any() else 0)
        retries = P['retriesNominal'] + self.boost * P['asmaUseRetries'] * (P['retriesBoost'] - P['retriesNominal'])
        return self.boost * P['asmaUsePower'], retries, mode, self.pdrWin, self.prr.copy()


def interference(t, P):
    if not (P['intOn_s'] <= t < P['intOff_s']):
        return 0.0
    if P['intProfile'] == 'step':
        return P['noiseRise_dB']
    if P['intProfile'] == 'ramp':
        return P['noiseRise_dB'] * min(1.0, (t - P['intOn_s']) / P['rampTime_s'])
    if P['intProfile'] == 'burst':
        return P['noiseRise_dB'] if ((t - P['intOn_s']) % P['burstPeriod_s']) < P['burstOn_s'] else 0.0
    raise ValueError('unknown profile')


# -------------------------------------------------------------------- run one
def run(P):
    rng = np.random.default_rng(P['seed'])
    path = Path(P, rng); ctl = Controller(P)
    n = P['nHops']
    N = int(round(P['Tstop'] / P['Ts'])) + 1
    D = P['cmdDelaySteps']
    boostQ = [np.zeros(n)] * D; retrQ = [np.full(n, float(P['retriesNominal']))] * D
    log = {k: [] for k in ['t', 'delivered', 'latency', 'onTime', 'energy', 'mode', 'pdrWin',
                           'boost', 'prr', 'hopAtt', 'hopSucc', 'noiseRise']}
    for s in range(N):
        t = s * P['Ts']
        nr = interference(t, P)
        bApplied, rApplied = boostQ[0], retrQ[0]
        dl, lat, hA, hS, hSnr, en = path.step(t, nr, bApplied, rApplied)
        onTime = int(dl == 1 and lat <= P['deadline_s'])
        b, r, mode, pdrWin, prr = ctl.step(t, dl, onTime, lat, hA, hS, hSnr)
        boostQ = boostQ[1:] + [b]; retrQ = retrQ[1:] + [r]
        for k, v in zip(log, [t, dl, lat, onTime, en, mode, pdrWin, bApplied, prr, hA, hS, nr]):
            log[k].append(v)
    return {k: np.array(v) for k, v in log.items()}


def hazard_signal_times(L, t0, t1, dt=0.01):
    """Time from a hazard at time h to arrival of the first on-time-or-late delivered packet generated at or after h."""
    gen = L['t']; arr = L['t'] + np.nan_to_num(L['latency'], nan=np.inf)
    ok = L['delivered'] == 1
    gen_ok = gen[ok]; arr_ok = arr[ok]
    hs = np.arange(t0, t1, dt)
    idx = np.searchsorted(gen_ok, hs - 1e-9)
    out = np.full(hs.shape, np.inf)
    valid = idx < len(gen_ok)
    out[valid] = arr_ok[idx[valid]] - hs[valid]
    return out


def summarize(L, P):
    dis = (L['t'] >= P['intOn_s']) & (L['t'] < P['intOff_s'])
    lat = L['latency'][L['delivered'] == 1]
    sig = hazard_signal_times(L, P['intOn_s'], P['intOff_s'])
    sdr = np.mean(sig <= P['PST_s'] - P['tAct_s'])
    return dict(
        pdr_all=L['onTime'].mean(),
        pdr_dist=L['onTime'][dis].mean(),
        deliv_dist=L['delivered'][dis].mean(),
        lat_p99=np.percentile(lat, 99) if len(lat) else np.nan,
        sig_p99=np.percentile(sig, 99), sig_max=np.max(sig),
        sdr=sdr,
        energy_per_pkt_mJ=1e3 * L['energy'].sum() / max(L['delivered'].sum(), 1),
        boost_frac=(L['boost'].sum(1) > 0).mean(),
        trip=int((L['mode'] == 2).any()),
        trip_t=L['t'][np.argmax(L['mode'] == 2)] if (L['mode'] == 2).any() else np.nan,
        first_boost=L['t'][np.argmax(L['boost'].sum(1) > 0)] if (L['boost'].sum(1) > 0).any() else np.nan,
    )


if __name__ == '__main__':
    import sys
    P = params()
    print('mean SNR per hop (no shadow):', np.round(P['txPower_dBm'] - path_loss_dB(P['d']) - P['noiseFloor_dBm'], 1))
    for snr in [-1, 0, 1, 2, 3]:
        print('SNR', snr, 'PER data', round(1 - (1 - float(ber_oqpsk(snr))) ** 988, 4))
