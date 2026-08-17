"""
Ensambla el entregable Excel: montecarlo_guatecompras.xlsx

Hojas:
  Portada          resumen del proyecto, segmento, método y resultados clave
  Supuestos        tabla de variables: rol, distribución, parámetros, fuente
  Correlacion      cópula de un factor + matrices de correlación de ejemplo
  Idea1_Matriz     matriz de simulación (1 fila = 1 iteración)
  Idea1_Curvas     P(ganar|precio) y ganancia esperada + gráficas
  Idea1_Result     precio óptimo por rivales, efecto de la admisión
  Idea3_Matriz     matriz de simulación (1 fila = 1 renglón simulado)
  Idea3_Curvas     brecha2 por N (obs vs simulado y barrido de rho) + gráficas
  Idea3_Result     resultados clave (sin competencia, ahorro, colusión)

Solo ensambla archivos ya generados en output/.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output"
XLSX = OUT / "montecarlo_guatecompras.xlsx"

P = json.load(open(OUT / "params.json", encoding="utf-8"))
r1 = json.load(open(OUT / "idea1_resultados.json", encoding="utf-8"))
r3 = json.load(open(OUT / "idea3_resultados.json", encoding="utf-8"))
m1 = pd.read_csv(OUT / "idea1_matriz.csv")
m3 = pd.read_csv(OUT / "idea3_matriz.csv")
c1 = pd.read_csv(OUT / "idea1_curvas.csv")

SIGMA = P.get("sigma_fija", 0.209)
RHO = P.get("rho_estimado", 0.0)


def autofit(ws, df, start=0):
    for i, col in enumerate(df.columns):
        w = max(len(str(col)), int(df[col].astype(str).str.len().max() if len(df) else 0))
        ws.set_column(i, i, min(max(w + 2, 10), 40))


with pd.ExcelWriter(XLSX, engine="xlsxwriter") as writer:
    wb = writer.book
    title = wb.add_format({"bold": True, "font_size": 15})
    h = wb.add_format({"bold": True, "font_size": 12, "bg_color": "#1F4E78",
                       "font_color": "white"})
    hdr = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    pct = wb.add_format({"num_format": "0.0%"})
    num3 = wb.add_format({"num_format": "0.000"})

    # ---------------- Portada ----------------
    ws = wb.add_worksheet("Portada")
    writer.sheets["Portada"] = ws
    ws.set_column(0, 0, 100)
    L = [
        ("Simulación Monte Carlo — Compras públicas de salud (Guatecompras)", title),
        ("", None),
        ("Segmento: Salud (categoría 26), recepción electrónica, adjudicados, 2022–2025.", None),
        ("  460,181 concursos · 557,710 renglones · 2,775 proveedores.", None),
        ("", None),
        ("Método: modelo de licitación competitiva (Friedman).", h),
        ("  - N competidores por renglón ~ distribución empírica (54% con una sola oferta).", None),
        (f"  - Oferta de cada proveedor ~ LogNormal(σ={SIGMA:.3f}) en espacio normalizado (referencia=1).", None),
        (f"  - Ofertas acopladas por cópula gaussiana de un factor (ρ={RHO:.2f} base; barrido para colusión).", None),
        ("  - El ganador se modela como la oferta mínima (orden mínimo), ponderada por", None),
        ("    la admisión: no gana el más barato por regla; empíricamente lo hace ~99%.", None),
        ("", None),
        ("Validación: la brecha vs segundo postor simulada reproduce la observada por N.", h),
        ("", None),
        ("Idea 1 — Estrategia de precio (proveedor):", h),
        ("  El precio óptimo baja al aumentar la competencia; la admisión (ser habilitado)", None),
        ("  es la palanca del proveedor nuevo, no bajar el precio.", None),
        ("", None),
        ("Idea 3 — Competencia y gasto público (Estado):", h),
        ("  54% de renglones sin competencia; donde hay, el ahorro vs segundo postor ~15–17%.", None),
        ("  La colusión (ρ→1) erosiona ese ahorro.", None),
        ("", None),
        ("Nota: los precios están en fracción de la referencia de mercado salvo columnas en Q.", None),
    ]
    for i, (txt, fmt) in enumerate(L):
        ws.write(i, 0, txt, fmt if fmt else None)

    # ---------------- Supuestos ----------------
    sup = pd.DataFrame([
        ["N (competidores por renglón)", "entrada", "pmf empírica",
         f"media={P['N']['media']:.2f}; P(N=1)={P['N']['pmf_empirica'].get('1',0):.3f}", "dato Guatecompras"],
        ["Oferta de cada rival (normalizada)", "entrada", "LogNormal",
         f"σ={SIGMA:.3f} (MAD robusto); mediana=1", "dato (ofertas_muestra)"],
        ["Correlación ρ entre ofertas", "parámetro / escenario", "cópula gaussiana 1 factor",
         f"base={RHO:.2f}; barrido 0.0–0.9", "calibrado vs brecha2"],
        ["Costo unitario propio c (Idea 1)", "entrada", "constante",
         f"{r1['supuestos']['costo']} de la referencia", "supuesto del negocio"],
        ["Admisión (Idea 1)", "entrada", "Bernoulli",
         f"establecido={r1['supuestos']['p_admit_establecido']}; nuevo={r1['supuestos']['p_admit_nuevo']}", "supuesto declarado"],
        ["P(ganar | ser el más barato)", "parámetro", "constante",
         f"{r1['validacion_P_ganar_si_mas_barato']:.3f}", "dato (estado_oferta)"],
        ["Nivel de monto (Idea 3)", "entrada", "bootstrap de datos reales",
         "precio_min × unidades observados", "dato (renglones_salud)"],
    ], columns=["Variable", "Rol", "Distribución", "Parámetros", "Fuente"])
    sup.to_excel(writer, sheet_name="Supuestos", index=False, startrow=1)
    ws = writer.sheets["Supuestos"]
    ws.write(0, 0, "Tabla de supuestos (variables de entrada y parámetros)", h)
    for c, col in enumerate(sup.columns):
        ws.write(1, c, col, hdr)
    ws.set_column(0, 0, 34); ws.set_column(1, 1, 20)
    ws.set_column(2, 2, 26); ws.set_column(3, 3, 40); ws.set_column(4, 4, 24)

    # ---------------- Correlacion ----------------
    ws = wb.add_worksheet("Correlacion")
    writer.sheets["Correlacion"] = ws
    ws.set_column(0, 6, 14)
    txt = [
        "Estructura de correlación — cópula gaussiana de un factor",
        "",
        "Cada oferta (en logaritmo) se genera como:",
        "   oferta_i = exp( mu + σ · ( √ρ·Z + √(1-ρ)·U_i ) )",
        "   Z  = choque común a todos los competidores (costo del insumo, mercado; colusión si ρ→1)",
        "   U_i = componente idiosincrático de cada proveedor",
        "",
        "La correlación entre dos ofertas cualesquiera del mismo renglón es exactamente ρ.",
        "Matrices de correlación de ejemplo (renglón con 4 competidores):",
    ]
    for i, t in enumerate(txt):
        ws.write(i, 0, t, title if i == 0 else None)
    row = len(txt) + 1
    for rho, lab in [(0.0, f"ρ = {RHO:.2f}  (base, calibrado: ofertas ~ independientes)"),
                     (0.6, "ρ = 0.60  (escenario de colusión / costo común alto)")]:
        ws.write(row, 0, lab, hdr); row += 1
        M = np.full((4, 4), rho); np.fill_diagonal(M, 1.0)
        dfM = pd.DataFrame(M, columns=[f"of{j+1}" for j in range(4)],
                           index=[f"of{j+1}" for j in range(4)])
        dfM.to_excel(writer, sheet_name="Correlacion", startrow=row, startcol=0)
        row += 6

    # ---------------- Idea 1 ----------------
    m1.to_excel(writer, sheet_name="Idea1_Matriz", index=False)
    autofit(writer.sheets["Idea1_Matriz"], m1)

    c1.to_excel(writer, sheet_name="Idea1_Curvas", index=False, startrow=1)
    ws = writer.sheets["Idea1_Curvas"]
    ws.write(0, 0, "P(ganar|precio) y ganancia esperada (mezcla empírica de rivales)", h)
    nrow = len(c1)
    chart = wb.add_chart({"type": "line"})
    for col, name in [(1, "1 rival"), (2, "3 rivales"), (3, "6 rivales"), (4, "mezcla")]:
        chart.add_series({
            "name": name,
            "categories": ["Idea1_Curvas", 2, 0, nrow + 1, 0],
            "values": ["Idea1_Curvas", 2, col, nrow + 1, col],
        })
    chart.set_title({"name": "P(ganar) vs mi precio"})
    chart.set_x_axis({"name": "precio (fracción de la referencia)"})
    chart.set_y_axis({"name": "P(ganar)"})
    ws.insert_chart("H2", chart, {"x_scale": 1.3, "y_scale": 1.4})
    ws.insert_image("H24", str(OUT / "fig_idea1_ganancia.png"), {"x_scale": 0.7, "y_scale": 0.7})
    ws.insert_image("R24", str(OUT / "fig_idea1_pstar_vs_rivales.png"), {"x_scale": 0.7, "y_scale": 0.7})

    po = r1["p_optimo_por_rivales"]
    dfp = pd.DataFrame(
        [[int(n), po[n][0], po[n][1], po[n][2]] for n in sorted(po, key=int)],
        columns=["N_rivales", "precio_optimo", "P_ganar", "E_ganancia"])
    dfp.to_excel(writer, sheet_name="Idea1_Result", index=False, startrow=1)
    ws = writer.sheets["Idea1_Result"]
    ws.write(0, 0, "Precio óptimo según número de rivales (costo c=0.75)", h)
    base = len(dfp) + 4
    adm = r1.get("admision_data_driven", 0.99)
    extra = pd.DataFrame([
        ["p* (mezcla empírica)", r1["p_optimo_mezcla"]],
        ["P(ganar) en p* (con admisión)", r1["P_ganar_en_pstar"]],
        ["E[ganancia] en p* (fracción de la referencia)", r1["E_ganancia_en_pstar"]],
        ["Admisión estimada de datos (P ganar|más barato)", adm],
        ["Novedad: P(ganar|más barato) nuevo", r1["supuestos"]["p_admit_nuevo"]],
        ["Novedad: P(ganar|más barato) establecido", r1["supuestos"]["p_admit_establecido"]],
        ["What-if descalificación (p_admit=0.70): E[ganancia]",
         r1["E_ganancia_en_pstar"] * (0.70 / adm)],
    ], columns=["Resultado", "Valor"])
    extra.to_excel(writer, sheet_name="Idea1_Result", index=False, startrow=base)
    ws.set_column(0, 0, 40); ws.set_column(1, 3, 16)

    # ---------------- Idea 3 ----------------
    m3.to_excel(writer, sheet_name="Idea3_Matriz", index=False)
    autofit(writer.sheets["Idea3_Matriz"], m3)

    Ns = sorted(int(k) for k in r3["observado"]["brecha2_por_N"])
    df3 = pd.DataFrame({"N": Ns,
                        "observado": [r3["observado"]["brecha2_por_N"][str(n)] for n in Ns]})
    for k in ["0.0", "0.3", "0.6", "0.9"]:
        df3[f"sim_rho_{k}"] = r3["simulado"]["brecha2_por_N_por_rho"][k]
    df3.to_excel(writer, sheet_name="Idea3_Curvas", index=False, startrow=1)
    ws = writer.sheets["Idea3_Curvas"]
    ws.write(0, 0, "Brecha vs 2º postor (P2−P1)/P2 por N: observado vs simulado y barrido de ρ", h)
    nrow = len(df3)
    chart = wb.add_chart({"type": "line"})
    for col, name in [(1, "observado"), (2, "sim ρ=0"), (3, "sim ρ=0.3"),
                      (4, "sim ρ=0.6"), (5, "sim ρ=0.9")]:
        chart.add_series({
            "name": name,
            "categories": ["Idea3_Curvas", 2, 0, nrow + 1, 0],
            "values": ["Idea3_Curvas", 2, col, nrow + 1, col],
        })
    chart.set_title({"name": "Ahorro marginal vs competencia y colusión"})
    chart.set_x_axis({"name": "N competidores"})
    chart.set_y_axis({"name": "brecha2"})
    ws.insert_chart("I2", chart, {"x_scale": 1.3, "y_scale": 1.4})
    ws.insert_image("I24", str(OUT / "fig_idea3_hist.png"), {"x_scale": 0.7, "y_scale": 0.7})
    ws.insert_image("S24", str(OUT / "fig_idea3_convergencia.png"), {"x_scale": 0.7, "y_scale": 0.7})

    dfr3 = pd.DataFrame([
        ["Renglones sin competencia (N=1)", r3["frac_sin_competencia_N1"]],
        ["Brecha2 media observada (N>=2)", r3["observado"]["brecha2_media_N>=2"]],
        ["Brecha2 media simulada (N>=2)", r3["simulado"]["brecha2_media_N>=2"]],
        ["Dinero sobre la mesa medio por renglón (Q)", r3["simulado"]["dinero_sobre_la_mesa_Q_medio"]],
        ["Error estándar MC de la brecha2", r3["simulado"]["brecha2_EE_MC"]],
        ["Renglones con bandera de colusión", r3["colusion_flag"]["n_sospechosos"]],
    ], columns=["Resultado", "Valor"])
    dfr3.to_excel(writer, sheet_name="Idea3_Result", index=False, startrow=1)
    ws = writer.sheets["Idea3_Result"]
    ws.write(0, 0, "Idea 3 — Resultados clave", h)
    ws.set_column(0, 0, 46); ws.set_column(1, 1, 18)

    # ---------------- Admision ----------------
    r_adm = json.load(open(OUT / "admision_resultados.json", encoding="utf-8"))
    adm_rows = []
    for rec in r_adm["P_ganar_si_lowest_por_experiencia"]:
        adm_rows.append([rec["exp_bucket"], "más barato (rank 1)", rec["n"], rec["p_ganar"]])
    for rec in r_adm["P_ganar_si_no_lowest_por_experiencia"]:
        adm_rows.append([rec["exp_bucket"], "NO más barato (rank>=2)", rec["n"], rec["p_ganar"]])
    dfa = pd.DataFrame(adm_rows, columns=["experiencia", "condición", "n", "P_ganar"])
    dfa.to_excel(writer, sheet_name="Admision", index=False, startrow=3)
    ws = writer.sheets["Admision"]
    ws.write(0, 0, "Admisión — ¿la novedad importa más allá del precio? (data-driven)", h)
    ws.write(1, 0, "Prueba: al controlar por 'ser el más barato', la experiencia casi no mueve P(ganar).", wrap)
    ws.write(2, 0, f"Veredicto: {r_adm['veredicto']}", wrap)
    ws.set_column(0, 0, 18); ws.set_column(1, 1, 26); ws.set_column(2, 3, 12)
    ws.insert_image("G4", str(OUT / "fig_admision.png"), {"x_scale": 0.8, "y_scale": 0.8})

    # ---------------- Sensibilidad ----------------
    r_sens = json.load(open(OUT / "sensibilidad_resultados.json", encoding="utf-8"))
    t1 = pd.DataFrame(r_sens["tornado_idea1"])
    t3 = pd.DataFrame(r_sens["tornado_idea3"])
    t1.to_excel(writer, sheet_name="Sensibilidad", index=False, startrow=2)
    ws = writer.sheets["Sensibilidad"]
    ws.write(0, 0, "Análisis de sensibilidad (tornado, one-at-a-time)", h)
    ws.write(1, 0, f"Idea 1 — salida: ganancia esperada en p* (base={r_sens['base_idea1_Estar']:.4f})")
    t3.to_excel(writer, sheet_name="Sensibilidad", index=False, startrow=2, startcol=6)
    ws.write(1, 6, f"Idea 3 — salida: brecha2 media (base={r_sens['base_idea3_brecha2']:.4f})")
    ws.insert_image("A12", str(OUT / "fig_tornado_idea1.png"), {"x_scale": 0.75, "y_scale": 0.75})
    ws.insert_image("A34", str(OUT / "fig_tornado_idea3.png"), {"x_scale": 0.75, "y_scale": 0.75})
    ws.set_column(0, 0, 16); ws.set_column(1, 3, 12)
    ws.set_column(6, 6, 16); ws.set_column(7, 9, 12)

print(f"OK -> {XLSX}")
