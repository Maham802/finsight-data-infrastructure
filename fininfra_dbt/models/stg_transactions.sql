{{ config(materialized='view') }}

select
    v:id::string as transaction_id,
    v:account_id::string as account_id,
    v:amount::number(18, 2) as amount,
    v:txn_type::string as transaction_type,
    v:related_account_id::string as related_account_id,
    v:status::string as status,
    v:created_at::timestamp_tz as transaction_time,
    current_timestamp() as load_timestamp
from {{ source('raw', 'transactions') }}