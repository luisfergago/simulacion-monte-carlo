"""
PROPUESTA 2 — El valor de la competencia (óptica del Estado)

Caso: medicamentos cardiometabólicos del IGSS (hipertensión, colesterol, diabetes).

Pregunta: ¿cuánto le ahorra al Estado que un renglón tenga competencia, y cuánto
más ahorraría si los renglones con un solo oferente tuvieran competencia?

Pipeline simple de Monte Carlo:
  1. tomar los datos del área,
  2. limpiar (precio y total positivos),
  3. por renglón medir el ahorro frente al segundo postor,
  4. simular años por remuestreo (bootstrap) para la distribución del ahorro,
  5. leer el resultado en quetzales, con su rango, y un contrafactual acotado.

Correlación: dentro de un mismo producto, el precio ganador baja cuando hay más
competidores. Se mide con Spearman sobre el precio normalizado por producto.
"""
import json
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
K = 5000

# ---------------- 1-2. datos y limpieza ----------------
d = pd.read_csv(DATA / "propuestas.csv", dtype={"nit": str}, parse_dates=["fecha"])
d = d[(d.precio_unitario > 0) & (d.precio_total > 0)].copy()
d["prod"] = (d.nombre.str.strip() + " | " + d.caracteristicas.fillna("").str.strip()
             + " | " + d.unidad_medida.fillna("").str.strip())

# ---------------- 3. ahorro por renglón ----------------
g = d.groupby("producto_id")
win_row = d.loc[g["precio_unitario"].idxmin()].set_index("producto_id")
ren = pd.DataFrame({
    "N": g["nit"].nunique(),
    "p1": g["precio_unitario"].min(),
    "p2": g["precio_unitario"].apply(lambda s: s.nsmallest(2).iloc[-1] if len(s) >= 2 else np.nan),
    "win_total": win_row["precio_total"],
    "anio": win_row["fecha"].dt.year,
    "prod": win_row["prod"],
})
ren = ren[ren.win_total > 0]
# ahorro frente al 2º postor (acotado por el dato): lo que se habría pagado de más
ren["ahorro"] = np.where(ren.N >= 2, ren.win_total * (ren.p2 / ren.p1 - 1.0), 0.0)
ren["brecha2"] = np.where(ren.N >= 2, (ren.p2 - ren.p1) / ren.p2, np.nan)
# precio ganador normalizado por producto (para la correlación limpia)
ren["win_norm"] = ren.p1 / ren.groupby("prod")["p1"].transform("median")

n_years = int(ren.anio.nunique())
n_ren = len(ren)
year_size = n_ren // n_years
gasto_total = float(ren.win_total.sum())
ahorro_total = float(ren.ahorro.sum())
print(f"renglones={n_ren:,}  años={n_years}  renglones/año≈{year_size:,}")
print(f"gasto total ({n_years} años) = Q{gasto_total:,.0f}")
print(f"ahorro observado vs 2º postor = Q{ahorro_total:,.0f}  "
      f"({ahorro_total/gasto_total*100:.1f}% del gasto)")
print(f"sin competencia (N=1): {(ren.N==1).mean()*100:.1f}% de los renglones")

rho_price = stats.spearmanr(ren.N, ren.win_norm).statistic
rho_b2 = stats.spearmanr(ren.N, ren.brecha2, nan_policy="omit").statistic
print(f"correlación precio ganador (normalizado por producto) vs N = {rho_price:.3f}")
print(f"  (nota: brecha2 vs N = {rho_b2:.3f}, marginal, baja al empacarse las 2 más bajas)")

# ---------------- 4. Monte Carlo: distribución del ahorro anual ----------------
ah = ren.ahorro.values
sim_year = np.array([ah[rng.integers(0, n_ren, size=year_size)].sum() for _ in range(K)])
p5, p50, p95 = np.percentile(sim_year, [5, 50, 95])
print(f"\nAhorro ANUAL simulado por competencia (bootstrap):")
print(f"  mediana=Q{p50:,.0f}   P5=Q{p5:,.0f}   P95=Q{p95:,.0f}")

# ---------------- contrafactual ACOTADO: sole-source con competencia ----------------
# descuento que la competencia logra vs el 2º postor (acotado, robusto)
b25, b50, b75 = np.nanpercentile(ren.brecha2, [25, 50, 75])
sole_spend = float(ren.loc[ren.N == 1, "win_total"].sum())
sole_spend_year = sole_spend / n_years
extra_med = sole_spend_year * b50
extra_lo, extra_hi = sole_spend_year * b25, sole_spend_year * b75
print(f"\nContrafactual acotado (los N=1 logran el descuento mediano {b50*100:.1f}%):")
print(f"  gasto anual sin competencia = Q{sole_spend_year:,.0f}")
print(f"  ahorro EXTRA anual = Q{extra_med:,.0f}  (rango Q{extra_lo:,.0f} .. Q{extra_hi:,.0f})")
print(f"  ahorro anual potencial = Q{p50+extra_med:,.0f}  (x{(p50+extra_med)/p50:.1f} vs actual)")

# ---------------- 5. salidas ----------------
ren.reset_index()[["producto_id", "N", "p1", "p2", "win_total", "brecha2", "win_norm", "ahorro", "anio"]]\
   .to_csv(OUT / "p2_matriz.csv", index=False)

fig, ax = plt.subplots(figsize=(7.8, 4.3))
ax.hist(sim_year / 1e6, bins=50, color="#2ca02c", alpha=0.8)
ax.axvline(p50 / 1e6, color="k", ls="--", label=f"mediana Q{p50/1e6:.0f} M")
ax.axvline(p5 / 1e6, color="gray", ls=":", label="P5–P95")
ax.axvline(p95 / 1e6, color="gray", ls=":")
ax.set_xlabel("ahorro anual por competencia (millones de Q)")
ax.set_ylabel("frecuencia (años simulados)")
ax.set_title("Propuesta 2 — Ahorro anual del IGSS por competencia (cardiometabólicos)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_p2_ahorro.png", dpi=110)

fig, ax = plt.subplots(figsize=(7, 4.3))
ax.bar(["actual\n(competencia real)", "potencial\n(+ sole-source con competencia)"],
       [p50 / 1e6, (p50 + extra_med) / 1e6], color=["#2ca02c", "#98df8a"])
ax.set_ylabel("ahorro anual (millones de Q)")
ax.set_title("Propuesta 2 — Ahorro actual vs potencial con más competencia")
fig.tight_layout()
fig.savefig(OUT / "fig_p2_contrafactual.png", dpi=110)

json.dump({
    "renglones": n_ren, "anios": n_years, "gasto_total_Q": gasto_total,
    "ahorro_observado_Q": ahorro_total, "ahorro_pct": ahorro_total / gasto_total,
    "pct_sin_competencia": float((ren.N == 1).mean()),
    "corr_precio_norm_vs_N_spearman": float(rho_price),
    "corr_brecha2_vs_N_spearman": float(rho_b2),
    "ahorro_anual_mediana_Q": float(p50), "ahorro_anual_P5_Q": float(p5), "ahorro_anual_P95_Q": float(p95),
    "descuento_competencia_mediano": float(b50),
    "contrafactual_extra_anual_Q": float(extra_med),
    "contrafactual_extra_rango_Q": [float(extra_lo), float(extra_hi)],
    "ahorro_anual_potencial_Q": float(p50 + extra_med),
}, open(OUT / "p2_resultados.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("\nOK -> p2_matriz.csv, p2_resultados.json, fig_p2_ahorro.png, fig_p2_contrafactual.png")
