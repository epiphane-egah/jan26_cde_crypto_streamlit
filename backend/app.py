import json
import ssl
import os
import time
import smtplib
from email.message import EmailMessage
from functools import lru_cache
from typing import Optional
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.cloud import secretmanager
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import HTTPException
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from models import db
from telemetry import setup_telemetry


app = Flask(__name__)
START_TIME = time.time()
STARTED_AT = datetime.now(timezone.utc).isoformat()
m = setup_telemetry(app)
tracer = trace.get_tracer("backend.app")
PROJECT_ID = "jan26-cde-crypto"
database_url = None 


# Secret Manager (avec span + cache)
@lru_cache(maxsize=32)
def _access_secret(project_id: str, secret_id: str, version: str) -> str:
    with tracer.start_as_current_span("secretmanager.access") as span:
        span.set_attribute("secret.id", secret_id)   # l'id, jamais la valeur
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")


def get_secret(project_id: str,
               secret_id: str,
               key: Optional[str] = None,
               version: str = "latest",
               from_json: bool = False) -> str:
    content = _access_secret(project_id, secret_id, version)
    return json.loads(content)[key] if from_json else content


# Configuration
database_url = get_secret(project_id=PROJECT_ID,
                          secret_id="clients-database-url-pooler")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

allowed_origins = [
    "https://jan26-cde-crypto-service-975242104567.europe-west1.run.app",
    "http://localhost:8501",
]
# CORS(app, origins=allowed_origins)
CORS(app, origins=allowed_origins)
db.init_app(app)


# Hooks transverses : tailles des requêtes/réponses + erreurs non gérées
def _route_attrs(status: Optional[int] = None) -> dict:
    """Attributs à cardinalité bornée : la route (pas l'URL), jamais l'utilisateur."""
    attrs = {
        "http.request.method": request.method,
        "http.route": request.url_rule.rule if request.url_rule else "unmatched",
    }
    if status is not None:
        attrs["http.response.status_code"] = status
    return attrs


@app.after_request
def record_http_sizes(resp):
    if request.path in ("/api/health", "/api/health/db"):
        return resp
    m["http_request_size"].record(request.content_length or 0, _route_attrs())
    m["http_response_size"].record(resp.content_length or 0, _route_attrs(resp.status_code))
    return resp


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint introuvable."}), 404


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Requête trop volumineuse."}), 413


@app.errorhandler(Exception)
def unhandled_error(exc):
    if isinstance(exc, HTTPException):   # 404, 413... déjà gérés ci-dessus
        return exc
    m["app_errors"].add(1,
                        {**_route_attrs(), "error.type": type(exc).__name__})
    span = trace.get_current_span()
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR))
    app.logger.exception("Erreur non gérée")
    return jsonify({"error": "Erreur interne."}), 500


# /api/health : alimente les 3 métriques database.*
@app.get("/api/health/db")
def health():
    start = time.perf_counter()
    attrs = {"db.system": "postgresql"}

    try:
        db.session.execute(text("SELECT 1"))
        duration_ms = (time.perf_counter() - start) * 1000

        m["database_health"].set(1, attrs)
        m["database_health_duration"].record(
            duration_ms, {**attrs, "status": "success"})
        return jsonify({"status": "ok", "database": "connected"}), 200

    except SQLAlchemyError:
        duration_ms = (time.perf_counter() - start) * 1000
        db.session.rollback()

        m["database_health"].set(0, attrs)
        m["database_health_duration"].record(
            duration_ms, {**attrs, "status": "error"})
        m["database_health_failures"].add(1, attrs)
        app.logger.exception("Health check DB en échec")
        return jsonify({"status": "degraded", "database": "unavailable"}), 503


@app.get("/api/health")
def uptime():
    """Liveness : répond 200 si le processus tourne.
    Ne touche ni la DB ni Secret Manager."""
    return jsonify({
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "started_at": STARTED_AT,
        "revision": os.environ.get("K_REVISION"),   # définie automatiquement par Cloud Run
    }), 200


# /api/trading-configs : compteur par issue + span sur le bloc SQL
@app.post("/api/trading-configs")
def create_trading_config():
    payload = request.get_json(silent=True) or {}

    prenom = str(payload.get("prenom", "")).strip().capitalize()
    nom = str(payload.get("nom", "")).strip().capitalize()
    crypto = str(payload.get("crypto", "")).strip()
    intervalle = str(payload.get("intervalle", "")).strip()

    def track(outcome: str, valid: bool = False):
        attrs = {"outcome": outcome}
        if valid:   # crypto/intervalle sont des ensembles fermés -> sûrs en attribut
            attrs.update({"crypto": crypto, "interval": intervalle})
        m["trading_configs"].add(1, attrs)

    try:
        montant = float(payload.get("montant", 0))
    except (TypeError, ValueError):
        track("invalid")
        return jsonify({"error": "Le montant doit être un nombre."}), 400

    if not prenom or not nom:
        track("invalid")
        return jsonify(
            {"error": "Veuillez renseigner votre nom et votre prénom."}), 400
    if montant < 10:
        track("invalid")
        return jsonify({"error": "Le montant minimum requis est de 10 USDT."}), 400
    if crypto not in {"Bitcoin (BTC)", "Binance Coin (BNB)", "Ethereum (ETH)"}:
        track("invalid")
        return jsonify({"error": "Crypto-monnaie non prise en charge."}), 400
    if intervalle not in {"1 Heure", "1 Journée"}:
        track("invalid")
        return jsonify({"error": "Intervalle de trading non pris en charge."}), 400

    client_order_id = f"bot_{prenom}_{nom}"

    select_sql = text("""
        SELECT ClientOrderId, lastname, firstname, interval,
               type_crypto, usdt, solde_crypto
        FROM Clients
        WHERE ClientOrderId = :client_order_id
        LIMIT 1
    """)
    insert_sql = text("""
        INSERT INTO Clients
            (ClientOrderId, lastname, firstname,
                      interval, type_crypto, usdt, solde_crypto)
        VALUES
            (:client_order_id, :lastname, :firstname, :interval,
                      :type_crypto, :usdt, :solde_crypto)
    """)

    def row_to_client(row):
        r = row._mapping
        return {
            "ClientOrderId": r["clientorderid"],
            "lastname": r["lastname"],
            "firstname": r["firstname"],
            "interval": r["interval"],
            "type_crypto": r["type_crypto"],
            "usdt": float(r["usdt"]),
            "solde_crypto": float(r["solde_crypto"]),
        }

    # Pas de nom/prénom en attribut de span : ce sont des données personnelles.
    with tracer.start_as_current_span("clients.create_or_get") as span:
        span.set_attribute("trading.crypto", crypto)
        span.set_attribute("trading.interval", intervalle)
        try:
            existing = db.session.execute(
                select_sql, {"client_order_id": client_order_id}
            ).first()

            if existing:
                span.set_attribute("clients.existed", True)
                track("existed", valid=True)
                return jsonify({
                    "message": "Le client existe déjà.",
                    "client": row_to_client(existing),
                    "existed": True,
                }), 200

            db.session.execute(insert_sql, {
                "client_order_id": client_order_id,
                "lastname": nom,
                "firstname": prenom,
                "interval": intervalle,
                "type_crypto": crypto,
                "usdt": montant,
                "solde_crypto": 0,
            })
            db.session.commit()

            created = db.session.execute(
                select_sql, {"client_order_id": client_order_id}
            ).first()

            span.set_attribute("clients.existed", False)
            track("created", valid=True)
            return jsonify({
                "message": "Paramètres validés avec succès.",
                "client": row_to_client(created),
                "existed": False,
            }), 201

        except IntegrityError:
            db.session.rollback()
            existing = db.session.execute(
                select_sql, {"client_order_id": client_order_id}
            ).first()
            if existing:
                track("existed", valid=True)   # course entre deux requêtes simultanées
                return jsonify({
                    "message": "Le client existe déjà.",
                    "client": row_to_client(existing),
                    "existed": True,
                }), 200
            track("error", valid=True)
            span.set_status(Status(StatusCode.ERROR, "conflict"))
            return jsonify({"error": "Conflit lors de l'enregistrement du client."}), 409

        except SQLAlchemyError as exc:
            db.session.rollback()
            track("error", valid=True)
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            app.logger.exception("Erreur PostgreSQL sur la table Clients")
            return jsonify({
                "error": "Impossible d'accéder à la table Clients existante."
            }), 500


# /api/backtest : rien de plus à instrumenter, les métriques HTTP
# automatiques (durée, nombre, statut par route) suffisent
BACKTEST = {
    "initial_balance": 1000,
    "currency": "USDT",
    "results": {
        "1h": [
            {"crypto": "BTC", "hold": 14690.26, "arch": 9655.24, "xgboost": 10},
            {"crypto": "BNB", "hold": 337211.76, "arch": 280188.85, "xgboost": 10},
            {"crypto": "ETH", "hold": 5917.34, "arch": 20449.96, "xgboost": 10},
        ],
        "1d": [
            {"crypto": "BTC", "hold": 14750.36, "arch": 4203.56, "xgboost": 9},
            {"crypto": "BNB", "hold": 364105.67, "arch": 8659.22, "xgboost": 7867},
            {"crypto": "ETH", "hold": 5884.40, "arch": 1536.84, "xgboost": 615},
        ],
    },
}


@app.get("/api/backtest")
def backtest():
    return jsonify(BACKTEST)


# /api/contact : compteur par issue + durée SMTP + span
@app.post("/api/contact")
def contact():
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()
    subject = str(payload.get("subject", "")).strip()
    message = str(payload.get("message", "")).strip()

    if not name or not email or "@" not in email or not message:
        m["contact_emails"].add(1, {"outcome": "invalid"})
        return jsonify({"error": "Nom, email valide et message obligatoires."}), 400

    smtp_port = 587
    smtp_cfg = lambda key: get_secret(PROJECT_ID,
                                      "smtp-config", key=key, from_json=True)
    smtp_host = smtp_cfg("SMTP_HOST")
    smtp_username = smtp_cfg("SMTP_USERNAME")
    smtp_password = smtp_cfg("SMTP_PASSWORD")
    contact_email = smtp_cfg("CONTACT_EMAIL")

    if not smtp_host:
        m["contact_emails"].add(1, {"outcome": "config_error"})
        app.logger.error("SMTP_HOST non défini dans smtp-config")
        return jsonify({"error": "Impossible d'envoyer le message."}), 500

    mail = EmailMessage()
    mail["Subject"] = f"[Crypto Bot] {subject}" if subject else "[Crypto Bot] Nouveau message"
    mail["From"] = smtp_username
    mail["To"] = contact_email
    mail["Reply-To"] = email
    mail.set_content(
        f"Nouveau message depuis le formulaire de contact\n\n"
        f"Nom : {name}\nEmail : {email}\n\nMessage :\n\n{message}\n"
    )

    start = time.perf_counter()
    with tracer.start_as_current_span("contact.send_mail") as span:
        span.set_attribute("smtp.host", smtp_host)   # pas d'email ni de contenu
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(mail)

            m["contact_smtp_duration"].record(
                (time.perf_counter() - start) * 1000, {"outcome": "success"})
            m["contact_emails"].add(1, {"outcome": "sent"})
            return jsonify({"message": "Votre message a bien été envoyé."}), 200

        except Exception as exc:
            m["contact_smtp_duration"].record(
                (time.perf_counter() - start) * 1000, {"outcome": "error"})
            m["contact_emails"].add(1, {"outcome": "error", "error.type": type(exc).__name__})
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            app.logger.exception("Erreur pendant l'envoi du mail")
            return jsonify({"error": "Impossible d'envoyer le message."}), 500