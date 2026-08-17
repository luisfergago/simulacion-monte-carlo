"""
OPCIÓN 2 — Precio del mismo insumo entre concursos (IGSS).

Compara lo mismo con lo mismo: se agrupa por producto comparable, que es la
combinación de nombre, presentación (caracteristicas) y unidad de medida, porque
el mismo insumo a distinta concentración o forma es otro producto.

Para la presentación dominante de cada insumo se mide:
  - el precio ganador (mínimo por concurso) a lo largo del tiempo,
  - el efecto de la competencia: precio ganador según número de competidores N,
  - la dispersión propia del producto (sigma), comparada con el 0.209 global,
  - validación del motor a nivel producto: min/mediana observado vs simulado por N.

Insumos: Sitagliptina fosfato (diabetes, alta competencia) y Trastuzumab
(oncológico, alto valor).

Salidas: output/insumo_resultados.json y figuras.
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
rng = np.random.default_rng(7)

df = pd.read_csv(DATA / "insumo_series.csv", dtype={"nit": str},
                 parse_dates=["fecha"])
df = df[df.precio_unitario > 0].copy()
df["pres"] = (df.nombre.str.strip() + " || " +
              df.caracteristicas.fillna("").str.strip() + " || " +
              df.unidad_medida.fillna("").str.strip())


def robust_sigma(sub):
    """sigma dentro del concurso: MAD de (log precio - mediana log del concurso)."""
    s = sub.copy()
    s["lp"] = np.log(s.precio_unitario)
    s["n"] = s.groupby("nog")["lp"].transform("size")
    s = s[s.n >= 2]
    if len(s) < 30:
        return np.nan
    res = (s.lp - s.groupby("nog")["lp"].transform("median")).values
    return float(1.4826 * np.median(np.abs(res - np.median(res))))


def sim_min_over_med(N, sigma, m=40000):
    if N < 2:
        return 1.0
    off = E.offers_block(m, int(N), 0.0, rng, sigma=sigma)
    return float(np.median(off.min(1) / np.median(off, axis=1)))


resultados = {}
insumos = ["Sitagliptina fosfato", "Trastuzumab"]

for ins in insumos:
    d = df[df.nombre == ins]
    # presentación dominante por nº de concursos
    pres_rank = d.groupby("pres")["nog"].nunique().sort_values(ascending=False)
    print(f"\n===== {ins} — presentaciones (concursos) =====")
    for k, v in pres_rank.head(4).items():
        print(f"  {v:>5}  {k[:90]}")
    dom = pres_rank.index[0]
    dd = d[d.pres == dom].copy()

    # nivel renglón/concurso: precio ganador y nº de competidores
    g = dd.groupby("nog")
    ren = pd.DataFrame({
        "fecha": g["fecha"].first(),
        "N": g["nit"].nunique(),
        "win": g["precio_unitario"].min(),
        "p2": g["precio_unitario"].apply(lambda s: s.nsmallest(2).iloc[-1] if len(s) >= 2 else np.nan),
        "med": g["precio_unitario"].median(),
    })
    n_conc = len(ren)

    # efecto de la competencia: precio ganador por N
    ren["Ncap"] = ren.N.clip(upper=5)
    comp = ren.groupby("Ncap").agg(n=("win", "size"), precio_ganador=("win", "median"))
    base_price = comp.loc[1, "precio_ganador"] if 1 in comp.index else ren.win.median()
    comp["vs_N1"] = comp.precio_ganador / base_price

    # dispersión propia del producto y brecha2
    sigma_p = robust_sigma(dd)
    ren["brecha2"] = np.where(ren.N >= 2, (ren.p2 - ren.win) / ren.p2, np.nan)
    brecha2_med = float(ren.brecha2.median())

    # validación motor: min/mediana observado vs simulado por N
    ren["mom"] = np.where(ren.N >= 2, ren.win / ren.med, 1.0)
    val = ren[ren.N >= 2].groupby("Ncap")["mom"].median()

    # serie temporal (trimestral) del precio ganador
    ren["q"] = ren.fecha.dt.to_period("Q").astype(str)
    serie = ren.groupby("q")["win"].median()

    print(f"  presentación dominante: {dom[:80]}")
    print(f"  concursos={n_conc}  precio ganador mediano=Q{ren.win.median():,.2f}  sigma_producto={sigma_p:.3f}")
    print(f"  efecto competencia (precio ganador mediano por N):")
    for N in comp.index:
        s = f"{sim_min_over_med(N, sigma_p)*base_price:,.2f}" if not np.isnan(sigma_p) else "na"
        print(f"    N={N}: Q{comp.loc[N,'precio_ganador']:>10,.2f}  (vs N=1: {comp.loc[N,'vs_N1']*100:5.1f}%)  n={int(comp.loc[N,'n'])}")
    ahorro_comp = 1 - comp.vs_N1.reindex([4, 5]).dropna().mean() if len(comp) > 2 else np.nan
    print(f"  ahorro por competencia (N>=4 vs N=1): {ahorro_comp*100:.1f}%")
    print(f"  brecha2 mediana: {brecha2_med*100:.1f}%")

    resultados[ins] = {
        "presentacion": dom,
        "n_concursos": int(n_conc),
        "precio_ganador_mediano": float(ren.win.median()),
        "sigma_producto": None if np.isnan(sigma_p) else sigma_p,
        "brecha2_mediana": brecha2_med,
        "precio_por_N": {int(k): float(v) for k, v in comp.precio_ganador.items()},
        "vs_N1_por_N": {int(k): float(v) for k, v in comp.vs_N1.items()},
        "ahorro_competencia_N4_vs_N1": None if np.isnan(ahorro_comp) else float(ahorro_comp),
        "min_sobre_mediana_obs": {int(k): float(v) for k, v in val.items()},
        "serie_trimestral": {k: float(v) for k, v in serie.items()},
    }

    # ---- figura 1: precio ganador en el tiempo ----
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.plot(range(len(serie)), serie.values, "o-")
    ax.set_xticks(range(len(serie)))
    ax.set_xticklabels(serie.index, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("precio ganador mediano (Q)")
    ax.set_title(f"{ins} — precio ganador por trimestre (misma presentación)")
    fig.tight_layout()
    fig.savefig(OUT / f"fig_insumo_{ins.split()[0].lower()}_tiempo.png", dpi=110)

    # ---- figura 2: efecto de la competencia (obs vs motor) ----
    fig, ax = plt.subplots(figsize=(7.5, 4))
    Ns = list(val.index)
    ax.plot(Ns, [val[n] for n in Ns], "o-", label="observado (min/mediana)")
    if not np.isnan(sigma_p):
        ax.plot(Ns, [sim_min_over_med(n, sigma_p) for n in Ns], "s--",
                label=f"motor simulado (σ={sigma_p:.2f})")
    ax.set_xlabel("nº de competidores N")
    ax.set_ylabel("precio ganador / mediana del concurso")
    ax.set_title(f"{ins} — efecto de la competencia (validación del motor)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / f"fig_insumo_{ins.split()[0].lower()}_competencia.png", dpi=110)

json.dump(resultados, open(OUT / "insumo_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"\nOK -> insumo_resultados.json y figuras por insumo.")
