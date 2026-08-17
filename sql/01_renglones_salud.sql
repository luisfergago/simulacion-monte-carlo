-- renglones_salud.csv  (Gen-1 · Ideas) — 1 fila por renglón (nog, producto).
-- Ámbito: salud (cat 26) · recepción electrónica · adjudicado · 2022-2025 · TODAS las entidades.
-- Verificado: 558,019 renglones.
-- Nota: n_pos = número de posturas, reconstruido como count(distinct nit).
select
  eo.producto,
  eo.nog,
  c.modalidad,
  extract(year from c.fecha_publicacion)::int             as anio,
  c.entidad,
  count(*)                                                as n_ofertas,
  count(distinct eo.nit)                                  as n_pos,
  max(eo.unidades_demanda)                                as unidades_demanda,
  min(eo.precio_unitario)                                 as precio_min,
  avg(eo.precio_unitario)                                 as precio_avg,
  stddev_samp(eo.precio_unitario)                         as precio_sd,
  max(eo.precio_unitario)                                 as precio_max
from estado_oferta eo
join concurso c on c.nog = eo.nog
where c.tipo_recepcion = 'Sólo electrónicas'
  and c.estatus in (select estatus_gc from estatus where estatus_kemok = 'Adjudicado')
  and c.fecha_publicacion >= '2022-01-01' and c.fecha_publicacion < '2026-01-01'
  and exists (select 1 from concurso_categoria cc where cc.nog = c.nog and cc.categoria = 26)
group by eo.producto, eo.nog, c.modalidad, anio, c.entidad