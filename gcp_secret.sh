gcloud services enable secretmanager.googleapis.com

gcloud secrets create google-application-credentials \
  --data-file="secret.json"
# gcloud secrets versions add google-application-credentials --data-file="secret.json"

gcloud secrets list

# echo -n "epiphane" | gcloud secrets create db-user --data-file=-

gcloud secrets versions access latest --secret=google-application-credentials

# accorder au compte de service jan_cde_crypto_automatisation le rôle d'accès au service secret manager
# liste des comptes de service : gcloud iam service-accounts list --project=jan26-cde-crypto
gcloud secrets add-iam-policy-binding google-application-credentials \
    --member="serviceAccount:jan-cde-crypto-automatisation@jan26-cde-crypto.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"