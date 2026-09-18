# 1. configuration gcloud 

PROJECT_ID="jan26-cde-crypto"
GITHUB_REPO="epiphane-egah/jan26_cde_crypto_streamlit"
POOL_NAME="github"
PROVIDER_NAME="github-provider" # Nom du provider OIDC

# selectionner un projet
gcloud config set project "$PROJECT_ID"
# récupérer le project number
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")

# activer les services si ce n'est pas encore fait
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project=jan26-cde-crypto

# création d'un espace workload identity sur gcloud (système externe)
gcloud iam workload-identity-pools create "$POOL_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions"
# si tu recoit une demande de connection de mon ripo github, il faut accepter
# github de son côté garantit que c'est bien un de ses repo
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$GITHUB_REPO'"
# autoriser github à utiliser le service account crée.
gcloud iam service-accounts add-iam-policy-binding \
  "$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

# lien qui identifie le provider name
gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --format="value(name)"


# 2. configuration de secrets sur Github
# GCP_WIF_PROVIDER
# GCP_SERVICE_ACCOUNT

# ADC pour notre container
gcloud iam service-accounts create container-runtime \
  --display-name="Backend Cloud Run"

gcloud secrets add-iam-policy-binding clients-database-url-pooler \
  --member="serviceAccount:container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"



