"""Synthesize a royalty-free music bed and SFX (all generated here), timed to timeline.json."""
import json, wave
import numpy as np
from pathlib import Path
HERE = Path(__file__).parent
TL = json.loads((HERE / "timeline.json").read_text(encoding="utf-8"))
SR = 48000; T = TL["total"]; N = int(T * SR) + SR
t = np.arange(N) / SR
rng = np.random.default_rng(7)

def env_at(points):
    xs, ys = zip(*points); return np.interp(t, xs, ys)

# --- music: chord pad + soft pulse, A minor progression, 2 s per chord
chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G (midi)
f = lambda m: 440 * 2 ** ((m - 69) / 12)
music = np.zeros(N)
for k in range(int(T / 2) + 2):
    a, b = int(k * 2 * SR), min(N, int((k + 1) * 2 * SR + SR * 0.3))
    if a >= N: break
    tt = t[a:b] - k * 2
    e = np.minimum(1, tt / 0.4) * np.exp(-tt * 0.35)
    for m in chords[k % 4]:
        music[a:b] += e * (np.sin(2 * np.pi * f(m) * tt) + 0.3 * np.sin(2 * np.pi * f(m) * 2 * tt + 0.5)) * 0.12
    bass = f(chords[k % 4][0] - 12)
    music[a:b] += e * np.sin(2 * np.pi * bass * tt) * 0.18
sc = {s["n"]: s for s in TL["scenes"]}
reveal, close = sc[3]["t0"], sc[8]["t0"]
# pulse (kick-ish) on beats from the reveal on, 120 bpm
pulse = np.zeros(N)
for bt in np.arange(reveal, T - 1.5, 0.5):
    a = int(bt * SR); L = int(0.18 * SR)
    if a + L >= N: break
    tt = np.arange(L) / SR
    pulse[a:a + L] += np.sin(2 * np.pi * (110 * np.exp(-tt * 18) + 45) * tt) * np.exp(-tt * 22) * 0.35
energy = env_at([(0, .45), (reveal - 2, .6), (reveal, 1.0), (sc[4]["t0"], .75), (sc[6]["t0"], .85), (close - 1, .9), (close, 1.0), (T - 0.6, 1.0), (T, 0)])
music = (music + pulse * env_at([(0, 0), (reveal, 0), (reveal + .1, .7), (sc[4]["t0"], .55), (close, 1), (T, 1)])) * energy

# --- sfx
sfx = np.zeros(N)
def add(at, sig):
    a = int(at * SR); b = min(N, a + len(sig))
    if 0 <= a < N: sfx[a:b] += sig[:b - a]
def whoosh(d=0.45, g=0.25):
    L = int(d * SR); tt = np.arange(L) / SR; n = rng.standard_normal(L)
    n = np.convolve(n, np.ones(12) / 12, "same")
    return n * np.sin(np.pi * tt / d) ** 2 * g
def pop(g=0.22):
    L = int(0.08 * SR); tt = np.arange(L) / SR
    return np.sin(2 * np.pi * (900 - 4000 * tt) * tt) * np.exp(-tt * 60) * g
def riser(d=2.2, g=0.3):
    L = int(d * SR); tt = np.arange(L) / SR; n = np.convolve(rng.standard_normal(L), np.ones(6) / 6, "same")
    return (n * 0.6 + np.sin(2 * np.pi * (200 + 600 * (tt / d) ** 2) * tt) * 0.5) * (tt / d) ** 2 * g
def hit(g=0.9):
    L = int(1.6 * SR); tt = np.arange(L) / SR
    return (np.sin(2 * np.pi * (60 * np.exp(-tt * 3) + 38) * tt) * np.exp(-tt * 2.5) + rng.standard_normal(L) * np.exp(-tt * 30) * 0.3) * g

for s in TL["scenes"][1:]:
    add(s["t0"] - 0.2, whoosh())
for s in TL["stills"]:
    if s["i"] > 0 and s["scene"] in (4, 5, 6, 7):
        add(s["t0"], pop())
add(reveal - 2.2, riser()); add(reveal, hit())
add(close - 1.6, riser(1.6, .25)); add(close, hit(.8)); add(T - 1.4, hit(.7))

def save(name, x):
    x = np.clip(x / max(1e-9, np.abs(x).max()) * 0.8, -1, 1)
    with wave.open(str(HERE / name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype(np.int16).tobytes())
save("music.wav", music); save("sfx.wav", sfx)
print("ok", round(T, 1))
