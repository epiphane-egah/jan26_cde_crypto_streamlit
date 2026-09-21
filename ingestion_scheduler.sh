gcloud services enable cloudscheduler.googleapis.com

gcloud scheduler jobs create http ingestion-hebdomadaire \
--schedule="0 9 * * 1" \
--uri="https://get-data-from-binance-975242104567.europe-west1.run.app" \
--http-method=POST \
--time-zone="Europe/Paris" \
--location="europe-west1"