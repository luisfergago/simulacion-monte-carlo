"""
IDEA 1 — Estrategia de oferta: ¿a qué precio ofertar para ganar?

Perspectiva: un proveedor decide su precio en un renglón.
Modelo de DOS ETAPAS (hurdle):
  Etapa 1 (admisión): con probabilidad p_admit el proveedor, siendo el más barato,
    efectivamente gana (pasa requisitos/evaluación). ESTIMADA DE DATOS en
    src/06_admision.py: P(ganar|más barato) ~ 0.99 y NO cambia con la novedad del
    proveedor, entonces la usamos como compuerta única y realista.
  Etapa 2 (precio): entre los admitidos gana el de MENOR precio. Los rivales
    presentan ofertas vía el motor común (engine.py).

Todo en espacio normalizado: precio de referencia del mercado = 1. Mi precio p y
mi costo c se expresan como fracción de esa referencia.

Variables de entrada:
  - N_riv : nº de rivales que enfrento  (~ distribución empírica de competidores)
  - oferta de cada rival  (LogNormal sigma fija, cópula de un factor con rho)
  - mi costo unitario c   (fracción de la referencia; decisión del negocio)
  - p_admit : P(ganar|más barato) estimada de datos (~0.99, plana por novedad)

Salidas:
  - P(ganar | mi precio)         curva de probabilidad vs precio
  - E[ganancia | mi precio]      y el PRECIO ÓPTIMO p*
  - p* y ganancia esperada según N_riv; efecto (nulo) de la novedad
  - matriz de simulación de una estrategia concreta

Archivos:
  output/idea1_matriz.csv, output/idea1_resultados.json y 3 figuras.
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
SIGMA = float(E._P.get("sigma_fija", 0.209))
rng = np.random.default_rng(4)

COST = 0.75           # mi costo unitario = 75% de la referencia de mercado
# Admisión estimada de datos (src/06_admision.py): P(ganar|más barato) ~ 0.99 y
# NO cambia con la novedad del proveedor. Compuerta única y realista.
_adm = json.load(open(OUT / "admision_resultados.json", encoding="utf-8"))
P_ADMIT = float(_adm["P_ganar_lowest_establecido"])       # ~0.99 (data-driven)
P_ADMIT_NUEVO_DATO = float(_adm["P_ganar_lowest_nuevo"])  # ~0.99-1.00 (data-driven)
P_ADMIT_HIPOT = 0.70   # what-if: proveedor propenso a descalificación (sensibilidad)
N_ITERS = 100_000
PGRID = np.round(np.arange(0.50, 1.301, 0.01), 3)


def rival_min(N_riv, rho, rng):
    """Precio mínimo entre los rivales por iteración (inf si no hay rivales)."""
    mmin = np.full(len(N_riv), np.inf)
    for n in np.unique(N_riv):
        idx = np.where(N_riv == n)[0]
        if n <= 0:
            continue
        off = E.offers_block(len(idx), int(n), rho, rng)
        mmin[idx] = off.min(axis=1)
    return mmin


def pwin_curve(mmin, pgrid, p_admit):
    """P(ganar|precio) = p_admit * P(min_rival > precio)."""
    m = mmin[:, None] > pgrid[None, :]
    return p_admit * m.mean(axis=0)


# =====================================================================
# Validación con datos: P(ganar | ser el más barato) ~ 0.99
# =====================================================================
o = pd.read_csv(DATA / "ofertas_muestra.csv")
o["win"] = o.estado.fillna("").str.startswith("Adjudicaci")
sub = o[(o.estado.notna()) & (o.ranking_de_precio == 1)]
p_low_wins = float(sub.win.mean())
print(f"[DATO] P(ganar | fuiste el más barato) = {p_low_wins:.3f}  (n={len(sub):,})")
print(f"       compuerta de admisión data-driven = {P_ADMIT:.3f} (plana por novedad)")

# =====================================================================
# A. P(ganar|precio) por escenario de rivales (admisión = 1, precio puro)
# =====================================================================
print("\n[A] P(ganar|precio) por nº de rivales (admisión=1)...")
scen = {}
for nriv in [1, 3, 6]:
    mmin = rival_min(np.full(60000, nriv), RHO, rng)
    scen[nriv] = pwin_curve(mmin, PGRID, 1.0)
# mezcla empírica de rivales
N_riv_mix = E.sample_N(N_ITERS, rng).astype(int)
mmin_mix = rival_min(N_riv_mix, RHO, rng)
pwin_mix = pwin_curve(mmin_mix, PGRID, 1.0)
for p_show in [0.7, 0.8, 0.9, 1.0]:
    j = int(np.argmin(np.abs(PGRID - p_show)))
    print(f"    precio={p_show:.2f} -> P(ganar) rivales(1/3/6)="
          f"{scen[1][j]:.2f}/{scen[3][j]:.2f}/{scen[6][j]:.2f}  mezcla={pwin_mix[j]:.2f}")

# =====================================================================
# B. Precio óptimo p* (maximiza ganancia esperada) según rivales
# =====================================================================
print(f"\n[B] Precio óptimo p* (costo c={COST}) según nº de rivales:")
print(f"{'N_riv':>6} {'p*':>6} {'P(ganar|p*)':>12} {'E[ganancia]':>12}")
popt_by_n = {}
for nriv in [0, 1, 2, 3, 5, 8]:
    mmin = rival_min(np.full(60000, nriv), RHO, rng)
    pw = pwin_curve(mmin, PGRID, P_ADMIT)
    profit = pw * (PGRID - COST)
    j = int(np.argmax(profit))
    popt_by_n[nriv] = (float(PGRID[j]), float(pw[j]), float(profit[j]))
    print(f"{nriv:>6} {PGRID[j]:>6.2f} {pw[j]:>12.3f} {profit[j]:>12.4f}")

# óptimo bajo mezcla empírica de rivales (con compuerta de admisión de datos)
pwin_mix_adm = pwin_mix * P_ADMIT
profit_mix = pwin_mix_adm * (PGRID - COST)
jmix = int(np.argmax(profit_mix))
pstar = float(PGRID[jmix])
print(f"\n    Mezcla empírica -> p*={pstar:.2f}  P(ganar|p*)={pwin_mix_adm[jmix]:.3f}  "
      f"E[ganancia]={profit_mix[jmix]:.4f} (de la referencia)")

# =====================================================================
# C. La novedad del proveedor NO cambia la estrategia (hallazgo de datos)
# =====================================================================
print("\n[C] Admisión estimada de datos (P(ganar|más barato) por novedad):")
print(f"    nuevo={P_ADMIT_NUEVO_DATO:.3f}   establecido={P_ADMIT:.3f}   "
      f"gap={P_ADMIT_NUEVO_DATO-P_ADMIT:+.3f}")
print("    -> la novedad NO baja P(ganar) una vez que eres el más barato: el precio")
print("       óptimo p* es el mismo. La palanca del nuevo es PARTICIPAR en más")
print("       renglones (y buscar los no disputados), no una admisión oculta.")
print(f"    what-if descalificación frecuente (p_admit={P_ADMIT_HIPOT}): E[ganancia]="
      f"{(P_ADMIT_HIPOT/P_ADMIT)*profit_mix[jmix]:.4f}")

# =====================================================================
# D. Matriz de simulación de la estrategia recomendada (p*, compuerta de datos)
# =====================================================================
beat = mmin_mix > pstar                            # vencí en precio
admit = rng.random(N_ITERS) < P_ADMIT              # gané dado que fui el más barato
gane = beat & admit                                # compuerta única (data-driven ~0.99)
margen = np.where(gane, pstar - COST, 0.0)
matriz = pd.DataFrame({
    "iter": np.arange(1, N_ITERS + 1),
    "N_rivales": N_riv_mix,
    "min_oferta_rival": np.round(mmin_mix, 5),
    "mi_precio": pstar,
    "mi_costo": COST,
    "vencio_en_precio": beat.astype(int),
    "admitido_dado_mas_barato": admit.astype(int),
    "gane": gane.astype(int),
    "margen_si_gana": np.round(margen, 5),
})
matriz.to_csv(OUT / "idea1_matriz.csv", index=False)
pwin_real = float(gane.mean())
ev_real = float(margen.mean())
print(f"\n[D] Estrategia p*={pstar}: P(ganar)={pwin_real:.3f}  "
      f"E[ganancia]={ev_real:.4f}  (EE ±{margen.std(ddof=1)/np.sqrt(N_ITERS):.5f})")

# =====================================================================
# FIGURAS
# =====================================================================
fig, ax = plt.subplots(figsize=(7.5, 4.5))
for nriv in [1, 3, 6]:
    ax.plot(PGRID, scen[nriv], label=f"{nriv} rivales")
ax.plot(PGRID, pwin_mix, "k--", label="mezcla empírica")
ax.axvline(COST, color="r", ls=":", label=f"mi costo {COST}")
ax.set_xlabel("mi precio (fracción de la referencia de mercado)")
ax.set_ylabel("P(ganar) [admisión=1]")
ax.set_title("Idea 1 — Probabilidad de ganar vs precio (más rivales ⇒ hay que bajar más)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_idea1_pwin.png", dpi=110)

fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.plot(PGRID, profit_mix, color="#137", lw=2, label="E[ganancia] (mezcla)")
ax.axvline(pstar, color="g", ls="--", label=f"p* = {pstar}")
ax.axvline(COST, color="r", ls=":", label=f"costo = {COST}")
ax.axhline(0, color="k", lw=0.6)
ax.set_xlabel("mi precio (fracción de la referencia)")
ax.set_ylabel("ganancia esperada por unidad (fracción)")
ax.set_title("Idea 1 — Ganancia esperada y precio óptimo")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_idea1_ganancia.png", dpi=110)

fig, ax = plt.subplots(figsize=(7.5, 4.5))
ns = [0, 1, 2, 3, 5, 8]
ax.plot(ns, [popt_by_n[n][0] for n in ns], "o-", label="p* óptimo")
ax.set_xlabel("nº de rivales")
ax.set_ylabel("precio óptimo p* (fracción de la referencia)")
ax.set_title("Idea 1 — El precio óptimo baja al aumentar la competencia")
ax.axhline(COST, color="r", ls=":", label=f"costo {COST}")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_idea1_pstar_vs_rivales.png", dpi=110)

# =====================================================================
# CURVAS -> CSV (para el export a Excel)
# =====================================================================
pd.DataFrame({
    "precio_frac_referencia": PGRID,
    "P_ganar_1_rival": scen[1],
    "P_ganar_3_rivales": scen[3],
    "P_ganar_6_rivales": scen[6],
    "P_ganar_mezcla": pwin_mix,
    "E_ganancia_mezcla": profit_mix,
}).to_csv(OUT / "idea1_curvas.csv", index=False)

# =====================================================================
# RESULTADOS
# =====================================================================
res = {
    "supuestos": {"costo": COST, "p_admit_establecido": P_ADMIT,
                  "p_admit_nuevo": P_ADMIT_NUEVO_DATO, "p_admit_hipotetico": P_ADMIT_HIPOT,
                  "sigma": SIGMA, "rho": RHO},
    "validacion_P_ganar_si_mas_barato": p_low_wins,
    "admision_data_driven": P_ADMIT,
    "p_optimo_mezcla": pstar,
    "P_ganar_en_pstar": float(pwin_mix_adm[jmix]),
    "E_ganancia_en_pstar": float(profit_mix[jmix]),
    "p_optimo_por_rivales": {str(n): popt_by_n[n] for n in popt_by_n},
    "estrategia_simulada": {"p": pstar, "P_ganar": pwin_real, "E_ganancia": ev_real},
}
json.dump(res, open(OUT / "idea1_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"\nOK -> idea1_matriz.csv ({N_ITERS:,} filas), idea1_resultados.json, 3 figuras.")
