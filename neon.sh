#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Configuration
# ============================================================

PROJECT_NAME="jan26-cde-crypto"
DATABASE="Clients"

DDL_FILE="../postgres/postgres_ddl.sql"
ENV_FILE=".env"

# Secret contenant les credentials applicatifs
SECRET_NAME="google-application-credentials"

# Secret qui contiendra l'URL poolée vers la base Clients
DATABASE_SECRET_NAME="clients-database-url-pooler"

# ============================================================
# Récupération des credentials depuis GCP Secret Manager
# ============================================================

echo "=== Configuration du projet GCP ==="

gcloud config set project "$PROJECT_NAME"

CONFIG="$(
    gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$PROJECT_NAME"
)"

DB_USER="$(echo "$CONFIG" | jq -r '.user')"
DB_PASSWORD="$(echo "$CONFIG" | jq -r '.password')"
ROOT_PASSWORD="$(echo "$CONFIG" | jq -r '.root_password')"

: "${DB_USER:?username absent du secret $SECRET_NAME}"
: "${DB_PASSWORD:?password absent du secret $SECRET_NAME}"

# ============================================================
# Vérifications
# ============================================================

command -v gcloud >/dev/null 2>&1 || {
    echo "ERREUR: gcloud CLI n'est pas installé."
    exit 1
}

command -v jq >/dev/null 2>&1 || {
    echo "ERREUR: jq n'est pas installé."
    exit 1
}

command -v neon >/dev/null 2>&1 || {
    echo "ERREUR: Neon CLI n'est pas installé."
    echo "npm install -g neon@latest"
    exit 1
}

command -v psql >/dev/null 2>&1 || {
    echo "ERREUR: psql n'est pas installé."
    exit 1
}

command -v python3 >/dev/null 2>&1 || {
    echo "ERREUR: python3 n'est pas installé."
    exit 1
}

[ -f "$DDL_FILE" ] || {
    echo "ERREUR: fichier DDL introuvable : $DDL_FILE"
    exit 1
}

# ============================================================
# Projet Neon
# ============================================================

echo
echo "=== Projet Neon : $PROJECT_NAME ==="

PROJECT_EXISTS="$(
    neon projects list --output json 2>/dev/null \
    | python3 -c '
import json
import sys

name = sys.argv[1]

try:
    data = json.load(sys.stdin)

    if isinstance(data, dict):
        projects = data.get("projects", data.get("data", []))
    else:
        projects = data

    found = any(
        isinstance(p, dict) and p.get("name") == name
        for p in projects
    )

    print("1" if found else "0")

except Exception:
    print("0")
' "$PROJECT_NAME"
)"

if [ "$PROJECT_EXISTS" = "0" ]; then

    echo "Création du projet Neon..."

    neon projects create \
        --name "$PROJECT_NAME" \
        --pg-version 16

else

    echo "Projet Neon déjà existant."

fi

# ============================================================
# Link Neon
# ============================================================

echo
echo "=== Association du projet au répertoire ==="

if [ ! -e ".neon" ]; then

    echo
    echo "Le répertoire n'est pas encore lié."
    echo "Sélectionne le projet : $PROJECT_NAME"
    echo

    neon link

else

    echo "Configuration .neon déjà présente."

fi

echo
echo "Contexte Neon :"

neon status || true

# ============================================================
# Récupération des URLs Neon
# ============================================================

echo
echo "=== Récupération des variables Neon ==="

neon env pull \
    --service postgres \
    --file "$ENV_FILE"

set -a

# shellcheck disable=SC1090
source "$ENV_FILE"

set +a

# DATABASE_URL          = URL poolée Neon
# DATABASE_URL_UNPOOLED = URL directe Neon

: "${DATABASE_URL:?DATABASE_URL absente de $ENV_FILE}"
: "${DATABASE_URL_UNPOOLED:?DATABASE_URL_UNPOOLED absente de $ENV_FILE}"

# DB_USER / DB_PASSWORD ont déjà été récupérés depuis Secret Manager.
# On ne les remplace pas ici.

# ============================================================
# Diagnostic connexion Neon
# ============================================================

echo
echo "=== Connexion Neon ==="

psql "$DATABASE_URL_UNPOOLED" \
    -v ON_ERROR_STOP=1 \
    -c "
        SELECT
            current_database() AS database,
            current_user       AS user;
    "

# ============================================================
# Création de la base Clients
# ============================================================

echo
echo "=== Base $DATABASE ==="

DATABASE_EXISTS="$(
    psql "$DATABASE_URL_UNPOOLED" \
        -v ON_ERROR_STOP=1 \
        -tAc \
        "SELECT 1
         FROM pg_database
         WHERE datname = '$DATABASE';"
)"

if [ "$DATABASE_EXISTS" = "1" ]; then

    echo "La base \"$DATABASE\" existe déjà."

else

    echo "Création de la base \"$DATABASE\"..."

    psql "$DATABASE_URL_UNPOOLED" \
        -v ON_ERROR_STOP=1 \
        -c "CREATE DATABASE \"$DATABASE\";"

    echo "Base \"$DATABASE\" créée."

fi

# ============================================================
# Construction de l'URL ADMIN vers Clients
# ============================================================

echo
echo "=== Construction de l'URL admin vers $DATABASE ==="

ADMIN_URL="$(
    python3 - "$DATABASE_URL_UNPOOLED" "$DATABASE" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit

source = sys.argv[1]
database = sys.argv[2]

u = urlsplit(source)

print(
    urlunsplit((
        u.scheme,
        u.netloc,
        "/" + database,
        u.query,
        u.fragment,
    ))
)
PY
)"

# ============================================================
# Vérification de la base Clients
# ============================================================

echo
echo "=== Vérification de $DATABASE ==="

CURRENT_DATABASE="$(
    psql "$ADMIN_URL" \
        -v ON_ERROR_STOP=1 \
        -tAc "SELECT current_database();"
)"

if [ "$CURRENT_DATABASE" != "$DATABASE" ]; then

    echo "ERREUR: connecté à '$CURRENT_DATABASE' au lieu de '$DATABASE'."
    exit 1

fi

echo "Connexion à \"$DATABASE\" OK."

# ============================================================
# Application du DDL
# ============================================================

echo
echo "=== Application du DDL ==="

psql "$ADMIN_URL" \
    -v ON_ERROR_STOP=1 \
    -f "$DDL_FILE"

echo "DDL appliqué."

# ============================================================
# Création du rôle applicatif
# ============================================================

echo
echo "=== Utilisateur applicatif : $DB_USER ==="

psql "$ADMIN_URL" \
    -v ON_ERROR_STOP=1 \
    -v db_user="$DB_USER" \
    -v db_password="$DB_PASSWORD" <<'SQL'

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'db_user',
    :'db_password'
)
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = :'db_user'
)
\gexec

SQL

# ============================================================
# Mise à jour du mot de passe du rôle
# ============================================================
#
# CREATE ROLE ne modifie pas le mot de passe si le rôle existe.
# Cette commande garantit que le mot de passe Neon correspond
# toujours à celui stocké dans Secret Manager.
# ============================================================

echo
echo "=== Synchronisation du mot de passe applicatif ==="

psql "$ADMIN_URL" \
    -v ON_ERROR_STOP=1 \
    -v db_user="$DB_USER" \
    -v db_password="$DB_PASSWORD" <<'SQL'

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L',
    :'db_user',
    :'db_password'
)
\gexec

SQL

# ============================================================
# Permissions
# ============================================================

echo
echo "=== Permissions ==="

psql "$ADMIN_URL" \
    -v ON_ERROR_STOP=1 \
    -v db_user="$DB_USER" <<'SQL'

SELECT format(
    'GRANT CONNECT ON DATABASE %I TO %I',
    current_database(),
    :'db_user'
)
\gexec

SELECT format(
    'GRANT USAGE ON SCHEMA public TO %I',
    :'db_user'
)
\gexec

SELECT format(
    'GRANT SELECT, INSERT, UPDATE, DELETE
     ON ALL TABLES IN SCHEMA public TO %I',
    :'db_user'
)
\gexec

SELECT format(
    'GRANT USAGE, SELECT
     ON ALL SEQUENCES IN SCHEMA public TO %I',
    :'db_user'
)
\gexec

-- Futures tables créées par l'utilisateur admin courant.

SELECT format(
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT SELECT, INSERT, UPDATE, DELETE
     ON TABLES TO %I',
    :'db_user'
)
\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public
     GRANT USAGE, SELECT
     ON SEQUENCES TO %I',
    :'db_user'
)
\gexec

SQL

# ============================================================
# Construction de l'URL poolée vers Clients
# ============================================================
#
# On part de DATABASE_URL (pooler Neon) et on :
#
#   1. remplace la database par Clients
#   2. remplace le user par DB_USER
#   3. remplace le password par DB_PASSWORD
#
# Le hostname du pooler et les paramètres Neon sont conservés.
# ============================================================

echo
echo "=== Construction de l'URL poolée applicative ==="

CLIENTS_POOLER_URL="$(
    python3 - \
        "$DATABASE_URL" \
        "$DATABASE" \
        "$DB_USER" \
        "$DB_PASSWORD" <<'PY'

import sys
from urllib.parse import (
    urlsplit,
    urlunsplit,
    quote,
)

source = sys.argv[1]
database = sys.argv[2]
username = sys.argv[3]
password = sys.argv[4]

u = urlsplit(source)

host = u.hostname

if not host:
    raise SystemExit(
        "Impossible de déterminer le hostname de DATABASE_URL"
    )

port = f":{u.port}" if u.port else ""

encoded_user = quote(username, safe="")
encoded_password = quote(password, safe="")

netloc = (
    f"{encoded_user}:"
    f"{encoded_password}"
    f"@{host}"
    f"{port}"
)

result = urlunsplit((
    u.scheme,
    netloc,
    "/" + database,
    u.query,
    u.fragment,
))

print(result)

PY
)"

# ============================================================
# Test de l'URL poolée avec l'utilisateur applicatif
# ============================================================

echo
echo "=== Test de la connexion poolée ==="

POOLER_DATABASE="$(
    psql "$CLIENTS_POOLER_URL" \
        -v ON_ERROR_STOP=1 \
        -tAc "SELECT current_database();"
)"

if [ "$POOLER_DATABASE" != "$DATABASE" ]; then

    echo "ERREUR: connexion poolée sur '$POOLER_DATABASE' au lieu de '$DATABASE'."
    exit 1

fi

POOLER_USER="$(
    psql "$CLIENTS_POOLER_URL" \
        -v ON_ERROR_STOP=1 \
        -tAc "SELECT current_user;"
)"

if [ "$POOLER_USER" != "$DB_USER" ]; then

    echo "ERREUR: connexion poolée avec '$POOLER_USER' au lieu de '$DB_USER'."
    exit 1

fi

echo "Connexion poolée OK."
echo "Database : $POOLER_DATABASE"
echo "User     : $POOLER_USER"

# IMPORTANT :
# Ne jamais afficher CLIENTS_POOLER_URL ici.
# Elle contient le mot de passe.

# ============================================================
# Création du secret GCP
# ============================================================

echo
echo "=== Secret Manager : $DATABASE_SECRET_NAME ==="

if gcloud secrets describe "$DATABASE_SECRET_NAME" \
    --project="$PROJECT_NAME" \
    >/dev/null 2>&1; then

    echo "Secret \"$DATABASE_SECRET_NAME\" déjà existant."

else

    echo "Création du secret \"$DATABASE_SECRET_NAME\"..."

    gcloud secrets create "$DATABASE_SECRET_NAME" \
        --project="$PROJECT_NAME" \
        --replication-policy="automatic"

    echo "Secret créé."

fi

# ============================================================
# Ajout d'une nouvelle version
# ============================================================

echo
echo "=== Enregistrement de l'URL poolée ==="

printf '%s' "$CLIENTS_POOLER_URL" \
    | gcloud secrets versions add "$DATABASE_SECRET_NAME" \
        --project="$PROJECT_NAME" \
        --data-file=-

echo "Nouvelle version du secret créée."

# ============================================================
# Vérification du secret
# ============================================================

echo
echo "=== Vérification du secret ==="

if gcloud secrets versions access latest \
    --secret="$DATABASE_SECRET_NAME" \
    --project="$PROJECT_NAME" \
    >/dev/null 2>&1; then

    echo "Secret \"$DATABASE_SECRET_NAME\" accessible."

else

    echo "ERREUR: impossible d'accéder au secret \"$DATABASE_SECRET_NAME\"."
    exit 1

fi

# ============================================================
# Vérification finale des bases
# ============================================================

echo
echo "=== Bases disponibles ==="

psql "$DATABASE_URL_UNPOOLED" \
    -v ON_ERROR_STOP=1 \
    -c "
        SELECT datname
        FROM pg_database
        WHERE datistemplate = false
        ORDER BY datname;
    "

# ============================================================
# Résumé
# ============================================================

echo
echo "============================================================"
echo " Configuration Neon terminée."
echo
echo " Projet        : $PROJECT_NAME"
echo " Database      : $DATABASE"
echo " User          : $DB_USER"
echo " Secret GCP    : $DATABASE_SECRET_NAME"
echo " Connexion     : Pooler Neon"
echo
echo " L'URL complète n'est volontairement pas affichée."
echo "============================================================"