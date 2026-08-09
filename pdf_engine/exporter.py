"""Orquestador de la Etapa 3: arma el HTML y lo renderiza a PDF con weasyprint."""

from pathlib import Path

from weasyprint import CSS, HTML

from pdf_engine.exceptions import PDFExportError
from pdf_engine.html_builder import build_report_html

_STYLES_PATH = Path(__file__).parent / "styles.css"


def generate_pdf(chart: dict, report: dict, output_path: str) -> str:
    """Genera el PDF final del informe.

    Args:
        chart: dict devuelto por natal_engine.generate_natal_chart() (Etapa 1).
        report: dict devuelto por report_engine.generate_report() (Etapa 2).
        output_path: ruta donde escribir el .pdf.

    Returns:
        output_path, para poder encadenar.

    Raises:
        PDFExportError: si weasyprint falla al renderizar.
    """
    html_document = build_report_html(chart, report)

    try:
        HTML(string=html_document, base_url=str(Path(__file__).parent)).write_pdf(
            output_path,
            stylesheets=[CSS(filename=str(_STYLES_PATH))],
        )
    except Exception as exc:
        raise PDFExportError(f"Fallo la renderizacion del PDF: {exc}") from exc

    return output_path
