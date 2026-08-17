"""
Genera una presentación HTML autocontenida y con estilo de las dos propuestas.

Un solo archivo con:
  - Chart.js incrustado (funciona sin internet).
  - Gráficos generados en el navegador (no imágenes de matplotlib).
  - Dos calculadoras interactivas con las fórmulas cerradas del modelo.
  - Ficha de datos de la muestra.

Salida: output/propuestas_montecarlo.html
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT, DATA = BASE / "output", BASE / "data"

r1 = json.load(open(OUT / "p1_resultados.json", encoding="utf-8"))
r2 = json.load(open(OUT / "p2_resultados.json", encoding="utf-8"))

draw = pd.read_csv(DATA / "propuestas.csv", dtype={"nit": str}, parse_dates=["fecha"])
draw = draw[draw.precio_unitario > 0].copy()
dg = draw[draw.nombre.str.lower().str.contains("glargina")].copy()
dg["pres"] = dg.caracteristicas.fillna("").str.strip() + " | " + dg.unidad_medida.fillna("")
dg = dg[dg.pres == dg.groupby("pres")["nog"].nunique().idxmax()]
pmf = dg.groupby("nog")["nit"].nunique().value_counts(normalize=True).sort_index()

SIGMA = float(r1["lognormal_sigma"]); SCALE = float(r1["lognormal_mediana"])
MU = math.log(SCALE); COSTO = float(r1["costo_supuesto_Q"]); POPT = float(r1["precio_optimo_Q"])
precios = dg.precio_unitario.values
PMIN, PMAX = float(np.percentile(precios, 2)), float(np.percentile(precios, 95))
PMF_JS = json.dumps([[int(n), round(float(p), 6)] for n, p in pmf.items()])


def _ficha(x):
    win = x.groupby("producto_id")["precio_unitario"].min()
    yr = x.groupby(x.fecha.dt.year)["producto_id"].nunique()
    return {"periodo": f"{x.fecha.min():%Y-%m} a {x.fecha.max():%Y-%m}",
            "concursos": int(x.nog.nunique()), "renglones": int(x.producto_id.nunique()),
            "ofertas": int(len(x)), "prov": int(x.nit.nunique()), "prod": int(x.nombre.nunique()),
            "pmed": float(win.median()), "p25": float(win.quantile(.25)), "p99": float(win.quantile(.99)),
            "anio": " · ".join(f"{int(a)}: {int(n):,}" for a, n in yr.items())}


FCAR, FGLA = _ficha(draw), _ficha(dg)

# histograma del ahorro anual (bootstrap) para el gráfico
ah = pd.read_csv(OUT / "p2_matriz.csv")["ahorro"].values
ys = len(ah) // int(r2["anios"])
rng = np.random.default_rng(1)
sim = np.array([ah[rng.integers(0, len(ah), ys)].sum() for _ in range(3000)]) / 1e6
lo, hi = np.percentile(sim, [0.5, 99.5])
cnt, edges = np.histogram(sim, bins=26, range=(lo, hi))
HLAB = json.dumps([round((edges[i] + edges[i + 1]) / 2) for i in range(len(cnt))])
HCNT = json.dumps([int(c) for c in cnt])
ACT = round(r2["ahorro_anual_mediana_Q"] / 1e6, 1)
POT = round(r2["ahorro_anual_potencial_Q"] / 1e6, 1)

chartlib = (OUT / "vendor_chartjs.js").read_text(encoding="utf-8")


def qm(x):
    return "Q" + format(round(x), ",")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--ind:#4f46e5;--ind2:#7c3aed;--sky:#0ea5e9;--grn:#10b981;--ink:#0f172a;--mut:#64748b;
--bg:#f8fafc;--card:#ffffff;--line:#e8ecf3}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg);line-height:1.6}
.hero{background:linear-gradient(120deg,#4f46e5,#7c3aed 55%,#0ea5e9);color:#fff;padding:46px 24px 40px}
.hero .wrap{max-width:1040px;margin:0 auto}
.hero h1{font-size:30px;font-weight:800;letter-spacing:-.5px;margin-bottom:8px}
.hero p{opacity:.92;font-size:16px;max-width:720px}
.chips{margin-top:16px;display:flex;gap:8px;flex-wrap:wrap}
.chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);
padding:5px 12px;border-radius:999px;font-size:13px;font-weight:600}
nav{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line)}
nav .wrap{max-width:1040px;margin:0 auto;padding:10px 24px;display:flex;gap:18px;flex-wrap:wrap}
nav a{color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;opacity:.75}
nav a:hover{opacity:1;color:var(--ind)}
main{max-width:1040px;margin:0 auto;padding:26px 24px 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:26px 28px;
margin:22px 0;box-shadow:0 8px 24px rgba(15,23,42,.05);animation:rise .5s ease both}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
h2{font-size:22px;font-weight:800;letter-spacing:-.3px;margin-bottom:4px}
.tag{display:inline-block;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;
padding:3px 10px;border-radius:8px;margin-bottom:12px}
.t-prov{background:#eef2ff;color:var(--ind)}.t-est{background:#ecfdf5;color:var(--grn)}
.lead{color:var(--mut);margin:6px 0 4px;font-size:15px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:18px 0}
.kpi{background:linear-gradient(180deg,#fbfcff,#f3f5fb);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.kpi .v{font-size:24px;font-weight:800;color:var(--ind)}
.kpi.est .v{color:var(--grn)}
.kpi .l{font-size:12.5px;color:var(--mut);margin-top:2px}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:6px}
@media(max-width:760px){.charts{grid-template-columns:1fr}}
.chartbox{border:1px solid var(--line);border-radius:14px;padding:14px 14px 8px}
.chartbox h4{font-size:14px;color:var(--ink);margin-bottom:8px;font-weight:700}
.canvas-h{position:relative;height:280px}
.cap{font-size:12px;color:var(--mut);margin-top:8px}
dl{display:grid;grid-template-columns:150px 1fr;gap:6px 16px;margin-top:14px;font-size:14px}
dt{font-weight:700;color:var(--ink)}dd{color:#334155}
table{border-collapse:collapse;width:100%;margin-top:12px;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:9px 10px;text-align:left}
th{color:var(--mut);font-size:12.5px;text-transform:uppercase;letter-spacing:.4px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.calc{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.calc{grid-template-columns:1fr}}
.panel{background:linear-gradient(180deg,#fbfcff,#f5f7fd);border:1px solid var(--line);border-radius:16px;padding:18px 20px}
.panel h4{font-size:15px;margin-bottom:10px}
.field{margin:10px 0}
.field label{display:block;font-size:13px;color:var(--mut);margin-bottom:4px;font-weight:600}
.field input{font-size:17px;font-weight:600;padding:10px 12px;border:1.5px solid #cbd5e1;border-radius:10px;width:100%;
background:#fffbeb}
.field input:focus{outline:none;border-color:var(--ind)}
.res{display:flex;gap:14px;margin-top:14px;flex-wrap:wrap}
.res .b{flex:1;min-width:130px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;text-align:center}
.res .b .v{font-size:26px;font-weight:800;color:var(--grn)}
.res .b .l{font-size:12px;color:var(--mut);margin-top:2px}
.note{font-size:13px;color:#7c5e10;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:11px 14px;margin-top:14px}
footer{max-width:1040px;margin:0 auto;padding:16px 24px 48px;color:var(--mut);font-size:13px}
"""

APPJS = r"""
const MU=__MU__,SIGMA=__SIGMA__,SCALE=__SCALE__,COSTO=__COSTO__,POPT=__POPT__,PMIN=__PMIN__,PMAX=__PMAX__;
const PMF=__PMF__,HLAB=__HLAB__,HCNT=__HCNT__,ACT=__ACT__,POT=__POT__;
function erf(x){var s=x<0?-1:1;x=Math.abs(x);var a1=.254829592,a2=-.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p=.3275911;
var t=1/(1+p*x);return s*(1-(((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*Math.exp(-x*x));}
function lncdf(x){return x<=0?0:.5*(1+erf((Math.log(x)-MU)/(SIGMA*Math.SQRT2)));}
function ninv(p){var a=[-3.969683028665376e1,2.209460984245205e2,-2.759285104469687e2,1.38357751867269e2,-3.066479806614716e1,2.506628277459239],
b=[-5.447609879822406e1,1.615858368580409e2,-1.556989798598866e2,6.680131188771972e1,-1.328068155288572e1],
c=[-7.784894002430293e-3,-.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783],
d=[7.784695709041462e-3,.3224671290700398,2.445134137142996,3.754408661907416],pl=.02425,ph=1-pl,q,r;
if(p<pl){q=Math.sqrt(-2*Math.log(p));return(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
if(p<=ph){q=p-.5;r=q*q;return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);}
q=Math.sqrt(-2*Math.log(1-p));return-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
function lninv(p){return Math.exp(MU+SIGMA*ninv(p));}
function pwinAt(p){var S=1-lncdf(p),w=0,tot=0;for(var k=0;k<PMF.length;k++){if(PMF[k][0]>=2){w+=PMF[k][1]*Math.pow(S,PMF[k][0]-1);tot+=PMF[k][1];}}return tot>0?w/tot:1;}
function Q(v){return 'Q'+v.toLocaleString('es-GT',{maximumFractionDigits:2});}
function calc1(){var p=+document.getElementById('precio').value,c=+document.getElementById('costo').value;
var w=pwinAt(p);document.getElementById('pwin').textContent=(w*100).toFixed(1)+'%';
document.getElementById('prof').textContent=Q(w*(p-c));}
function calc2(){var N=Math.max(1,Math.round(+document.getElementById('ncomp').value));
var pr=lninv(1-Math.pow(.5,1/N));document.getElementById('pwn').textContent=Q(pr);
document.getElementById('sav').textContent=((1-pr/SCALE)*100).toFixed(1)+'%';}
var GRID='#eef1f6',AX={grid:{color:GRID},ticks:{color:'#64748b'}};
function line(id,lab,data,color,ytitle,mark){
var ds=[{data:data,borderColor:color,backgroundColor:color+'22',fill:true,tension:.35,pointRadius:0,borderWidth:2.5}];
if(mark!=null){var pt=data.map((v,i)=>i===mark?v:null);ds.push({data:pt,showLine:false,pointRadius:6,pointBackgroundColor:'#f59e0b',pointBorderColor:'#fff',pointBorderWidth:2});}
new Chart(document.getElementById(id),{type:'line',data:{labels:lab,datasets:ds},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},
tooltip:{callbacks:{title:it=>'precio Q'+it[0].label}}},
scales:{y:{title:{display:true,text:ytitle},grid:{color:GRID}},x:{title:{display:true,text:'mi precio (Q)'},grid:{display:false},ticks:{maxTicksLimit:8}}}}});}
function bar(id,lab,data,colors,ytitle){
new Chart(document.getElementById(id),{type:'bar',data:{labels:lab,datasets:[{data:data,backgroundColor:colors,borderRadius:6}]},
options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
scales:{y:{title:{display:true,text:ytitle},grid:{color:GRID}},x:{grid:{display:false},ticks:{color:'#64748b'}}}}});}
function build(){var G=[],pw=[],pr=[],lab=[];
for(var i=0;i<=60;i++){var p=PMIN+(PMAX-PMIN)*i/60;G.push(p);lab.push(Math.round(p));
pw.push(+(pwinAt(p)*100).toFixed(2));pr.push(+(pwinAt(p)*(p-COSTO)).toFixed(2));}
var jm=0;for(var i=1;i<pr.length;i++)if(pr[i]>pr[jm])jm=i;
line('cPwin',lab,pw,'#4f46e5','probabilidad de ganar (%)',null);
line('cProfit',lab,pr,'#7c3aed','ganancia esperada por unidad (Q)',jm);
bar('cHist',HLAB,HCNT,'#10b981','años simulados');
bar('cActPot',['Actual','Potencial'],[ACT,POT],['#10b981','#6ee7b7'],'ahorro anual (millones Q)');}
window.addEventListener('load',function(){calc1();calc2();build();});
"""
for k, v in {"__MU__": repr(MU), "__SIGMA__": repr(SIGMA), "__SCALE__": repr(SCALE),
             "__COSTO__": repr(COSTO), "__POPT__": repr(POPT), "__PMIN__": repr(PMIN),
             "__PMAX__": repr(PMAX), "__PMF__": PMF_JS, "__HLAB__": HLAB, "__HCNT__": HCNT,
             "__ACT__": repr(ACT), "__POT__": repr(POT)}.items():
    APPJS = APPJS.replace(k, v)

head = ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Monte Carlo — Compras del IGSS</title><style>' + CSS + '</style></head><body>')

hero = f"""<div class="hero"><div class="wrap">
<h1>Simulación Monte Carlo sobre compras del IGSS</h1>
<p>Dos propuestas sobre datos públicos de Guatecompras. Una desde el proveedor, que decide su precio, y otra desde el Estado, que valora la competencia.</p>
<div class="chips"><span class="chip">Guatecompras · IGSS</span><span class="chip">Salud · 2022-2025</span>
<span class="chip">Método Monte Carlo</span><span class="chip">{FCAR['renglones']+FGLA['renglones']:,} renglones</span></div>
</div></div>
<nav><div class="wrap"><a href="#datos">Datos</a><a href="#p1">Propuesta 1</a>
<a href="#p2">Propuesta 2</a><a href="#calc">Calculadora</a></div></nav><main>"""

datos = f"""<div class="card" id="datos"><h2>Datos y muestra</h2>
<p class="lead">Todo viene de Guatecompras, entidad IGSS, salud con recepción electrónica y concursos adjudicados. La modalidad dominante es Compra Directa.</p>
<table><tr><th>Detalle</th><th>Cardiometabólicos (Prop. 2)</th><th>Insulina glargina (Prop. 1)</th></tr>
<tr><td>Periodo</td><td>{FCAR['periodo']}</td><td>{FGLA['periodo']}</td></tr>
<tr><td>Concursos</td><td class="num">{FCAR['concursos']:,}</td><td class="num">{FGLA['concursos']:,}</td></tr>
<tr><td>Renglones</td><td class="num">{FCAR['renglones']:,}</td><td class="num">{FGLA['renglones']:,}</td></tr>
<tr><td>Ofertas</td><td class="num">{FCAR['ofertas']:,}</td><td class="num">{FGLA['ofertas']:,}</td></tr>
<tr><td>Proveedores distintos</td><td class="num">{FCAR['prov']}</td><td class="num">{FGLA['prov']}</td></tr>
<tr><td>Productos distintos</td><td class="num">{FCAR['prod']}</td><td class="num">{FGLA['prod']}</td></tr>
<tr><td>Precio ganador, mediana (p25 a p99)</td><td class="num">Q{FCAR['pmed']:.2f} (Q{FCAR['p25']:.2f} a Q{FCAR['p99']:.0f})</td><td class="num">Q{FGLA['pmed']:.2f} (Q{FGLA['p25']:.0f} a Q{FGLA['p99']:.0f})</td></tr>
<tr><td>Renglones por año</td><td>{FCAR['anio']}</td><td>{FGLA['anio']}</td></tr></table>
<p class="note">La insulina glargina la surten solo {FGLA['prov']} proveedores en el periodo, un mercado concentrado, y por eso su competencia es baja. En cambio en cardiometabólicos compiten {FCAR['prov']} proveedores en {FCAR['prod']} productos distintos.</p></div>"""

p1 = f"""<div class="card" id="p1"><span class="tag t-prov">Óptica del proveedor</span>
<h2>Propuesta 1 — ¿A qué precio ofertar para ganar?</h2>
<p class="lead">Para la Insulina glargina se ajusta el precio de las ofertas rivales como LogNormal y el número de competidores con su distribución empírica, se simulan las licitaciones y se busca el precio que maximiza la ganancia esperada.</p>
<div class="kpis">
<div class="kpi"><div class="v">Q{r1['precio_optimo_Q']:.2f}</div><div class="l">precio óptimo</div></div>
<div class="kpi"><div class="v">{r1['P_ganar_opt']*100:.0f}%</div><div class="l">prob. de ganar si compites</div></div>
<div class="kpi"><div class="v">Q{r1['ganancia_esperada_Q']:.2f}</div><div class="l">ganancia esperada por unidad</div></div>
<div class="kpi"><div class="v">{r1['corr_precio_vs_N_spearman']:.2f}</div><div class="l">correlación precio vs competidores</div></div></div>
<div class="charts">
<div class="chartbox"><h4>Probabilidad de ganar según mi precio</h4><div class="canvas-h"><canvas id="cPwin"></canvas></div></div>
<div class="chartbox"><h4>Ganancia esperada y precio óptimo</h4><div class="canvas-h"><canvas id="cProfit"></canvas></div>
<div class="cap">El punto naranja marca el precio óptimo. A la izquierda del costo la ganancia se vuelve negativa.</div></div></div>
<dl><dt>Entradas</dt><dd>competidores, precio de cada oferta rival, mi costo unitario.</dd>
<dt>Correlación</dt><dd>a más competidores, menor precio ganador (Spearman {r1['corr_precio_vs_N_spearman']:.3f}).</dd>
<dt>Salida</dt><dd>probabilidad de ganar según el precio y precio óptimo.</dd>
<dt>Utilidad</dt><dd>una regla de precio con su probabilidad de ganar y su margen.</dd></dl></div>"""

p2 = f"""<div class="card" id="p2"><span class="tag t-est">Óptica del Estado</span>
<h2>Propuesta 2 — El valor de la competencia</h2>
<p class="lead">Para los medicamentos cardiometabólicos se mide el ahorro frente al segundo postor y se simulan años por remuestreo, para obtener la distribución del ahorro anual y un contrafactual de dar competencia a los renglones que hoy no la tienen.</p>
<div class="kpis">
<div class="kpi est"><div class="v">{qm(r2['ahorro_anual_mediana_Q'])}</div><div class="l">ahorro anual (mediana)</div></div>
<div class="kpi est"><div class="v">{r2['pct_sin_competencia']*100:.0f}%</div><div class="l">renglones sin competencia</div></div>
<div class="kpi est"><div class="v">{qm(r2['contrafactual_extra_anual_Q'])}</div><div class="l">ahorro extra potencial</div></div>
<div class="kpi est"><div class="v">{r2['corr_precio_norm_vs_N_spearman']:.2f}</div><div class="l">correlación precio vs competidores</div></div></div>
<div class="charts">
<div class="chartbox"><h4>Distribución del ahorro anual (Monte Carlo)</h4><div class="canvas-h"><canvas id="cHist"></canvas></div>
<div class="cap">Cada barra es cuántos años simulados cayeron en ese nivel de ahorro. Rango P5 a P95: {qm(r2['ahorro_anual_P5_Q'])} a {qm(r2['ahorro_anual_P95_Q'])}.</div></div>
<div class="chartbox"><h4>Ahorro actual vs potencial</h4><div class="canvas-h"><canvas id="cActPot"></canvas></div>
<div class="cap">Potencial, si los renglones sin competencia lograran el descuento mediano observado.</div></div></div>
<dl><dt>Entradas</dt><dd>competidores por renglón, precio ganador y del 2º postor, valor de la línea.</dd>
<dt>Correlación</dt><dd>dentro de un producto, a más competidores menor precio (Spearman {r2['corr_precio_norm_vs_N_spearman']:.3f}).</dd>
<dt>Salida</dt><dd>distribución del ahorro anual y ahorro potencial.</dd>
<dt>Utilidad</dt><dd>pone en quetzales el valor de la competencia y dónde conviene abrir los procesos.</dd></dl></div>"""

calc = f"""<div class="card" id="calc"><h2>Calculadora interactiva</h2>
<p class="lead">Las dos preguntas tienen fórmula cerrada, entonces se calculan en vivo. Parámetros de la Insulina glargina.</p>
<div class="calc">
<div class="panel"><h4>Caso 1 — ¿Cuál es mi probabilidad de ganar?</h4>
<div class="field"><label>Mi precio (Q)</label><input id="precio" type="number" step="1" value="{POPT:.0f}" oninput="calc1()"></div>
<div class="field"><label>Mi costo (Q)</label><input id="costo" type="number" step="1" value="{COSTO:.0f}" oninput="calc1()"></div>
<div class="res"><div class="b"><div class="v" id="pwin">-</div><div class="l">prob. de ganar si compites</div></div>
<div class="b"><div class="v" id="prof">-</div><div class="l">ganancia esperada por unidad</div></div></div>
<div class="note">El costo es privado; acá se supone un <b>margen bruto del 30%</b> sobre la mediana (costo ≈ Q{COSTO:.0f}). La probabilidad es <b>condicional a que haya competencia</b>: el {r1['P_sin_competencia']*100:.0f}% de los concursos no la tiene, y ahí el techo es el precio de referencia, no el rival.</div></div>
<div class="panel"><h4>Caso 2 — ¿Cuánto baja el precio con más competencia?</h4>
<div class="field"><label>Número de competidores N</label><input id="ncomp" type="number" step="1" min="1" value="3" oninput="calc2()"></div>
<div class="res"><div class="b"><div class="v" id="pwn">-</div><div class="l">precio ganador esperado</div></div>
<div class="b"><div class="v" id="sav">-</div><div class="l">ahorro frente a un solo oferente</div></div></div>
<div class="note">Usa la mediana del mínimo de N ofertas del mismo producto. Es el efecto limpio de la competencia.</div></div>
</div></div>"""

footer = ("</main><footer><p>Método Monte Carlo. Las entradas se ajustan a datos reales, "
          "se simulan miles de licitaciones y se lee la distribución del resultado. El costo del "
          "proveedor es una entrada, no un dato del portal. Fuente, Guatecompras, entidad IGSS. "
          "Gana el de menor precio en cerca del 99% de los casos, no siempre, por la evaluación de requisitos.</p></footer>")

html = (head + hero + datos + p1 + p2 + calc + footer
        + "<script>" + chartlib + "</script><script>" + APPJS + "</script></body></html>")
(OUT / "propuestas_montecarlo.html").write_text(html, encoding="utf-8")
print(f"OK -> {OUT/'propuestas_montecarlo.html'}  ({len(html)//1024} KB)")
