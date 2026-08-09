"""Motor de generacion de informes via LLM (Etapa 2)."""

from report_engine.generator import generate_report
from report_engine.exceptions import (
    ReportEngineError,
    MissingAPIKeyError,
    LLMGenerationError,
    LLMRefusalError,
)

__all__ = [
    "generate_report",
    "ReportEngineError",
    "MissingAPIKeyError",
    "LLMGenerationError",
    "LLMRefusalError",
]
