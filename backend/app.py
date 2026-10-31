
import json
import ssl
import os
import time
import smtplib

from email.message import EmailMessage
from functools import lru_cache
from typing import Optional
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g
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


@lru_cache(maxsize=32)
def _access_secret(project_id: str, secret_id: str, version: str) -> str:
    """
    Retrieve a secret value from Google Cloud Secret Manager.

    A CLIENT span is created because the application communicates
    with an external Google Cloud service.

    Args:
        project_id: Google Cloud project identifier.
        secret_id: Secret Manager secret identifier.
        version: Secret version to retrieve.

    Returns:
        The decoded secret value.
    """
    with tracer.start_as_current_span(
        "secretmanager.access",
        kind=trace.SpanKind.CLIENT,
    ) as span:
        span.set_attribute("secret.id", secret_id)

        try:
            client = secretmanager.SecretManagerServiceClient()

            name = (
                f"projects/{project_id}/secrets/"
                f"{secret_id}/versions/{version}"
            )

            response = client.access_secret_version(
                request={"name": name}
            )

            span.set_status(Status(StatusCode.OK))

            return response.payload.data.decode("UTF-8")

        except Exception as exc:
            span.record_exception(exc)
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Secret Manager access failed",
                )
            )
            raise


def get_secret(
    project_id: str,
    secret_id: str,
    key: Optional[str] = None,
    version: str = "latest",
    from_json: bool = False,
) -> str:
    """
    Retrieve a secret and optionally extract a value from JSON.

    Args:
        project_id: Google Cloud project identifier.
        secret_id: Secret Manager secret identifier.
        key: Optional JSON key to extract.
        version: Secret version to retrieve.
        from_json: Whether the secret contains JSON data.

    Returns:
        The complete secret value or the selected JSON value.
    """
    content = _access_secret(
        project_id,
        secret_id,
        version,
    )

    return json.loads(content)[key] if from_json else content


database_url = get_secret(
    project_id=PROJECT_ID,
    secret_id="clients-database-url-pooler",
)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


allowed_origins = [
    "https://jan26-cde-crypto-service-975242104567.europe-west1.run.app",
    "http://localhost:8501",
]

CORS(
    app,
    origins=allowed_origins,
)

db.init_app(app)


def _route_attrs(status: Optional[int] = None) -> dict:
    """
    Build bounded-cardinality HTTP attributes.

    The Flask route pattern is used instead of the complete URL
    to prevent high-cardinality metric dimensions.

    Args:
        status: Optional HTTP response status code.

    Returns:
        HTTP attributes containing method, route and optionally
        status_code.
    """
    attrs = {
        "method": request.method,
        "route": (
            request.url_rule.rule
            if request.url_rule
            else "unmatched"
        ),
    }

    if status is not None:
        attrs["status_code"] = status

    return attrs


@app.before_request
def record_http_request_start():
    """
    Start HTTP request instrumentation.

    Stores the request start time, increments the active request
    counter and starts a SERVER span representing the incoming
    HTTP request.
    """
    g.http_start_time = time.perf_counter()

    attrs = _route_attrs()

    m["http_active_requests"].add(
        1,
        attrs,
    )

    route = attrs["route"]

    span = tracer.start_span(
        f"{request.method} {route}",
        kind=trace.SpanKind.SERVER,
        attributes=attrs,
    )

    g.http_span = span


@app.after_request
def record_http_metrics(resp):
    """
    Record HTTP metrics and finalize the HTTP SERVER span.

    The following metrics are recorded:
        - app.http.request.total
        - app.http.request.duration
        - app.http.request.size
        - app.http.response.size
        - app.http.active_requests

    Metric attributes:
        Request total:
            - method
            - route
            - status_code

        Request duration:
            - method
            - route
            - status_code

        Request size:
            - method
            - route

        Response size:
            - method
            - route
            - status_code

        Active requests:
            - method
            - route

    The SERVER span receives:
        - method
        - route
        - status_code

    Span status:
        - OK for HTTP responses below 400.
        - ERROR for HTTP responses greater than or equal to 400.

    Args:
        resp: Flask response generated by the endpoint.

    Returns:
        The original Flask response.
    """
    attrs = _route_attrs(resp.status_code)

    request_attrs = _route_attrs()

    m["http_request_total"].add(
        1,
        attrs,
    )

    start_time = getattr(
        g,
        "http_start_time",
        None,
    )

    if start_time is not None:
        duration = time.perf_counter() - start_time

        m["http_request_duration"].record(
            duration,
            attrs,
        )

    m["http_request_size"].record(
        request.content_length or 0,
        request_attrs,
    )

    m["http_response_size"].record(
        resp.content_length or 0,
        attrs,
    )

    m["http_active_requests"].add(
        -1,
        request_attrs,
    )

    span = getattr(
        g,
        "http_span",
        None,
    )

    if span is not None:
        span.set_attribute(
            "method",
            request.method,
        )

        span.set_attribute(
            "route",
            request_attrs["route"],
        )

        span.set_attribute(
            "status_code",
            resp.status_code,
        )

        if resp.status_code >= 400:
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    f"HTTP {resp.status_code}",
                )
            )
        else:
            span.set_status(
                Status(StatusCode.OK)
            )

        span.end()

    return resp


@app.errorhandler(404)
def not_found(_error):
    """
    Handle requests targeting an unknown endpoint.

    Args:
        _error: Flask HTTP exception associated with the request.

    Returns:
        A JSON response with HTTP status 404.
    """
    return jsonify({
        "error": "Endpoint introuvable."
    }), 404


@app.errorhandler(413)
def too_large(_error):
    """
    Handle requests exceeding the maximum allowed payload size.

    Args:
        _error: Flask HTTP exception associated with the request.

    Returns:
        A JSON response with HTTP status 413.
    """
    return jsonify({
        "error": "Requête trop volumineuse."
    }), 413


@app.errorhandler(Exception)
def unhandled_error(exc):
    """
    Handle unexpected application exceptions.

    HTTP exceptions are returned unchanged. Unexpected exceptions
    increment the application error counter and are recorded on
    the current trace span.

    The app.errors metric uses:
        - method
        - route
        - error.type

    Args:
        exc: Exception raised while processing the request.

    Returns:
        The original HTTP exception or an HTTP 500 JSON response.
    """
    if isinstance(exc, HTTPException):
        return exc

    attrs = _route_attrs()

    attrs["error.type"] = type(exc).__name__

    m["app_errors"].add(
        1,
        attrs,
    )

    span = trace.get_current_span()

    span.record_exception(exc)

    span.set_status(
        Status(
            StatusCode.ERROR,
            type(exc).__name__,
        )
    )

    http_span = getattr(
        g,
        "http_span",
        None,
    )

    if http_span is not None:
        http_span.record_exception(exc)

        http_span.set_attribute(
            "error.type",
            type(exc).__name__,
        )

        http_span.set_status(
            Status(
                StatusCode.ERROR,
                type(exc).__name__,
            )
        )

    app.logger.exception(
        "Erreur non gérée"
    )

    return jsonify({
        "error": "Erreur interne."
    }), 500


@app.get("/api/health/db")
def health():
    """
    Check PostgreSQL connectivity.

    Executes a lightweight SELECT 1 query and updates the database
    health gauge and health-check duration histogram.

    An INTERNAL span represents the database health-check operation.

    Returns:
        HTTP 200 when PostgreSQL is reachable.
        HTTP 503 when PostgreSQL is unavailable.
    """
    attrs = {
        "db.system": "postgresql"
    }

    start = time.perf_counter()

    with tracer.start_as_current_span(
        "database.health_check",
        kind=trace.SpanKind.INTERNAL,
    ) as span:

        span.set_attribute(
            "db.system",
            "postgresql",
        )

        try:
            db.session.execute(
                text("SELECT 1")
            )

            m["database_health"].set(
                1,
                attrs,
            )

            span.set_status(
                Status(StatusCode.OK)
            )

            return jsonify({
                "status": "ok",
                "database": "connected",
            }), 200

        except SQLAlchemyError as exc:
            db.session.rollback()

            m["database_health"].set(
                0,
                attrs,
            )

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Database health check failed",
                )
            )

            app.logger.exception(
                "Health check DB en échec"
            )

            return jsonify({
                "status": "degraded",
                "database": "unavailable",
            }), 503

        finally:
            m["database_health_check_duration"].record(
                time.perf_counter() - start,
                attrs,
            )


@app.get("/api/health")
def uptime():
    """
    Return application liveness and uptime information.

    The current application uptime is also added to the up.time
    metric.

    Returns:
        A JSON response containing application status, uptime,
        startup timestamp and Cloud Run revision.
    """
    uptime_seconds = round(
        time.time() - START_TIME,
        1,
    )

    m["up_time"].add(
        uptime_seconds,
    )

    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime_seconds,
        "started_at": STARTED_AT,
        "revision": os.environ.get("K_REVISION"),
    }), 200


@app.post("/api/trading-configs")
def create_trading_config():
    """
    Create or retrieve a client trading configuration.

    Validates the submitted client information and stores the
    configuration in PostgreSQL.

    An INTERNAL span represents the database business operation.

    Returns:
        HTTP 201 when the client is created.
        HTTP 200 when the client already exists.
        HTTP 400 when validation fails.
        HTTP 409 when a database conflict occurs.
        HTTP 500 when the database operation fails.
    """
    payload = request.get_json(
        silent=True
    ) or {}

    prenom = str(
        payload.get("prenom", "")
    ).strip().capitalize()

    nom = str(
        payload.get("nom", "")
    ).strip().capitalize()

    crypto = str(
        payload.get("crypto", "")
    ).strip()

    intervalle = str(
        payload.get("intervalle", "")
    ).strip()

    try:
        montant = float(
            payload.get("montant", 0)
        )

    except (TypeError, ValueError):
        return jsonify({
            "error": "Le montant doit être un nombre."
        }), 400

    if not prenom or not nom:
        return jsonify({
            "error": (
                "Veuillez renseigner votre nom "
                "et votre prénom."
            )
        }), 400

    if montant < 10:
        return jsonify({
            "error": (
                "Le montant minimum requis "
                "est de 10 USDT."
            )
        }), 400

    if crypto not in {
        "Bitcoin (BTC)",
        "Binance Coin (BNB)",
        "Ethereum (ETH)",
    }:
        return jsonify({
            "error": "Crypto-monnaie non prise en charge."
        }), 400

    if intervalle not in {
        "1 Heure",
        "1 Journée",
    }:
        return jsonify({
            "error": (
                "Intervalle de trading "
                "non pris en charge."
            )
        }), 400

    client_order_id = (
        f"bot_{prenom}_{nom}"
    )

    select_sql = text("""
        SELECT ClientOrderId,
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
            (
                ClientOrderId,
                lastname,
                firstname,
                interval,
                type_crypto,
                usdt,
                solde_crypto
            )
        VALUES
            (
                :client_order_id,
                :lastname,
                :firstname,
                :interval,
                :type_crypto,
                :usdt,
                :solde_crypto
            )
    """)

    def row_to_client(row):
        """
        Convert a SQLAlchemy row into a serializable client object.

        Args:
            row: SQLAlchemy result row.

        Returns:
            A dictionary containing the client information.
        """
        r = row._mapping

        return {
            "ClientOrderId": r["clientorderid"],
            "lastname": r["lastname"],
            "firstname": r["firstname"],
            "interval": r["interval"],
            "type_crypto": r["type_crypto"],
            "usdt": float(r["usdt"]),
            "solde_crypto": float(
                r["solde_crypto"]
            ),
        }

    with tracer.start_as_current_span(
        "clients.create_or_get",
        kind=trace.SpanKind.INTERNAL,
    ) as span:

        span.set_attribute(
            "trading.crypto",
            crypto,
        )

        span.set_attribute(
            "trading.interval",
            intervalle,
        )

        try:
            existing = db.session.execute(
                select_sql,
                {
                    "client_order_id":
                        client_order_id
                },
            ).first()

            if existing:
                span.set_attribute(
                    "clients.existed",
                    True,
                )

                span.set_status(
                    Status(StatusCode.OK)
                )

                return jsonify({
                    "message":
                        "Le client existe déjà.",
                    "client":
                        row_to_client(existing),
                    "existed":
                        True,
                }), 200

            db.session.execute(
                insert_sql,
                {
                    "client_order_id":
                        client_order_id,
                    "lastname":
                        nom,
                    "firstname":
                        prenom,
                    "interval":
                        intervalle,
                    "type_crypto":
                        crypto,
                    "usdt":
                        montant,
                    "solde_crypto":
                        0,
                },
            )

            db.session.commit()

            created = db.session.execute(
                select_sql,
                {
                    "client_order_id":
                        client_order_id
                },
            ).first()

            span.set_attribute(
                "clients.existed",
                False,
            )

            span.set_status(
                Status(StatusCode.OK)
            )

            return jsonify({
                "message":
                    "Paramètres validés avec succès.",
                "client":
                    row_to_client(created),
                "existed":
                    False,
            }), 201

        except IntegrityError as exc:
            db.session.rollback()

            existing = db.session.execute(
                select_sql,
                {
                    "client_order_id":
                        client_order_id
                },
            ).first()

            if existing:
                span.set_attribute(
                    "clients.existed",
                    True,
                )

                span.set_status(
                    Status(StatusCode.OK)
                )

                return jsonify({
                    "message":
                        "Le client existe déjà.",
                    "client":
                        row_to_client(existing),
                    "existed":
                        True,
                }), 200

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Database conflict",
                )
            )

            return jsonify({
                "error": (
                    "Conflit lors de "
                    "l'enregistrement du client."
                )
            }), 409

        except SQLAlchemyError as exc:
            db.session.rollback()

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Database error",
                )
            )

            app.logger.exception(
                "Erreur PostgreSQL sur la table Clients"
            )

            return jsonify({
                "error": (
                    "Impossible d'accéder à la "
                    "table Clients existante."
                )
            }), 500


BACKTEST = {
    "initial_balance": 1000,
    "currency": "USDT",
    "results": {
        "1h": [
            {
                "crypto": "BTC",
                "hold": 14690.26,
                "arch": 9655.24,
                "xgboost": 10,
            },
            {
                "crypto": "BNB",
                "hold": 337211.76,
                "arch": 280188.85,
                "xgboost": 10,
            },
            {
                "crypto": "ETH",
                "hold": 5917.34,
                "arch": 20449.96,
                "xgboost": 10,
            },
        ],
        "1d": [
            {
                "crypto": "BTC",
                "hold": 14750.36,
                "arch": 4203.56,
                "xgboost": 9,
            },
            {
                "crypto": "BNB",
                "hold": 364105.67,
                "arch": 8659.22,
                "xgboost": 7867,
            },
            {
                "crypto": "ETH",
                "hold": 5884.40,
                "arch": 1536.84,
                "xgboost": 615,
            },
        ],
    },
}


@app.get("/api/backtest")
def backtest():
    """
    Return predefined cryptocurrency backtest results.

    The endpoint is covered by the global HTTP metrics and
    SERVER request span.

    Returns:
        A JSON response containing the backtest results.
    """
    return jsonify(BACKTEST)


@app.post("/api/contact")
def contact():
    """
    Send a contact form message through SMTP.

    The SMTP operation is represented by a CLIENT span because
    the application communicates with an external SMTP server.

    No email address, message content or other personal data is
    added to the trace.

    Returns:
        HTTP 200 when the message is sent.
        HTTP 400 when validation fails.
        HTTP 500 when SMTP configuration or delivery fails.
    """
    payload = request.get_json(
        silent=True
    ) or {}

    name = str(
        payload.get("name", "")
    ).strip()

    email = str(
        payload.get("email", "")
    ).strip()

    subject = str(
        payload.get("subject", "")
    ).strip()

    message = str(
        payload.get("message", "")
    ).strip()

    if (
        not name
        or not email
        or "@" not in email
        or not message
    ):
        return jsonify({
            "error": (
                "Nom, email valide et "
                "message obligatoires."
            )
        }), 400

    smtp_port = 587

    smtp_cfg = lambda key: get_secret(
        PROJECT_ID,
        "smtp-config",
        key=key,
        from_json=True,
    )

    smtp_host = smtp_cfg(
        "SMTP_HOST"
    )

    smtp_username = smtp_cfg(
        "SMTP_USERNAME"
    )

    smtp_password = smtp_cfg(
        "SMTP_PASSWORD"
    )

    contact_email = smtp_cfg(
        "CONTACT_EMAIL"
    )

    if not smtp_host:
        app.logger.error(
            "SMTP_HOST non défini dans smtp-config"
        )

        return jsonify({
            "error":
                "Impossible d'envoyer le message."
        }), 500

    mail = EmailMessage()

    mail["Subject"] = (
        f"[Crypto Bot] {subject}"
        if subject
        else "[Crypto Bot] Nouveau message"
    )

    mail["From"] = smtp_username
    mail["To"] = contact_email
    mail["Reply-To"] = email

    mail.set_content(
        f"Nouveau message depuis "
        f"le formulaire de contact\n\n"
        f"Nom : {name}\n"
        f"Email : {email}\n\n"
        f"Message :\n\n"
        f"{message}\n"
    )

    with tracer.start_as_current_span(
        "contact.send_mail",
        kind=trace.SpanKind.CLIENT,
    ) as span:

        span.set_attribute(
            "smtp.host",
            smtp_host,
        )

        span.set_attribute(
            "smtp.port",
            smtp_port,
        )

        try:
            context = (
                ssl.create_default_context()
            )

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=10,
            ) as server:

                server.ehlo()

                server.starttls(
                    context=context
                )

                server.ehlo()

                server.login(
                    smtp_username,
                    smtp_password,
                )

                server.send_message(
                    mail
                )

            span.set_status(
                Status(StatusCode.OK)
            )

            return jsonify({
                "message":
                    "Votre message a bien été envoyé."
            }), 200

        except Exception as exc:
            span.record_exception(exc)

            span.set_attribute(
                "error.type",
                type(exc).__name__,
            )

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "SMTP send failed",
                )
            )

            app.logger.exception(
                "Erreur pendant l'envoi du mail"
            )

            return jsonify({
                "error":
                    "Impossible d'envoyer le message."
            }), 500
