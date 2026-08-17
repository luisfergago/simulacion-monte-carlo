-- areas_uso.csv  (Gen-2 · análisis 09_areas) — 1 fila por oferta, entidad IGSS.
-- Ámbito: salud (cat 26) · recepción electrónica · adjudicado · 2022-2025 · IGSS (entidad 52).
--
-- NOTA: el CSV original (110,355 ofertas) estaba filtrado por listas de medicamentos
-- por área (oncología / renal / cardiometabólico). Esta query trae el segmento IGSS
-- completo (superconjunto); src/09_areas.py clasifica por nombre y descarta el resto,
-- así que reproduce el análisis. Las listas de nombres viven en src/09_areas.py.
select
  eo.producto               as producto_id,
  p.nombre,
  p.caracteristicas,
  p.unidad_medida,
  eo.nog,
  c.fecha_publicacion::date as fecha,
  eo.nit,
  eo.precio_unitario,
  eo.ranking_de_precio
from estado_oferta eo
join concurso c on c.nog = eo.nog
join producto p on p.id = eo.producto
where c.entidad = '52'
  and c.tipo_recepcion = 'Sólo electrónicas'
  and c.estatus in (select estatus_gc from estatus where estatus_kemok = 'Adjudicado')
  and c.fecha_publicacion >= '2022-01-01' and c.fecha_publicacion < '2026-01-01'
  and exists (select 1 from concurso_categoria cc where cc.nog = c.nog and cc.categoria = 26)