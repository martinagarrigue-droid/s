"""Tests del formateo HTML de la Etapa 3, sin renderizar PDF (rapido, sin weasyprint)."""

import pytest

from natal_engine.chart import generate_natal_chart
from pdf_engine.html_builder import (
    _format_spanish_date,
    _text_block_to_html,
    build_cover_html,
    build_report_html,
    build_section_html,
)

TEST_KWARGS = dict(
    name="Persona de Prueba",
    date_str="1990-05-14",
    time_str="14:32",
    latitude=-34.6037,
    longitude=-58.3816,
)


@pytest.fixture(scope="module")
def chart():
    return generate_natal_chart(**TEST_KWARGS)


def test_format_spanish_date():
    assert _format_spanish_date("1990-05-14T14:32:00-03:00") == "14 de mayo de 1990, 14:32 hs"


def test_text_block_bold_markdown_becomes_strong():
    html = _text_block_to_html("El **Sol en Tauro** domina.")
    assert "<strong>Sol en Tauro</strong>" in html


def test_text_block_italic_markdown_becomes_em():
    html = _text_block_to_html("Una nota *al pasar* sobre esto.")
    assert "<em>al pasar</em>" in html


def test_text_block_bold_and_italic_together():
    html = _text_block_to_html("Es **importante** pero *matizado*.")
    assert "<strong>importante</strong>" in html
    assert "<em>matizado</em>" in html


def test_text_block_splits_paragraphs_on_blank_line():
    html = _text_block_to_html("Primer parrafo.\n\nSegundo parrafo.")
    assert html.count("<p>") == 2
    assert "<p>Primer parrafo.</p>" in html
    assert "<p>Segundo parrafo.</p>" in html


def test_text_block_joins_multiline_paragraph_with_space():
    html = _text_block_to_html("Linea uno\nlinea dos sin blank line.")
    assert "<p>Linea uno linea dos sin blank line.</p>" in html


def test_text_block_bullet_list_becomes_ul():
    html = _text_block_to_html("- Primer punto.\n- Segundo punto.")
    assert "<ul>" in html
    assert html.count("<li>") == 2
    assert "<li>Primer punto.</li>" in html


def test_text_block_single_dash_line_is_not_treated_as_list():
    # Un solo renglon con guion no alcanza para ser lista (podria ser un
    # guion enfatico dentro de una oracion suelta).
    html = _text_block_to_html("- Solo una linea.")
    assert "<ul>" not in html
    assert "<p>- Solo una linea.</p>" in html


def test_text_block_escapes_html_special_characters():
    html = _text_block_to_html("El signo < domina & condiciona > todo.")
    assert "<script>" not in html
    assert "&lt;" in html
    assert "&amp;" in html
    assert "&gt;" in html


def test_build_cover_html_includes_name_and_house_system(chart):
    cover = build_cover_html(chart)
    assert "Persona de Prueba" in cover
    assert "Placidus" in cover
    assert "14 de mayo de 1990" in cover


def test_build_cover_html_escapes_subject_name():
    chart = generate_natal_chart(
        name="Ana & Cia <script>",
        date_str="1990-05-14",
        time_str="14:32",
        latitude=-34.6037,
        longitude=-58.3816,
    )
    cover = build_cover_html(chart)
    assert "<script>" not in cover
    assert "&amp;" in cover
    assert "&lt;script&gt;" in cover


def test_build_cover_html_uses_na_fallback_when_place_unresolved(chart):
    cover = build_cover_html(chart)
    assert "N/D" in cover  # no se paso place_text, no hay resolved_display_name


def test_build_section_html_contains_title_as_h2():
    section = {"key": "intro", "title": "Introduccion operativa", "text": "Texto."}
    html = build_section_html(section)
    assert "<h2>Introduccion operativa</h2>" in html
    assert '<article class="report-section">' in html


def test_build_report_html_includes_cover_and_all_sections(chart):
    report = {
        "sections": [
            {"key": "a", "title": "Seccion A", "text": "Contenido A."},
            {"key": "b", "title": "Seccion B", "text": "Contenido B."},
        ]
    }
    document = build_report_html(chart, report)
    assert "<!doctype html>" in document
    assert "Persona de Prueba" in document
    assert "Seccion A" in document
    assert "Seccion B" in document
    assert document.index("Seccion A") < document.index("Seccion B")
