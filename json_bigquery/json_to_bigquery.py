from google.cloud import bigquery
import glob
import json
import re

client = (bigquery.Client.
          from_service_account_json("jan26-cde-crypto-d2cceea1a4dd.json"))

table_id = "jan26-cde-crypto.db_crypto.STAGING"

data = []

for path in glob.glob("data/*.json"):
    reg = re.compile(r'(BTCUSDT|ETHUSDT|BNBUSDT)_(\d\w)')
    crypto, interval = reg.findall(path)[0]
    with open(path, "r") as f:
        data_temp = json.load(f)

        for doc in data_temp:
            doc["interval"] = interval
            doc["crypto"] = crypto
        data.extend(data_temp)

rows_to_insert = [{"raw_data": doc} for doc in data]

job = client.load_table_from_json(
    rows_to_insert,
    table_id,
)

job.result()
print("OK")
