gcloud services enable cloudscheduler.googleapis.com

if gcloud scheduler jobs describe ingestion-hebdomadaire --location="europe-west1" 1>/dev/null 2>&1
then
  gcloud scheduler jobs update http ingestion-hebdomadaire \
    --schedule="0 9 * * 1" \
    --uri="https://get-data-from-binance-975242104567.europe-west1.run.app" \
    --http-method=POST \
    --time-zone="Europe/Paris" \
    --location="europe-west1" \
    --oidc-service-account-email="975242104567-compute@developer.gserviceaccount.com" \
    --oidc-token-audience="https://get-data-from-binance-975242104567.europe-west1.run.app/"
else
  gcloud scheduler jobs create http ingestion-hebdomadaire \
    --schedule="0 9 * * 1" \
    --uri="https://get-data-from-binance-975242104567.europe-west1.run.app" \
    --http-method=POST \
    --time-zone="Europe/Paris" \
    --location="europe-west1" \
    --oidc-service-account-email="975242104567-compute@developer.gserviceaccount.com" \
    --oidc-token-audience="https://get-data-from-binance-975242104567.europe-west1.run.app/"
fi

