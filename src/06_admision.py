"""
ETAPA DE ADMISIÓN (data-driven) — ¿la novedad del proveedor baja P(ganar)
MÁS ALLÁ del precio?

Prueba la hipótesis del modelo de dos etapas (hurdle) de la Idea 1:
  - Si al controlar por "ser el más barato" la experiencia/antigüedad todavía
    mueve P(ganar), hay una etapa de admisión/no-precio que castiga al nuevo.
  - Si no, el castigo al nuevo NO está en ganar-dado-que-ofertaste, sino antes
    (participar / estar habilitado), y el supuesto p_admit=0.55 no se sostiene.

Datos: ofertas_muestra.csv (ranking, estado) + nit_features.csv (antigüedad,
experiencia). win = estado empieza con 'Adjudicaci'.

Salidas: output/admision_resultados.json, output/fig_admision.png
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

# ---------- cargar y unir ----------
o = pd.read_csv(DATA / "ofertas_muestra.csv", dtype={"nit": str})
nf = pd.read_csv(DATA / "nit_features.csv", dtype={"nit": str},
                 parse_dates=["first_seen", "last_seen"])
o = o[o.precio_unitario > 0].merge(nf, on="nit", how="left")
print(f"ofertas: {len(o):,} | con features de NIT: {o.n_part_total.notna().mean()*100:.1f}%")

o = o[o.n_part_total.notna()].copy()
o["is_lowest"] = (o.ranking_de_precio == 1).astype(int)
o["win"] = o.estado.fillna("").str.startswith("Adjudicaci").astype(int)
o["tenure_yrs"] = (o.anio - o.first_seen.dt.year).clip(lower=0)
o["logexp"] = np.log1p(o.n_part_total)


def exp_bucket(n):
    if n <= 5:
        return "a) 1-5 (nuevo)"
    if n <= 50:
        return "b) 6-50"
    if n <= 500:
        return "c) 51-500"
    return "d) 500+"


o["exp_bucket"] = o.n_part_total.apply(exp_bucket)
lab = o.estado.notna()          # solo donde hay desenlace para 'win'
print(f"ofertas con desenlace (estado no nulo): {lab.sum():,}")

# ---------- A. win rate por experiencia (crudo, confundido) ----------
print("\n[A] win rate CRUDO por experiencia (confundido por competencia):")
A = o[lab].groupby("exp_bucket").agg(n=("win", "size"), win_rate=("win", "mean"))
print(A.to_string())

# ---------- B. P(ganar | ERES EL MÁS BARATO) por experiencia ----------
print("\n[B] P(ganar | ranking==1) por experiencia  <-- prueba clave:")
B = (o[lab & (o.is_lowest == 1)].groupby("exp_bucket")
     .agg(n=("win", "size"), p_ganar=("win", "mean")))
print(B.to_string())

# ---------- C. P(ganar | NO eres el más barato) por experiencia ----------
print("\n[C] P(ganar | ranking>=2) por experiencia  <-- ¿ventaja no-precio?:")
C = (o[lab & (o.is_lowest == 0)].groupby("exp_bucket")
     .agg(n=("win", "size"), p_ganar=("win", "mean")))
print(C.to_string())

# ---------- D. regresión logística (IRLS) ----------
def logit_irls(X, y, iters=60):
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(X @ beta)))
        W = np.clip(p * (1 - p), 1e-9, None)
        H = (X * W[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
        beta = beta + np.linalg.solve(H, X.T @ (y - p))
    cov = np.linalg.inv(H)
    return beta, np.sqrt(np.diag(cov))


d = o[lab].copy()
# estandariza continuas para comparar magnitudes
z_logexp = (d.logexp - d.logexp.mean()) / d.logexp.std()
z_ten = (d.tenure_yrs - d.tenure_yrs.mean()) / d.tenure_yrs.std()
X = np.column_stack([np.ones(len(d)), d.is_lowest.values, z_logexp.values, z_ten.values])
y = d.win.values.astype(float)
beta, se = logit_irls(X, y)
names = ["intercepto", "is_lowest", "z_log_experiencia", "z_antiguedad"]
print("\n[D] Regresión logística  win ~ is_lowest + experiencia + antigüedad")
print(f"{'variable':>20} {'coef':>9} {'SE':>7} {'z':>7}")
for nm, b, s in zip(names, beta, se):
    print(f"{nm:>20} {b:>9.3f} {s:>7.3f} {b/s:>7.1f}")

# efecto marginal: cuánto sube P(ganar) por +1 desv. de experiencia, dado lowest
def pr(is_low, zexp): 
    return 1/(1+np.exp(-(beta[0]+beta[1]*is_low+beta[2]*zexp+beta[3]*0)))
eff = pr(1, 1) - pr(1, 0)
print(f"\nEfecto de +1 desv. de experiencia sobre P(ganar|lowest): {eff*100:+.2f} pp")

# ---------- conclusión + parámetro para Idea 1 ----------
pwin_low_new = float(B.loc["a) 1-5 (nuevo)", "p_ganar"]) if "a) 1-5 (nuevo)" in B.index else float("nan")
pwin_low_estab = float(B.loc["d) 500+", "p_ganar"]) if "d) 500+" in B.index else float("nan")
gap = pwin_low_estab - pwin_low_new
veredicto = ("REFUTA el castigo grande al nuevo: ganar-dado-lowest casi no cambia con experiencia"
             if abs(gap) < 0.05 else
             "APOYA un castigo al nuevo en la etapa no-precio")
print(f"\nVEREDICTO: {veredicto}")
print(f"  P(ganar|lowest) nuevo={pwin_low_new:.3f}  establecido={pwin_low_estab:.3f}  gap={gap:+.3f}")

res = {
    "cobertura_features": float(o.n_part_total.notna().mean()),
    "win_rate_por_experiencia": A.reset_index().to_dict("records"),
    "P_ganar_si_lowest_por_experiencia": B.reset_index().to_dict("records"),
    "P_ganar_si_no_lowest_por_experiencia": C.reset_index().to_dict("records"),
    "logit": {nm: {"coef": float(b), "se": float(s)} for nm, b, s in zip(names, beta, se)},
    "efecto_marginal_experiencia_pp": float(eff * 100),
    "P_ganar_lowest_nuevo": pwin_low_new,
    "P_ganar_lowest_establecido": pwin_low_estab,
    "veredicto": veredicto,
}
json.dump(res, open(OUT / "admision_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)

# ---------- figura ----------
fig, ax = plt.subplots(figsize=(7.5, 4.5))
order = ["a) 1-5 (nuevo)", "b) 6-50", "c) 51-500", "d) 500+"]
ax.plot(order, [B.p_ganar.get(k, np.nan) for k in order], "o-", label="P(ganar | más barato)")
ax.plot(order, [C.p_ganar.get(k, np.nan) for k in order], "s--", label="P(ganar | NO más barato)")
ax.plot(order, [A.win_rate.get(k, np.nan) for k in order], "^:", label="win rate crudo")
ax.set_ylim(0, 1.02)
ax.set_ylabel("probabilidad de ganar")
ax.set_xlabel("experiencia del proveedor (nº participaciones)")
ax.set_title("Admisión — ¿la novedad importa más allá del precio?")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_admision.png", dpi=110)
print(f"\nOK -> admision_resultados.json, fig_admision.png")
