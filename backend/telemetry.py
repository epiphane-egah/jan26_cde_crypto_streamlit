"""Mise en place OpenTelemetry : métriques -> Cloud Monitoring, traces -> Cloud Trace."""
import atexit
import os
import socket

from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource, get_aggregated_resources
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.resourcedetector.gcp_resource_detector import GoogleCloudResourceDetector
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

MS_BUCKETS = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
S_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
BYTES_BUCKETS = [256, 1024, 4096, 16384, 65536, 262144, 1048576]

_instruments = None  # un seul setup par processus


def _hist_view(name, buckets):
    return View(instrument_name=name,
                aggregation=ExplicitBucketHistogramAggregation(buckets))


def setup_telemetry(app, service_name="flask-trading-api"):
    global _instruments
    if _instruments is not None:
        return _instruments

    # RESOURCE : identité du service + détection Cloud Run / GKE / GCE
    resource = get_aggregated_resources(
        [GoogleCloudResourceDetector(raise_on_error=False)],
        initial_resource=Resource.create({
            "service.name": service_name,
            "service.namespace": "trading-api",
            # unique par processus (workers gunicorn) pour éviter les
            # écritures concurrentes sur la même série temporelle
            "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
        }),
    )

    # METRICS -> Google Cloud Monitoring
    reader = PeriodicExportingMetricReader(
        CloudMonitoringMetricsExporter(),
        export_interval_millis=60_000,
    )

    views = [
        # Durée HTTP émise par FlaskInstrumentor (le nom/l'unité dépend du
        # mode semconv : ms en historique, s avec OTEL_SEMCONV_STABILITY_OPT_IN=http)
        _hist_view("http.server.duration", MS_BUCKETS),
        _hist_view("http.server.request.duration", S_BUCKETS),
        # Métriques custom
        _hist_view("database.health_check.duration", MS_BUCKETS),
        _hist_view("contact.smtp.duration", MS_BUCKETS),
        _hist_view("app.http.request.size", BYTES_BUCKETS),
        _hist_view("app.http.response.size", BYTES_BUCKETS),
    ]

    meter_provider = MeterProvider(
        resource=resource, metric_readers=[reader], views=views
    )
    metrics.set_meter_provider(meter_provider)

    # Métriques process (vérifier les noms émis selon la version installée)
    SystemMetricsInstrumentor(config={
        "process.cpu.utilization": None,
        "process.memory.usage": None,
        "process.thread.count": None,
    }).instrument()

    # ------------------------------------------------------------------
    # TRACES -> Google Cloud Trace
    # ------------------------------------------------------------------
    tracer_provider = TracerProvider(
        resource=resource,
        # échantillonne 10 % des traces racines, respecte la décision du parent
        sampler=ParentBased(TraceIdRatioBased(0.1)),
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # ------------------------------------------------------------------
    # FLASK (après les providers). Le health check est exclu : il serait
    # sinon appelé en continu par les sondes et polluerait les traces.
    # ------------------------------------------------------------------
    FlaskInstrumentor().instrument_app(app, excluded_urls="api/health/db,api/health")

    # Flush des dernières données à l'arrêt du processus
    atexit.register(meter_provider.shutdown)
    atexit.register(tracer_provider.shutdown)

    # ------------------------------------------------------------------
    # MÉTRIQUES APPLICATIVES
    # (la durée et les requêtes actives HTTP viennent de FlaskInstrumentor)
    # ------------------------------------------------------------------
    meter = metrics.get_meter("backend.app")

    _instruments = {
        # --- HTTP (complément) ---
        "http_request_size": meter.create_histogram(
            "app.http.request.size", unit="By",
            description="Taille des requêtes HTTP"),
        "http_response_size": meter.create_histogram(
            "app.http.response.size", unit="By",
            description="Taille des réponses HTTP"),
        "app_errors": meter.create_counter(
            "app.errors", unit="{error}",
            description="Exceptions non gérées"),

        # --- Base de données ---
        "database_health": meter.create_gauge(
            "database.health", unit="1",
            description="Disponibilité de la base (1=OK, 0=KO)"),
        "database_health_duration": meter.create_histogram(
            "database.health_check.duration", unit="ms",
            description="Durée du health check DB"),
        "database_health_failures": meter.create_counter(
            "database.health_check.failures", unit="{failure}",
            description="Échecs du health check DB"),

        # --- Métier : /api/trading-configs ---
        "trading_configs": meter.create_counter(
            "trading_configs.requests", unit="{request}",
            description="Créations de configuration de trading par issue "
                        "(created, existed, invalid, error)"),

        # --- Métier : /api/contact ---
        "contact_emails": meter.create_counter(
            "contact.emails", unit="{email}",
            description="Envois du formulaire de contact par issue"),
        "contact_smtp_duration": meter.create_histogram(
            "contact.smtp.duration", unit="ms",
            description="Durée de l'envoi SMTP"),
    }
    return _instruments