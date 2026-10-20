"""PCA of node position snapshots (T6 *_snap.csv): the dominant motion pattern of a residual oscillation and where it
lives (per node family amplitude, rigid vs deformation share). Usage: snap_modes.py docs/p3/validation/T6_drop_snap.csv"""
import csv, json, re, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
g = json.loads((ROOT / "sim/vehicle/hellcat/geometry.json").read_text())
names = [n["name"] for n in g["nodes"]]
parts = [n["part"] for n in g["nodes"]]
fam = lambda n: re.split(r"\d", n, 1)[0].rstrip("_")
data = np.loadtxt(sys.argv[1], delimiter=",", skiprows=1)
ts = np.unique(data[:, 0])
N = int(data[:, 1].max()) + 1
X = np.zeros((len(ts), N, 3))
for k, t in enumerate(ts):
    rows = data[data[:, 0] == t]
    X[k, rows[:, 1].astype(int)] = rows[:, 2:5]
D = X - X.mean(0)
A = D.reshape(len(ts), -1)
U, S, Vt = np.linalg.svd(A, full_matrices=False)
print(f"{len(ts)} snapshots, dt {ts[1]-ts[0]:.3f} s; singular values {np.round(S[:5], 4)}")
for c in range(3):
    shape = Vt[c].reshape(N, 3)
    amp = np.linalg.norm(shape, axis=1) * S[c] / np.sqrt(len(ts))
    tc = U[:, c] * S[c]
    # dominant frequency of the time coefficient
    f = np.fft.rfftfreq(len(ts) * 8, ts[1] - ts[0])
    P = np.abs(np.fft.rfft(tc - tc.mean(), n=len(ts) * 8))
    fk = f[np.argmax(P[1:]) + 1]
    agg = defaultdict(lambda: np.zeros(3)); am = defaultdict(float); cnt = defaultdict(int)
    for i in range(N):
        agg[fam(names[i])] += shape[i] * S[c] / np.sqrt(len(ts)); am[fam(names[i])] += amp[i]; cnt[fam(names[i])] += 1
    top = sorted(am, key=lambda q: -am[q] / cnt[q])[:10]
    print(f"component {c}: rms {S[c]/np.sqrt(len(ts))*1000:.2f} mm (all nodes), ~{fk:.2f} Hz")
    for q in top:
        v = agg[q] / cnt[q] * 1000
        print(f"   {q:16s} rms amp {am[q]/cnt[q]*1000:6.2f} mm  mean dir (x right, y up, z fwd) {np.round(v, 2)}")
    # wheel family summary
    wf = {q: am[q] / cnt[q] * 1000 for q in am if q.startswith(("FL_", "FR_", "RL_", "RR_"))}
    print("   wheels:", ", ".join(f"{q} {v:.2f}" for q, v in sorted(wf.items(), key=lambda kv: -kv[1])[:8]))
