"""Tests de formateo de prompts (Etapa 2), sin llamadas a la API."""

import pytest

from natal_engine.chart import generate_natal_chart
from report_engine.config import SECTIONS
from report_engine.prompt_builder import build_section_user_message, format_natal_summary

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


def test_natal_summary_contains_subject_and_place(chart):
    summary = format_natal_summary(chart)
    assert "Persona de Prueba" in summary
    assert "Placidus" in summary


def test_natal_summary_translates_signs_and_bodies_to_spanish(chart):
    summary = format_natal_summary(chart)
    # Nombres en espanol presentes, nombres crudos en ingles ausentes como palabra propia.
    assert "Sol:" in summary
    assert "Luna:" in summary
    assert "Ascendente:" in summary
    assert "Medio Cielo:" in summary
    assert "Sun:" not in summary
    assert "Taurus" not in summary or "Tauro" in summary


def test_natal_summary_lists_all_twelve_houses(chart):
    summary = format_natal_summary(chart)
    for house_number in range(1, 13):
        assert f"Casa {house_number}:" in summary


def test_natal_summary_includes_aspects_with_orb_and_applying(chart):
    summary = format_natal_summary(chart)
    assert "orbe" in summary
    assert "aplicativo" in summary or "separativo" in summary


def test_section_user_message_includes_directive_and_title(chart):
    section = SECTIONS[0]
    message = build_section_user_message(section, chart)
    assert section["title"] in message
    assert section["directive"] in message


def test_planet_section_lists_spanish_body_names(chart):
    planet_section = next(s for s in SECTIONS if s["key"] == "identidad_nuclear")
    message = build_section_user_message(planet_section, chart)
    assert "Sol" in message
    assert "Luna" in message
    assert "Ascendente" in message


def test_all_sections_have_required_keys():
    required = {"key", "title", "kind", "directive"}
    for section in SECTIONS:
        assert required <= set(section.keys())


def test_section_keys_are_unique():
    keys = [s["key"] for s in SECTIONS]
    assert len(keys) == len(set(keys))
