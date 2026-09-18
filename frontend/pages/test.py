import time
import psycopg2
from google.cloud import secretmanager
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    "jan26-cde-crypto-3e6ed86f7bdf.json")
# export GOOGLE_APPLICATION_CREDENTIALS="/chemin/vers/service-account.json"


def get_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient(credentials=credentials)

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"

    response = client.access_secret_version(
        request={"name": name}
    )

    return response.payload.data.decode("UTF-8")


while True:
    try:
        db_url = get_secret(
            project_id="jan26-cde-crypto",
            secret_id="clients-database-url-pooler"
                    )
        conn = psycopg2.connect(db_url)
        print("Connexion PostgreSQL réussie !")
        break
    except Exception as e:
        print(f"Connexion échouée : {e}")
        time.sleep(2)