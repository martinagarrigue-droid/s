"""Excepciones especificas de la Etapa 2 (prompt + integracion LLM)."""


class ReportEngineError(Exception):
    """Excepcion base del motor de generacion de informes."""


class MissingAPIKeyError(ReportEngineError):
    """No se encontro ANTHROPIC_API_KEY en las variables de entorno."""


class LLMGenerationError(ReportEngineError):
    """Fallo la generacion de una seccion despues de agotar los reintentos."""


class LLMRefusalError(ReportEngineError):
    """El modelo rechazo la generacion (stop_reason == 'refusal')."""
