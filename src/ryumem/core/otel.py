"""
OpenTelemetry integration for Ryumem.

Provides tracing and metrics for tool tracking and query flow in Google ADK integration.
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPTraceExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCTraceExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCMetricExporter
from opentelemetry.trace import Status, StatusCode

from ryumem.core.config import OpenTelemetryConfig

logger = logging.getLogger(__name__)

# Global telemetry instance
_telemetry_instance: Optional['RyumemTelemetry'] = None


class RyumemTelemetry:
    """
    OpenTelemetry instrumentation for Ryumem.

    Provides distributed tracing and metrics for tool execution and query flow.
    """

    def __init__(self, config: OpenTelemetryConfig):
        """
        Initialize OpenTelemetry telemetry.

        Args:
            config: OpenTelemetry configuration
        """
        self.config = config
        self.enabled = config.otel_enabled

        if not self.enabled:
            self.tracer = None
            self.meter = None
            self._tool_execution_counter = None
            self._tool_execution_duration = None
            self._query_counter = None
            self._query_duration = None
            return

        # Create resource with service information
        resource = Resource.create({
            SERVICE_NAME: "ryumem",
            SERVICE_VERSION: "0.6.1",
        })

        # Initialize tracing and metrics
        self.tracer = self._initialize_tracing(resource)
        self.meter = self._initialize_metrics(resource)
        self._create_metrics()

        logger.info(
            f"OpenTelemetry initialized: "
            f"endpoint={config.otlp_endpoint or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'default')}, "
            f"protocol={config.otlp_protocol}"
        )

    def _initialize_tracing(self, resource: Resource) -> Optional[trace.Tracer]:
        """Initialize trace provider and exporter."""
        # Create sampler
        sampler = sampling.TraceIdRatioBased(self.config.trace_sample_rate)

        # Create trace provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Create exporter based on protocol
        endpoint = self.config.otlp_endpoint or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')

        if self.config.otlp_protocol == 'grpc':
            exporter = GRPCTraceExporter(
                endpoint=endpoint,
                insecure=True  # Use insecure for local development
            )
        else:  # http/protobuf
            exporter = HTTPTraceExporter(
                endpoint=f"{endpoint}/v1/traces" if endpoint else None
            )

        # Add batch span processor
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set global trace provider
        trace.set_tracer_provider(provider)

        # Get tracer
        return trace.get_tracer(__name__)

    def _initialize_metrics(self, resource: Resource) -> Optional[metrics.Meter]:
        """Initialize metrics provider and exporter."""
        # Create exporter based on protocol
        endpoint = self.config.otlp_endpoint or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')

        if self.config.otlp_protocol == 'grpc':
            exporter = GRPCMetricExporter(
                endpoint=endpoint,
                insecure=True
            )
        else:  # http/protobuf
            exporter = HTTPMetricExporter(
                endpoint=f"{endpoint}/v1/metrics" if endpoint else None
            )

        # Create metric reader with periodic export
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=self.config.metric_export_interval_millis
        )

        # Create metrics provider
        provider = MeterProvider(resource=resource, metric_readers=[reader])

        # Set global metrics provider
        metrics.set_meter_provider(provider)

        # Get meter
        return metrics.get_meter(__name__)

    def _create_metrics(self):
        """Create metric instruments."""
        if not self.enabled or not self.meter:
            return

        # Tool execution metrics
        self._tool_execution_counter = self.meter.create_counter(
            name="ryumem.tool.execution.count",
            description="Number of tool executions",
            unit="1"
        )

        self._tool_execution_duration = self.meter.create_histogram(
            name="ryumem.tool.execution.duration",
            description="Duration of tool executions",
            unit="ms"
        )

        # Query flow metrics
        self._query_counter = self.meter.create_counter(
            name="ryumem.query.count",
            description="Number of queries processed",
            unit="1"
        )

        self._query_duration = self.meter.create_histogram(
            name="ryumem.query.duration",
            description="Duration of query processing",
            unit="ms"
        )

    @contextmanager
    def trace_tool_execution(
        self,
        tool_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracing tool execution.

        Args:
            tool_name: Name of the tool being executed
            user_id: User identifier
            session_id: Session identifier
            input_params: Tool input parameters (will be sanitized)

        Yields:
            Span object if tracing is enabled, None otherwise
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        with self.tracer.start_as_current_span(f"tool.{tool_name}") as span:
            # Set span attributes
            span.set_attribute("tool.name", tool_name)

            if user_id:
                span.set_attribute("user.id", user_id)
            if session_id:
                span.set_attribute("session.id", session_id)

            # Add sanitized input parameters
            if input_params:
                for key, value in input_params.items():
                    # Skip sensitive keys
                    if key.lower() in ('password', 'api_key', 'secret', 'token', 'auth'):
                        continue
                    # Truncate long values
                    str_value = str(value)
                    if len(str_value) > 100:
                        str_value = str_value[:100] + "..."
                    span.set_attribute(f"tool.input.{key}", str_value)

            try:
                yield span
            except Exception as e:
                # Record exception in span
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def trace_query_flow(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        augmented: bool = False
    ):
        """
        Context manager for tracing query flow.

        Args:
            query_text: The query text
            user_id: User identifier
            session_id: Session identifier
            augmented: Whether query was augmented with history

        Yields:
            Span object if tracing is enabled, None otherwise
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        with self.tracer.start_as_current_span("query.flow") as span:
            # Set span attributes
            # Truncate query text to 200 chars
            truncated_query = query_text[:200] if len(query_text) > 200 else query_text
            span.set_attribute("query.text", truncated_query)
            span.set_attribute("query.augmented", augmented)

            if user_id:
                span.set_attribute("user.id", user_id)
            if session_id:
                span.set_attribute("session.id", session_id)

            try:
                yield span
            except Exception as e:
                # Record exception in span
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def record_tool_execution(
        self,
        tool_name: str,
        duration_ms: int,
        success: bool,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        parent_tool_name: Optional[str] = None
    ):
        """
        Record tool execution metrics.

        Args:
            tool_name: Name of the tool
            duration_ms: Execution duration in milliseconds
            success: Whether execution was successful
            user_id: User identifier
            session_id: Session identifier
            parent_tool_name: Parent tool name if nested
        """
        if not self.enabled or not self._tool_execution_counter:
            return

        # Build attributes
        attributes = {
            "tool.name": tool_name,
            "tool.success": str(success).lower()
        }

        if user_id:
            attributes["user.id"] = user_id
        if session_id:
            attributes["session.id"] = session_id
        if parent_tool_name:
            attributes["tool.parent"] = parent_tool_name

        # Record metrics
        self._tool_execution_counter.add(1, attributes)
        self._tool_execution_duration.record(duration_ms, attributes)

    def record_query(
        self,
        duration_ms: int,
        augmented: bool,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tools_used_count: int = 0
    ):
        """
        Record query processing metrics.

        Args:
            duration_ms: Query processing duration in milliseconds
            augmented: Whether query was augmented with history
            user_id: User identifier
            session_id: Session identifier
            tools_used_count: Number of tools used in query
        """
        if not self.enabled or not self._query_counter:
            return

        # Build attributes
        attributes = {
            "query.augmented": str(augmented).lower(),
            "query.tools_used": str(tools_used_count)
        }

        if user_id:
            attributes["user.id"] = user_id
        if session_id:
            attributes["session.id"] = session_id

        # Record metrics
        self._query_counter.add(1, attributes)
        self._query_duration.record(duration_ms, attributes)

    def shutdown(self):
        """Shutdown telemetry and flush remaining data."""
        if not self.enabled:
            return

        logger.info("Shutting down OpenTelemetry")

        # Flush trace provider
        if trace.get_tracer_provider():
            try:
                trace.get_tracer_provider().shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down trace provider: {e}")

        # Flush metrics provider
        if metrics.get_meter_provider():
            try:
                metrics.get_meter_provider().shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down metrics provider: {e}")


def init_telemetry(config: OpenTelemetryConfig) -> Optional[RyumemTelemetry]:
    """
    Initialize global telemetry instance.

    Args:
        config: OpenTelemetry configuration

    Returns:
        RyumemTelemetry instance if enabled, None otherwise
    """
    global _telemetry_instance

    if not config.otel_enabled:
        logger.debug("OpenTelemetry is disabled")
        _telemetry_instance = None
        return None

    _telemetry_instance = RyumemTelemetry(config)
    return _telemetry_instance


def get_telemetry() -> Optional[RyumemTelemetry]:
    """
    Get global telemetry instance.

    Returns:
        RyumemTelemetry instance if initialized, None otherwise
    """
    return _telemetry_instance


def shutdown_telemetry():
    """Shutdown global telemetry instance."""
    global _telemetry_instance

    if _telemetry_instance:
        _telemetry_instance.shutdown()
        _telemetry_instance = None
