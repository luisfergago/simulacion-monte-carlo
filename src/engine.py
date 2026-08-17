"""
Motor común de simulación Monte Carlo para las Ideas 1 y 3.

Modelo de licitación competitiva (tipo Friedman):
  - En un renglón compiten N proveedores (N ~ pmf empírica; 54% tiene N=1).
  - Cada proveedor presenta una oferta en espacio normalizado (mediana ~ 1) que
    se genera con una LOGNORMAL de dispersión FIJA sigma, acopladas por una
    CÓPULA GAUSSIANA DE UN FACTOR:
        oferta_i = exp( mu + sigma * ( sqrt(rho)*Z + sqrt(1-rho)*U_i ) )
    Z = choque común (costo del insumo / condiciones de mercado; colusión si rho->1)
    U_i = componente idiosincrático de cada proveedor.
  - El ganador se modela como la oferta MÍNIMA (estadístico de orden mínimo),
    ponderada por una probabilidad de admisión. No es que el más barato gane por
    regla (la adjudicación es por evaluación de requisitos); empíricamente el más
    barato gana ~0.99 en este segmento (ver p_win_by_rank / 06_admision.py).

Decisión de modelado (ver src/00_diagnostico.py):
  sigma es FIJA, no crece con N. El aumento del CV con N que se observa en los
  datos se reproduce con sigma fija por puro muestreo (con más ofertas se captura
  más dispersión), entonces subir sigma con N sería doble conteo. Con sigma fija
  las curvas min/media y (P2-P1)/P2 bajan con N, igual que en los datos.

Parámetros anclados a datos reales (output/params.json + estimación robusta aquí):
  - pmf de N.
  - sigma: dispersión robusta (MAD) de log-precio dentro del renglón.
  - rho: se calibra contra la curva observada de brecha2 = (P2-P1)/P2 por N.

Importable (funciones) y ejecutable (estima sigma, calibra rho, valida y guarda).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
DATA = BASE / "data"

_P = json.load(open(OUT / "params.json", encoding="utf-8"))

# --- distribución de N ---
_PMF = {int(k): float(v) for k, v in _P["N"]["pmf_empirica"].items()}
_N_KEYS = np.array(sorted(_PMF))
_N_PROB = np.array([_PMF[k] for k in _N_KEYS], float)
_N_PROB = _N_PROB / _N_PROB.sum()

# --- dispersión fija (se estima al ejecutar; se guarda en params) ---
SIGMA = float(_P.get("sigma_fija", 0.45))


def sample_N(size, rng):
    return rng.choice(_N_KEYS, size=size, p=_N_PROB)


def offers_block(m, N, rho, rng, sigma=None):
    """m renglones x N ofertas normalizadas (E[oferta]=1), equicorrelación rho."""
    if sigma is None:
        sigma = SIGMA
    if N < 1:
        return np.ones((m, 1))
    if sigma == 0.0:
        return np.full((m, N), 1.0)
    Z = rng.standard_normal((m, 1))
    U = rng.standard_normal((m, N))
    normal = np.sqrt(rho) * Z + np.sqrt(1.0 - rho) * U
    mu = -0.5 * sigma * sigma
    return np.exp(mu + sigma * normal)


def two_lowest(off):
    part = np.partition(off, 1, axis=1)[:, :2]
    return part.min(axis=1), part.max(axis=1)


# =====================================================================
# ESTIMACIÓN de sigma + CALIBRACIÓN de rho + VALIDACIÓN
# =====================================================================
def estimate_sigma():
    """sigma robusta = MAD de (log precio - mediana log precio del renglón), N>=2."""
    o = pd.read_csv(DATA / "ofertas_muestra.csv")
    o = o[o.precio_unitario > 0].copy()
    o["lp"] = np.log(o.precio_unitario)
    o["n"] = o.groupby("producto")["lp"].transform("size")
    o = o[o.n >= 2]
    med = o.groupby("producto")["lp"].transform("median")
    res = (o.lp - med).values
    mad = np.median(np.abs(res - np.median(res)))
    return float(1.4826 * mad)


def _obs_curves():
    r = pd.read_csv(DATA / "renglones_salud.csv")
    r = r[(r.precio_min > 0) & (r.precio_avg > 0)].copy()
    r["N"] = r.n_ofertas.astype(int)
    cv = r[r.N >= 2].groupby("N").apply(
        lambda d: (d.precio_sd / d.precio_avg).median(), include_groups=False)
    moa = r[r.N >= 2].groupby("N").apply(
        lambda d: (d.precio_min / d.precio_avg).median(), include_groups=False)
    o = pd.read_csv(DATA / "ofertas_muestra.csv")
    o = o[o.precio_unitario > 0].sort_values(["producto", "precio_unitario"])
    o["rk"] = o.groupby("producto").cumcount()
    gsz = o.groupby("producto")["precio_unitario"].size()
    p1 = o.groupby("producto")["precio_unitario"].min()
    p2 = o[o.rk == 1].set_index("producto")["precio_unitario"]
    d = pd.DataFrame({"N": gsz, "p1": p1, "p2": p2}).dropna()
    d["b2"] = (d.p2 - d.p1) / d.p2
    b2 = d.groupby("N")["b2"].median()
    cnt = d.groupby("N").size()
    return cv, moa, b2, cnt


def _sim_curve(N, rho, rng, m=40000):
    off = offers_block(m, N, rho, rng)
    p1, p2 = two_lowest(off)
    cv = np.median(off.std(1, ddof=1) / off.mean(1))
    moa = np.median(off.min(1) / off.mean(1))
    b2 = np.median((p2 - p1) / p2)
    return cv, moa, b2


def calibrate_rho(Ns=range(2, 13), seed=7):
    rng = np.random.default_rng(seed)
    cv_o, moa_o, b2_o, cnt = _obs_curves()
    Ns = [n for n in Ns if n in b2_o.index]
    w = np.array([cnt[n] for n in Ns], float); w /= w.sum()
    grid = np.round(np.linspace(0.0, 0.8, 17), 3)
    best = None
    for rho in grid:
        b2s = np.array([_sim_curve(n, rho, rng)[2] for n in Ns])
        err = float(np.sum(w * (b2s - np.array([b2_o[n] for n in Ns])) ** 2))
        if best is None or err < best[0]:
            best = (err, float(rho))
    return best[1], Ns, (cv_o, moa_o, b2_o)


if __name__ == "__main__":
    SIGMA = estimate_sigma()
    print(f"sigma robusta estimada = {SIGMA:.3f}")
    best_rho, Ns, (cv_o, moa_o, b2_o) = calibrate_rho()
    print(f"rho calibrado (contra brecha2) = {best_rho:.3f}\n")

    rng = np.random.default_rng(3)
    print(f"{'N':>3} | {'CV o':>6} {'CV s':>6} | {'moa o':>6} {'moa s':>6} "
          f"| {'b2 o':>6} {'b2 s':>6}")
    for n in Ns:
        cvs, moas, b2s = _sim_curve(n, best_rho, rng)
        print(f"{n:>3} | {cv_o[n]:>6.3f} {cvs:>6.3f} | {moa_o[n]:>6.3f} {moas:>6.3f} "
              f"| {b2_o[n]:>6.3f} {b2s:>6.3f}")

    _P["sigma_fija"] = SIGMA
    _P["rho_estimado"] = best_rho
    json.dump(_P, open(OUT / "params.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print(f"\nparams.json actualizado: sigma_fija={SIGMA:.3f}, rho_estimado={best_rho}")
