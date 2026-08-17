"""
Comparación por ÁREA DE USO (clasificación clínica), segmento IGSS.

Tres áreas: oncología, renal (solo medicamentos e insumos, sin el servicio de
diálisis) y cardiometabólico (hipertensión, colesterol, diabetes).

Método: se clasifica cada producto por su nombre, se define el producto
comparable como (nombre, presentación, unidad de medida), se normaliza cada
producto contra sí mismo y se agregan las métricas por área. Así se compara la
intensidad de competencia y el ahorro entre áreas con muestras grandes.

Métricas por área:
  - intensidad de competencia: N medio y % de renglones sin competencia (N=1)
  - curva de competencia: precio ganador / mediana del concurso, por N
  - dispersión propia (sigma) y brecha vs 2º postor
  - precio ganador típico (contexto)

Salidas: output/areas_resultados.json y figuras.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E

OUT, DATA = E.OUT, E.DATA


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


ONC = ("trastuzumab pertuzumab bevacizumab rituximab pembrolizumab nivolumab cetuximab "
       "panitumumab imatinib dasatinib nilotinib erlotinib sorafenib sunitinib pazopanib "
       "everolimus enzalutamida abiraterona bicalutamida leuprorelina goserelina letrozol "
       "anastrozol exemestano tamoxifeno fulvestrant capecitabina gemcitabina oxaliplatino "
       "carboplatino cisplatino paclitaxel docetaxel doxorrubicina ciclofosfamida fluorouracilo "
       "irinotecan bortezomib carfilzomib lenalidomida azacitidina fludarabina temozolomida "
       "ruxolitinib ibrutinib palbociclib ribociclib olaparib vincristina vinblastina vinorelbina "
       "etoposido bleomicina citarabina hidroxiurea").split()
RENAL = ("eritropoyetina epoetina darbepoetina sevelamer cinacalcet paricalcitol calcitriol "
         "alfacalcidol hemodialisis dialisis peritoneal").split()
CARDIO = ("losart valsart irbesart candesart telmisart enalapril lisinopril ramipril amlodipino "
          "felodipino nifedipino atenolol metoprolol carvedilol bisoprolol hidroclorotiazida "
          "espironolactona atorvastatina rosuvastatina simvastatina pravastatina fenofibrato "
          "gemfibrozilo clopidogrel warfarina rivaroxab apixab metformina glibenclamida gliclazida "
          "sitagliptina linagliptina vildagliptina empagliflozina dapagliflozina insulina glargina").split()


def area_of(nombre):
    n = norm(nombre)
    if "procedimiento" in n or "tratamiento de hemodi" in n:
        return None
    if any(t in n for t in ONC):
        return "oncologia"
    if any(t in n for t in RENAL) or re.search(r"\brenal\b", n) or re.search(r"\bnefro", n):
        return "renal"
    if any(t in n for t in CARDIO):
        return "cardiometabolico"
    return None


# ---------- cargar y clasificar ----------
o = pd.read_csv(DATA / "areas_uso.csv", dtype={"nit": str})
o = o[o.precio_unitario > 0].copy()
o["area"] = o.nombre.map(area_of)
o = o[o.area.notna()].copy()
print("ofertas por area:\n", o.area.value_counts().to_string())

# ---------- nivel renglón (producto_id = un renglón) ----------
g = o.groupby("producto_id")
ren = pd.DataFrame({
    "area": g["area"].first(),
    "nog": g["nog"].first(),
    "nombre": g["nombre"].first(),
    "N": g["nit"].nunique(),
    "win": g["precio_unitario"].min(),
    "med": g["precio_unitario"].median(),
    "p2": g["precio_unitario"].apply(lambda s: s.nsmallest(2).iloc[-1] if len(s) >= 2 else np.nan),
})
ren["mom"] = np.where(ren.N >= 2, ren.win / ren.med, 1.0)
ren["brecha2"] = np.where(ren.N >= 2, (ren.p2 - ren.win) / ren.p2, np.nan)


def sigma_area(area):
    sub = o[o.area == area].copy()
    sub["lp"] = np.log(sub.precio_unitario)
    sub["n"] = sub.groupby("producto_id")["lp"].transform("size")
    sub = sub[sub.n >= 2]
    if len(sub) < 30:
        return np.nan
    res = (sub.lp - sub.groupby("producto_id")["lp"].transform("median")).values
    return float(1.4826 * np.median(np.abs(res - np.median(res))))


# ---------- métricas por área ----------
areas = ["cardiometabolico", "renal", "oncologia"]
tabla = []
curva = {}
for a in areas:
    r = ren[ren.area == a]
    r2 = r[r.N >= 2]
    tabla.append({
        "area": a,
        "renglones": int(len(r)),
        "concursos": int(r.nog.nunique()),
        "N_medio": float(r.N.mean()),
        "pct_sin_competencia": float((r.N == 1).mean()),
        "sigma": sigma_area(a),
        "brecha2_mediana": float(r2.brecha2.median()) if len(r2) else np.nan,
        "precio_ganador_mediano": float(r.win.median()),
    })
    r2 = r2.copy()
    r2["Ncap"] = r2.N.clip(upper=6)
    curva[a] = r2.groupby("Ncap")["mom"].median()

tab = pd.DataFrame(tabla)
pd.set_option("display.width", 140)
print("\n=== Comparación por área de uso ===")
print(tab.to_string(index=False,
      formatters={"N_medio": "{:.2f}".format, "pct_sin_competencia": "{:.1%}".format,
                  "sigma": "{:.3f}".format, "brecha2_mediana": "{:.1%}".format,
                  "precio_ganador_mediano": "Q{:,.2f}".format}))

# ---------- figuras ----------
labels = {"cardiometabolico": "Cardiometabólico", "renal": "Renal (productos)",
          "oncologia": "Oncología"}
col = {"cardiometabolico": "#2ca02c", "renal": "#1f77b4", "oncologia": "#d62728"}

# 1) intensidad de competencia: N medio y % sin competencia
fig, ax1 = plt.subplots(figsize=(7.5, 4.2))
x = np.arange(len(areas))
ax1.bar(x - 0.2, [tab.set_index("area").loc[a, "N_medio"] for a in areas], 0.4,
        label="N medio", color="#4C78A8")
ax1.set_ylabel("N medio de competidores")
ax2 = ax1.twinx()
ax2.bar(x + 0.2, [tab.set_index("area").loc[a, "pct_sin_competencia"] * 100 for a in areas], 0.4,
        label="% sin competencia", color="#E45756")
ax2.set_ylabel("% de renglones con una sola oferta")
ax1.set_xticks(x); ax1.set_xticklabels([labels[a] for a in areas])
ax1.set_title("Competencia por área de uso (IGSS)")
ax1.legend(loc="upper left"); ax2.legend(loc="upper right")
fig.tight_layout()
fig.savefig(OUT / "fig_areas_competencia.png", dpi=110)

# 2) curva de competencia por área (precio ganador / mediana del concurso)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
for a in areas:
    c = curva[a]
    ax.plot(list(c.index), list(c.values), "o-", color=col[a], label=labels[a])
ax.set_xlabel("N competidores en el renglón")
ax.set_ylabel("precio ganador / mediana del concurso")
ax.set_title("Efecto de la competencia por área de uso")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_areas_curva.png", dpi=110)

# ---------- guardar ----------
res = {
    "tabla": tabla,
    "curva_min_sobre_mediana_por_N": {a: {int(k): float(v) for k, v in curva[a].items()}
                                      for a in areas},
    "definicion": "areas por clasificacion de uso; renal sin el servicio de dialisis",
}
json.dump(res, open(OUT / "areas_resultados.json", "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
print(f"\nOK -> areas_resultados.json, fig_areas_competencia.png, fig_areas_curva.png")
