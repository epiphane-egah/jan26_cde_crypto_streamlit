import json
import os
from typing import Optional  
import smtplib
import ssl
from email.message import EmailMessage
from flask import jsonify, request
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from models import db
from google.cloud import secretmanager
# creds = service_account.Credentials.from_service_account_file(
#     "jan26-cde-crypto-097cf6e49500.json"
# )


def get_secret(project_id: str,
               secret_id: str,
               key: Optional[str] = None,
               version: str = "latest",
               from_json: bool = False) -> str:
    client = secretmanager.SecretManagerServiceClient()

    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"

    response = client.access_secret_version(
        request={"name": name}
    )
    if not from_json:
        return response.payload.data.decode("UTF-8")
    else:
        secret_content = response.payload.data.decode("UTF-8")
        secret_data = json.loads(secret_content)
        return secret_data[key]


app = Flask(__name__)

database_url = get_secret(
    project_id="jan26-cde-crypto",
    secret_id="clients-database-url-pooler"
    )
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

allowed_origins = ["https://jan26-cde-crypto-service-975242104567.europe-west1.run.app",
                   "http://localhost:8501"]
# CORS(app, origins=allowed_origins)
CORS(app, origins="*")
db.init_app(app)


@app.get("/api/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected"})
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"status": "degraded", "database": "unavailable"}), 503


@app.post("/api/trading-configs")
def create_trading_config():
    """
    Compatibilité stricte avec le formulaire Streamlit d'origine.

    INSERT historique :
      INSERT INTO Clients
      (ClientOrderId, lastname, firstname, interval, type_crypto, usdt, solde_crypto)
      VALUES ('bot_{prenom}_{nom}', nom, prenom, intervalle, crypto, montant, 0)

    Les noms de colonnes et les valeurs textuelles sont volontairement conservés.
    """
    payload = request.get_json(silent=True) or {}

    prenom = str(payload.get("prenom", "")).strip().capitalize()
    nom = str(payload.get("nom", "")).strip().capitalize()
    crypto = str(payload.get("crypto", "")).strip()
    intervalle = str(payload.get("intervalle", "")).strip()

    try:
        montant = float(payload.get("montant", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Le montant doit être un nombre."}), 400

    if not prenom or not nom:
        return jsonify({"error": "Veuillez renseigner votre nom et votre prénom."}), 400
    if montant < 10:
        return jsonify({"error": "Le montant minimum requis est de 10 USDT."}), 400
    if crypto not in {"Bitcoin (BTC)", "Binance Coin (BNB)", "Ethereum (ETH)"}:
        return jsonify({"error": "Crypto-monnaie non prise en charge."}), 400
    if intervalle not in {"1 Heure", "1 Journée"}:
        return jsonify({"error": "Intervalle de trading non pris en charge."}), 400

    client_order_id = f"bot_{prenom}_{nom}"

    # Identifiants SQL identiques à l'ancien code. Les valeurs utilisateur,
    # elles, sont paramétrées pour éviter l'injection SQL.
    select_sql = text("""
        SELECT
            ClientOrderId,
            lastname,
            firstname,
            interval,
            type_crypto,
            usdt,
            solde_crypto
        FROM Clients
        WHERE ClientOrderId = :client_order_id
        LIMIT 1
    """)

    insert_sql = text("""
        INSERT INTO Clients
            (ClientOrderId, lastname, firstname, interval, type_crypto, usdt, solde_crypto)
        VALUES
            (:client_order_id, :lastname, :firstname, :interval, :type_crypto, :usdt, :solde_crypto)
    """)

    def row_to_client(row):
        m = row._mapping
        return {
            "ClientOrderId": m["clientorderid"],
            "lastname": m["lastname"],
            "firstname": m["firstname"],
            "interval": m["interval"],
            "type_crypto": m["type_crypto"],
            "usdt": float(m["usdt"]),
            "solde_crypto": float(m["solde_crypto"]),
        }

    try:
        existing = db.session.execute(
            select_sql, {"client_order_id": client_order_id}
        ).first()

        if existing:
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
            return jsonify({
                "message": "Le client existe déjà.",
                "client": row_to_client(existing),
                "existed": True,
            }), 200
        return jsonify({"error": "Conflit lors de l'enregistrement du client."}), 409

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Erreur PostgreSQL sur la table Clients")
        return jsonify({
            "error": "Impossible d'accéder à la table Clients existante."
        }), 500


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


@app.post("/api/contact")
def contact():
    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()
    subject = str(payload.get("subject", "")).strip()
    message = str(payload.get("message", "")).strip()

    if not name or not email or "@" not in email or not message:
        return jsonify({
            "error": "Nom, email valide et message obligatoires."
        }), 400

    smtp_port = 587
    smtp_host = get_secret(project_id="jan26-cde-crypto",
                           secret_id="smtp-config",
                           key='SMTP_HOST',
                           from_json=True)
    smtp_username = get_secret(project_id="jan26-cde-crypto",
                               secret_id="smtp-config",
                               key="SMTP_USERNAME",
                               from_json=True)
    smtp_password = get_secret(project_id="jan26-cde-crypto",
                               secret_id="smtp-config",
                               key="SMTP_PASSWORD",
                               from_json=True)
    contact_email = get_secret(project_id="jan26-cde-crypto",
                               secret_id="smtp-config",
                               key="CONTACT_EMAIL",
                               from_json=True)

    mail = EmailMessage()

    mail["Subject"] = (
        f"[Crypto Bot] {subject}"
        if subject
        else "[Crypto Bot] Nouveau message"
    )

    # L'expéditeur doit être ton compte SMTP.
    mail["From"] = smtp_username

    # Le message arrive dans ta boîte.
    mail["To"] = contact_email

    # Permet de répondre directement au visiteur.
    mail["Reply-To"] = email

    mail.set_content(
        f"""
Nouveau message depuis le formulaire de contact

Nom : {name}
Email : {email}

Message :

{message}
"""
    )
    if not smtp_host:
        raise RuntimeError("MAIL_SERVER n'est pas défini")
    try:
        context = ssl.create_default_context()
        print(smtp_host)
        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=10
        ) as server:

            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

            server.login(
                smtp_username,
                smtp_password
            )

            server.send_message(mail)

        return jsonify({
            "message": "Votre message a bien été envoyé."
        }), 200

    except Exception:
        app.logger.exception(
            "Erreur pendant l'envoi du mail"
        )

        return jsonify({
            "error": "Impossible d'envoyer le message."
        }), 500


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Endpoint introuvable."}), 404


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Requête trop volumineuse."}), 413