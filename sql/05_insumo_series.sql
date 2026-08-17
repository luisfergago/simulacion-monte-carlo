-- insumo_series.csv  (Gen-2 · análisis 08_insumo) — 1 fila por oferta, entidad IGSS,
-- filtrado a los insumos estudiados.
-- Ámbito: salud (cat 26) · recepción electrónica · adjudicado · 2022-2025 · IGSS (entidad 52).
-- Verificado: 8,887 ofertas (Sitagliptina fosfato + Trastuzumab).
select
  p.nombre,
  p.caracteristicas,
  p.unidad_medida,
  eo.nog,
  c.fecha_publicacion::date as fecha,
  c.modalidad,
  eo.nit,
  eo.precio_unitario,
  eo.ranking_de_precio,
  eo.ofertas_por_producto
from estado_oferta eo
join concurso c on c.nog = eo.nog
join producto p on p.id = eo.producto
where c.entidad = '52'
  and c.tipo_recepcion = 'Sólo electrónicas'
  and c.estatus in (select estatus_gc from estatus where estatus_kemok = 'Adjudicado')
  and c.fecha_publicacion >= '2022-01-01' and c.fecha_publicacion < '2026-01-01'
  and exists (select 1 from concurso_categoria cc where cc.nog = c.nog and cc.categoria = 26)
  and p.nombre in ('Sitagliptina fosfato', 'Trastuzumab')