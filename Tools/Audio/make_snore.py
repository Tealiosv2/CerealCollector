# Generates Grandma's sleeping-breath loop: a low, creaky snore on each inhale
# and a breathy sigh on each exhale. Two breaths per loop; the second is
# deeper and ends in a wet catch. Lo-fi on purpose (22.05 kHz, mono).
#
#   python make_snore.py [out.wav]
#
# The breath timeline must match Grandma_SleepSit.anim, which is built by
# Assets/Editor/GrandmaSleepBuilder.cs (BREATHS there).
# All filtering is done circularly in the frequency domain, so the file loops
# with no click.
import sys
import wave
import numpy as np

SR = 22050
LENGTH = 9.0                                 # seconds, one animation loop
# (inhale start, inhale end, exhale end, depth)
BREATHS = [(0.00, 1.90, 4.20, 1.00),
           (4.30, 6.50, 8.90, 1.25)]
OUT = sys.argv[1] if len(sys.argv) > 1 else "Grandma_Snore.wav"

rng = np.random.default_rng(7)
N = int(SR * LENGTH)
t = np.arange(N) / SR
freqs = np.fft.rfftfreq(N, 1 / SR)


def spectral(x, mag):
    """Zero-phase circular filter with magnitude response mag(freqs)."""
    return np.fft.irfft(np.fft.rfft(x) * mag, N)


def peak(f0, q, gain=1.0):
    """Resonance magnitude curve (a soft bandpass) centred on f0."""
    bw = f0 / q
    return gain / np.sqrt(1 + ((freqs - f0) / (bw / 2)) ** 2)


def lowpass(fc, order=2):
    return 1 / np.sqrt(1 + (freqs / fc) ** (2 * order))


def highpass(fc, order=2):
    r = (freqs / fc) ** (2 * order)
    return np.sqrt(r / (1 + r))


def window(a, b, rise, fall):
    """Smooth 0..1 envelope that is 1 between a and b."""
    up = np.clip((t - a) / rise, 0, 1)
    down = np.clip((b - t) / fall, 0, 1)
    e = np.minimum(up, down)
    return e * e * (3 - 2 * e)               # smoothstep


def flutter(a, b, f_lo, f_hi, jitter, depth):
    """Soft-palate rattle: a jittery train of short damped knocks."""
    out = np.zeros(N)
    pos = a
    while pos < b:
        u = (pos - a) / (b - a)
        f = f_lo + (f_hi - f_lo) * np.sin(np.pi * u) + rng.normal(0, 2)
        amp = (0.55 + 0.45 * np.sin(np.pi * u)) * rng.uniform(0.6, 1.0) * depth
        i = int(pos * SR)
        n = int(0.022 * SR)
        k = np.arange(n) / SR
        burst = np.exp(-k * rng.uniform(140, 220)) * (
            np.sin(2 * np.pi * rng.uniform(85, 120) * k) + 0.6 * rng.normal(0, 1, n))
        idx = (i + np.arange(n)) % N
        out[idx] += amp * burst
        pos += (1 / f) * (1 + rng.uniform(-jitter, jitter))
    return out


sig = np.zeros(N)
for k, (a, b, c, depth) in enumerate(BREATHS):
    # ── inhale: the snore ──
    rattle = flutter(a + 0.15, b - 0.05, 24, 36 + 6 * k, 0.28 + 0.1 * k, depth)
    rattle = spectral(rattle, peak(105, 1.8, 1.0) + peak(290, 3, 0.8)
                      + peak(640, 4, 0.45) + peak(1500, 5, 0.12))
    air_in = spectral(rng.normal(0, 1, N), (peak(450, 1.2, 0.5) + peak(1200, 2, 0.25)) * highpass(150))
    env_in = window(a, b, 0.55, 0.30)
    sig += env_in * (rattle * 1.0 + air_in * 0.10 * depth)

    # ── exhale: a slow breathy sigh, with a faint lip flap at the start ──
    air_out = spectral(rng.normal(0, 1, N), (peak(380, 1.0, 0.6) + peak(900, 1.5, 0.3)) * highpass(120))
    lips = 0.6 + 0.4 * np.sin(2 * np.pi * 11 * t + k) ** 2
    lip_env = window(b + 0.05, b + 0.9, 0.08, 0.6)
    env_out = window(b + 0.02, c, 0.25, 1.6) * (1 - 0.5 * np.clip((t - b) / (c - b), 0, 1))
    sig += env_out * air_out * 0.16 * depth * np.where(lip_env > 0, 1 - lip_env * (1 - lips), 1)

    # ── the deeper breath ends its snore in a wet catch and a faint groan ──
    if k == 1:
        catch = flutter(b - 0.25, b + 0.18, 9, 13, 0.4, 1.4)
        catch = spectral(catch, peak(180, 2, 1.0) + peak(520, 3, 0.6))
        sig += catch * window(b - 0.25, b + 0.18, 0.05, 0.08)
        groan_t = t - (b + 0.25)
        f0 = 92 - 10 * np.clip(groan_t / 1.2, 0, 1)
        groan = np.sin(2 * np.pi * np.cumsum(f0) / SR) + 0.35 * np.sin(4 * np.pi * np.cumsum(f0) / SR)
        groan = spectral(groan, peak(300, 2, 1.0) + peak(700, 3, 0.4))
        sig += groan * window(b + 0.25, b + 1.45, 0.25, 0.8) * 0.05

# Small, dark room: circular convolution with a short noise tail.
tail = np.zeros(N)
L = int(0.45 * SR)
tail[:L] = rng.normal(0, 1, L) * np.exp(-np.arange(L) / (0.09 * SR))
tail[0] = 0
room = np.fft.irfft(np.fft.rfft(sig) * np.fft.rfft(tail) * lowpass(2500), N)
sig = sig + 0.18 * room / (np.abs(room).max() + 1e-9) * np.abs(sig).max()

sig = spectral(sig, lowpass(4800, 3) * highpass(55, 2))
sig += rng.normal(0, 0.0015, N) * np.abs(sig).max()      # faint tape hiss
sig *= 10 ** (-3 / 20) / np.abs(sig).max()

with wave.open(OUT, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((sig * 32767).astype("<i2").tobytes())
print(f"wrote {OUT}: {LENGTH}s @ {SR} Hz, breaths={len(BREATHS)}")
