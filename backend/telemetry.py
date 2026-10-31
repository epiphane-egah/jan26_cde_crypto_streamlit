"""Mise en place OpenTelemetry : métriques -> Cloud Monitoring, traces -> Cloud Trace."""
import atexit
import os
import socket
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource, get_aggregated_resources
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter 
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.resourcedetector.gcp_resource_detector import GoogleCloudResourceDetector
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from collections.abc import Sequence
from typing import Union, Dict
from opentelemetry.metrics import (
    Histogram,
    Counter,
    UpDownCounter,
)
from opentelemetry.sdk.metrics.view import (
    View,
    SumAggregation,
    ExplicitBucketHistogramAggregation,
    LastValueAggregation
)
from flask import Flask

_instruments = None  # un seul setup par processus

MetricInstrument = Union[
    Histogram,
    Counter,
    UpDownCounter,
]


def setup_telemetry(
    app: Flask,
    service_name: str = "flask-trading-api",
) -> Dict[str, MetricInstrument]:
    """This function setup opentelemetry

    Args:
        app (Flask): The app to instrument.
        service_name (str, optional): Name of the service that produce the 
        instruments. Defaults to "flask-trading-api".

    Returns:
        Dict[str, MetricInstrument]: Dictionary with instrument 
        names as keys and metric definitions as values.
    """
    global _instruments
    if _instruments is not None:
        return _instruments

    """I create a unique identity for each Docker container running my service,
    since each one will have its own distinct OpenTelemetry time series.

    The important line is: "service.instance.id": 
    f"{socket.gethostname()}-{os.getpid()}"
    """
    resource = get_aggregated_resources(
        [GoogleCloudResourceDetector(raise_on_error=False)],
        initial_resource=Resource.create({
            "service.name": service_name,
            "service.namespace": "trading-api",
            "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
        }),
    )

    '''Unlike Prometheus, OpenTelemetry uses a push-based system
    rather than a pull-based one. I configure it to export
    metrics to Cloud Monitoring every 60 seconds.
    '''
    reader = PeriodicExportingMetricReader(
        CloudMonitoringMetricsExporter(),
        export_interval_millis=60_000,
    )

    '''paramètre de notre forunisseur de métriques
    '''
    views = [View(
            instrument_name="app.http.request.total",
            aggregation=SumAggregation(),
        ),
        View(
            instrument_name="app.http.active_requests",
            aggregation=SumAggregation(),
        ),
        View(
        instrument_name="app.errors",
        aggregation=SumAggregation(),
        ),

        View(
            instrument_name="app.http.request.duration",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0, 2.0, 5.0, 10.0]),
            ),
        View(
            instrument_name="app.http.request.size",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[1_024, 10_240, 102_400, 1_048_576, 5_242_880, 10_485_760]),
            ),
        View(
            instrument_name="app.http.response.size",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[1_024, 10_240, 102_400, 1_048_576, 5_242_880, 10_485_760]),
            ),
        View(
            instrument_name="up.time",
            aggregation=LastValueAggregation()),
        View(
            instrument_name="db.health_check.duration",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.001, 0.0025, 0.005, 0.01, 0.025, 0.05,
                            0.1, 0.25, 0.5, 1.0, 2.5, 5.0,]),
            attribute_keys={"db.system"},)
        ]

    meter_provider = MeterProvider(
        resource=resource, metric_readers=[reader], views=views)
    
    '''Définir comme fournisseur de métriques pour notre instance
    '''
    metrics.set_meter_provider(meter_provider)

    # Métriques process (pas de métriques systèmes car serverless)
    SystemMetricsInstrumentor(config={
        "process.cpu.utilization": None,
        "process.memory.usage": None,
    }).instrument()

    # TRACES -> Google Cloud Trace (cheminement des requêtes http)
    tracer_provider = TracerProvider(
        resource=resource,
        # échantillonne 10 % des traces racines, respecte la décision du parent
        sampler=ParentBased(TraceIdRatioBased(0.1)),
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # sinon appelé en continu par les sondes et polluerait les traces.
    FlaskInstrumentor().instrument_app(app, excluded_urls="api/health/db,api/health")

    # arrêt de métriques provider et de trace provider dans l'application s'arrête.
    atexit.register(meter_provider.shutdown)
    atexit.register(tracer_provider.shutdown)

    # l'api ce création des métriques tagger par le module qui le produit app.py
    meter = meter_provider.get_meter("backend.app")

    return {
        # - http.request.method - http.route - http.response.status_code
        "http_request_total": meter.create_counter(
            "app.http.request.total",
            unit="{request}",
            description="Total number of HTTP requests",
        ),
        # - http.request.method - http.route - http.response.status_code
        "http_request_duration": meter.create_histogram(
            "app.http.request.duration",
            unit="s",
            description="HTTP request duration",
        ),
        # - http.request.method - http.route
        "http_request_size": meter.create_histogram(
            "app.http.request.size",
            unit="By",
            description="HTTP request size",
        ),
        # - http.request.method - http.route - http.response.status_code
        "http_response_size": meter.create_histogram(
            "app.http.response.size",
            unit="By",
            description="HTTP response size",
        ),
        # - http.request.method - http.route
        "http_active_requests": meter.create_up_down_counter(
            "app.http.active_requests",
            unit="{request}",
            description="Number of HTTP requests currently being processed",
        ),
        # - http.request.method - http.route - error.type
        "app_errors": meter.create_counter(
            "app.errors",
            unit="{error}",
            description="Total number of unhandled application errors",
        ),
        "up_time": meter.create_counter(
            "up.time",
            unit="{s}",
            description="Up time"
        ),
        "database_health": meter.create_gauge(
            name="db.health",
            description="PostgreSQL health status (1 = up, 0 = down)",
        ),
        "database_health_check_duration": meter.create_histogram(
            name="db.health_check.duration",
            unit="s",
            description="Duration of the PostgreSQL health check query (SELECT 1)",
        )
    }