{{ config(
    materialized='table',
    unique_key='id_crypto'
) }}

select 1 as id_crypto, 'BTCUSDT' as symbole, 'Bitcoin' as nom
union all
select 2, 'ETHUSDT', 'Ethereum'
union all
select 3, 'BNBUSDT', 'Binance Coin'