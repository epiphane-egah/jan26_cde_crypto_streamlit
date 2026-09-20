{{ config(
    materialized='incremental',
    unique_key='id_intervalle'
) }}

select 1 as id_intervalle, '1h' as code_intervalle, 'une heure' as libelle
union all
select 2, '1d', 'un jour'