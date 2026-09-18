# 1. configuration gcloud 

PROJECT_ID="jan26-cde-crypto"
GITHUB_REPO="epiphane-egah/jan26_cde_crypto_streamlit"
SA_NAME="github-cloud-run"
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

# création d'un service account sur gcloud
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="GitHub Actions Cloud Run"
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
  "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"
# utiliser un service account sans crédentials
gcloud iam service-accounts add-iam-policy-binding \
  "975242104567-compute@developer.gserviceaccount.com" \
  --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
# autoriser le service account à utiliser le service cloud run
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.developer"
# autoriser le service account à utiliser le service artifact registry.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
# lien qui identifie le provider name
gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --format="value(name)"


# 2. configuration de secrets sur Github
# GCP_WIF_PROVIDER
# GCP_SERVICE_ACCOUNT



