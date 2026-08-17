-- nit_features.csv  (Gen-1 · Ideas) — 1 fila por proveedor (NIT) del segmento salud.
-- Las estadísticas se calculan sobre TODO el historial del NIT (no acotado al segmento),
-- por eso last_seen puede caer fuera de 2022-2025.
-- Verificado: 2,775 NIT; el NIT de muestra reproduce first/last/participaciones/ganados.
with seg_nits as (
  select distinct eo.nit
  from estado_oferta eo
  join concurso c on c.nog = eo.nog
  where c.tipo_recepcion = 'Sólo electrónicas'
    and c.estatus in (select estatus_gc from estatus where estatus_kemok = 'Adjudicado')
    and c.fecha_publicacion >= '2022-01-01' and c.fecha_publicacion < '2026-01-01'
    and exists (select 1 from concurso_categoria cc where cc.nog = c.nog and cc.categoria = 26)
)
select
  eo.nit,
  min(c.fecha_publicacion)::date                                    as first_seen,
  max(c.fecha_publicacion)::date                                    as last_seen,
  count(distinct eo.nog)                                            as n_part_total,
  count(distinct eo.nog) filter (where eo.estado like 'Adjudicaci%') as n_win_total
from estado_oferta eo
join concurso c on c.nog = eo.nog
where eo.nit in (select nit from seg_nits)
group by eo.nit