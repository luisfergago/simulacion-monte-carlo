"""
IDEA 3 — Efecto de la competencia en el gasto público (ahorro del Estado).

Motor: engine.py (cópula de un factor, ganador = mínimo de N ofertas).

MÉTRICA PRINCIPAL (robusta, estándar en subastas): "dinero dejado sobre la mesa"
respecto al segundo mejor postor:
        brecha2 = (P2 - P1) / P2
Es lo que el Estado se ahorra gracias a que el ganador vino a competir contra el
runner-up. No depende de la cola alta de ofertas (a diferencia de "vs promedio"),
se mide directo del histórico y el motor la reproduce.

Hallazgo de contexto (no se simula, es dato): el 54% de los renglones NO tiene
competencia (N=1). Ese es el mayor cuello de botella del ahorro público.

Experimentos:
  A. brecha2 esperada por nivel de competencia N, observada vs simulada, y
     barrido de rho (colusión) que muestra cómo se erosiona el ahorro.
  B. Matriz de simulación + agregado de "dinero sobre la mesa" con montos reales.
  C. Bandera de colusión: renglones con N alto pero CV bajo (ofertas casi iguales).

Salidas:
  output/idea3_matriz.csv, output/idea3_resultados.json y 3 figuras.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

OUT, DATA = E.OUT, E.DATA
RHO = float(E._P.get("rho_estimado", 0.0))
N_ITERS = 100_000
rng = np.random.default_rng(2026)


def two_lowest(off):
    """Devuelve (P1, P2) = dos ofertas más bajas por fila de una matriz (m,N>=2)."""
    part = np.partition(off, 1, axis=1)[:, :2]
    p1 = part.min(axis=1)
    p2 = part.max(axis=1)
    return p1, p2


def sim_gap2_by_N(n, rho, m=40000):
    off = E.offers_block(m, n, rho, rng)
    p1, p2 = two_lowest(off)
    return float(np.mean((p2 - p1) / p2))


# =====================================================================
# DATOS REALES
# =====================================================================
# nivel renglón (para fracción sin competencia y montos reales)
r = pd.read_csv(DATA / "renglones_salud.csv")
r = r[(r.precio_min > 0) & (r.precio_avg > 0) & (r.unidades_demanda > 0)].copy()
r["N"] = r.n_ofertas.astype(int)
r["cv"] = r.precio_sd / r.precio_avg
r["line_min"] = r.precio_min * r.unidades_demanda
frac_sin_comp = float((r.N == 1).mean())
print(f"[DATO] renglones: {len(r):,} | sin competencia (N=1): {frac_sin_comp*100:.1f}%")

# nivel oferta (para brecha2 observada = (P2-P1)/P2)
o = pd.read_csv(DATA / "ofertas_muestra.csv")
o = o[o.precio_unitario > 0].copy()
o = o.sort_values(["producto", "precio_unitario"])
o["rk"] = o.groupby("producto").cumcount()
Ncount = o.groupby("producto").size().rename("Nreal")
piv = (o[o.rk < 2].pivot_table(index="producto", columns="rk",
                               values="precio_unitario"))
piv = piv.join(Ncount)
piv = piv[piv[1].notna()].copy()            # N>=2
piv["gap2"] = (piv[1] - piv[0]) / piv[1]
obs_gap2_overall = float(piv["gap2"].mean())
print(f"[DATO] brecha2 observada (N>=2): media={obs_gap2_overall*100:.1f}%  "
      f"mediana={piv['gap2'].median()*100:.1f}%  (n={len(piv):,} renglones)")

# =====================================================================
# A. brecha2 por N: observada vs simulada + barrido de rho
# =====================================================================
print("\n[A] brecha2 por N (observada vs simulada) y barrido de rho...")
Ns = list(range(2, 13))
obs_gap2 = [float(piv.loc[piv.Nreal == n, "gap2"].median()) for n in Ns]
rhos = [0.0, 0.3, 0.6, 0.9]
curve = {rho: [sim_gap2_by_N(n, rho) for n in Ns] for rho in rhos}
print(f"{'N':>3} {'obs':>7} " + " ".join(f"rho={x:<4}" for x in rhos))
for i, n in enumerate(Ns):
    print(f"{n:>3} {obs_gap2[i]:>7.3f} " +
          " ".join(f"{curve[x][i]:>7.3f}" for x in rhos))

# =====================================================================
# B. Matriz de simulación + agregado de dinero sobre la mesa
# =====================================================================
print(f"\n[B] Simulando {N_ITERS:,} renglones (rho={RHO}) + bootstrap de montos...")
N = E.sample_N(N_ITERS, rng).astype(int)
p1n = np.ones(N_ITERS)      # ganador normalizado
p2n = np.ones(N_ITERS)      # runner-up normalizado
meann = np.ones(N_ITERS)
for n in np.unique(N):
    if n < 2:
        continue
    idx = np.where(N == n)[0]
    off = E.offers_block(len(idx), int(n), RHO, rng)
    a, b = two_lowest(off)
    p1n[idx], p2n[idx], meann[idx] = a, b, off.mean(axis=1)
gap2 = np.where(N >= 2, (p2n - p1n) / p2n, 0.0)       # sobre la mesa vs runner-up
gap_avg = np.where(N >= 2, 1.0 - p1n / meann, 0.0)     # vs promedio (referencia)

# bootstrap de montos reales del ganador (line_min) para el agregado absoluto
boot = rng.integers(0, len(r), size=N_ITERS)
paid = (r.line_min.values)[boot]                       # lo que se pagó (real)
money_table = gap2 / np.maximum(1e-9, 1 - gap2) * paid  # (P2-P1)/P1 * pagado

matriz = pd.DataFrame({
    "iter": np.arange(1, N_ITERS + 1),
    "N_competidores": N,
    "ganador_norm": np.round(p1n, 5),
    "runnerup_norm": np.round(p2n, 5),
    "media_norm": np.round(meann, 5),
    "brecha2_vs_runnerup": np.round(gap2, 5),
    "brecha_vs_promedio": np.round(gap_avg, 5),
    "pagado_real_Q": np.round(paid, 2),
    "dinero_sobre_la_mesa_Q": np.round(money_table, 2),
})
matriz.to_csv(OUT / "idea3_matriz.csv", index=False)

mean_g2 = float(gap2.mean())
se_g2 = float(gap2.std(ddof=1) / np.sqrt(N_ITERS))
g2_comp = gap2[N >= 2]
print(f"    brecha2 media (todos los renglones) = {mean_g2*100:.2f}%  (EE ±{se_g2*100:.3f} pp)")
print(f"    brecha2 media (solo N>=2)            = {g2_comp.mean()*100:.2f}%")
print(f"    dinero sobre la mesa medio/renglón   = Q{money_table.mean():,.0f}")

# =====================================================================
# C. Bandera de colusión
# =====================================================================
r2 = r[r.N >= 2]
susp = r2[(r2.N >= 4) & (r2.cv < 0.05)]
print(f"\n[C] Colusión (N>=4 y CV<0.05): {len(susp):,} renglones "
      f"({len(susp)/max(1,len(r2[r2.N>=4]))*100:.2f}% de los N>=4)")

# =====================================================================
# FIGURAS
# =====================================================================
fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.plot(Ns, [x * 100 for x in obs_gap2], "ko-", lw=2, label="observado (dato)")
for rho in rhos:
    ax.plot(Ns, [x * 100 for x in curve[rho]], "--", label=f"simulado ρ={rho}")
ax.set_xlabel("N competidores en el renglón")
ax.set_ylabel("brecha vs runner-up (P2−P1)/P2  (%)")
ax.set_title("Idea 3 — Ahorro marginal por competencia\n(se erosiona cuando hay colusión ρ→1)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_idea3_ahorro_vs_n.png", dpi=110)

fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.hist(g2_comp * 100, bins=60, color="#3a7", alpha=0.75)
ax.axvline(g2_comp.mean() * 100, color="k", ls="--",
           label=f"media {g2_comp.mean()*100:.1f}%")
ax.set_xlabel("brecha2 (%) en renglones con competencia")
ax.set_ylabel("frecuencia (renglones simulados)")
ax.set_title(f"Idea 3 — Distribución del ahorro vs runner-up (N>=2, ρ={RHO})")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_idea3_hist.png", dpi=110)

fig, ax = plt.subplots(figsize=(7.5, 4.5))
run = np.cumsum(gap2) / np.arange(1, N_ITERS + 1)
ks = np.linspace(100, N_ITERS, 200).astype(int)
run_se = np.array([gap2[:k].std(ddof=1) / np.sqrt(k) for k in ks])
ax.plot(np.arange(1, N_ITERS + 1), run * 100, color="#137", lw=1)
ax.fill_between(ks, (run[ks - 1] - 1.96 * run_se) * 100,
                (run[ks - 1] + 1.96 * run_se) * 100, color="#137", alpha=0.2)
ax.set_xlabel("iteraciones")
ax.set_ylabel("brecha2 media acumulada (%)")
ax.set_title("Idea 3 — Convergencia Monte Carlo (media ± 1.96·EE)")
fig.tight_layout()
fig.savefig(OUT / "fig_idea3_convergencia.png", dpi=110)

# =====================================================================
# RESULTADOS
# =====================================================================
res = {
    "rho_usado": RHO, "n_iters": N_ITERS,
    "frac_sin_competencia_N1": frac_sin_comp,
    "observado": {
        "brecha2_media_N>=2": obs_gap2_overall,
        "brecha2_por_N": {n: g for n, g in zip(Ns, obs_gap2)},
    },
    "simulado": {
        "brecha2_media_todos": mean_g2,
        "brecha2_media_N>=2": float(g2_comp.mean()),
        "brecha2_EE_MC": se_g2,
        "dinero_sobre_la_mesa_Q_medio": float(money_table.mean()),
        "brecha2_por_N_por_rho": {str(k): v for k, v in curve.items()},
    },
    "colusion_flag": {"n_sospechosos": int(len(susp))},
}
json.dump(res, open(OUT / "idea3_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"\nOK -> idea3_matriz.csv ({N_ITERS:,} filas), idea3_resultados.json, 3 figuras.")
