# autoriser l'utilisation de l'api artifact registry
gcloud services enable artifactregistry.googleapis.com

# créer un repo
gcloud artifacts repositories describe jan26-cde-crypto --location=europe-west1 &>/dev/null || \
gcloud artifacts repositories create jan26-cde-crypto \
  --repository-format=docker \
  --location=europe-west1

# 3. Configurer l'authentification Docker pour pouvoir push
gcloud auth configure-docker europe-west1-docker.pkg.dev

# 4. Vérifier que ça a bien été créé
# gcloud artifacts repositories list

TAG=$(date +%Y-%m-%d_%Hh%M)
docker buildx build --platform linux/amd64 -t trading-bot-frontend:$TAG frontend/.
# --build-arg VITE_API_URL="https://jan26-cde-crypto-api-975242104567.europe-west1.run.app" \


docker tag trading-bot-frontend:$TAG europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-frontend:$TAG
docker push europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-frontend:$TAG

gcloud run deploy jan26-cde-crypto-service \
  --image=europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-frontend:$TAG \
  --platform=managed \
  --region=europe-west1 \
  --port=8501 \
  --service-account=container-runtime@jan26-cde-crypto.iam.gserviceaccount.com  \
  --allow-unauthenticated