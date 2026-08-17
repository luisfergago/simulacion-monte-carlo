# Resumen ejecutivo y procedimiento de la Simulación Monte Carlo sobre Guatecompras

Segmento de estudio: compras de salud (categoría 26) por recepción electrónica,
concursos adjudicados entre 2022 y 2025. En total 460,181 concursos y 557,710
renglones, con 2,775 proveedores distintos.

---

## 1. Resumen ejecutivo

El proyecto simula cómo se decide el precio ganador en un renglón de compra
pública cuando compiten varios proveedores. El modelo es de licitación
competitiva: cada proveedor presenta una oferta y el modelo toma la oferta
mínima como base, ponderada por una probabilidad de admisión. Importante: no se
supone que el precio más bajo gane por regla —la adjudicación depende de la
evaluación de requisitos y puede ganar cualquier oferente—; se usa la oferta
mínima ponderada por una admisión estimada en 0.99 porque, empíricamente, en este
segmento el más barato gana ~99% de las veces. Sobre ese motor común se responden
dos preguntas.

La Idea 1 toma la perspectiva del proveedor y busca el precio que maximiza la
ganancia esperada. La Idea 3 toma la perspectiva del Estado y mide cuánto se
ahorra gracias a la competencia. Las dos comparten el mismo generador de ofertas,
entonces se construyó una sola vez y se reutiliza.

Resultados principales:

| Tema | Resultado |
|---|---|
| Competencia real | 54.4% de los renglones tienen una sola oferta, sin competencia |
| Número de competidores | media 2.02 por renglón, mediana 1 |
| Dispersión de ofertas | sigma = 0.209 (log-precio, estimador robusto MAD) |
| Correlación entre ofertas | rho = 0.0 calibrado, sin evidencia de colusión en promedio |
| Idea 1, precio óptimo | baja con la competencia: 1 rival p*=1.00, 3 rivales p*=0.88, 8 rivales p*=0.81 |
| Idea 1, driver dominante | la competencia (cuántos rivales), luego el costo propio |
| Idea 1, admisión | P(ganar dado que eres el más barato) = 0.99, plana por antigüedad |
| Idea 3, ahorro vs 2º postor | 15 a 17% donde hay competencia |
| Idea 3, driver dominante | la dispersión de ofertas, luego la colusión |

La utilidad es doble. Para el proveedor, el modelo dice a qué precio ofertar y
cuánto pesa cada factor en su ganancia. Para el Estado, el modelo cuantifica el
valor de la competencia y muestra que el mayor problema no es el nivel de precios
sino que la mitad de los renglones no tiene con quién competir.

---

## 2. Procedimiento común (motor compartido por las dos ideas)

### Paso 1. Definición del segmento
Se filtran los concursos de la base con cuatro condiciones: recepción electrónica,
fecha de publicación entre 2022 y 2025, categoría 26 (salud) y estatus canónico
Adjudicado. El estatus se normaliza con la tabla de mapeo `estatus`, que convierte
los textos crudos de Guatecompras a un estado único. Este segmento es grande y
homogéneo, entonces sirve para ajustar distribuciones sin mezclar realidades muy
distintas.

### Paso 2. Extracción de datos reales
Se conecta a PostgreSQL por SSH y se exportan los archivos con `COPY ... TO STDOUT`,
sin dejar archivos en el servidor. Los queries exactos de los seis CSV —con las
tablas, los filtros verificados contra la base y un script `dump_data.sh`— están en
`sql/` (ver `sql/README.md`).

1. `data/renglones_salud.csv` (557,710 filas). Una fila por renglón, con el número
   de ofertas, las unidades demandadas y el precio mínimo, promedio, desviación y
   máximo. Sale de agrupar `estado_oferta` por producto.
2. `data/ofertas_muestra.csv` (113,369 filas). Una fila por oferta individual, con
   NIT, marca, precio unitario, ranking de precio y estado. Es una muestra de uno
   de cada diez renglones (`mod(producto,10)=0`) que conserva todas las ofertas de
   los renglones elegidos.
3. `data/nit_features.csv` (2,775 filas). Una fila por proveedor, con su primera y
   última aparición, número de participaciones y número de concursos ganados. Se
   usa el índice de `oferta(nit)` para que la consulta sea barata.

### Paso 3. Calibración de parámetros (`src/01_calibrate.py`, `src/engine.py`)
Del dato se estiman cuatro cosas.

1. La distribución del número de competidores N. Se cuenta cuántos NIT distintos
   ofertan en cada renglón. La media es 2.02 y el 54.4% de los renglones tiene N=1.
   Se guarda la distribución empírica completa para muestrear de ella.
2. La dispersión de las ofertas. Se normaliza cada oferta contra la mediana de su
   renglón y se estima sigma con el MAD, que es resistente a valores extremos. El
   resultado es sigma = 0.209.
3. La correlación rho entre ofertas del mismo renglón. Se calibra buscando el valor
   que hace que la brecha simulada contra el segundo postor reproduzca la brecha
   observada por cada N. El mejor ajuste es rho = 0.0.
4. La probabilidad de que el más barato realmente gane, que sale en 0.99.

Un hallazgo de esta etapa es que el coeficiente de variación de precios sube con N,
pero eso se reproduce con sigma fija por puro efecto de muestreo, entonces subir
sigma con N sería contar dos veces el mismo fenómeno.

### Paso 4. Motor de simulación (`src/engine.py`)
Cada oferta se genera en escala normalizada, con la mediana del renglón igual a 1,
mediante una cópula gaussiana de un factor.

    oferta_i = exp( mu + sigma * ( raiz(rho)*Z + raiz(1-rho)*U_i ) )

Z es un choque común a todos los competidores del renglón, que representa el costo
del insumo o las condiciones de mercado, y en el extremo la colusión. U_i es el
componente propio de cada proveedor. El término mu se fija en -sigma^2/2 para que
la oferta esperada sea 1. El ganador del renglón se modela como la oferta mínima
(un estadístico de orden), que luego se pondera por la probabilidad de admisión:
no es que el más barato gane por regla, sino que empíricamente lo hace ~99% de las
veces (ver Paso 3, punto 4).

### Paso 5. Validación del motor
Se compara la brecha contra el segundo postor simulada contra la observada, por
cada nivel de N. El ajuste es cercano, por ejemplo en N=2 la observada es 0.188 y
la simulada 0.198, y las dos bajan de forma parecida hasta N=12. Esa coincidencia
es la prueba de que el motor reproduce el comportamiento real, entonces sirve como
base para las dos ideas.

---

## 3. Procedimiento de la Idea 1 (estrategia de precio del proveedor)

Archivo principal `src/04_idea1.py`, con la etapa de admisión en `src/06_admision.py`.

### Variables de entrada
1. Número de rivales que enfrenta el proveedor, tomado de la distribución empírica.
2. La oferta de cada rival, generada por el motor con sigma y rho calibrados.
3. El costo unitario propio, expresado como fracción de la referencia de mercado.
   Se usa 0.75 como caso de estudio.
4. La probabilidad de admisión, es decir la probabilidad de ganar dado que se es el
   más barato. Se estima del dato en 0.99.

### Correlación
Las ofertas de los rivales no son independientes entre sí porque comparten el
choque común Z de la cópula. La correlación entre dos ofertas cualquiera del mismo
renglón es exactamente rho. Además se estudió la relación entre la antigüedad del
proveedor y el resultado, que entra en la etapa de admisión.

### Pasos
1. Se arma la curva de probabilidad de ganar contra el precio propio. Para cada
   precio de una grilla se calcula la fracción de veces que ese precio es menor que
   la oferta mínima de los rivales, y se multiplica por la probabilidad de admisión.
2. Se calcula la ganancia esperada como probabilidad de ganar por el margen, donde
   el margen es el precio menos el costo.
3. Se busca el precio óptimo que maximiza la ganancia esperada. Este paso se repite
   para distintos números de rivales, entonces se obtiene cómo cambia la estrategia
   con la competencia.
4. Se estima la etapa de admisión con una regresión logística sobre datos reales,
   donde la variable a explicar es ganar y las explicativas son ser el más barato,
   la experiencia y la antigüedad del proveedor. El resultado muestra que ser el más
   barato domina y que la novedad casi no cambia la probabilidad de ganar, entonces
   la barrera del proveedor nuevo no está en ganar sino en participar.
5. Se arma la matriz de simulación con cien mil iteraciones, donde cada fila es un
   escenario con su número de rivales, la oferta mínima rival, si venció en precio,
   si fue admitido y el margen obtenido.

### Variables de salida
1. La probabilidad de ganar en función del precio.
2. El precio óptimo y su ganancia esperada.
3. Cómo se mueve el precio óptimo con el número de rivales.

Resultados: el precio óptimo baja al aumentar la competencia, de 1.00 con un rival a
0.81 con ocho rivales. Con la mezcla real de rivales el precio óptimo es 0.95, con
probabilidad de ganar 0.389 y ganancia esperada 0.078 de la referencia.

### Utilidad
El proveedor obtiene una regla de precio que equilibra ganar más seguido contra
ganar con más margen, y ve que su costo es lo único que controla mientras que la
competencia es lo que más pesa.

---

## 4. Procedimiento de la Idea 3 (competencia y gasto público)

Archivo principal `src/03_idea3.py`.

### Variables de entrada
1. Número de competidores por renglón, de la distribución empírica.
2. Las ofertas de cada competidor, del motor con sigma calibrada.
3. La correlación rho, que se usa como perilla de escenario para representar la
   colusión.

### Correlación
La correlación rho entre ofertas es central en esta idea. Cuando rho sube, las
ofertas se parecen más entre sí y el ahorro por competencia desaparece, entonces
variar rho es el experimento que muestra el efecto de la colusión.

### Pasos
1. Se define la métrica de ahorro como la brecha contra el segundo mejor postor,
   es decir la diferencia entre la segunda oferta más baja y la más baja, dividida
   entre la segunda. Esta métrica es robusta porque no depende de la cola alta de
   ofertas caras, y se puede medir directo del histórico.
2. Se mide la brecha observada por cada N en la muestra de ofertas reales.
3. Se simula la brecha por cada N y se compara contra la observada, lo que valida el
   modelo, y se repite el cálculo para varios valores de rho para ver la colusión.
4. Se arma la matriz de simulación con cien mil renglones, donde cada fila trae el
   número de competidores, la oferta ganadora, la del segundo postor, la brecha y un
   monto real tomado por remuestreo de los datos, con lo que se estima el dinero
   dejado sobre la mesa en quetzales.
5. Se marca una bandera de posible colusión en los renglones que tienen muchos
   competidores pero ofertas casi idénticas.

### Variables de salida
1. La brecha de ahorro contra el segundo postor, por nivel de competencia.
2. La distribución del ahorro y el dinero dejado sobre la mesa por renglón.
3. El efecto de la colusión sobre el ahorro.

Resultados: el 54.4% de los renglones no tiene competencia. Donde la hay, el ahorro
contra el segundo postor está entre 15 y 17%, y el dinero medio dejado sobre la mesa
ronda 5,074 quetzales por renglón. Al subir rho a 0.9 el ahorro cae a un rango de 3
a 7%, lo que muestra el daño de la colusión.

### Utilidad
El Estado obtiene una medida en quetzales del valor de la competencia, y ve que la
palanca más grande no es sumar un rival donde ya hay competencia sino llevar
competencia a los renglones que hoy tienen una sola oferta.

---

## 5. Análisis de sensibilidad (`src/07_sensibilidad.py`)

Se aplica el método de una variable a la vez. Se fija cada entrada en su valor base
y se mueve a un extremo bajo y uno alto, dejando las demás en base, y se mide cuánto
cambia la salida. Se usan números aleatorios comunes para que la diferencia refleje
el efecto de la entrada y no el ruido de la simulación.

En la Idea 1 la salida es la ganancia esperada en el precio óptimo. El factor que
más la mueve es la competencia, con un salto de 0.048 a 0.307 según el número de
rivales, y después el costo propio. La admisión, la dispersión y la correlación
pesan poco.

En la Idea 3 la salida es la brecha media de ahorro. El factor que más la mueve es
la dispersión de las ofertas, y después la colusión. Sumar un rival donde ya hay
competencia casi no cambia la brecha, lo que confirma que el ahorro grande viene del
margen extensivo, es decir de pasar renglones de una sola oferta a tener competencia.

---

## 6. Correspondencia con los requisitos del curso

| Requisito | Dónde está |
|---|---|
| Variables de entrada | Sección 3 y 4, con su distribución y fuente. Hoja Supuestos del Excel |
| Correlación | Cópula de un factor con rho. Hoja Correlacion del Excel |
| Variables de salida | Precio óptimo y ganancia en la Idea 1, ahorro y dinero sobre la mesa en la Idea 3 |
| Matriz de datos | Hojas Idea1_Matriz e Idea3_Matriz, cien mil filas cada una |
| Validación | Brecha simulada contra observada por N |
| Sensibilidad | Hoja Sensibilidad con los tornados |
| Utilidad | Sección 3 y 4, cierre de cada idea |

---

## 7. Cómo reproducir todo

El proyecto está en `~/Downloads/montecarlo_guatecompras`. El orden importa porque
cada script deja parámetros que usan los siguientes.

    python3.13 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    # los CSV de data/ y las salidas de output/ NO se versionan; los CSV se generan
    # por SSH con COPY (paso 2) y las salidas se generan al correr los scripts.
    .venv/bin/python src/01_calibrate.py     # parámetros base
    .venv/bin/python src/engine.py           # estima sigma, calibra rho, valida
    .venv/bin/python src/06_admision.py      # etapa de admisión (Idea 1)
    .venv/bin/python src/03_idea3.py         # Idea 3
    .venv/bin/python src/04_idea1.py         # Idea 1
    .venv/bin/python src/07_sensibilidad.py  # tornados
    .venv/bin/python src/05_export_excel.py  # entregable Excel (Ideas)

    # --- Propuestas (IGSS, productos concretos) ---
    .venv/bin/python src/p1_precio.py        # precio para ganar (Insulina glargina)
    .venv/bin/python src/p1_costo.py         # sensibilidad al costo (Propuesta 1)
    .venv/bin/python src/p2_ahorro.py        # valor de la competencia (cardiometabólicos)
    .venv/bin/python src/08_insumo.py        # precio del mismo insumo en el tiempo
    .venv/bin/python src/09_areas.py         # comparación por área clínica
    .venv/bin/python src/p_export_html.py    # presentación HTML
    .venv/bin/python src/p_export_excel.py   # entregable Excel (Propuestas)

El archivo `src/00_diagnostico.py` es opcional y sirvió para decidir que sigma es
fija y no crece con el número de competidores.

---

## 8. Propuestas (IGSS): productos concretos

Segunda iteración del proyecto, enfocada en la entidad IGSS y en productos con
nombre en lugar del segmento agregado. Cambia el ajuste: en vez de la cópula en
espacio normalizado, se ajusta una LogNormal directo al histórico de precios
reales (en quetzales) de cada producto. Es el entregable pulido (ver README), con
presentación HTML interactiva (`p_export_html.py`) y Excel con calculadoras
(`p_export_excel.py`).

### Propuesta 1 — Precio para ganar (proveedor), `src/p1_precio.py`
Caso: Insulina glargina (presentación dominante, ~5,900 concursos). Se ajusta el
precio de las ofertas rivales como LogNormal y el número de competidores con su
distribución empírica, se simulan las licitaciones —enfrentando N−1 rivales, condicional a que haya
competencia (N≥2)— y se busca el precio que maximiza la ganancia esperada.
Resultado: precio óptimo Q391.64, P(ganar|compites) 0.65, ganancia Q55.94/unidad (costo = margen bruto 30% sobre la mediana);
el 50.5% de los concursos no tiene competencia (ahí el techo es el precio de
referencia, no el rival); correlación precio–competidores −0.41. El complemento
`src/p1_costo.py` muestra cómo cambian el óptimo y P(ganar) con el costo, y el
trade-off contra una meta de P(ganar).

### Propuesta 2 — Valor de la competencia (Estado), `src/p2_ahorro.py`
Caso: medicamentos cardiometabólicos (~26,900 renglones, 4 años). Se mide el
ahorro frente al segundo postor por renglón y se simulan años por remuestreo
(bootstrap) para la distribución del ahorro anual, con un contrafactual acotado de
dar competencia a los renglones que hoy no la tienen. Resultado: 40% de renglones
sin competencia; ahorro anual mediano Q89.6 M; potencial +Q61.9 M/año.

### Análisis de apoyo
- `src/08_insumo.py`: precio del mismo insumo entre concursos (Sitagliptina,
  Trastuzumab), con validación del motor a nivel producto.
- `src/09_areas.py`: comparación de intensidad de competencia y ahorro por área
  clínica (cardiometabólico, renal, oncología).

### Nota sobre el precio
En las dos propuestas aplica el mismo encuadre: no se supone que gane el precio
más bajo por regla; la adjudicación depende de la evaluación de requisitos y puede
ganar cualquier oferente. El precio es el driver dominante en la práctica (el más
barato gana ~99%), pero no una regla.
