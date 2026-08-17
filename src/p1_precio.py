"""
PROPUESTA 1 — ¿A qué precio ofertar para ganar? (óptica del proveedor)

Caso concreto: Insulina glargina en el IGSS, un producto con miles de concursos.

Pipeline simple de Monte Carlo:
  1. tomar los datos del producto (una presentación),
  2. limpiar (precio positivo),
  3. ajustar distribuciones de entrada desde el dato,
  4. simular muchas licitaciones y ver a qué precio conviene ofertar,
  5. leer el resultado (probabilidad de ganar y precio óptimo).

Variables de entrada:
  - N, número de competidores por concurso, de su distribución empírica.
  - precio de cada oferta rival, LogNormal ajustada al histórico del producto.
  - mi costo unitario, supuesto declarado (fracción del precio típico).

Correlación: el precio ganador baja cuando hay más competidores. Se mide en el
dato (coeficiente de Spearman) y el modelo la reproduce porque gana el mínimo.

Salida: P(ganar) según mi precio, el precio óptimo y la ganancia esperada.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

BASE = Path(__file__).resolve().parent.parent
OUT, DATA = BASE / "output", BASE / "data"
rng = np.random.default_rng(20260810)

PRODUCTO = "glargina"           # Insulina glargina
COSTO_FRAC = 0.75               # mi costo = 75% del precio ganador mediano (supuesto)
M = 100_000

# ---------------- 1-2. datos y limpieza ----------------
d = pd.read_csv(DATA / "propuestas.csv", dtype={"nit": str})
d = d[d.nombre.str.lower().str.contains(PRODUCTO) & (d.precio_unitario > 0)].copy()
# presentación dominante (mismo producto, sin mezclar concentraciones)
d["pres"] = d.caracteristicas.fillna("").str.strip() + " | " + d.unidad_medida.fillna("")
dom = d.groupby("pres")["nog"].nunique().idxmax()
d = d[d.pres == dom].copy()
print(f"Producto: Insulina glargina")
print(f"Presentación dominante: {dom[:80]}")
print(f"Ofertas: {len(d):,} | concursos: {d.nog.nunique():,}")

# ---------------- 3. ajustar distribuciones de entrada ----------------
# N por concurso (competidores distintos)
Nporconc = d.groupby("nog")["nit"].nunique()
Nvals, Ncnt = np.unique(Nporconc.values, return_counts=True)
Nprob = Ncnt / Ncnt.sum()
print(f"\nN competidores: media={Nporconc.mean():.2f}  "
      f"P(N=1)={Nprob[Nvals==1][0] if 1 in Nvals else 0:.2f}")

# precio de una oferta ~ LogNormal
precios = d.precio_unitario.values
s, loc, scale = stats.lognorm.fit(precios, floc=0)
mediana = float(np.median(precios))
COSTO = COSTO_FRAC * mediana
print(f"Precio de oferta ~ LogNormal(sigma={s:.3f}, mediana=Q{scale:.2f})")
print(f"Precio ganador mediano observado=Q{d.groupby('nog').precio_unitario.min().median():.2f}")
print(f"Mi costo (supuesto {COSTO_FRAC:.0%} del precio mediano)=Q{COSTO:.2f}")

# ---------------- correlación precio ganador vs N (evidencia) ----------------
gan = d.groupby("nog").agg(win=("precio_unitario", "min"),
                           N=("nit", "nunique"))
rho_s = stats.spearmanr(gan.N, gan.win).statistic
print(f"\nCorrelación precio ganador vs N (Spearman) = {rho_s:.3f}  (negativa esperada)")

# ---------------- 4. simulación Monte Carlo ----------------
# min de las ofertas rivales por concurso
Nsim = rng.choice(Nvals, size=M, p=Nprob)
min_rival = np.empty(M)
for n in np.unique(Nsim):
    idx = np.where(Nsim == n)[0]
    off = stats.lognorm.rvs(s, loc=0, scale=scale, size=(len(idx), int(n)),
                            random_state=rng)
    min_rival[idx] = off.min(axis=1)

grid = np.round(np.linspace(np.percentile(precios, 2), np.percentile(precios, 80), 70), 2)
pganar = np.array([(min_rival > p).mean() for p in grid])
ganancia = pganar * (grid - COSTO)
jopt = int(np.argmax(ganancia))
p_opt = float(grid[jopt])
print(f"\nPrecio óptimo p* = Q{p_opt:.2f}")
print(f"  P(ganar|p*) = {pganar[jopt]:.3f}")
print(f"  ganancia esperada por unidad = Q{ganancia[jopt]:.2f}")

# ---------------- 5. matriz de simulación en p* + salidas ----------------
gane = min_rival > p_opt
margen = np.where(gane, p_opt - COSTO, 0.0)
se = margen.std(ddof=1) / np.sqrt(M)
matriz = pd.DataFrame({
    "iter": np.arange(1, M + 1),
    "N_rivales": Nsim,
    "min_oferta_rival_Q": np.round(min_rival, 2),
    "mi_precio_Q": p_opt,
    "mi_costo_Q": round(COSTO, 2),
    "gane": gane.astype(int),
    "ganancia_Q": np.round(margen, 2),
}).head(50000)
matriz.to_csv(OUT / "p1_matriz.csv", index=False)
print(f"  ganancia esperada (EE MC) = Q{margen.mean():.2f} ± {se:.3f}")

# ---- figuras ----
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
ax[0].plot(grid, pganar, color="#1f77b4")
ax[0].axvline(p_opt, color="g", ls="--", label=f"p*=Q{p_opt:.2f}")
ax[0].axvline(COSTO, color="r", ls=":", label=f"costo=Q{COSTO:.2f}")
ax[0].set_xlabel("mi precio (Q)"); ax[0].set_ylabel("P(ganar)")
ax[0].set_title("Probabilidad de ganar vs mi precio"); ax[0].legend()
ax[1].plot(grid, ganancia, color="#137")
ax[1].axvline(p_opt, color="g", ls="--", label=f"p*=Q{p_opt:.2f}")
ax[1].axhline(0, color="k", lw=0.6)
ax[1].set_xlabel("mi precio (Q)"); ax[1].set_ylabel("ganancia esperada por unidad (Q)")
ax[1].set_title("Ganancia esperada y precio óptimo"); ax[1].legend()
fig.suptitle("Propuesta 1 — Insulina glargina: estrategia de precio (IGSS)")
fig.tight_layout()
fig.savefig(OUT / "fig_p1_precio.png", dpi=110)

# convergencia
fig, ax = plt.subplots(figsize=(7.5, 4))
run = np.cumsum(margen) / np.arange(1, M + 1)
ax.plot(np.arange(1, M + 1), run, color="#137", lw=1)
ax.axhline(margen.mean(), color="r", ls="--", label=f"media=Q{margen.mean():.2f}")
ax.set_xlabel("iteraciones"); ax.set_ylabel("ganancia media acumulada (Q)")
ax.set_title("Propuesta 1 — Convergencia Monte Carlo"); ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_p1_convergencia.png", dpi=110)

json.dump({
    "producto": "Insulina glargina", "presentacion": dom,
    "n_ofertas": int(len(d)), "n_concursos": int(d.nog.nunique()),
    "N_medio": float(Nporconc.mean()),
    "lognormal_sigma": float(s), "lognormal_mediana": float(scale),
    "costo_supuesto_Q": float(COSTO),
    "corr_precio_vs_N_spearman": float(rho_s),
    "precio_optimo_Q": p_opt, "P_ganar_opt": float(pganar[jopt]),
    "ganancia_esperada_Q": float(ganancia[jopt]), "EE_MC": float(se),
}, open(OUT / "p1_resultados.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("\nOK -> p1_matriz.csv, p1_resultados.json, fig_p1_precio.png, fig_p1_convergencia.png")
