"""
Ensambla el entregable de las dos propuestas: propuestas_montecarlo.xlsx

Hojas:
  Portada       resumen de las dos propuestas y sus resultados
  Calculadora   herramienta interactiva (celdas editables, fórmulas en vivo)
  Propuesta1    supuestos, resultados y gráficas (precio para ganar, Insulina glargina)
  P1_Matriz     matriz de simulación (1 fila = 1 licitación simulada)
  Propuesta2    supuestos, resultados y gráficas (valor de la competencia)
  P2_Matriz     matriz por renglón (dato + ahorro calculado)

La Calculadora usa fórmulas cerradas equivalentes a la simulación:
  P(ganar|precio) = suma_N P(N) * (1 - LOGNORM.DIST(precio))^N
  precio ganador esperado con N competidores = LOGNORM.INV(1 - 0.5^(1/N))
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT, DATA = BASE / "output", BASE / "data"
XLSX = OUT / "propuestas_montecarlo.xlsx"

r1 = json.load(open(OUT / "p1_resultados.json", encoding="utf-8"))
r2 = json.load(open(OUT / "p2_resultados.json", encoding="utf-8"))
m1 = pd.read_csv(OUT / "p1_matriz.csv")
m2 = pd.read_csv(OUT / "p2_matriz.csv")

# distribución empírica de N para Insulina glargina (presentación dominante)
dg = pd.read_csv(DATA / "propuestas.csv", dtype={"nit": str})
dg = dg[dg.nombre.str.lower().str.contains("glargina") & (dg.precio_unitario > 0)].copy()
dg["pres"] = dg.caracteristicas.fillna("").str.strip() + " | " + dg.unidad_medida.fillna("")
dg = dg[dg.pres == dg.groupby("pres")["nog"].nunique().idxmax()]
pmf = dg.groupby("nog")["nit"].nunique().value_counts(normalize=True).sort_index()
SIGMA = float(r1["lognormal_sigma"])
SCALE = float(r1["lognormal_mediana"])
MU = math.log(SCALE)
COSTO = float(r1["costo_supuesto_Q"])
POPT = float(r1["precio_optimo_Q"])


def q(x):
    return f"Q{x:,.2f}"


with pd.ExcelWriter(XLSX, engine="xlsxwriter") as w:
    wb = w.book
    title = wb.add_format({"bold": True, "font_size": 15})
    h = wb.add_format({"bold": True, "font_size": 12, "bg_color": "#1F4E78", "font_color": "white"})
    lbl = wb.add_format({"bold": True})
    inp = wb.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "0.00"})
    inpN = wb.add_format({"bg_color": "#FFF2CC", "border": 1, "num_format": "0"})
    money = wb.add_format({"num_format": "Q#,##0.00"})
    pctf = wb.add_format({"num_format": "0.0%"})
    p3 = wb.add_format({"num_format": "0.000"})

    # ---------- Portada ----------
    ws = wb.add_worksheet("Portada")
    w.sheets["Portada"] = ws
    ws.set_column(0, 0, 104)
    L = [
        ("Monte Carlo sobre compras del IGSS — dos propuestas", title),
        ("", None),
        ("Datos públicos de Guatecompras ya obtenidos. Segmento: salud, recepción electrónica,", None),
        ("concursos adjudicados 2022-2025, entidad IGSS.", None),
        ("", None),
        ("Propuesta 1 — Precio para ganar (proveedor).", h),
        (f"  Insulina glargina ({r1['n_concursos']:,} concursos). Precio óptimo {q(r1['precio_optimo_Q'])}, "
         f"P(ganar) {r1['P_ganar_opt']:.2f}, ganancia {q(r1['ganancia_esperada_Q'])}/u.", None),
        (f"  Correlación precio vs competidores = {r1['corr_precio_vs_N_spearman']:.3f}.", None),
        ("", None),
        ("Propuesta 2 — Valor de la competencia (Estado).", h),
        (f"  Cardiometabólicos ({r2['renglones']:,} renglones). Ahorro anual mediana "
         f"{q(r2['ahorro_anual_mediana_Q'])} (P5 {q(r2['ahorro_anual_P5_Q'])} .. P95 {q(r2['ahorro_anual_P95_Q'])}).", None),
        (f"  {r2['pct_sin_competencia']*100:.0f}% de renglones sin competencia. Contrafactual: "
         f"+{q(r2['contrafactual_extra_anual_Q'])}/año.", None),
        ("", None),
        ("La hoja Calculadora deja jugar con los datos, escribe en las celdas amarillas.", lbl),
    ]
    for i, (t, f) in enumerate(L):
        ws.write(i, 0, t, f if f else None)

    # ---------- Calculadora interactiva ----------
    ws = wb.add_worksheet("Calculadora")
    w.sheets["Calculadora"] = ws
    ws.set_column(0, 0, 34); ws.set_column(1, 1, 16); ws.set_column(3, 5, 13)
    ws.write(0, 0, "Calculadora interactiva (Insulina glargina)", title)

    # -- Caso 1 --
    ws.write(2, 0, "CASO 1 — Escribe tu precio y tu costo, mira la probabilidad de ganar", h)
    ws.write(4, 0, "sigma (de log-precio)"); ws.write(4, 1, SIGMA, p3)
    ws.write(5, 0, "mu (ln de la mediana)"); ws.write(5, 1, MU, p3)
    ws.write(6, 0, "mediana de oferta (Q)"); ws.write(6, 1, SCALE, money)
    ws.write(8, 0, "Mi precio (Q)  <--editable", lbl); ws.write(8, 1, POPT, inp)
    ws.write(9, 0, "Mi costo (Q)  <--editable", lbl); ws.write(9, 1, COSTO, inp)
    # tabla pmf de N + supervivencia^N (col D,E,F = idx 3,4,5)
    ws.write(4, 3, "N", hdr := wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1}))
    ws.write(4, 4, "P(N)", hdr); ws.write(4, 5, "S(precio)^N", hdr)
    r0 = 5
    for i, (n, p) in enumerate(pmf.items()):
        rr = r0 + i
        ws.write(rr, 3, int(n)); ws.write(rr, 4, float(p), p3)
        ws.write_formula(rr, 5, f"=(1-LOGNORM.DIST($B$9,$B$6,$B$5,TRUE))^D{rr+1}", p3)
    rN = r0 + len(pmf) - 1
    ws.write(11, 0, "P(ganar)", lbl)
    ws.write_formula(11, 1, f"=SUMPRODUCT(E{r0+1}:E{rN+1},F{r0+1}:F{rN+1})", p3)
    ws.write(12, 0, "Ganancia esperada por unidad (Q)", lbl)
    ws.write_formula(12, 1, "=B12*(B9-B10)", money)

    # -- Caso 2 --
    ws.write(15, 0, "CASO 2 — Cambia el número de competidores, mira el precio y el ahorro", h)
    ws.write(17, 0, "Número de competidores N  <--editable", lbl); ws.write(17, 1, 3, inpN)
    ws.write(18, 0, "Precio ganador esperado (Q)", lbl)
    ws.write_formula(18, 1, "=LOGNORM.INV(1-0.5^(1/B18),$B$6,$B$5)", money)
    ws.write(19, 0, "Precio con 1 competidor (Q)", lbl)
    ws.write_formula(19, 1, "=$B$7", money)
    ws.write(20, 0, "Ahorro vs 1 competidor", lbl)
    ws.write_formula(20, 1, "=1-B19/B20", pctf)
    # tabla de referencia N=1..8
    ws.write(22, 0, "Referencia: precio y ahorro por N", lbl)
    ws.write(23, 3, "N", hdr); ws.write(23, 4, "precio (Q)", hdr); ws.write(23, 5, "ahorro", hdr)
    for i, n in enumerate(range(1, 9)):
        rr = 24 + i
        ws.write(rr, 3, n)
        ws.write_formula(rr, 4, f"=LOGNORM.INV(1-0.5^(1/D{rr+1}),$B$6,$B$5)", money)
        ws.write_formula(rr, 5, f"=1-E{rr+1}/$B$7", pctf)

    # ---------- Propuesta 1 ----------
    sup1 = pd.DataFrame([
        ["N competidores", "entrada", "distribución empírica", f"media {r1['N_medio']:.2f}"],
        ["precio de oferta rival", "entrada", "LogNormal",
         f"sigma {SIGMA:.3f}, mediana {q(SCALE)}"],
        ["mi costo unitario", "entrada (supuesto)", "constante", q(COSTO)],
        ["mi precio", "decisión", "grilla", "se busca el óptimo"],
    ], columns=["Variable", "Rol", "Distribución", "Parámetro"])
    res1 = pd.DataFrame([
        ["Precio óptimo", q(r1["precio_optimo_Q"])],
        ["P(ganar) en el óptimo", f"{r1['P_ganar_opt']:.3f}"],
        ["Ganancia esperada por unidad", q(r1["ganancia_esperada_Q"])],
        ["Error estándar Monte Carlo", q(r1["EE_MC"])],
        ["Correlación precio vs N (Spearman)", f"{r1['corr_precio_vs_N_spearman']:.3f}"],
    ], columns=["Resultado", "Valor"])
    sup1.to_excel(w, sheet_name="Propuesta1", index=False, startrow=1)
    res1.to_excel(w, sheet_name="Propuesta1", index=False, startrow=8)
    ws = w.sheets["Propuesta1"]
    ws.write(0, 0, "Propuesta 1 — Precio para ganar (Insulina glargina)", h)
    ws.set_column(0, 0, 34); ws.set_column(1, 3, 26)
    ws.insert_image("G2", str(OUT / "fig_p1_precio.png"), {"x_scale": 0.7, "y_scale": 0.7})
    ws.insert_image("G24", str(OUT / "fig_p1_convergencia.png"), {"x_scale": 0.7, "y_scale": 0.7})
    m1.to_excel(w, sheet_name="P1_Matriz", index=False)

    # ---------- Propuesta 2 ----------
    sup2 = pd.DataFrame([
        ["N competidores por renglón", "entrada", "dato", f"{r2['pct_sin_competencia']*100:.0f}% con N=1"],
        ["precio ganador y 2º postor", "entrada", "dato", "por renglón"],
        ["valor de la línea (precio total)", "entrada", "dato", "del ganador"],
        ["descuento de competencia", "supuesto contrafactual", "mediano observado",
         f"{r2['descuento_competencia_mediano']*100:.1f}%"],
    ], columns=["Variable", "Rol", "Fuente", "Detalle"])
    res2 = pd.DataFrame([
        ["Gasto total (4 años)", f"Q{r2['gasto_total_Q']:,.0f}"],
        ["Ahorro observado vs 2º postor", f"Q{r2['ahorro_observado_Q']:,.0f} ({r2['ahorro_pct']*100:.1f}%)"],
        ["Ahorro anual (mediana, bootstrap)", f"Q{r2['ahorro_anual_mediana_Q']:,.0f}"],
        ["Ahorro anual P5–P95", f"Q{r2['ahorro_anual_P5_Q']:,.0f} .. Q{r2['ahorro_anual_P95_Q']:,.0f}"],
        ["% renglones sin competencia", f"{r2['pct_sin_competencia']*100:.1f}%"],
        ["Contrafactual: ahorro extra anual", f"Q{r2['contrafactual_extra_anual_Q']:,.0f}"],
        ["Ahorro anual potencial", f"Q{r2['ahorro_anual_potencial_Q']:,.0f}"],
        ["Correlación precio norm. vs N", f"{r2['corr_precio_norm_vs_N_spearman']:.3f}"],
    ], columns=["Resultado", "Valor"])
    sup2.to_excel(w, sheet_name="Propuesta2", index=False, startrow=1)
    res2.to_excel(w, sheet_name="Propuesta2", index=False, startrow=8)
    ws = w.sheets["Propuesta2"]
    ws.write(0, 0, "Propuesta 2 — Valor de la competencia (cardiometabólicos)", h)
    ws.set_column(0, 0, 40); ws.set_column(1, 3, 30)
    ws.insert_image("G2", str(OUT / "fig_p2_ahorro.png"), {"x_scale": 0.7, "y_scale": 0.7})
    ws.insert_image("G24", str(OUT / "fig_p2_contrafactual.png"), {"x_scale": 0.7, "y_scale": 0.7})
    m2.to_excel(w, sheet_name="P2_Matriz", index=False)

print(f"OK -> {XLSX}")
