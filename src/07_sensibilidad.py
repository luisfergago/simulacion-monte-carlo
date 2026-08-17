"""
ANÁLISIS DE SENSIBILIDAD (tornado) para las Ideas 1 y 3.

Método: one-at-a-time. Se fija cada entrada en su valor base y se mueve a un
extremo bajo y uno alto (dejando las demás en base), midiendo cuánto cambia la
salida. Se usan NÚMEROS ALEATORIOS COMUNES (misma semilla en cada evaluación)
para que la diferencia refleje el efecto de la entrada y no ruido Monte Carlo.

Idea 1 (salida: ganancia esperada en el precio óptimo, mezcla de rivales):
  entradas: costo, sigma, rho, p_admit, competencia (desplazamiento de N).
Idea 3 (salida: brecha2 media = (P2-P1)/P2 en renglones con N>=2):
  entradas: sigma, rho, competencia.

Salidas: output/sensibilidad_resultados.json,
         output/fig_tornado_idea1.png, output/fig_tornado_idea3.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

OUT = E.OUT
SEED = 2026
M = 60000
PGRID = np.round(np.arange(0.50, 1.301, 0.01), 3)

# valores base (de la calibración)
BASE = {
    "costo": 0.75,
    "sigma": float(E._P.get("sigma_fija", 0.209)),
    "rho": float(E._P.get("rho_estimado", 0.0)),
    "p_admit": 0.99,
    "nshift": 0,      # desplazamiento del nº de rivales respecto a la mezcla real
}
# rangos (bajo, alto) para cada entrada
RANGES = {
    "costo": (0.65, 0.85),
    "sigma": (0.15, 0.30),
    "rho": (0.0, 0.6),
    "p_admit": (0.70, 1.00),
    "nshift": (-1, 1),
}
NICE = {"costo": "costo propio c", "sigma": "dispersión σ", "rho": "correlación ρ",
        "p_admit": "admisión", "nshift": "competencia (±1 rival)"}


def _rng():
    return np.random.default_rng(SEED)


def rival_min(N, rho, sigma, rng):
    mmin = np.full(len(N), np.inf)
    for n in np.unique(N):
        if n <= 0:
            continue
        idx = np.where(N == n)[0]
        off = E.offers_block(len(idx), int(n), rho, rng, sigma=sigma)
        mmin[idx] = off.min(axis=1)
    return mmin


def idea1_Estar(costo, sigma, rho, p_admit, nshift):
    rng = _rng()
    N = np.clip(E.sample_N(M, rng).astype(int) + nshift, 0, None)
    mmin = rival_min(N, rho, sigma, rng)
    pw = p_admit * (mmin[:, None] > PGRID[None, :]).mean(axis=0)
    profit = pw * (PGRID - costo)
    return float(profit.max())


def idea3_brecha2(sigma, rho, nshift):
    rng = _rng()
    N = np.clip(E.sample_N(M, rng).astype(int) + nshift, 0, None)
    vals = []
    for n in np.unique(N):
        if n < 2:
            continue
        idx = np.where(N == n)[0]
        off = E.offers_block(len(idx), int(n), rho, rng, sigma=sigma)
        p1, p2 = E.two_lowest(off)
        vals.append((p2 - p1) / p2)
    return float(np.concatenate(vals).mean())


def tornado(fn, inputs, base):
    b = fn(**base)
    rows = []
    for k in inputs:
        lo_args = dict(base); lo_args[k] = RANGES[k][0]
        hi_args = dict(base); hi_args[k] = RANGES[k][1]
        lo, hi = fn(**lo_args), fn(**hi_args)
        rows.append((k, lo, hi, abs(hi - lo)))
    rows.sort(key=lambda r: r[3])
    return b, rows


def plot_tornado(base_val, rows, title, xlabel, path, pct=False):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for i, (k, lo, hi, _) in enumerate(rows):
        left, right = min(lo, hi), max(lo, hi)
        ax.barh(i, right - left, left=left, color="#4C78A8", alpha=0.85)
        f = (lambda v: f"{v*100:.1f}%") if pct else (lambda v: f"{v:.3f}")
        ax.text(left, i, f" {f(lo)}", va="center", ha="right", fontsize=8)
        ax.text(right, i, f"{f(hi)} ", va="center", ha="left", fontsize=8)
    ax.axvline(base_val, color="k", ls="--", lw=1, label=f"base={base_val:.3f}")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([NICE[k] for k, *_ in rows])
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=110)


# ---------------- Idea 1 ----------------
print("Tornado Idea 1 (salida = ganancia esperada en p*)...")
b1, rows1 = tornado(idea1_Estar, ["costo", "sigma", "rho", "p_admit", "nshift"], BASE)
print(f"  base E*={b1:.4f}")
for k, lo, hi, sw in rows1:
    print(f"  {NICE[k]:>26}: [{lo:.4f} .. {hi:.4f}]  swing={sw:.4f}")
plot_tornado(b1, rows1, "Idea 1 — Sensibilidad de la ganancia esperada",
             "ganancia esperada por unidad (fracción de la referencia)",
             OUT / "fig_tornado_idea1.png")

# ---------------- Idea 3 ----------------
print("\nTornado Idea 3 (salida = brecha2 media, N>=2)...")
base3 = {"sigma": BASE["sigma"], "rho": BASE["rho"], "nshift": BASE["nshift"]}
b3, rows3 = tornado(idea3_brecha2, ["sigma", "rho", "nshift"], base3)
print(f"  base brecha2={b3:.4f}")
for k, lo, hi, sw in rows3:
    print(f"  {NICE[k]:>26}: [{lo:.4f} .. {hi:.4f}]  swing={sw:.4f}")
plot_tornado(b3, rows3, "Idea 3 — Sensibilidad del ahorro (brecha vs 2º postor)",
             "brecha2 media (N>=2)", OUT / "fig_tornado_idea3.png", pct=True)

# ---------------- guardar ----------------
res = {
    "base_idea1_Estar": b1,
    "tornado_idea1": [{"input": k, "bajo": lo, "alto": hi, "swing": sw}
                      for k, lo, hi, sw in rows1],
    "base_idea3_brecha2": b3,
    "tornado_idea3": [{"input": k, "bajo": lo, "alto": hi, "swing": sw}
                      for k, lo, hi, sw in rows3],
    "rangos": RANGES,
}
json.dump(res, open(OUT / "sensibilidad_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print("\nOK -> sensibilidad_resultados.json, fig_tornado_idea1.png, fig_tornado_idea3.png")
