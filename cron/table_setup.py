import os
import dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
from google.cloud import storage
from google.api_core.exceptions import Conflict

dotenv.load_dotenv()

# connetion au client google cloud storage grâce
# au compte de service avec les bon droits
client = storage.Client.from_service_account_json(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
)

# création d'un bucket gcp s'il n'existe pas encore
try:
    bucket_name = "trading-bot-bucket-epiphane-2026"
    bucket = client.create_bucket(bucket_name, location="europe-west1")
    print(f"Bucket '{bucket_name}' created.")
except Conflict:
    bucket = client.get_bucket(bucket_name)
    print(f"Bucket '{bucket_name}' already exists, connected instead.")

# envoie des données de transactions du mois dans 
# le bucket et suppression des données dans le volume 
date_info = datetime.now(tz=ZoneInfo("Europe/Paris"))

year, month = date_info.year, date_info.month

file_path = f"info_transactions/transactions-{year}-{month}.jsonl"

try:
    blob = bucket.blob(file_path)
    blob.upload_from_filename(file_path)
except Exception as e:
    print(e)
else:
    if blob.exists():
        os.remove(file_path)
