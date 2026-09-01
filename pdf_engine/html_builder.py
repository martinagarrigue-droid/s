"""Arma el HTML del informe a partir de la carta (Etapa 1) y el texto (Etapa 2).

Modulo de puro formateo: no toca weasyprint. Separado de exporter.py para
poder testear el marcado generado sin renderizar un PDF real.
"""

import html
import re
from datetime import datetime

from pdf_engine.config import (
    COVER_FIELD_LABELS,
    COVER_FOOTER_LABEL,
    COVER_SUBTITLE,
    COVER_WORDMARK,
    MONTHS_ES,
)

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def _escape(text: str) -> str:
    return html.escape(text)


def _apply_inline_markdown(escaped_text: str) -> str:
    """Convierte **negrita** y *cursiva* a HTML sobre texto ya escapado.

    Se aplica DESPUES de escapar (los marcadores * no son caracteres HTML
    especiales, asi que el orden es seguro) por si el LLM no respeta al pie
    de la letra la instruccion de "prosa corrida sin markdown".
    """
    escaped_text = _BOLD_RE.sub(r"<strong>\1</strong>", escaped_text)
    escaped_text = _ITALIC_RE.sub(r"<em>\1</em>", escaped_text)
    return escaped_text


def _format_spanish_date(iso_datetime: str) -> str:
    dt = datetime.fromisoformat(iso_datetime)
    return f"{dt.day} de {MONTHS_ES[dt.month - 1]} de {dt.year}, {dt.strftime('%H:%M')} hs"


def _wordmark_html(wordmark: str) -> str:
    """Resalta la É del wordmark, igual que el tratamiento del sitio."""
    accent_index = wordmark.find("É")
    if accent_index == -1:
        return _escape(wordmark)
    before, after = wordmark[:accent_index], wordmark[accent_index + 1:]
    return f'{_escape(before)}<span class="cover-wordmark-accent">É</span>{_escape(after)}'


def _text_block_to_html(text: str) -> str:
    """Parrafos separados por linea en blanco -> <p>. Listas con '- ' -> <ul>."""
    blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
    html_parts = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        is_list = len(lines) > 1 and all(line.startswith(("- ", "* ")) for line in lines)
        if is_list:
            items = "".join(
                f"<li>{_apply_inline_markdown(_escape(line[2:].strip()))}</li>" for line in lines
            )
            html_parts.append(f"<ul>{items}</ul>")
        else:
            paragraph = _apply_inline_markdown(_escape(" ".join(lines)))
            html_parts.append(f"<p>{paragraph}</p>")
    return "\n".join(html_parts)


def build_cover_html(chart: dict) -> str:
    subject = chart["subject"]
    place = subject["place"]
    place_desc = place.get("resolved_display_name") or place.get("input_text") or "N/D"
    house_system = chart["meta"]["engine"]["house_system"]

    return f"""<section class="cover">
  <div class="cover-wordmark">{_wordmark_html(COVER_WORDMARK)}</div>
  <div class="cover-subtitle">{_escape(COVER_SUBTITLE)}</div>
  <div class="cover-main">
    <div class="cover-name">{_escape(subject["name"])}</div>
    <div class="cover-rule"></div>
    <div class="cover-data">
      <div class="row"><span class="label">{_escape(COVER_FIELD_LABELS["birth"])}</span> {_escape(_format_spanish_date(subject["birth"]["local_datetime"]))}</div>
      <div class="row"><span class="label">{_escape(COVER_FIELD_LABELS["place"])}</span> {_escape(place_desc)}</div>
      <div class="row"><span class="label">{_escape(COVER_FIELD_LABELS["house_system"])}</span> {_escape(house_system)}</div>
    </div>
  </div>
  <div class="cover-footer">{_escape(COVER_FOOTER_LABEL)}</div>
</section>"""


def build_section_html(section: dict) -> str:
    return (
        f'<article class="report-section">\n'
        f'  <h2>{_escape(section["title"])}</h2>\n'
        f'  {_text_block_to_html(section["text"])}\n'
        f"</article>"
    )


def build_report_html(chart: dict, report: dict) -> str:
    """Arma el documento HTML completo, listo para pdf_engine.exporter."""
    cover_html = build_cover_html(chart)
    sections_html = "\n".join(build_section_html(section) for section in report["sections"])

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe natal - {_escape(chart["subject"]["name"])}</title>
</head>
<body>
{cover_html}
<section class="content">
{sections_html}
</section>
</body>
</html>"""
