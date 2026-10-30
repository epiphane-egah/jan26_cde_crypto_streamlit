#!/usr/bin/env bash

set -euo pipefail

# Configuration

PROJECT_ID="jan26-cde-crypto"
SERVICE_ACCOUNT="container-runtime@jan26-cde-crypto.iam.gserviceaccount.com"
REGION="europe-west1"
SERVICE_NAME="jan26-cde-crypto-api"
NAME="Alertes Trading"
EMAIL="egahepiphane@gmail.com"

M="workload_googleapis_com"          
MR="generic_task"                    
                                    
SEL="monitored_resource=\"${MR}\""   

HEALTH_PATH="/api/health"           
HEALTH_DB_PATH="/api/health/db" 
UPTIME_NAME="trading-api-liveness"
UPTIME_DB_NAME="trading-api-health-db"
UPTIME_DB_PERIOD=10  

# Pour connaître le vôtre :
#   gcloud logging read 'jsonPayload.job="weekly_extract"' --limit=1 --format="value(resource.type)"
EXTRACT_RESOURCE_FILTER='resource.type=one_of("cloud_run_revision","cloud_function")'

# Restriction resource.type à utiliser pour chaque métrique de logs
resource_filter_for () {
  case "$1" in
    scheduler_*)                 echo 'resource.type="cloud_scheduler_job"' ;;
    weekly_extract_*|binance_*)  echo "$EXTRACT_RESOURCE_FILTER" ;;
    *)                           echo 'resource.type="cloud_run_job"' ;;   # jobs trading, dbt, GCS
  esac
}

for cmd in gcloud jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Commande requise introuvable : $cmd" >&2; exit 1; }
done

gcloud config set project "$PROJECT_ID"

# 0. APIs et droits du service account de l'API Flask (OpenTelemetry)
gcloud services enable monitoring.googleapis.com \
    logging.googleapis.com \
    cloudtrace.googleapis.com

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/monitoring.metricWriter" --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/cloudtrace.agent" --condition=None >/dev/null

# 1. Canal de notification email (réutilisé s'il existe)

CHANNEL_ID=$(gcloud beta monitoring channels list \
  --filter="displayName=\"${NAME}\" AND type=\"email\"" \
  --format="value(name)" \
  --limit=1)
if [ -z "$CHANNEL_ID" ]; then
  CHANNEL_ID=$(gcloud beta monitoring channels create \
    --display-name="$NAME" \
    --type=email \
    --channel-labels=email_address="$EMAIL" \
    --format="value(name)")
  echo "Canal créé : $CHANNEL_ID"
else
  echo "Canal déjà existant : $CHANNEL_ID"
fi
CHANNEL="$CHANNEL_ID"   # variable utilisée par les fonctions d'alerte

# 2. Métriques basées sur les logs
#    Prérequis : les jobs écrivent des logs JSON avec "job" et "event".

create_metric() {
  local name="$1" description="$2" filter="$3"
  if gcloud logging metrics describe "$name" >/dev/null 2>&1; then
    echo "Métrique déjà existante : $name"
  else
    gcloud logging metrics create "$name" \
      --description="$description" \
      --log-filter="$filter"
    echo "Métrique créée : $name"
  fi
}

# --- Nettoyage GCS mensuel ---
BASE='resource.type="cloud_run_job" AND jsonPayload.job="gcs_monthly_cleaning"'
create_metric gcs_cleaning_job_success \
  "Nettoyages GCS mensuels réussis" \
  "${BASE} AND jsonPayload.event=\"gcs_cleaning_job_success\""
create_metric gcs_cleaning_job_failed \
  "Nettoyages GCS mensuels en échec" \
  "${BASE} AND jsonPayload.event=\"gcs_cleaning_job_failed\""

# --- Trading quotidien ---
BASE='resource.type="cloud_run_job" AND jsonPayload.job="daily_trading"'
create_metric daily_trade_job_success \
  "Runs de trading quotidiens réussis" \
  "${BASE} AND jsonPayload.event=\"daily_trade_job_success\""
create_metric daily_trade_job_failed \
  "Runs de trading quotidiens en échec" \
  "${BASE} AND jsonPayload.event=\"daily_trade_job_failed\""

# --- Trading horaire ---
BASE='resource.type="cloud_run_job" AND jsonPayload.job="hourly_trading"'
create_metric hourly_trade_job_success \
  "Runs de trading horaires réussis" \
  "${BASE} AND jsonPayload.event=\"hourly_trade_job_success\""
create_metric hourly_trade_job_failed \
  "Runs de trading horaires en échec" \
  "${BASE} AND jsonPayload.event=\"hourly_trade_job_failed\""

# --- dbt ---
BASE='resource.type="cloud_run_job" AND jsonPayload.job="dbt"'
create_metric dbt_job_success \
  "Runs dbt réussis" \
  "${BASE} AND jsonPayload.event=\"dbt_job_success\""
create_metric dbt_job_failed \
  "Runs dbt en échec" \
  "${BASE} AND jsonPayload.event=\"dbt_job_failed\""
# NB : les comparaisons numériques supposent que failed/error sont loggés en nombres
create_metric dbt_tests_failed \
  "Runs dbt avec au moins un test en échec" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary\" AND jsonPayload.failed>0"
create_metric dbt_models_error \
  "Runs dbt avec au moins un modèle en erreur" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary\" AND jsonPayload.error>0"
create_metric dbt_summary_missing \
  "Résumé dbt introuvable" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary_missing\""

# --- Cloud Function d'extraction Binance ---
BASE='jsonPayload.job="weekly_extract"'
create_metric weekly_extract_success \
  "Extractions Binance hebdomadaires réussies" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_success\""
create_metric weekly_extract_failed \
  "Extractions Binance en échec (exception)" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_failed\""
create_metric weekly_extract_no_data \
  "Extractions sans aucune donnée collectée" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_no_data\""
create_metric binance_fetch_failed \
  "Appels Binance en erreur (une entrée par paire)" \
  "${BASE} AND jsonPayload.event=\"binance_fetch_failed\""
create_metric binance_data_empty \
  "Paires Binance sans nouvelles données" \
  "${BASE} AND jsonPayload.event=\"binance_data_empty\""

# --- Cloud Scheduler : déclenchements en erreur (job jamais lancé) ---
create_metric scheduler_job_failed \
  "Déclenchements Cloud Scheduler en erreur" \
  'resource.type="cloud_scheduler_job" AND severity>=ERROR'

# 3. Fonctions de création d'alertes
FAILED=""    # policies en erreur
PENDING=""   # policies en attente (métrique pas encore émise)

policy_exists () {
  [ -n "$(gcloud monitoring policies list \
    --filter="displayName=\"$1\"" --format="value(name)" 2>/dev/null)" ]
}

# Applique /tmp/policy.json.
#  - métrique PromQL inexistante -> "en attente" (inutile de réessayer)
#  - autre erreur (ex. métrique de logs pas encore propagée) -> 3 essais
apply_policy () {
  local name="$1" out
  for attempt in 1 2 3; do
    if out=$(gcloud monitoring policies create --policy-from-file=/tmp/policy.json 2>&1); then
      echo "Policy créée : $name"
      return 0
    fi
    if echo "$out" | grep -qi "PromQL metric(s) are invalid"; then
      echo "En attente (métrique pas encore émise) : $name"
      PENDING="${PENDING}\n - ${name}"
      return 0
    fi
    echo "$out" >&2
    # Erreur définitive (argument invalide...) : inutile de réessayer
    if ! echo "$out" | grep -qi "unknown\|not found\|does not exist\|NOT_FOUND"; then
      break
    fi
    echo "Échec (essai $attempt/3) : $name - nouvel essai dans 30 s"
    sleep 30
  done
  echo "ERREUR : policy non créée : $name" >&2
  FAILED="${FAILED}\n - ${name}"
}

# Alerte PromQL
# args : nom | sévérité | durée | requête | documentation
create_policy () {
  local name="$1" severity="$2" duration="$3" query="$4" doc="$5"
  if policy_exists "$name"; then echo "Policy déjà présente, ignorée : $name"; return; fi

  jq -n \
    --arg name "$name" --arg sev "$severity" --arg dur "$duration" \
    --arg q "$query" --arg doc "$doc" --arg ch "$CHANNEL" '
    {
      displayName: $name, severity: $sev, combiner: "OR", enabled: true,
      notificationChannels: [$ch],
      conditions: [{
        displayName: $name,
        conditionPrometheusQueryLanguage: {
          query: $q, duration: $dur, evaluationInterval: "60s"
        }
      }],
      documentation: { content: $doc, mimeType: "text/markdown" }
    }' > /tmp/policy.json
  apply_policy "$name"
}

# Alerte sur l'échec d'un uptime check
# args : nom | sévérité | check_id | documentation
create_uptime_policy () {
  local name="$1" severity="$2" check_id="$3" doc="$4"
  if policy_exists "$name"; then echo "Policy déjà présente, ignorée : $name"; return; fi

  local filter="metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${check_id}\" AND resource.type=\"uptime_url\""

  jq -n \
    --arg name "$name" --arg sev "$severity" --arg filter "$filter" \
    --arg doc "$doc" --arg ch "$CHANNEL" '
    {
      displayName: $name, severity: $sev, combiner: "OR", enabled: true,
      notificationChannels: [$ch],
      conditions: [{
        displayName: $name,
        conditionThreshold: {
          filter: $filter,
          aggregations: [{
            alignmentPeriod: "1200s",
            perSeriesAligner: "ALIGN_NEXT_OLDER",
            crossSeriesReducer: "REDUCE_COUNT_FALSE",
            groupByFields: ["resource.label.*"]
          }],
          comparison: "COMPARISON_GT", thresholdValue: 1, duration: "60s"
        }
      }],
      documentation: { content: $doc, mimeType: "text/markdown" }
    }' > /tmp/policy.json
  apply_policy "$name"
}

# Alerte sur une métrique de logs (compteur) : déclenchée si le nombre
# d'événements dans la fenêtre de 10 min est >= min_count.
# autoClose 30 min : l'incident se ferme seul, donc le prochain échec
# renvoie bien un email (sinon l'incident reste ouvert 7 jours).
# args : nom | sévérité | métrique_de_logs | min_count | documentation
create_log_alert () {
  local name="$1" severity="$2" metric="$3" min_count="$4" doc="$5"
  if policy_exists "$name"; then echo "Policy déjà présente, ignorée : $name"; return; fi

  local filter="metric.type=\"logging.googleapis.com/user/${metric}\" AND $(resource_filter_for "$metric")"

  jq -n \
    --arg name "$name" --arg sev "$severity" --arg filter "$filter" \
    --argjson min "$min_count" --arg doc "$doc" --arg ch "$CHANNEL" '
    {
      displayName: $name, severity: $sev, combiner: "OR", enabled: true,
      notificationChannels: [$ch],
      alertStrategy: { autoClose: "1800s" },
      conditions: [{
        displayName: $name,
        conditionThreshold: {
          filter: $filter,
          aggregations: [{
            alignmentPeriod: "600s",
            perSeriesAligner: "ALIGN_SUM",
            crossSeriesReducer: "REDUCE_SUM"
          }],
          comparison: "COMPARISON_GT",
          thresholdValue: ($min - 1),
          duration: "0s"
        }
      }],
      documentation: { content: $doc, mimeType: "text/markdown" }
    }' > /tmp/policy.json
  apply_policy "$name"
}

# Alerte d'ABSENCE d'une métrique de logs.
# Uniquement pour les jobs dont la période est inférieure à 23,5 h
# (limite de Cloud Monitoring pour les conditions d'absence).
# args : nom | sévérité | métrique_de_logs | durée_secondes | documentation
create_absence_alert () {
  local name="$1" severity="$2" metric="$3" duration="$4" doc="$5"
  if policy_exists "$name"; then echo "Policy déjà présente, ignorée : $name"; return; fi

  local filter="metric.type=\"logging.googleapis.com/user/${metric}\" AND $(resource_filter_for "$metric")"

  jq -n \
    --arg name "$name" --arg sev "$severity" --arg filter "$filter" \
    --arg dur "${duration}s" --arg doc "$doc" --arg ch "$CHANNEL" '
    {
      displayName: $name, severity: $sev, combiner: "OR", enabled: true,
      notificationChannels: [$ch],
      conditions: [{
        displayName: $name,
        conditionAbsent: {
          filter: $filter,
          duration: $dur,
          aggregations: [{ alignmentPeriod: "600s", perSeriesAligner: "ALIGN_SUM" }]
        }
      }],
      documentation: { content: $doc, mimeType: "text/markdown" }
    }' > /tmp/policy.json
  apply_policy "$name"
}

# Alerte sur la métrique NATIVE Cloud Run Jobs : exécution en échec
# (crash, OOM, timeout... même si le job n'a pas pu loguer son événement)
create_job_execution_failed_alert () {
  local name="Cloud Run Job : exécution en échec"
  local doc="Une exécution de Cloud Run Job s'est terminée en échec (voir le label job_name). Consulter Cloud Run > Jobs > Exécutions et les logs."
  if policy_exists "$name"; then echo "Policy déjà présente, ignorée : $name"; return; fi

  local filter='metric.type="run.googleapis.com/job/completed_execution_count" AND resource.type="cloud_run_job" AND metric.label.result="failed"'

  jq -n --arg name "$name" --arg filter "$filter" \
        --arg doc "$doc" --arg ch "$CHANNEL" '
    {
      displayName: $name, severity: "CRITICAL", combiner: "OR", enabled: true,
      notificationChannels: [$ch],
      alertStrategy: { autoClose: "1800s" },
      conditions: [{
        displayName: $name,
        conditionThreshold: {
          filter: $filter,
          aggregations: [{
            alignmentPeriod: "600s",
            perSeriesAligner: "ALIGN_SUM",
            crossSeriesReducer: "REDUCE_SUM",
            groupByFields: ["resource.label.job_name"]
          }],
          comparison: "COMPARISON_GT", thresholdValue: 0, duration: "0s"
        }
      }],
      documentation: { content: $doc, mimeType: "text/markdown" }
    }' > /tmp/policy.json
  apply_policy "$name"
}

# Crée un uptime check s'il n'existe pas et affiche son ID (stdout).
# args : nom | chemin | type_matcher | contenu_matcher | période_minutes
ensure_uptime_check () {
  local name="$1" path="$2" mtype="$3" mcontent="$4" period="$5"
  if [ -z "$(gcloud monitoring uptime list-configs \
        --filter="displayName=\"$name\"" --format="value(name)" 2>/dev/null)" ]; then
    gcloud monitoring uptime create "$name" \
      --resource-type=uptime-url \
      --resource-labels=host="$SERVICE_HOST",project_id="$PROJECT_ID" \
      --protocol=https \
      --path="$path" \
      --period="$period" \
      --timeout=10 \
      --matcher-type="$mtype" \
      --matcher-content="$mcontent" >&2
  fi
  local full
  full=$(gcloud monitoring uptime list-configs \
    --filter="displayName=\"$name\"" --format="value(name)" | head -n1)
  echo "${full##*/}"
}

# 4. Nettoyage de l'ancienne version (matcher "connected" sur /api/health,
#    qui échouait en permanence car /api/health ne renvoie pas "connected")
OLD_POLICY=$(gcloud monitoring policies list \
  --filter='displayName="API /api/health en échec"' \
  --format="value(name)" 2>/dev/null | head -n1)
if [ -n "$OLD_POLICY" ]; then
  gcloud monitoring policies delete "$OLD_POLICY" --quiet
  echo "Ancienne policy supprimée."
fi
OLD_CHECK=$(gcloud monitoring uptime list-configs \
  --filter='displayName="trading-api-health"' \
  --format="value(name)" 2>/dev/null | head -n1)
if [ -n "$OLD_CHECK" ]; then
  gcloud monitoring uptime delete "${OLD_CHECK##*/}" --quiet
  echo "Ancien uptime check supprimé."
fi

# 5. Uptime checks
#    Le service doit accepter les appels non authentifiés.
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" --format="value(status.url)")
SERVICE_HOST="${SERVICE_URL#https://}"
echo "Service : $SERVICE_HOST"

# Liveness : /api/health doit répondre 200 avec "status":"ok"
# (si l'option matches-regex est refusée par votre gcloud, utiliser
#  contains-string avec le contenu : ok)
LIVENESS_ID=$(ensure_uptime_check "$UPTIME_NAME" "$HEALTH_PATH" \
  "matches-regex" '"status":\s*"ok"' 5)
echo "Uptime liveness : $LIVENESS_ID"

# Base de données : /api/health/db doit répondre 200 avec "connected"
# (l'API renvoie 503 quand la base est KO)
DB_CHECK_ID=$(ensure_uptime_check "$UPTIME_DB_NAME" "$HEALTH_DB_PATH" \
  "contains-string" "connected" "$UPTIME_DB_PERIOD")
echo "Uptime base de données : $DB_CHECK_ID"

# 6. ALERTES API
create_uptime_policy "API injoignable (/api/health)" "CRITICAL" "$LIVENESS_ID" \
  "/api/health ne répond pas 200 avec status=ok depuis plusieurs régions : le service Cloud Run est tombé ou injoignable. Voir la révision, les logs et les quotas."

create_uptime_policy "DB injoignable (/api/health/db)" "CRITICAL" "$DB_CHECK_ID" \
  "/api/health/db ne répond pas 200 avec database=connected depuis plusieurs régions : la base de données est injoignable depuis l'API. Vérifier Cloud SQL / pooler et le secret clients-database-url-pooler."

create_policy "DB indisponible" "CRITICAL" "120s" \
  "min(${M}:database_health{${SEL}}) < 1" \
  "Le health check DB échoue depuis 2 min (gauge database.health à 0). Vérifier Cloud SQL / pooler et le secret clients-database-url-pooler."

create_policy "Taux d'erreurs 5xx élevé" "ERROR" "300s" \
  "(sum(rate(${M}:http_server_duration_count{http_status_code=~\"5..\",${SEL}}[5m])) / sum(rate(${M}:http_server_duration_count{${SEL}}[5m]))) > 0.05 and sum(rate(${M}:http_server_duration_count{${SEL}}[5m])) > 0.02" \
  "Plus de 5 % des requêtes HTTP répondent en 5xx. Voir Cloud Trace et les logs Cloud Run."

create_policy "Latence p95 élevée" "WARNING" "300s" \
  "histogram_quantile(0.95, sum by (le) (rate(${M}:http_server_duration_bucket{${SEL}}[5m]))) > 1000" \
  "La latence p95 dépasse 1 s sur 5 min (buckets en ms, mode historique). Chercher le span le plus long dans Cloud Trace."

create_policy "Échecs envoi mail contact" "WARNING" "0s" \
  "sum(increase(${M}:contact_emails{outcome=\"error\",${SEL}}[15m])) >= 3" \
  "3 échecs SMTP ou plus en 15 min. Vérifier le secret smtp-config et le serveur SMTP."

create_policy "SMTP lent" "WARNING" "600s" \
  "histogram_quantile(0.95, sum by (le) (rate(${M}:contact_smtp_duration_bucket{${SEL}}[10m]))) > 5000" \
  "Le serveur SMTP met plus de 5 s à répondre (p95)."

create_policy "Exceptions non gérées" "ERROR" "0s" \
  "sum(increase(${M}:app_errors{${SEL}}[10m])) > 0" \
  "Au moins une exception non gérée en 10 min. Voir les logs et les spans en erreur."

create_policy "Erreurs création config trading" "ERROR" "0s" \
  "sum(increase(${M}:trading_configs_requests{outcome=\"error\",${SEL}}[10m])) > 0" \
  "Erreur PostgreSQL pendant POST /api/trading-configs."

# ------------------------------------------------------------------
# 7. ALERTES JOBS : échecs (une policy par métrique d'échec)
# Trading (argent réel -> CRITICAL)
create_log_alert "Trading horaire en échec" "CRITICAL" "hourly_trade_job_failed" 1 \
  "Le job hourly_trading a signalé un échec. Vérifier les logs du job, l'API Binance et les soldes."
create_log_alert "Trading quotidien en échec" "CRITICAL" "daily_trade_job_failed" 1 \
  "Le job daily_trading a signalé un échec. Vérifier les logs du job, l'API Binance et les soldes."

# dbt
create_log_alert "dbt : job en échec" "ERROR" "dbt_job_failed" 1 \
  "Le job dbt a échoué. Voir les logs Cloud Run Job (jsonPayload.event=dbt_job_failed)."
create_log_alert "dbt : tests en échec" "WARNING" "dbt_tests_failed" 1 \
  "Au moins un test dbt a échoué (dbt_run_summary avec failed>0). Données potentiellement incohérentes."
create_log_alert "dbt : modèles en erreur" "ERROR" "dbt_models_error" 1 \
  "Au moins un modèle dbt est en erreur (dbt_run_summary avec error>0)."
create_log_alert "dbt : résumé introuvable" "WARNING" "dbt_summary_missing" 1 \
  "run_results.json introuvable après le run dbt : résultats non vérifiables."

# Nettoyage GCS mensuel
create_log_alert "Nettoyage GCS en échec" "ERROR" "gcs_cleaning_job_failed" 1 \
  "Le nettoyage mensuel GCS a échoué. Vérifier les droits du service account et les logs du job."

# Extraction Binance hebdomadaire (Cloud Function)
create_log_alert "Extraction Binance en échec" "ERROR" "weekly_extract_failed" 1 \
  "La fonction weekly_extract a levé une exception. Voir les logs de la fonction."
create_log_alert "Extraction Binance sans données" "ERROR" "weekly_extract_no_data" 1 \
  "L'extraction hebdomadaire n'a collecté aucune donnée. Vérifier l'API Binance et les paires configurées."
# Une entrée de log par paire : seuil à 3 pour éviter le bruit d'une paire isolée
create_log_alert "Binance : appels en erreur" "WARNING" "binance_fetch_failed" 3 \
  "3 appels Binance ou plus en erreur sur 10 min (une entrée par paire). Vérifier rate limits et disponibilité."
create_log_alert "Binance : paires sans données" "WARNING" "binance_data_empty" 3 \
  "3 paires ou plus sans nouvelles données. Vérifier la plage de dates et l'API Binance."

# Filets de sécurité transverses
create_job_execution_failed_alert
create_log_alert "Cloud Scheduler : déclenchement en erreur" "ERROR" "scheduler_job_failed" 1 \
  "Un job Cloud Scheduler a échoué à déclencher sa cible. Le job associé n'a probablement pas tourné."

# 8. ALERTES JOBS : absence de succès (uniquement période < 23,5 h)
#    Les jobs quotidien, hebdomadaire et mensuel ne peuvent pas être
#    surveillés ainsi : leur période dépasse la fenêtre maximale.
# Job horaire : 70 min = 4200 s (1 h + marge)
create_absence_alert "Trading horaire absent" "CRITICAL" "hourly_trade_job_success" 4200 \
  "Aucun succès de hourly_trading depuis 70 min. Vérifier Cloud Scheduler et les exécutions du job."

# Si dbt tourne plusieurs fois par jour (ex. toutes les 6 h), décommentez :
# create_absence_alert "dbt absent" "ERROR" "dbt_job_success" 25200 \
#   "Aucun succès dbt depuis 7 h."

# Bilan
if [ -n "$PENDING" ]; then
  printf "\nPolicies EN ATTENTE (métrique pas encore émise par l'API) :%b\n" "$PENDING"
  echo "-> Générez du trafic (voir le guide), attendez 2 min, puis relancez ce script."
fi
if [ -n "$FAILED" ]; then
  printf "\nPolicies NON créées (erreur) :%b\n" "$FAILED" >&2
  exit 1
fi
echo "Terminé."