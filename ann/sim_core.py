"""Fast design-space simulator for the multi-hop IEEE 802.15.4 route.

Same physics as the Simulink model (wsn_path_step.m): dual-slope path loss,
static log-normal shadowing, per-attempt Rician fading, O-QPSK DSSS bit error
rate, CSMA backoff, ACK, retries, per-hop queueing, energy accounting.
No ASMA here: this generates design-time training data for the ANN.
"""
import math
import random
import numpy as np
from math import comb

# ---------------------------------------------------------------- constants
BIT_RATE = 250e3
MAC_OVH = 11 * 8
PHY_OVH = 6 * 8
ACK_BITS = 11 * 8
BACKOFF_UNIT = 20 * 16e-6
MIN_BE = 3
CCA = 8 * 16e-6
TURN = 12 * 16e-6
ACK_WAIT = 54 * 16e-6
PROC = 1e-3
DEADLINE = 0.100
NOISE_FLOOR = -101.0
SHADOW_SIGMA = 4.0
RICIAN_K_DB = 3.0
V_SUPPLY = 3.0                # V
I_TX_BASE = 8.5e-3            # A: fit to CC2420 datasheet, I = 8.5 + 8.9 * 10^(P/20) mA
I_TX_PA = 8.9e-3              # A
P_RX = 3 * 18.8e-3
TS = 0.1
PST = 2.0
T_ACT = 0.5
CRC_BITS = 16

# BER lookup table for speed (identical formula to berOqpsk in MATLAB)
_SNR_MIN, _SNR_MAX, _SNR_STEP = -20.0, 30.0, 0.001
_grid = np.arange(_SNR_MIN, _SNR_MAX + _SNR_STEP / 2, _SNR_STEP)
_s = 10 ** (_grid / 10)
_tot = np.zeros_like(_s)
for _k in range(2, 17):
    _tot += (-1) ** _k * comb(16, _k) * np.exp(20 * _s * (1 / _k - 1))
_BER = np.clip(8 / 15 / 16 * _tot, 0, 0.5)
_LOG1M = np.log1p(-_BER).tolist()          # log(1 - BER)
_N = len(_LOG1M)


def log1m_ber(snr):
    if snr >= _SNR_MAX:
        return 0.0
    if snr <= _SNR_MIN:
        return _LOG1M[0]
    x = (snr - _SNR_MIN) / _SNR_STEP
    i = int(x)
    if i >= _N - 1:
        return _LOG1M[-1]
    f = x - i
    return _LOG1M[i] + f * (_LOG1M[i + 1] - _LOG1M[i])


def ber_exact(snr):
    s = 10 ** (snr / 10)
    tot = sum((-1) ** k * comb(16, k) * math.exp(20 * s * (1 / k - 1)) for k in range(2, 17))
    return min(max(8 / 15 / 16 * tot, 0.0), 0.5)


def path_loss(d):
    return 46 + 11 * math.log10(d) if d <= 11 else 30 + 26 * math.log10(d)


def tx_power_w(tx_dbm):
    """Supply power while transmitting: fit to CC2420 datasheet currents (within 0.5 mA, -25 to 0 dBm)."""
    return V_SUPPLY * (I_TX_BASE + I_TX_PA * 10 ** (tx_dbm / 20))


def hop_distances(K, mean_d, std_d):
    """Deterministic spacing pattern with exactly the requested mean and std."""
    if K == 1 or std_d <= 0:
        return np.full(K, float(mean_d))
    z = np.linspace(-1, 1, K)
    z = (z - z.mean()) / z.std(ddof=1)
    return mean_d + std_d * z


def interference_hops(K):
    """Middle min(3, K) hops (1-based), e.g. hops 4-6 for K = 10."""
    n = min(3, K)
    start = (K - n) // 2 + 1
    return set(range(start, start + n))


def simulate(K, mean_d, std_d, tx_dbm, payload, retries, noise_rise, seed,
             duration=60.0, boost=None, d_override=None):
    rnd = random.Random(seed)
    d = hop_distances(K, mean_d, std_d)
    order = list(range(K)); rnd.shuffle(order)       # random placement of the hops
    d = d[order]
    if d_override is not None:
        d = np.asarray(d_override, float)
    shadow = [rnd.gauss(0, SHADOW_SIGMA) for _ in range(K)]
    zone = interference_hops(K)
    boost = boost or [0.0] * K
    mean_snr = [tx_dbm + boost[i] - path_loss(d[i]) - shadow[i] - NOISE_FLOOR
                - (noise_rise if (i + 1) in zone else 0.0) for i in range(K)]
    Kr = 10 ** (RICIAN_K_DB / 10)
    los = math.sqrt(Kr / (Kr + 1)); sc = math.sqrt(1 / (2 * (Kr + 1)))
    mac_bits = payload + MAC_OVH
    frame = (mac_bits + PHY_OVH) / BIT_RATE
    t_att_fixed = CCA + TURN + frame + ACK_WAIT
    e_att = [tx_power_w(tx_dbm + boost[i]) * frame + P_RX * (TURN + ACK_WAIT) for i in range(K)]
    busy = [0.0] * K
    n_pk = int(round(duration / TS))
    gen, arr, ok_list = [], [], []
    on_time = 0; delivered = 0; energy = 0.0; failed_frames = 0; lat_sum = 0.0
    lats = []
    for p in range(n_pk):
        t = p * TS
        tnow = t
        ok = True
        for i in range(K):
            tc = max(tnow, busy[i])
            hop_ok = False
            for a in range(retries + 1):
                tc += rnd.randrange(8) * BACKOFF_UNIT + t_att_fixed
                energy += e_att[i]
                gI = los + sc * rnd.gauss(0, 1); gQ = sc * rnd.gauss(0, 1)
                g = gI * gI + gQ * gQ
                snr = mean_snr[i] + 10 * math.log10(max(g, 1e-12))
                l1m = log1m_ber(snr)
                per_d = 1 - math.exp(mac_bits * l1m)
                per_a = 1 - math.exp(ACK_BITS * l1m)
                if rnd.random() >= per_d and rnd.random() >= per_a:
                    hop_ok = True
                    break
                failed_frames += 1
            busy[i] = tc
            if not hop_ok:
                ok = False
                break
            tnow = tc + PROC
        if ok:
            lat = tnow - t
            delivered += 1
            lats.append(lat)
            gen.append(t); arr.append(tnow)
            if lat <= DEADLINE:
                on_time += 1
    # hazard signalling over the whole run (10 ms grid)
    sig = hazard_signal(np.array(gen), np.array(arr), np.arange(0, duration - 1e-9, 0.01))
    srt = np.sort(sig)
    p99 = srt[int(math.ceil(0.99 * len(srt))) - 1]    # nearest-rank 99th percentile (may be inf)
    out = dict(
        PDR=on_time / n_pk,
        SDR=float(np.mean(sig <= PST - T_ACT)),
        NWLat_ms=1e3 * float(np.mean(lats)) if lats else np.nan,
        LatP99_ms=1e3 * float(np.percentile(lats, 99)) if lats else np.nan,
        Energy_mJ=1e3 * energy / delivered if delivered else np.nan,
        MinPST_s=float(p99 + T_ACT),
        FPDR=failed_frames * 2.0 ** (-CRC_BITS) / n_pk,
        Delivered=delivered / n_pk,
    )
    return out


def hazard_signal(gen, arr, h):
    sig = np.full(h.shape, np.inf)
    if len(gen) == 0:
        return sig
    suf = np.minimum.accumulate(arr[::-1])[::-1]
    idx = np.searchsorted(gen, h - 1e-9)
    ok = idx < len(gen)
    sig[ok] = suf[idx[ok]] - h[ok]
    return sig


if __name__ == '__main__':
    import time
    # check the BER table against the exact formula
    worst = max(abs(math.exp(log1m_ber(s)) - (1 - ber_exact(s))) for s in np.arange(-5, 10, 0.0137))
    print('max |1-BER| table error:', worst)
    t0 = time.time()
    r = simulate(10, 29.3, 11.57, 0.0, 900, 3, 30.0, seed=1, duration=100)
    print(r, 'time', round(time.time() - t0, 2), 's')
