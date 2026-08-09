"""Tests de exportacion a PDF (Etapa 3). Renderiza PDFs reales con weasyprint
y los valida con pypdf -- no hay forma util de mockear esto sin perder
cobertura sobre lo que realmente importa (que el PDF resultante sea valido).
"""

import pytest
from pypdf import PdfReader

from natal_engine.chart import generate_natal_chart
from pdf_engine.exceptions import PDFExportError
from pdf_engine.exporter import generate_pdf

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


def make_report(n_sections=3):
    return {
        "subject_name": "Persona de Prueba",
        "model": "claude-opus-4-8",
        "sections": [
            {
                "key": f"seccion_{i}",
                "title": f"Seccion de prueba {i}",
                "text": f"Parrafo uno de la seccion {i}.\n\nParrafo dos de la seccion {i}.",
            }
            for i in range(1, n_sections + 1)
        ],
        "full_text": "",
        "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    }


def test_generate_pdf_creates_valid_pdf_file(chart, tmp_path):
    output_path = tmp_path / "informe.pdf"
    result = generate_pdf(chart, make_report(), str(output_path))

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.read_bytes()[:5] == b"%PDF-"
    assert output_path.stat().st_size > 1000


def test_generate_pdf_page_count_is_cover_plus_one_page_per_section(chart, tmp_path):
    output_path = tmp_path / "informe.pdf"
    generate_pdf(chart, make_report(n_sections=4), str(output_path))

    reader = PdfReader(str(output_path))
    # 1 portada + 1 pagina por seccion (los textos de prueba son cortos y no
    # deberian desbordar a una segunda pagina cada uno).
    assert len(reader.pages) == 5


def test_generate_pdf_content_pages_are_numbered_starting_at_one(chart, tmp_path):
    output_path = tmp_path / "informe.pdf"
    generate_pdf(chart, make_report(n_sections=3), str(output_path))

    reader = PdfReader(str(output_path))
    # pagina 0 = portada (sin numero). Paginas 1..3 = contenido, numeradas 1..3.
    for content_index, expected_number in enumerate(["1", "2", "3"], start=1):
        page_text = reader.pages[content_index].extract_text()
        assert page_text.strip().endswith(expected_number)


def test_generate_pdf_cover_page_contains_subject_name_and_no_page_number(chart, tmp_path):
    output_path = tmp_path / "informe.pdf"
    generate_pdf(chart, make_report(), str(output_path))

    reader = PdfReader(str(output_path))
    cover_text = reader.pages[0].extract_text()
    assert "Persona de Prueba" in cover_text
    assert not cover_text.strip().endswith("1")


def test_generate_pdf_includes_section_titles_in_extracted_text(chart, tmp_path):
    output_path = tmp_path / "informe.pdf"
    generate_pdf(chart, make_report(n_sections=2), str(output_path))

    reader = PdfReader(str(output_path))
    full_text = "\n".join(page.extract_text() for page in reader.pages)
    assert "SECCION DE PRUEBA 1" in full_text.upper()
    assert "SECCION DE PRUEBA 2" in full_text.upper()


def test_generate_pdf_raises_pdf_export_error_on_render_failure(chart, tmp_path, monkeypatch):
    def broken_html(*args, **kwargs):
        raise RuntimeError("fallo simulado de weasyprint")

    monkeypatch.setattr("pdf_engine.exporter.HTML", broken_html)

    with pytest.raises(PDFExportError):
        generate_pdf(chart, make_report(), str(tmp_path / "informe.pdf"))
