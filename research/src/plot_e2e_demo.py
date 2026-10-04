"""Plot one workload end to end from a compare.py timeseries dump (all values from the file)."""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ts_file, res_file, out, title = sys.argv[1:5]
ts = json.load(open(ts_file))
res = json.load(open(res_file))
sid = next(iter(ts))
d = ts[sid]
thr = res["settings"]["T_threshold_C"]
P = np.array(d["_inputs"]["measured_power_W"])
fc = d["_inputs"]["forecasts"]
ml = [k for k in fc if k.startswith("ml_")]
t = np.arange(len(P)) / 60.0
# zoom on the window where the reactive controller first exceeds the threshold
Tr = np.array(d["reactive_threshold"]["timeseries"]["T_j"])
above = np.where(Tr > thr)[0]
c = above[0] if len(above) else int(np.argmax(P))
lo, hi = max(0, c - 300), min(len(P), c + 600)
sl = slice(lo, hi)
ctrls = [("reactive_threshold", "Reactive (threshold)", "#d9534f"), ("reactive_pi", "Reactive (PI)", "#f0ad4e"),
         ("predictive_persistence", "Predictive (persistence forecast)", "#5bc0de")]
if ml:
    ctrls.append((f"predictive_{ml[0]}", f"Predictive ({ml[0]})", "#2a6fdb"))
ctrls.append(("predictive_oracle", "Predictive (oracle, upper bound)", "#7a7a7a"))

fig, ax = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
ax[0].plot(t[sl], P[sl], color="k", lw=1, label="MEASURED GPU power (real trace)")
if ml:
    f30 = np.array(fc[ml[0]])[:, 0]
    ax[0].plot(t[sl] + 0.5, f30[sl], color="#2a6fdb", lw=1, alpha=0.8, label=f"PREDICTED +30 s ({ml[0]}), plotted at t+30 s")
ax[0].set_ylabel("W")
ax[0].legend(fontsize=8, loc="upper left")
for key, lab, col in ctrls:
    s = d[key]["timeseries"]
    ax[1].plot(t[sl], np.array(s["T_j"])[sl], color=col, lw=1.2, label=lab)
    ax[2].plot(t[sl], np.array(s["v"])[sl] * 100, color=col, lw=1, label=lab)
    ax[3].plot(t[sl], np.array(s["Q"])[sl], color=col, lw=1, label=lab)
ax[1].axhline(thr, color="r", ls="--", lw=1, label=f"threshold {thr} °C")
ax[1].set_ylabel("SIMULATED twin T_j (°C)")
ax[1].legend(fontsize=7, loc="upper left", ncol=2)
ax[2].set_ylabel("SIMULATED valve (%)")
ax[3].set_ylabel("SIMULATED flow (L/min)")
ax[3].set_xlabel("time in trace (min)")
import textwrap
fig.suptitle("\n".join(textwrap.wrap(title, 120)), fontsize=9)
fig.tight_layout()
fig.savefig(out, dpi=130)
print("saved", out, "window", lo, hi)
