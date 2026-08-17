"""
Propuesta 1 - ¿de qué depende el precio óptimo? Sensibilidad al margen bruto supuesto.

Muestra dos cosas:
  A. cómo cambian el precio óptimo, P(ganar) y la ganancia esperada según el margen
     bruto supuesto (que ancla el costo = mediana − margen). Caso base: 30%.
  B. el trade-off: si en vez de maximizar ganancia fijo una meta de P(ganar),
     qué precio y qué ganancia obtengo (a margen 30%).
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
rng = np.random.default_rng(20260810)
M = 100_000

d = pd.read_csv(DATA / "propuestas.csv", dtype={"nit": str})
d = d[d.nombre.str.lower().str.contains("glargina") & (d.precio_unitario > 0)].copy()
d["pres"] = d.caracteristicas.fillna("").str.strip() + " | " + d.unidad_medida.fillna("")
d = d[d.pres == d.groupby("pres")["nog"].nunique().idxmax()]
precios = d.precio_unitario.values
s, _, scale = stats.lognorm.fit(precios, floc=0)
mediana = float(np.median(precios))

Nporconc = d.groupby("nog")["nit"].nunique()
Nv, Nc = np.unique(Nporconc.values, return_counts=True)
Np = Nc / Nc.sum()
comp = Nv >= 2                              # el óptimo solo aplica donde hay competencia
Nvc, Npc = Nv[comp], Np[comp] / Np[comp].sum()
Nsim = rng.choice(Nvc, size=M, p=Npc)
min_rival = np.empty(M)
for n in np.unique(Nsim):
    idx = np.where(Nsim == n)[0]
    off = stats.lognorm.rvs(s, scale=scale, size=(len(idx), int(n) - 1), random_state=rng)  # N-1 rivales
    min_rival[idx] = off.min(axis=1)

grid = np.round(np.linspace(np.percentile(precios, 1), np.percentile(precios, 90), 120), 2)
pwin = np.array([(min_rival > p).mean() for p in grid])

print(f"Insulina glargina | precio mediano Q{mediana:.0f} | N medio {Nporconc.mean():.2f}\n")
print("A. Precio óptimo (máx ganancia esperada) según el margen bruto supuesto:")
print(f"{'margen':>8} {'costo':>9} {'p*':>10} {'P(ganar|p*)':>13} {'ganancia/u':>12}")
for margen in [0.20, 0.25, 0.30, 0.35, 0.45]:
    c = (1 - margen) * mediana
    prof = pwin * (grid - c)
    j = int(np.argmax(prof))
    marca = "  <- caso base" if abs(margen - 0.30) < 1e-9 else ""
    print(f"  {margen:>5.0%}  Q{c:>7.0f}  Q{grid[j]:>8.2f} {pwin[j]:>12.2f}  Q{prof[j]:>10.2f}{marca}")

c = (1 - 0.30) * mediana
print(f"\nB. Trade-off a margen 30% (costo Q{c:.0f}): si fijas una meta de P(ganar):")
print(f"{'meta P(ganar)':>16} {'precio':>10} {'ganancia/u':>12}")
for meta in [0.55, 0.70, 0.85, 0.95]:
    j = int(np.argmin(np.abs(pwin - meta)))
    print(f"  {meta:>13.2f}  Q{grid[j]:>7.2f}   Q{(grid[j]-c):>8.2f}  (ganancia esperada Q{pwin[j]*(grid[j]-c):.2f})")
