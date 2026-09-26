gcloud services enable workflows.googleapis.com --location=jan26-cde-crypto
gcloud workflows deploy my-dbt-workflow \
  --location="europe-west1" \
  --source="./workflows.yml" \
  --service-account="975242104567-compute@developer.gserviceaccount.com"