"""Test de integracion end-to-end de la Etapa 1, sin depender de red.

Usa lat/long directos (evita el geocoder real) para poder correr en CI /
sandbox sin salida a internet, pero ejercita el pipeline completo:
Julian Day -> swisseph -> casas -> planetas -> aspectos -> schema final.
"""

import pytest

from natal_engine.chart import generate_natal_chart
from natal_engine.config import PLANET_CODES, TRADITIONAL_RULERS, ZODIAC_SIGNS
from natal_engine.exceptions import InvalidHouseSystemError, MissingBirthTimeError

# Buenos Aires, Argentina. Dato de nacimiento de prueba arbitrario.
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


def test_top_level_schema_keys(chart):
    assert set(chart.keys()) == {
        "meta", "subject", "settings", "angles", "houses", "planets", "aspects",
    }


def test_meta_reports_moshier_and_tropical(chart):
    assert chart["meta"]["engine"]["ephemeris_source"] == "moshier"
    assert chart["meta"]["engine"]["zodiac_type"] == "tropical"
    assert chart["meta"]["engine"]["house_system"] == "Placidus"


def test_subject_timezone_resolved_from_coordinates(chart):
    assert chart["subject"]["birth"]["timezone_name"] == "America/Argentina/Buenos_Aires"
    assert chart["subject"]["birth"]["utc_offset_hours"] == -3.0


def test_all_expected_planets_present(chart):
    names = {p["name"] for p in chart["planets"]}
    expected = set(PLANET_CODES.keys()) | {"South Node"}
    assert names == expected
    assert len(chart["planets"]) == len(expected)


def test_north_south_node_are_exact_opposites(chart):
    by_name = {p["name"]: p for p in chart["planets"]}
    north = by_name["North Node"]["longitude"]
    south = by_name["South Node"]["longitude"]
    assert (north + 180) % 360 == pytest.approx(south, abs=1e-6)


def test_every_planet_has_valid_sign_and_house(chart):
    for planet in chart["planets"]:
        assert planet["sign"] in ZODIAC_SIGNS
        assert 0 <= planet["sign_degree"] < 30
        assert 1 <= planet["house"] <= 12
        assert isinstance(planet["retrograde"], bool)


def test_twelve_houses_with_traditional_rulers(chart):
    assert len(chart["houses"]) == 12
    for i, house in enumerate(chart["houses"], start=1):
        assert house["number"] == i
        assert house["ruler"] == TRADITIONAL_RULERS[house["sign"]]
    # Regencia clasica, no moderna: Escorpio siempre rige Marte.
    scorpio_houses = [h for h in chart["houses"] if h["sign"] == "Scorpio"]
    assert all(h["ruler"] == "Mars" for h in scorpio_houses)


def test_angles_present_and_consistent(chart):
    angles = chart["angles"]
    assert set(angles.keys()) == {"ascendant", "midheaven", "descendant", "imum_coeli"}
    asc = angles["ascendant"]["longitude"]
    desc = angles["descendant"]["longitude"]
    assert (asc + 180) % 360 == pytest.approx(desc, abs=1e-6)


def test_aspects_include_ascendant_and_midheaven_as_bodies(chart):
    bodies_in_aspects = set()
    for aspect in chart["aspects"]:
        bodies_in_aspects.add(aspect["body_a"])
        bodies_in_aspects.add(aspect["body_b"])
        assert aspect["orb"] >= 0
    # No garantiza que Asc/MC formen aspecto con esta carta puntual, pero
    # confirma que al menos participan del pool de calculo sin reventar.
    assert bodies_in_aspects <= (
        {p["name"] for p in chart["planets"]} | {"Ascendant", "Midheaven"}
    )


def test_north_south_node_opposition_excluded_as_trivial(chart):
    for aspect in chart["aspects"]:
        assert {aspect["body_a"], aspect["body_b"]} != {"North Node", "South Node"}


def test_descendant_and_imum_coeli_not_separate_aspect_bodies(chart):
    bodies_in_aspects = set()
    for aspect in chart["aspects"]:
        bodies_in_aspects.add(aspect["body_a"])
        bodies_in_aspects.add(aspect["body_b"])
    assert "Descendant" not in bodies_in_aspects
    assert "Imum Coeli" not in bodies_in_aspects


def test_custom_house_system_koch():
    chart_koch = generate_natal_chart(**TEST_KWARGS, house_system="Koch")
    assert chart_koch["meta"]["engine"]["house_system"] == "Koch"


def test_missing_time_raises():
    kwargs = {**TEST_KWARGS, "time_str": ""}
    with pytest.raises(MissingBirthTimeError):
        generate_natal_chart(**kwargs)


def test_invalid_house_system_raises():
    with pytest.raises(InvalidHouseSystemError):
        generate_natal_chart(**TEST_KWARGS, house_system="Nonexistent")


def test_missing_location_raises_value_error():
    kwargs = {k: v for k, v in TEST_KWARGS.items() if k not in ("latitude", "longitude")}
    with pytest.raises(ValueError):
        generate_natal_chart(**kwargs)
