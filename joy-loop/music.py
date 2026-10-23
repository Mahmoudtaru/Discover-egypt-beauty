"""Original 12.000 s loop, 80 BPM, D major, I-vi-IV-V. Pure numpy/scipy synthesis, 48 kHz stereo."""
import numpy as np, wave
from scipy.signal import sosfilt, butter, resample_poly, fftconvolve
from scipy.ndimage import minimum_filter1d, uniform_filter1d

SR = 48000; BPM = 80; BEAT = 60 / BPM; N = SR * 12; TAIL = SR * 5
rng = np.random.default_rng(7)                       # fixed seed: deterministic render
mf = lambda m: 440.0 * 2 ** ((m - 69) / 12)

L = np.zeros(N + TAIL); Rr = np.zeros(N + TAIL)      # extended buffers, tails get folded onto the start

def add(sig, start, pan=0.0, gain=1.0):
    i = int(round(start * SR)); n = min(len(sig), len(L) - i)
    a = (pan + 1) * np.pi / 4
    L[i:i+n] += sig[:n] * np.cos(a) * gain; Rr[i:i+n] += sig[:n] * np.sin(a) * gain

def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, 'low', fs=SR, output='sos'), x)

# ── felt piano: sine + soft 2nd/3rd, fast attack, ~1.2 s to -20 dB, light low-pass, tiny felt thump
def piano(m, dur=4.0, vel=1.0):
    t = np.arange(int(dur * SR)) / SR; f = mf(m); tau = 1.2 / np.log(10)
    s = (np.sin(2*np.pi*f*t) * np.exp(-t/tau)
         + 0.32 * np.sin(2*np.pi*2*f*t) * np.exp(-t/(tau*0.7))
         + 0.12 * np.sin(2*np.pi*3*f*t) * np.exp(-t/(tau*0.5)))
    s *= 1 - np.exp(-t / 0.004)                       # fast attack
    th = rng.standard_normal(int(0.03*SR)); th = lp(th, 900) * np.exp(-np.arange(len(th))/(0.006*SR))
    s[:len(th)] += 0.05 * th / (np.abs(th).max() + 1e-9)
    s *= np.minimum(1, (dur - t) / 0.3)               # release at the very end
    return lp(s, 3800) * vel

# melody: (beat, midi, length-beats, velocity) — D5=74 F#5=78 A5=81 B5=83 D6=86(peak) C#6=85
MEL = [
 (0.0,78,1,.80),(1.0,81,.5,.60),(1.5,78,.5,.55),(2.0,76,1,.70),(3.5,78,.5,.55),            # bar 1: sparse
 (4.0,74,.5,.65),(4.5,78,.5,.60),(5.0,83,1,.75),(6.0,81,1,.65),(7.0,78,.5,.55),(7.5,81,.5,.65), # bar 2
 (8.0,86,1,1.0),(9.0,83,.5,.70),(9.5,81,.5,.65),(10.0,83,1,.80),(11.0,81,.5,.60),(11.5,83,.5,.65),# bar 3: peak
 (12.0,85,1,.80),(13.0,81,.5,.55),(14.0,76,1,.60),(15.5,76,.5,.50),                         # bar 4: thins, lands on V
]
for b, m, ln, v in MEL:
    add(piano(m, vel=v), b * BEAT, pan=(m - 78) / 40, gain=0.50)

# ── pad: detuned additive saws (±7 cents), 0.6 s attack, LP 1.8 kHz, stereo spread, enters at bar 2
CH = {1: [50,54,57,62], 2: [47,50,54,59], 3: [43,50,57,59],        # bar 3 = G add9 (A is the 9th, opened voicing)
      4: [45,52,57,61]}
def saw(f, t):
    s = np.zeros_like(t); n = 1
    while f * n < 5000: s += np.sin(2*np.pi*f*n*t) / n; n += 1
    return s
def pad_chord(notes, dur, gain):
    t = np.arange(int(dur * SR)) / SR
    outL = np.zeros_like(t); outR = np.zeros_like(t)
    for k, m in enumerate(notes):
        for cents, pan in ((-7, -.7), (0, 0), (7, .7)):
            s = saw(mf(m) * 2 ** (cents/1200), t + 0.013*k) / 3
            outL += s * np.cos((pan+1)*np.pi/4); outR += s * np.sin((pan+1)*np.pi/4)
    env = np.minimum(1, t/0.6) * np.minimum(1, (dur - t)/0.9)
    env = env ** 1.0
    return lp(outL*env, 1800)*gain, lp(outR*env, 1800)*gain
for bar, g in ((2, .09), (3, .11), (4, .07)):
    pl, pr = pad_chord(CH[bar] if bar != 4 else CH[4][:3], 3.0 + 0.9, g)
    i = int((bar - 1) * 3.0 * SR)
    L[i:i+len(pl)] += pl; Rr[i:i+len(pr)] += pr

# ── soft round sub on each bar downbeat
for bar, m in enumerate((38, 35, 31, 33)):
    t = np.arange(int(2.6*SR)) / SR; f = mf(m)
    s = (np.sin(2*np.pi*f*t) + 0.28*np.sin(2*np.pi*2*f*t)) * np.exp(-t/0.9) * (1-np.exp(-t/0.02))
    s *= np.minimum(1, (2.6 - t)/0.3)
    add(s, bar * 3.0, 0, 0.22)

# ── the one liquid bloop at exactly 6.0 s: ~150 ms sine, downward bend
t = np.arange(int(0.22*SR)) / SR
f = 260 + 520 * np.exp(-t / 0.05)
ph = 2*np.pi*np.cumsum(f) / SR
bl = np.sin(ph) * (1-np.exp(-t/0.003)) * np.exp(-t/0.055) * np.minimum(1, (0.22-t)/0.03)
add(bl, 6.0, 0, 0.16)

# ── fold tails onto the start → sample-accurate seamless loop
def fold(x): y = x[:N].copy(); y[:TAIL] += x[N:N+TAIL]; return y
dryL, dryR = fold(L), fold(Rr)

# ── light room reverb (~15 % wet), circular convolution so the loop stays seamless
def ir(seed):
    r = np.random.default_rng(seed); n = int(0.7*SR); t = np.arange(n)/SR
    h = r.standard_normal(n) * np.exp(-t/0.16); h = lp(h, 5500)
    h[:int(0.012*SR)] *= np.linspace(0, 1, int(0.012*SR)); return h / np.sqrt((h**2).sum())
def circ(x, h):
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(h, len(x)), len(x))
wl, wr = circ(dryL, ir(1)), circ(dryR, ir(2))
outL = dryL * 0.87 + wl * 0.15; outR = dryR * 0.87 + wr * 0.15

# ── loudness (BS.1770 K-weighting) → -14 LUFS, circular look-ahead soft limiter, true-peak check
def kw(x):
    s1 = ([1.53512485958697,-2.69169618940638,1.19839281085285],[1,-1.69065929318241,0.73248077421585])
    s2 = ([1,-2,1],[1,-1.99004745483398,0.99007225036621])
    from scipy.signal import lfilter
    return lfilter(*s2, lfilter(*s1, x))
def lufs(l, r):
    kl, kr = kw(l), kw(r); b = int(.4*SR); h = int(.1*SR)
    z = [ (np.mean(kl[i:i+b]**2) + np.mean(kr[i:i+b]**2)) for i in range(0, len(kl)-b, h)]
    z = np.array(z); lk = -0.691 + 10*np.log10(z + 1e-12)
    g = z[lk > -70]; rel = -0.691 + 10*np.log10(g.mean()) - 10
    g = z[lk > max(-70, rel)]; return -0.691 + 10*np.log10(g.mean())
def limit(l, r, ceil):
    env = np.maximum(np.abs(l), np.abs(r)); g = np.minimum(1, ceil/np.maximum(env, 1e-9))
    w = int(0.006*SR)
    g = minimum_filter1d(g, w*2+1, mode='wrap'); g = uniform_filter1d(g, w*2+1, mode='wrap')
    return l*g, r*g
ceil = 10**(-1.5/20); gain = 1.0
for _ in range(8):
    l2, r2 = limit(outL*gain, outR*gain, ceil)
    cur = lufs(l2, r2); gain *= 10 ** ((-14 - cur)/20)
l2, r2 = limit(outL*gain, outR*gain, ceil)
print('LUFS', round(lufs(l2, r2), 2))
tp = max(np.abs(resample_poly(x, 4, 1)).max() for x in (l2, r2))
print('true peak dBTP', round(20*np.log10(tp), 2), ' sample peak', round(20*np.log10(max(abs(l2).max(), abs(r2).max())), 2))

# ── write 16-bit WAV, exactly 12.000 s
dith = lambda: (rng.random(N) - rng.random(N)) / 32768
pcm = np.stack([l2 + dith(), r2 + dith()], 1)
pcm = (np.clip(pcm, -1, 1) * 32767).round().astype('<i2')
with wave.open('joy-loop.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('frames', len(pcm), 'seconds', len(pcm)/SR)

# ── loop seam analysis: jump across the seam vs typical sample-to-sample step
x = np.concatenate([l2, l2, l2]); d = np.abs(np.diff(x))
for k in (1, 2):
    print('seam', k, 'step', round(d[k*N-1], 6), ' 99.9th pct step', round(np.percentile(d, 99.9), 6), ' max step', round(d.max(), 6))
rms = lambda a: np.sqrt(np.mean(a**2))
print('rms last 200ms', round(rms(l2[-9600:]), 4), ' first 200ms', round(rms(l2[:9600]), 4))
