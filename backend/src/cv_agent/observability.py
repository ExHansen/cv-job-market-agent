"""Optional Arize Phoenix OpenTelemetry tracing for LangGraph & local Ollama agents."""

from __future__ import annotations

import logging

from cv_agent.config import settings

logger = logging.getLogger(__name__)

_TRACING_STATE: dict[str, str | bool] = {
    "enabled": False,
    "status": "disabled",
    "endpoint": "",
    "ui_url": "",
}


def init_phoenix_tracing() -> dict[str, str | bool]:
    """Register OpenTelemetry tracing with Arize Phoenix when ENABLE_PHOENIX_TRACING=true."""
    _TRACING_STATE["endpoint"] = settings.phoenix_collector_endpoint
    _TRACING_STATE["ui_url"] = settings.phoenix_ui_url

    if not settings.enable_phoenix_tracing:
        _TRACING_STATE["enabled"] = False
        _TRACING_STATE["status"] = "disabled (set ENABLE_PHOENIX_TRACING=true to activate)"
        return dict(_TRACING_STATE)

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            project_name="careeros-cv-agent",
            endpoint=settings.phoenix_collector_endpoint,
            auto_instrument=False,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        _TRACING_STATE["enabled"] = True
        _TRACING_STATE["status"] = "active"
        logger.info(
            "Arize Phoenix OTel tracing active -> %s",
            settings.phoenix_collector_endpoint,
        )
    except ImportError as exc:
        _TRACING_STATE["enabled"] = False
        _TRACING_STATE["status"] = f"missing_v2_extra ({exc.name})"
    except Exception as exc:
        _TRACING_STATE["enabled"] = False
        _TRACING_STATE["status"] = f"init_error ({type(exc).__name__})"

    return dict(_TRACING_STATE)


def get_tracing_status() -> dict[str, str | bool]:
    return dict(_TRACING_STATE)
