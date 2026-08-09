"""Excepciones especificas de la Etapa 3 (exportacion a PDF)."""


class PDFEngineError(Exception):
    """Excepcion base del motor de exportacion a PDF."""


class PDFExportError(PDFEngineError):
    """Fallo la renderizacion del PDF (weasyprint)."""
