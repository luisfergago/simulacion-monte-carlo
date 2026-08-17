"""
Diagnóstico de la estructura de dispersión de ofertas.

Pregunta: ¿el CV(N) creciente es real o artefacto de muestreo?
Compara los datos reales contra dos modelos independientes:
  - sigma FIJA (una sola dispersión, order-statistics hacen el resto)
  - (referencia) lo que implicaría cada sigma
sobre TRES estadísticos por N (todos en mediana, robustos):
  CV = sd/media ,  min/media ,  brecha2 = (P2-P1)/P2
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

DATA = E.DATA
rng = np.random.default_rng(1)

# ---------- OBSERVADO ----------
r = pd.read_csv(DATA / "renglones_salud.csv")
r = r[(r.precio_min > 0) & (r.precio_avg > 0)].copy()
r["N"] = r.n_ofertas.astype(int)
r["cv"] = r.precio_sd / r.precio_avg
r["moa"] = r.precio_min / r.precio_avg
cv_obs = r[r.N >= 2].groupby("N")["cv"].median()
moa_obs = r[r.N >= 2].groupby("N")["moa"].median()

o = pd.read_csv(DATA / "ofertas_muestra.csv")
o = o[o.precio_unitario > 0].sort_values(["producto", "precio_unitario"])
o["rk"] = o.groupby("producto").cumcount()
g = o.groupby("producto")["precio_unitario"]
info = pd.DataFrame({"N": g.size(), "p1": g.min(),
                     "med": g.median()})
p2 = o[o.rk == 1].set_index("producto")["precio_unitario"].rename("p2")
info = info.join(p2)
info = info[info.p2.notna()]
info["brecha2"] = (info.p2 - info.p1) / info.p2
info["minmed"] = info.p1 / info.med
b2_obs = info.groupby("N")["brecha2"].median()
mm_obs = info.groupby("N")["minmed"].median()

# ---------- MODELO sigma fija ----------
def sim_stats(N, sigma, m=40000):
    mu = -0.5 * sigma * sigma
    off = np.exp(mu + sigma * rng.standard_normal((m, N)))
    part = np.partition(off, 1, axis=1)[:, :2]
    p1 = part.min(1); p2 = part.max(1)
    return (np.median(off.std(1, ddof=1) / off.mean(1)),
            np.median(off.min(1) / off.mean(1)),
            np.median(p1 / np.median(off, axis=1)),
            np.median((p2 - p1) / p2))

Ns = list(range(2, 13))
print("Buscando sigma fija que mejor reproduce las 4 curvas (en mediana)...")
best = None
for sigma in np.round(np.arange(0.40, 1.01, 0.05), 2):
    sim = {n: sim_stats(n, sigma) for n in Ns}
    e_cv = np.mean([(sim[n][0] - cv_obs[n]) ** 2 for n in Ns])
    e_moa = np.mean([(sim[n][1] - moa_obs[n]) ** 2 for n in Ns])
    e_b2 = np.mean([(sim[n][3] - b2_obs[n]) ** 2 for n in Ns if n in b2_obs.index])
    tot = e_cv + e_moa + e_b2
    if best is None or tot < best[0]:
        best = (tot, sigma, sim)
print(f"sigma fija optima ~ {best[1]}\n")

sigma = best[1]
sim = best[2]
print(f"{'N':>3} | {'CV obs':>7} {'CV sim':>7} | {'moa obs':>7} {'moa sim':>7} "
      f"| {'b2 obs':>7} {'b2 sim':>7}")
for n in Ns:
    b2o = b2_obs[n] if n in b2_obs.index else float("nan")
    print(f"{n:>3} | {cv_obs[n]:>7.3f} {sim[n][0]:>7.3f} | "
          f"{moa_obs[n]:>7.3f} {sim[n][1]:>7.3f} | {b2o:>7.3f} {sim[n][3]:>7.3f}")

print("\nLectura: si 'CV sim' crece con N como 'CV obs' aun con sigma FIJA,")
print("entonces el CV creciente es artefacto de muestreo (no dispersión real que sube).")
