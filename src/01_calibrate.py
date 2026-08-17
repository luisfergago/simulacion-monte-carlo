"""
Calibración de parámetros desde datos reales de Guatecompras.

Segmento: Salud (categoría 26), recepción electrónica, adjudicados, 2022-2025.

Estima todo lo que el motor de simulación necesita:
  - Distribución de N (número de competidores por renglón)  -> pmf empírica + fit NB
  - Relación CV(N): dispersión de precios dentro del renglón según N
  - Forma de la oferta normalizada (precio_i / media_del_renglón) -> LogNormal
  - Correlación intra-renglón (ICC) de log-precios
  - P(ganar | ranking de precio) para validar el supuesto "gana el mínimo"
  - Distribuciones de nivel: precio ganador y unidades demandadas (para gasto)

Salidas:
  output/params.json    (parámetros para el motor)
  output/fig_cv_vs_n.png
  output/fig_oferta_normalizada.png
  output/fig_n_dist.png
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
DATA = BASE / "data"
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 30)


def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# =====================================================================
# 1) NIVEL RENGLÓN
# =====================================================================
section("1) RENGLONES: carga y limpieza")
r = pd.read_csv(DATA / "renglones_salud.csv")
print(f"filas crudas: {len(r):,}")
r = r[(r.precio_min > 0) & (r.precio_avg > 0)].copy()
r["N"] = r.n_ofertas.astype(int)
r["cv"] = r.precio_sd / r.precio_avg          # NaN cuando N==1
r["min_over_avg"] = r.precio_min / r.precio_avg
print(f"filas limpias (precio>0): {len(r):,}")
print(f"renglones con N>=2: {(r.N >= 2).sum():,}  ({(r.N>=2).mean()*100:.1f}%)")

# --- Distribución de N ---
section("2) DISTRIBUCIÓN DE N (competidores por renglón)")
Ncounts = r.N.value_counts().sort_index()
Nshare = Ncounts / Ncounts.sum()
mN, vN = r.N.mean(), r.N.var()
print(f"media={mN:.3f}  var={vN:.3f}  (var>media => sobredispersión)")
print("pmf empírica N=1..12:")
for n in range(1, 13):
    print(f"  N={n:2d}  share={Nshare.get(n,0.0):.4f}  n={int(Ncounts.get(n,0)):,}")
print(f"  N>=13 share={Nshare[Nshare.index >= 13].sum():.4f}")

# Fit binomial negativa por momentos (soporte >=1 modelado como 1+NB(support>=0))
x = r.N.values - 1  # competidores extra sobre el mínimo de 1
mx, vx = x.mean(), x.var()
if vx > mx:
    p_nb = mx / vx
    r_nb = mx * mx / (vx - mx)
else:
    p_nb, r_nb = 0.999, 1e6
print(f"fit NB (sobre N-1): r={r_nb:.3f}  p={p_nb:.3f}")

# pmf empírica para el motor (hasta 20, con cola agregada)
NMAX = 20
pmf = {int(n): float(Nshare.get(n, 0.0)) for n in range(1, NMAX + 1)}
tail = float(Nshare[Nshare.index > NMAX].sum())
pmf[NMAX] += tail  # colapsa la cola en NMAX

# --- CV(N) ---
section("3) CV(N): dispersión de precios dentro del renglón")
cvtab = (r[r.N >= 2].groupby("N")["cv"]
         .agg(n="size", cv_median="median", cv_mean="mean")
         .reset_index())
print(cvtab[cvtab.N <= 12].to_string(index=False))
cv_by_N = {int(row.N): float(row.cv_median) for _, row in cvtab.iterrows()
           if np.isfinite(row.cv_median)}
# meseta para N grandes = mediana de CV en N>=6
plateau = float(cvtab.loc[cvtab.N >= 6, "cv_median"].median())
print(f"meseta CV (N>=6) = {plateau:.3f}")

# --- min/avg (proxy de ahorro vs media) ---
section("4) PRECIO MÍNIMO vs MEDIA del renglón (proxy de ahorro)")
moa = (r[r.N >= 2].groupby("N")["min_over_avg"]
       .agg(n="size", median="median", mean="mean").reset_index())
print(moa[moa.N <= 12].to_string(index=False))

# =====================================================================
# 5) NIVEL OFERTA
# =====================================================================
section("5) OFERTAS: forma de la oferta normalizada + ICC + P(ganar|rank)")
o = pd.read_csv(DATA / "ofertas_muestra.csv")
o = o[o.precio_unitario > 0].copy()
g = o.groupby("producto")["precio_unitario"]
o["r_mean"] = g.transform("mean")
o["r_min"] = g.transform("min")
o["r_n"] = g.transform("size")
o["norm_mean"] = o.precio_unitario / o.r_mean       # oferta / media del renglón
o["logp"] = np.log(o.precio_unitario)
oo = o[o.r_n >= 2].copy()
print(f"ofertas limpias: {len(o):,}  | en renglones N>=2: {len(oo):,}")

# Forma de la oferta normalizada -> LogNormal (floc=0)
nm = oo.norm_mean.values
shape, loc, scale = stats.lognorm.fit(nm, floc=0)
sigma_log = float(shape)
mu_log = float(np.log(scale))
print(f"LogNormal(oferta/media): sigma={sigma_log:.4f}  mu={mu_log:.4f}  "
      f"(media teórica={np.exp(mu_log+sigma_log**2/2):.3f})")

# ICC de log-precio por renglón (one-way random effects, no balanceado)
grand = oo.logp.mean()
grp_mean = oo.groupby("producto")["logp"].transform("mean")
ss_within = float(((oo.logp - grp_mean) ** 2).sum())
gm = oo.groupby("producto")["logp"].mean()
gsz = oo.groupby("producto").size()
ss_between = float((gsz * (gm - grand) ** 2).sum())
k = int(oo.groupby("producto").ngroups)
Ntot = int(len(oo))
ms_w = ss_within / (Ntot - k)
ms_b = ss_between / (k - 1)
n0 = (Ntot - float((gsz ** 2).sum()) / Ntot) / (k - 1)
var_b = (ms_b - ms_w) / n0
icc = float(var_b / (var_b + ms_w))
print(f"ICC(log-precio | renglón) = {icc:.3f}  "
      f"(var_between={var_b:.3f}, var_within={ms_w:.3f})")
print("  -> interpretación: fracción de la varianza de precios que es 'del producto'")
print("     (común a los competidores) vs idiosincrática de cada oferta.")

# P(ganar | ranking) usando estado adjudicado como 'ganó'
o["win"] = o.estado.fillna("").str.startswith("Adjudicaci")
sub = o[o.estado.notna()]
pw = (sub.groupby("ranking_de_precio")["win"]
      .agg(n="size", p_ganar="mean").reset_index())
print("\nP(ganar | ranking) [solo renglones con estado no nulo]:")
print(pw[pw.ranking_de_precio <= 8].to_string(index=False))
p_win_by_rank = {int(row.ranking_de_precio): float(row.p_ganar)
                 for _, row in pw.iterrows() if row.ranking_de_precio <= 10}

# =====================================================================
# 6) NIVEL: precio ganador y unidades (para gasto de la Idea 3)
# =====================================================================
section("6) NIVELES: precio ganador y unidades demandadas (LogNormal)")
pmin = r.loc[r.precio_min > 0, "precio_min"].values
s_pm, _, sc_pm = stats.lognorm.fit(pmin, floc=0)
ud = r.loc[r.unidades_demanda > 0, "unidades_demanda"].values
s_ud, _, sc_ud = stats.lognorm.fit(ud, floc=0)
print(f"precio_min ~ LogNormal(sigma={s_pm:.3f}, scale={sc_pm:.1f})  "
      f"[p50={np.median(pmin):.2f}]")
print(f"unidades   ~ LogNormal(sigma={s_ud:.3f}, scale={sc_ud:.1f})  "
      f"[p50={np.median(ud):.2f}]")

# =====================================================================
# GRÁFICAS
# =====================================================================
# CV vs N
fig, ax = plt.subplots(figsize=(7, 4))
d = cvtab[cvtab.N <= 12]
ax.plot(d.N, d.cv_median, "o-", label="CV mediana (dato)")
ax.axhline(plateau, ls="--", color="gray", label=f"meseta {plateau:.2f}")
ax.set_xlabel("N competidores en el renglón")
ax.set_ylabel("CV de precios (sd/media)")
ax.set_title("Dispersión de precios vs competencia — Salud, Compra Directa")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_cv_vs_n.png", dpi=110)

# Oferta normalizada
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(nm[nm < 3], bins=80, density=True, alpha=0.6, label="dato")
xs = np.linspace(0.01, 3, 300)
ax.plot(xs, stats.lognorm.pdf(xs, sigma_log, 0, scale), "r-",
        label=f"LogNormal σ={sigma_log:.2f}")
ax.axvline(1.0, color="k", ls=":", lw=1)
ax.set_xlabel("oferta / media del renglón")
ax.set_ylabel("densidad")
ax.set_title("Forma de la oferta individual (normalizada)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_oferta_normalizada.png", dpi=110)

# Distribución de N
fig, ax = plt.subplots(figsize=(7, 4))
ks = list(range(1, 13))
ax.bar(ks, [Nshare.get(k, 0) for k in ks], alpha=0.7)
ax.set_xlabel("N competidores")
ax.set_ylabel("proporción de renglones")
ax.set_title(f"Distribución de competidores por renglón (media={mN:.2f})")
fig.tight_layout()
fig.savefig(OUT / "fig_n_dist.png", dpi=110)

# =====================================================================
# GUARDA PARAMS
# =====================================================================
params = {
    "segmento": "Salud(cat26)_electronica_adjudicado_2022_2025",
    "n_renglones_limpios": int(len(r)),
    "N": {
        "media": float(mN), "var": float(vN),
        "pmf_empirica": pmf,
        "nb_fit_sobre_N_menos_1": {"r": float(r_nb), "p": float(p_nb)},
    },
    "cv_by_N": cv_by_N,
    "cv_plateau_N6": plateau,
    "oferta_normalizada_lognormal": {"sigma": sigma_log, "mu": mu_log},
    "icc_log_precio": icc,
    "p_win_by_rank": p_win_by_rank,
    "precio_min_lognormal": {"sigma": float(s_pm), "scale": float(sc_pm),
                             "p50": float(np.median(pmin))},
    "unidades_lognormal": {"sigma": float(s_ud), "scale": float(sc_ud),
                           "p50": float(np.median(ud))},
}
with open(OUT / "params.json", "w") as f:
    json.dump(params, f, indent=2, ensure_ascii=False)

section("LISTO")
print(f"params -> {OUT/'params.json'}")
print("figuras -> fig_cv_vs_n.png, fig_oferta_normalizada.png, fig_n_dist.png")
