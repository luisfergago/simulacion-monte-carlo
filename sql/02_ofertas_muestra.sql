-- ofertas_muestra.csv  (Gen-1 · Ideas) — 1 fila por oferta.
-- Ámbito: salud (cat 26) · recepción electrónica · adjudicado · 2022-2025 · TODAS las entidades.
-- Muestra: se conservan todas las ofertas de los renglones con mod(producto,10)=0.
-- Verificado: 113,369 ofertas.
select
  eo.producto,
  eo.nog,
  eo.nit,
  eo.marca,
  eo.precio_unitario,
  eo.ranking_de_precio,
  eo.ofertas_por_producto,
  eo.unidades_demanda,
  eo.unidades_oferta,
  eo.estado,
  c.modalidad,
  extract(year from c.fecha_publicacion)::int as anio
from estado_oferta eo
join concurso c on c.nog = eo.nog
where c.tipo_recepcion = 'Sólo electrónicas'
  and c.estatus in (select estatus_gc from estatus where estatus_kemok = 'Adjudicado')
  and c.fecha_publicacion >= '2022-01-01' and c.fecha_publicacion < '2026-01-01'
  and exists (select 1 from concurso_categoria cc where cc.nog = c.nog and cc.categoria = 26)
  and (eo.producto % 10) = 0