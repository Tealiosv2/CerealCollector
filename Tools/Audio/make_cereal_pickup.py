# Generates the sound of a cardboard box of cereal being picked up: the hand
# landing on the box, the cereal rattling inside as it is snatched and lifted,
# a small settle, then the cereal sliding over as the box is turned to face
# the player. Lo-fi on purpose (22.05 kHz, mono), like the snore.
#
#   python make_cereal_pickup.py [out.wav]
#
# The clip starts when the hand closes (FirstPersonArm_Script.OnGrab) and is
# timed to the rest of that 2.2 s animation: lift, pull in, turn. Times below
# are seconds after the grab.
import sys
import wave
import numpy as np

SR = 22050
LENGTH = 1.25
OUT = sys.argv[1] if len(sys.argv) > 1 else "Cereal_Pickup.wav"

rng = np.random.default_rng(11)
N = int(SR * LENGTH)
t = np.arange(N) / SR
freqs = np.fft.rfftfreq(N, 1 / SR)


def spectral(x, mag):
    return np.fft.irfft(np.fft.rfft(x) * mag, N)


def peak(f0, q, gain=1.0):
    bw = f0 / q
    return gain / np.sqrt(1 + ((freqs - f0) / (bw / 2)) ** 2)


def lowpass(fc, order=2):
    return 1 / np.sqrt(1 + (freqs / fc) ** (2 * order))


def highpass(fc, order=2):
    r = (freqs / fc) ** (2 * order)
    return np.sqrt(r / (1 + r))


def taps(times, amps, decay):
    """Many tiny knocks: an impulse per tap, smeared into a short decay, each
    filled with its own noise so no two taps sound the same."""
    imp = np.zeros(N)
    idx = np.clip((np.asarray(times) * SR).astype(int), 0, N - 1)
    np.add.at(imp, idx, amps)
    n = int(decay * 6 * SR)
    env = np.convolve(imp, np.exp(-np.arange(n) / (decay * SR)))[:N]
    return env * rng.normal(0, 1, N)


def shake(start, end, count, shape, level):
    """Cereal shifting between start and end. shape(u) is how busy it is over
    the shake (u = 0..1); returns pieces, cardboard and inner-bag layers."""
    u = rng.random(count * 4)
    u = u[rng.random(count * 4) < shape(u) / shape(np.linspace(0, 1, 200)).max()][:count]
    when = start + u * (end - start)
    amp = level * shape(u) / shape(np.linspace(0, 1, 200)).max() * rng.uniform(0.3, 1.0, len(u)) ** 1.5
    # Dry, hard little pieces knocking each other and the box walls.
    pieces = spectral(taps(when, amp, 0.0022), (peak(2300, 0.9) + peak(4300, 1.2, 0.8) + peak(7000, 1.5, 0.35)) * highpass(900))
    # The box itself: the same knocks heard through cardboard.
    box = spectral(taps(when, amp, 0.007), (peak(260, 1.6) + peak(540, 2.0, 0.8) + peak(1100, 2.2, 0.45)) * lowpass(1500))
    # The plastic bag inside: sparser, brighter crackle.
    k = rng.random(len(when)) < 0.22
    bag = spectral(taps(when[k], amp[k] * 1.3, 0.0009), highpass(3800, 3) * lowpass(9500, 2))
    return pieces * 1.5 + box * 1.5 + bag * 0.6


sig = np.zeros(N)

# The hand lands on the box: a hollow cardboard pat.
pat = np.exp(-np.clip(t - 0.012, 0, None) / 0.028) * (t >= 0.012)
thump = pat * np.sin(2 * np.pi * (150 - 500 * np.clip(t - 0.012, 0, 0.06)) * (t - 0.012))
slap = spectral(pat ** 2 * rng.normal(0, 1, N), (peak(420, 1.2) + peak(950, 1.5, 0.7)) * lowpass(2200) * highpass(180))
sig += 1.6 * thump + 3.2 * slap
# Fingers dragging a little way across the card as they close.
drag = spectral(rng.normal(0, 1, N), peak(1700, 1.0) * highpass(700) * lowpass(4500))
sig += 0.10 * drag * np.exp(-((t - 0.05) / 0.035) ** 2)

# Snatched and lifted: the cereal jumps, then rains back down.
sig += shake(0.03, 0.46, 420, lambda u: np.exp(-u * 2.3) * (1 - np.exp(-u * 40)) + 0.05, 1.0)
# Lift stops as the box is pulled in: a small settle.
sig += shake(0.47, 0.66, 70, lambda u: np.exp(-u * 4.0) + 0.05, 0.45)
# Turned to face the player: the cereal slides over and piles against the side.
sig += shake(0.76, 1.06, 260, lambda u: u ** 1.3 * (u < 0.93) + 0.02, 0.55)
stop = np.exp(-np.clip(t - 1.04, 0, None) / 0.03) * (t >= 1.04)
sig += 2.0 * spectral(stop * rng.normal(0, 1, N), (peak(300, 1.5) + peak(700, 2, 0.5)) * lowpass(1400))

sig = spectral(sig, highpass(70, 2) * lowpass(9000, 3))
sig = np.tanh(sig / (np.abs(sig).max() * 0.55))          # a little crunch; evens out the loudest knocks
fade = np.minimum(1, np.minimum(t / 0.004, (LENGTH - t) / 0.05))
sig *= fade * 10 ** (-2 / 20) / np.abs(sig).max()

with wave.open(OUT, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((sig * 32767).astype("<i2").tobytes())
print(f"wrote {OUT}: {LENGTH}s @ {SR} Hz")
